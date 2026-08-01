import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field, fields
from enum import Enum, auto
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, Self

import coral
import hypixel
import keyring
import seraph
from petty.events import subscribe

from plugins.statcheck.models import (
    BedWarsTeam,
    GamePlayerStatus,
    Nick,
)
from proxhy.secrets import delete_secret, get_secret, set_secret
from proxhy.utils import nearest_mc_color, offline_uuid
from proxhypixel.formatting import format_player_dict

if TYPE_CHECKING:
    from proxhy.plugin import ProxhyPlugin

DEFAULT_COLUMNS = (
    "team_prefix",
    "bedwars_star",
    "nick_tag",
    "username",
    "fkdr",
    "seraph_tag",
    "coral_tag",
)


class PopulateStatus(Enum):
    OK = auto()  # data cached; move on to the next provider
    DONE = auto()  # data cached (e.g. a Nick), but final answer (stop)
    RETRY = auto()  # no data; transient failure, retryable, continuable
    SKIP = auto()  # no data; not worth retrying (e.g. invalid key), still continuable
    FATAL = auto()  # no data; abort the pipeline for whatever reason


@dataclass(frozen=True, slots=True)
class PopulateResult:
    status: PopulateStatus
    retries_remaining: int
    detail: str = ""

    @property
    def populated(self) -> bool:
        return self.status in (PopulateStatus.OK, PopulateStatus.DONE)

    @property
    def ok(self) -> bool:
        return self.status is PopulateStatus.OK

    @property
    def continuable(self) -> bool:
        return self.status not in (PopulateStatus.DONE, PopulateStatus.FATAL)


@dataclass(frozen=True, slots=True)
class ProviderError:
    provider: type[Provider]
    status: PopulateStatus  # RETRY (exhausted), SKIP, or FATAL
    detail: str
    retries_remaining: int

    @property
    def message(self) -> str:
        reason = self.detail or self.status.name.lower()
        return f"{self.provider.display_name()}: {reason}"


@dataclass(slots=True)
class FetchReport:
    errors: list[ProviderError] = field(default_factory=list)
    aborted: ProviderError | None = None  # the FATAL that stopped the pipeline

    @property
    def ok(self) -> bool:
        return not self.errors

    def user_messages(self) -> list[str]:
        return [e.message for e in self.errors]


class FetchOutcome(Enum):
    OK = auto()
    DONE = auto()  # got data that ends the lookup (Nick); cache and stop
    TRANSIENT = auto()  # retryable (timeout, 5xx, rate limit, ...)
    SKIP = auto()  # can't produce data and retrying won't help (invalid key)
    FATAL = auto()  # player doesn't exist / anything that should abort the pipeline


@dataclass(slots=True)
class ProviderCache[PT]:
    data: PT | None = None
    attempts: int = 0
    terminal: bool = False  # data present AND lookup is final (e.g. a Nick)


class ProviderCacheDict(dict):
    def __getitem__[CT: _HasClose, PT](
        self, key: type[Provider[CT, PT]]
    ) -> ProviderCache[PT] | None:
        return super().get(key)

    def __setitem__[CT: _HasClose, PT](
        self, key: type[Provider[CT, PT]], value: ProviderCache[PT]
    ) -> None:
        super().__setitem__(key, value)


class _HasClose(Protocol):
    async def close(self) -> None: ...


class Provider[CT: _HasClose, PT](ABC):
    # user-facing provider name (e.g. 'Hypixel' for HypixelProvider)
    _name: ClassVar[str] = ""
    # field key: user-facing field name
    _fields: ClassVar[dict[str, str]]
    # retries allowed after the first attempt (total attempts = max_retries + 1)
    max_retries: ClassVar[int] = 2

    def __init__(self, client: CT, api_key: str | None = None) -> None:
        self._client = client
        self._api_key = api_key
        self._key_valid: bool | None = None  # None = not yet checked

    @classmethod
    def display_name(cls) -> str:
        return cls._name or cls.__name__.removesuffix("Provider")

    @classmethod
    def internal_name(cls) -> str:
        return cls.display_name().casefold()

    @classmethod
    def key_name(cls) -> str:
        return f"{cls.internal_name()}_api_key"

    @classmethod
    @abstractmethod
    def _new_client(cls, api_key: str | None = None) -> CT: ...

    @classmethod
    def setup(cls, api_key: str | None = None) -> Self:
        """Build a provider from a key (or the stored one), with no existing client."""
        key = api_key if api_key is not None else get_secret(cls.key_name())
        return cls(cls._new_client(key), key)

    @property
    def api_key(self) -> str | None:
        self._api_key = get_secret(self.key_name())
        return self._api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        """Set this provider's API key."""
        set_secret(self.key_name(), value)
        asyncio.create_task(self._client.close())
        self._client = self._build_client(value)

        self._api_key = value
        self._key_valid = None  # force a re-check on next validate_key()

    @api_key.deleter
    def api_key(self) -> None:
        delete_secret(self.key_name())
        asyncio.create_task(self._client.close())
        self._client = self._build_client()

    def _build_client(self, *args, **kwargs) -> CT:
        return type(self._client)(*args, **kwargs)

    @property
    def key_valid(self) -> bool | None:
        return self._key_valid

    @abstractmethod
    async def _validate_key(self, client: CT) -> bool: ...

    async def validate_key(self, key: str | None = None) -> bool:
        """Validate key if it is passed in, otherwise current API key."""
        if key is None:
            key_valid = await self._validate_key(self._client)
            self._key_valid = key_valid
        else:
            key_valid = await self._validate_key(client := self._build_client(key))
            asyncio.create_task(client.close())

        return key_valid

    def _slot(self, player: GamePlayer) -> ProviderCache[PT]:
        cache = player._provider_data
        slot = cache[type(self)]
        if slot is None:
            slot = ProviderCache()
            cache[type(self)] = slot
        return slot

    def _retries_left(self, slot: ProviderCache[PT]) -> int:
        # first attempt is free; each further attempt eats one retry
        return max(self.max_retries - max(slot.attempts - 1, 0), 0)

    async def populate(self, player: GamePlayer) -> PopulateResult:
        """Fetch this provider's data for `player` and cache it.

        Once the slot holds data this just always reports OK.
        There is exactly one network attempt per call;
        manager decides whether or not to call again based on retries.
        """
        slot = self._slot(player)
        if slot.data is not None:
            status = PopulateStatus.DONE if slot.terminal else PopulateStatus.OK
            return PopulateResult(status, self._retries_left(slot))

        if self._key_valid is False:
            return PopulateResult(
                PopulateStatus.SKIP, self._retries_left(slot), "Invalid API Key"
            )

        slot.attempts += 1
        outcome, data, detail = await self._fetch(player)
        retries = self._retries_left(slot)

        match outcome:
            case FetchOutcome.OK:
                slot.data = data
                return PopulateResult(PopulateStatus.OK, retries, detail)
            case FetchOutcome.DONE:
                slot.data = data
                slot.terminal = True
                return PopulateResult(PopulateStatus.DONE, retries, detail)
            case FetchOutcome.SKIP:
                return PopulateResult(PopulateStatus.SKIP, retries, detail)
            case FetchOutcome.FATAL:
                return PopulateResult(PopulateStatus.FATAL, retries, detail)
            case _:  # TRANSIENT
                return PopulateResult(PopulateStatus.RETRY, retries, detail)

    @abstractmethod
    async def _fetch(self, player: GamePlayer) -> tuple[FetchOutcome, PT | None, str]:
        """One network attempt. Return (outcome, data, human-readable detail)."""
        ...

    @classmethod
    @abstractmethod
    def extract(cls, player: GamePlayer, data: PT | None, key: str) -> str | None:
        """Pull one user-facing field value out of already-fetched data."""
        ...


class HypixelProvider(Provider[hypixel.Client, Nick | dict[str, str | float | int]]):
    _fields = {
        "team_prefix": "Team Prefix",
        "bedwars_star": "BedWars Star",
        "username": "Player Name",
        "fkdr": "FKDR",
        "ms_fkdr": "Mode-Specific FKDR",
        "nick_tag": "Nick Tag",
    }
    max_retries = 2

    @classmethod
    def _new_client(cls, api_key: str | None = None) -> hypixel.Client:
        keys = (api_key,) if api_key is not None else ("",)
        return hypixel.Client(*keys, cache_h=False, cache_m=False)

    async def _validate_key(self, client: hypixel.Client) -> bool:
        try:
            await client.player_count()
            return True
        except hypixel.InvalidApiKey, hypixel.KeyRequired, hypixel.MalformedApiKey:
            return False

    async def _fetch(
        self, player: GamePlayer
    ) -> tuple[FetchOutcome, Nick | dict[str, str | float | int] | None, str]:
        outcome = FetchOutcome.OK
        data = None
        details = ""

        try:
            player_result: hypixel.Player | Nick = await self._client.player(
                player.username
            )
            data = format_player_dict(player_result, "bedwars")  # type: ignore
            outcome = FetchOutcome.OK
        except hypixel.PlayerNotFound as err:  # assume nick
            player_result = Nick(err.player, player.uuid)
            data = player_result
            outcome = FetchOutcome.DONE
        except hypixel.InvalidApiKey:
            self._key_valid = False
            outcome = FetchOutcome.SKIP
            details = "Invalid API Key"
        except hypixel.KeyRequired:
            # self._key_valid = False ?
            outcome = FetchOutcome.SKIP
            details = "No API Key Provided"

        # except RateLimitError: # should not happen

        except TimeoutError, hypixel.TimeoutError:
            outcome = FetchOutcome.TRANSIENT
            details = "Request Timed Out"
        except hypixel.ApiError:
            outcome = FetchOutcome.TRANSIENT
            details = "Unknown API Error"
        except Exception:
            # TODO: log
            outcome = FetchOutcome.TRANSIENT
            details = "Unknown Error"
        else:
            if player.username != player_result.name:
                # TODO: log
                # assume nick
                # TODO: should we assume this?
                player_result = Nick(player.username, player.uuid)
                outcome = FetchOutcome.DONE

        return outcome, data, details

    @classmethod
    def extract(
        cls,
        player: GamePlayer,
        data: Nick | dict[str, str | float | int] | None,
        key: str,
    ):
        match key:
            case "username":
                return player.team.code + player.username
            case "rankname":
                if data is None:
                    return player.team.code + player.username
                if not isinstance(data, Nick):
                    return data["rankname"]
                return f"§5{data.name}"
            case "bedwars_star":
                if data is None:
                    return None
                if not isinstance(data, Nick):
                    return data["star"]
                return None
            case "team_prefix":
                return player.team.prefix
            case "fkdr":
                if data is None:
                    return None
                if not isinstance(data, Nick):
                    return data["fkdr"]
                return None
            case "ms_fkdr":
                if data is None:
                    return None
                if not isinstance(data, Nick):
                    mode = player.mode
                    return data[f"{mode}_fkdr"]
                return None
            case "nick_tag":
                return "§5[NICK]" if isinstance(data, Nick) else None
            case _:
                return None


class SeraphProvider(Provider[seraph.Seraph, seraph.CubelifyResponse]):
    _fields = {"seraph_tag": "Seraph Tag"}
    max_retries = 1

    @classmethod
    def _new_client(cls, api_key: str | None = None) -> seraph.Seraph:
        return seraph.Seraph(api_key or "")

    async def _validate_key(self, client: seraph.Seraph) -> bool:
        try:
            await client.blacklist("3e392b7f-b18f-49ec-a058-8c7227febd9e")
            return True
        except seraph.SeraphError:
            return False
            # if (
            #     e.cause == "Invalid API Key"
            # ):  # could alternatively check e.code/e.status == 401?
            #     return False
            # else:
            #     # TODO: log instead of this
            #     raise RuntimeError("This should not happen!")

    async def _fetch(
        self, player: GamePlayer
    ) -> tuple[FetchOutcome, seraph.CubelifyResponse | None, str]:
        try:
            data = await self._client.cubelify_blacklist(str(player.uuid))
        except Exception as exc:  # TODO: narrow
            return FetchOutcome.TRANSIENT, None, str(exc)
        return FetchOutcome.OK, data, ""

    @classmethod
    def extract(
        cls, player: GamePlayer, data: seraph.CubelifyResponse | None, key: str
    ) -> str | None:
        if data is None:
            return None

        if key == "seraph_tag":
            tag_texts = [
                nearest_mc_color(tag.color) + tag.text for tag in data.tags if tag.text
            ]
            if not tag_texts:
                return None
            return f"§dS:{'§f/'.join(tag_texts)}"  # TODO: make better?

        return None


class CoralProvider(Provider[coral.Coral, coral.CubelifyResponse]):
    _fields = {"coral_tag": "Coral Tag"}
    max_retries = 1

    @classmethod
    def _new_client(cls, api_key: str | None = None) -> coral.Coral:
        return coral.Coral(api_key or "")

    async def _validate_key(self, client: coral.Coral) -> bool:
        try:
            await client.cubelify("3e392b7f-b18f-49ec-a058-8c7227febd9e")
            return True
        except coral.CoralError:
            return False

    async def _fetch(
        self, player: GamePlayer
    ) -> tuple[FetchOutcome, coral.CubelifyResponse | None, str]:
        try:
            data = await self._client.cubelify(str(player.uuid))
        except Exception as exc:  # TODO: narrow
            return FetchOutcome.TRANSIENT, None, str(exc)
        return FetchOutcome.OK, data, ""

    @classmethod
    def extract(
        cls, player: GamePlayer, data: coral.CubelifyResponse | None, key: str
    ) -> str | None:
        if data is None:
            return None

        if key == "coral_tag":
            tag_texts = [
                nearest_mc_color(tag.color) + tag.text for tag in data.tags if tag.text
            ]
            if not tag_texts:
                return None
            return f"§2C:{'§f/'.join(tag_texts)}"  # TODO: make better?

        return None


RegisteredProvider_T = Literal["Hypixel", "Seraph", "Coral"]
_LowerRegisteredProvider_T = Literal["hypixel", "seraph", "coral"]  # not pretty
REGISTERED_PROVIDERS: dict[_LowerRegisteredProvider_T, type[Provider]] = {
    "hypixel": HypixelProvider,
    "seraph": SeraphProvider,
    "coral": CoralProvider,
}

# e.g. {"bedwars_star": HypixelProvider, "seraph_tag": SeraphProvider}
_PROVIDER_FIELD_MAP: dict[str, type[Provider]] = {}
for _provider in REGISTERED_PROVIDERS.values():
    for _key in _provider._fields:
        if _key in _PROVIDER_FIELD_MAP:
            raise ValueError(
                f"conflicting field {_key!r}: "
                f"{_PROVIDER_FIELD_MAP[_key].__name__} vs {_provider.__name__}"
            )
        _PROVIDER_FIELD_MAP[_key] = _provider


def _field_provider(key: str) -> type[Provider]:
    try:
        return _PROVIDER_FIELD_MAP[key]
    except KeyError:
        raise KeyError(
            f"unknown field {key!r}; known: {sorted(_PROVIDER_FIELD_MAP)}"
        ) from None


_migrated_legacy_api_key = False


_shared_providers: dict[_LowerRegisteredProvider_T, Provider] = {}

for provider_name, provider in REGISTERED_PROVIDERS.items():
    if provider is not HypixelProvider and provider_name not in _shared_providers:
        _shared_providers[provider_name] = provider.setup()


class ProviderPlugin:
    def _init_providers(self: ProxhyPlugin):
        global _migrated_legacy_api_key  # ):

        self.active_providers = _shared_providers.copy()
        self.provided_fields: list[str] = [
            GamePlayer.field_name(key) for key in _PROVIDER_FIELD_MAP
        ]

        # TODO: remove sometime in future
        if not _migrated_legacy_api_key:
            _migrated_legacy_api_key = True
            old = keyring.get_password("proxhy", "hypixel_api_key")
            if old:
                set_secret("hypixel_api_key", old)
                keyring.delete_password("proxhy", "hypixel_api_key")

    @subscribe("login_success")
    async def _statcheck_event_login_success(self: ProxhyPlugin, _match, _data):
        self.create_task(self._login_success_helper())

    async def _login_success_helper(self: ProxhyPlugin):
        # TODO: maybe not hardocde so much?
        self.hypixel_client = hypixel.Client(
            get_secret("hypixel_api_key"), cache_h=False, cache_m=False
        )
        self.active_providers["hypixel"] = (
            hprovider := HypixelProvider(client=self.hypixel_client)
        )
        self.hypixel_provider: HypixelProvider = hprovider

        self.create_task(self.log_stats("login"))

    async def populate_player(
        self, player: GamePlayer, *, retry_delay: float = 0.0
    ) -> FetchReport:
        report = FetchReport()
        for provider in self.active_providers.values():
            result = await provider.populate(player)
            while (
                result.status is PopulateStatus.RETRY and result.retries_remaining > 0
            ):
                if retry_delay:
                    await asyncio.sleep(retry_delay)
                result = await provider.populate(player)

            if not result.populated:  # RETRY exhausted, SKIP, or FATAL
                error = ProviderError(
                    type(provider),
                    result.status,
                    result.detail,
                    result.retries_remaining,
                )
                report.errors.append(error)
                if result.status is PopulateStatus.FATAL:
                    report.aborted = error

            if not result.continuable:  # DONE or FATAL -> stop
                break

        return report

    async def validate_keys(self) -> dict[type[Provider], bool]:
        return {type(p): await p.validate_key() for p in self.active_providers.values()}


# here to avoid circular imports
@dataclass
class GamePlayer:
    """A player in a Bed Wars game.

    Lives for exactly one game and caches all provider data for that lifetime.
    """

    username: str
    uuid: uuid.UUID
    team: BedWarsTeam
    status: GamePlayerStatus
    respawn_time: int
    mode: str  # like eight_two

    display_name: str = field(init=False)
    default_display_name: str = field(init=False)
    respawn_timer_task: asyncio.Task | None = field(default=None, init=False)
    offline_uuid: uuid.UUID = field(init=False)
    # set once populate_player() has run (successfully or not)
    stats_fetched: bool = field(default=False, init=False)
    _provider_data: ProviderCacheDict = field(
        default_factory=ProviderCacheDict, init=False, repr=False
    )

    def __post_init__(self):
        self.offline_uuid = offline_uuid(self.username)
        self.display_name = f"{self.team.prefix} {self.username}"
        self.default_display_name = self.display_name

    def field(self, key: str) -> str | None:
        provider_cls = _field_provider(key)
        slot = self._provider_data[provider_cls]
        if slot is None or slot.data is None:
            data = None
        else:
            data = slot.data

        return provider_cls.extract(player=self, data=data, key=key)

    def __hash__(self):
        return hash((self.username, self.uuid))

    def __deepcopy__(self, memo: dict) -> Self:
        # respawn_timer_task is an asyncio.Task which cannot be deep-copied
        # (e.g. by emit())
        copied = object.__new__(type(self))
        memo[id(self)] = copied
        for f in fields(self):
            if f.name == "respawn_timer_task":
                value = self.respawn_timer_task
            else:
                value = deepcopy(getattr(self, f.name), memo)
            setattr(copied, f.name, value)
        return copied

    def fields(self, keys: Iterable[str]) -> dict[str, str | None]:
        return {k: self.field(k) for k in keys}

    @staticmethod
    def field_name(key: str) -> str:
        return _field_provider(key)._fields[key]

    def name_differs(self) -> bool:
        """Return True if display name needs to be sent to override Hypixel"""
        return self.display_name != self.default_display_name
