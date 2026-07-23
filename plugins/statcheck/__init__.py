import asyncio
import builtins
import re
import typing
import uuid
from collections import defaultdict
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeIs, get_args

from platformdirs import user_cache_dir

from assets import load_json_asset
from petty.events import listen_server, subscribe
from petty.protocol.datatypes import (
    UUID,
    Boolean,
    Buffer,
    Byte,
    Chat,
    String,
    TextComponent,
    VarInt,
)
from plugins.commands import CommandException, command
from plugins.statcheck.models import (
    COLOR_CODE_TO_NAME,
    BedWarsTeam,
    GamePlayerStatus,
    Nick,
    TeamColorCode,
    TeamLetter,
    TeamName,
)
from plugins.statcheck.providers import (
    DEFAULT_COLUMNS,
    FetchReport,
    GamePlayer,
    HypixelProvider,
    _LowerRegisteredProvider_T,
)
from proxhy.utils import offline_uuid, uuid_version
from proxhypixel.models import Game

if TYPE_CHECKING:
    from proxhy.plugin import ProxhyPlugin

BW_MAPS: dict = load_json_asset("bedwars_maps.json")
RUSH_MAPPINGS = load_json_asset("rush_mappings.json")
KILL_MSGS: list[str] = load_json_asset("bedwars_chat.json")["kill_messages"]

GAME_START_MESSAGE_SETS = [  # block all the game start messages
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                                  Bed Wars",
        "     Protect your bed and destroy the enemy beds.",
        "      Upgrade yourself and your team by collecting",
        "    Iron, Gold, Emerald and Diamond from generators",
        "                  to access powerful upgrades.",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
    #
    # no armed
    #
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                       Bed Wars Lucky Blocks",
        "    Collect Lucky Blocks from resource generators",
        "       to receive random loot! Break them to reveal",
        "                             their contents!",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                              Bed Wars Rush",
        "     All generators are maxed! Your bed has three",
        "       layers of protection! Left click while holding",
        "                 wool to activate bridge building!",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                           Bed Wars Ultimate",
        "          Select an ultimate in the store! They will",
        "                     be enabled in 10 seconds!",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
    #
    # no voidless
    #
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                          Bed Wars Swappage",
        "    Players swap teams at random intervals! Players",
        "        also swap positions with the players of the",
        "                    team they are swapping to!",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                                  Bed Wars",
        "     Every few seconds brings a new surprise! Use",
        "        these items to defend your bed or destroy",
        "                                enemy beds.",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
    [
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "                             Bed Wars Duels",
        "      Protect your bed and destroy the enemy bed.",
        "         Upgrade yourself by collecting Iron, Gold,",
        "    Emerald and Diamond from generators to access",
        "                          powerful upgrades.",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
    ],
]
GAME_START_MESSAGES = [msg for msg_set in GAME_START_MESSAGE_SETS for msg in msg_set]

# --- regexes
JOIN_RE = re.compile(
    r"^(?:\[[A-Za-z0-9+]+\]\s*)?"  # optional rank tag like [MVP++]
    r"(?P<ign>[A-Za-z0-9_]{3,16}) has joined (?P<context>.+)!$"
)
# TODO: should these really ignore case?
COLOR_CODE = re.compile(r"(§[0-9a-fk-or])", re.IGNORECASE)
TEAM_COLOR_CODE = re.compile(r"(§[0-9a-f])", re.IGNORECASE)
TEAM_COLOR_NAME = re.compile(
    r"\b(?:green|yellow|aqua|white|pink|gray|red|blue)\d+\b", re.IGNORECASE
)
REMOVE_DIGITS = re.compile(r"\d+")


def is_team_name(name: str) -> TypeIs[TeamName]:
    return name in set(get_args(TeamName))


def is_team_letter(letter: str) -> TypeIs[TeamLetter]:
    return letter in set(get_args(TeamLetter))


def match_team_name(name: str) -> TeamName | None:
    m = TEAM_COLOR_NAME.fullmatch(name)
    if m is not None:
        return REMOVE_DIGITS.sub("", m.group())  # type: ignore


def match_player_color(username: str, msg: str) -> TeamColorCode | None:
    m = re.search(rf"(§.){username}", msg)
    if m is not None:
        return m.group(1)  # type: ignore


class StatCheckPlugin:
    def _init_statcheck(self: ProxhyPlugin):
        # players from packet_teams
        self.game_players: dict[
            str, GamePlayer
        ] = {}  # username: player object (see above)

        self.game_error = None  # if invalid key error has been sent that game

        self.stats_highlighted = False
        self.adjacent_teams_highlighted = False

        self.game_errors: defaultdict[GamePlayer, list[FetchReport]] = defaultdict(
            list
        )  # player: fetch reports containing errors

        self.player_stats_queue: asyncio.Queue[GamePlayer] = asyncio.Queue()

        self.log_path = (
            Path(user_cache_dir("proxhy", ensure_exists=True)) / "stat_log.jsonl"
        )
        self._api_key_valid: bool | None = None

        # _update_stats
        self.player_stats_task: asyncio.Task[None] | None = None
        # list of tasks spawned by _update_player_stats
        self.player_stats_tasks: list[asyncio.Task[None]] = list()
        # players from /who
        self.who_players: set[str] = set()

        self.who_players_statted = asyncio.Event()

    @listen_server(0x01, blocking=True)
    async def packet_join_game(self: ProxhyPlugin, _):
        for player in self.game_players.values():
            self.downstream.send_packet(
                0x38,
                VarInt.pack(4),
                VarInt.pack(1),
                UUID.pack(player.offline_uuid),
            )

        # flush player lists
        self.game_players.clear()
        self.who_players.clear()

        self.who_players_statted.clear()
        self.stats_highlighted = False
        self.adjacent_teams_highlighted = False
        self.game_errors.clear()

        self.game = Game()

        if self.player_stats_task:
            self.player_stats_task.cancel()

        while not self.player_stats_queue.empty():
            self.player_stats_queue.get_nowait()

        for task in self.player_stats_tasks:
            task.cancel()

        self.player_stats_task = self.create_task(self._update_stats())

    @property
    def respawning(self: ProxhyPlugin) -> dict[str, GamePlayer]:
        return {
            player.username: player
            for player in self.game_players.values()
            if player.status == GamePlayerStatus.RESPAWNING
        }

    @property
    def eliminated(self: ProxhyPlugin) -> dict[str, GamePlayer]:
        return {
            player.username: player
            for player in self.game_players.values()
            if player.status == GamePlayerStatus.ELIMINATED
        }

    @property
    def all_players(self: ProxhyPlugin) -> set[str]:
        all_players = self.real_players()

        if self.settings.bedwars.tablist.show_eliminated_players.get() == "ON":
            all_players |= set(self.eliminated.keys())
        if self.settings.bedwars.tablist.show_respawn_timer.get() == "ON":
            all_players |= set(self.respawning.keys())

        return all_players

    # TODO: rewrite?
    # @property
    # def players_with_stats(self: ProxhyPlugin) -> dict[str, GamePlayerWithStats]:
    #     return {
    #         player.username: player
    #         for player in self.game_players.values()
    #         if isinstance(player, GamePlayerWithStats)
    #     }

    def _send_tablist_update(self: ProxhyPlugin, updates: dict[uuid.UUID, str]):
        """Send a packet to update players' display names in the tab list.

        Args:
            updates: Dict of {player_uuid: display_name}
        """
        if not updates:
            return

        self.downstream.send_packet(
            0x38,
            VarInt.pack(3),
            VarInt.pack(len(updates)),
            *(
                UUID.pack(player_uuid) + Boolean.pack(True) + Chat.pack(display_name)
                for player_uuid, display_name in updates.items()
            ),
        )

    def _build_player_display_name(self: ProxhyPlugin, player: GamePlayer) -> str:
        field_values = player.fields(DEFAULT_COLUMNS)  # will be customizable later
        return " ".join(
            [
                value
                for column in DEFAULT_COLUMNS
                if (value := field_values[column]) is not None
            ]
        )

    def _get_dead_display_name(self: ProxhyPlugin, player: GamePlayer) -> str:
        """Get the grayed-out display name for a dead player.

        Args:
            player_name: The player's name

        Returns:
            The formatted display name with gray color codes
        """
        # Use bold+italic for current user, just italic for others
        color = "§7§l§o" if player.username == self.nick_or_username else "§7§o"

        # show_stats = self.settings.bedwars.tablist.stats.show_stats.get() == "ON"

        unformatted_name = COLOR_CODE.sub("", player.display_name)
        return color + unformatted_name

    def _get_respawning_display_name(self: ProxhyPlugin, player: GamePlayer) -> str:
        return f"§6§l{player.respawn_time}s {self._get_dead_display_name(player)}"

    def _remove_display_names(self: ProxhyPlugin, players: Collection[GamePlayer]):
        self.downstream.send_packet(
            0x38,
            VarInt.pack(3),
            VarInt.pack(len(players)),
            *(UUID.pack(player.uuid) + Boolean.pack(False) for player in players),
        )

    def _rebuild_display_names(self: ProxhyPlugin):
        show_stats = self.settings.bedwars.tablist.stats.show_stats.get() == "ON"

        for player in self.game_players.values():
            player.display_name = self._build_player_display_name(player)

        if show_stats:
            _defaulted_dnames = {
                player
                for player in self.game_players.values()
                if player.display_name == player.default_display_name
            }
            # remove display names from those who do not need them
            self._remove_display_names(_defaulted_dnames)

            self._send_tablist_update(
                {
                    player.uuid: player.display_name
                    # for players whose display names are modified from default, update
                    for player in set(self.game_players.values()) - _defaulted_dnames
                }
            )
        else:
            # remove all stats from tab
            self.downstream.send_packet(
                0x38,
                VarInt.pack(3),
                VarInt.pack(len(self.game_players)),
                *(
                    UUID.pack(player.uuid) + Boolean.pack(False)
                    for player in self.game_players.values()
                ),
            )

            # finaled players
            self._send_tablist_update(
                {
                    player.offline_uuid: self._get_dead_display_name(player)
                    for player in self.eliminated.values()
                }
            )
            # respawning players
            self._send_tablist_update(
                {
                    player.offline_uuid: self._get_respawning_display_name(player)
                    for player in self.respawning.values()
                }
            )

    @subscribe("setting:bedwars.tablist.stats.show_stats")
    async def _statcheck_event_setting_bedwars_tablist_show_stats(
        self: ProxhyPlugin, _match, data: list
    ):
        if data == ["OFF", "ON"]:
            if not await self.hypixel_provider.validate_key():
                await self.send_api_key_err()

        self._rebuild_display_names()

    @subscribe("setting:bedwars.tablist.stats.is_mode_specific")
    async def _statcheck_event_setting_bedwars_tablist_is_mode_specific(
        self: ProxhyPlugin, _match, data: list
    ) -> None:
        self._rebuild_display_names()

    @subscribe("setting:bedwars.tablist.stats.show_rankname")
    async def _statcheck_event_setting_bedwars_tablist_show_rankname(
        self: ProxhyPlugin, _match, data: list
    ) -> None:
        self._rebuild_display_names()

    @subscribe("setting:bedwars.tablist.show_eliminated_players")
    async def _statcheck_event_setting_bedwars_tablist_show_eliminated_players(
        self: ProxhyPlugin, _match, data: list
    ) -> None:
        # remove self from final_dead
        final_dead_no_self = self.eliminated.copy()
        if self.nick_or_username in final_dead_no_self:
            del final_dead_no_self[self.nick_or_username]

        if data == ["OFF", "ON"]:
            packet = VarInt.pack(0) + VarInt.pack(len(final_dead_no_self))
            for player in final_dead_no_self.values():
                packet += UUID.pack(player.offline_uuid)
                packet += String.pack(player.username)
                packet += VarInt.pack(0)  # properties
                packet += VarInt.pack(3)  # gamemode; spectator
                packet += VarInt.pack(0)  # ping
                packet += Boolean.pack(True)  # has display name
                packet += Chat.pack(self._get_dead_display_name(player))

            self.downstream.send_packet(0x38, packet)
        elif data == ["ON", "OFF"]:
            packet = VarInt.pack(4) + VarInt.pack(len(final_dead_no_self))
            for player in final_dead_no_self.values():
                packet += UUID.pack(player.offline_uuid)

            self.downstream.send_packet(0x38, packet)

    @listen_server(0x3E, blocking=True)
    async def packet_teams(self: ProxhyPlugin, buff: Buffer):
        self.downstream.send_packet(0x3E, buff.getvalue())

        name = buff.unpack(String)
        mode = buff.unpack(Byte)
        if mode == 3 and (team := self.gamestate.teams.get(name)) is not None:
            player_count = buff.unpack(VarInt)
            for _ in range(player_count):
                username = buff.unpack(String)
                player = self.gamestate.get_player_by_name_from_player_list(username)
                if player is None:
                    continue
                elif player.name in self.game_players:
                    continue

                team_letter = COLOR_CODE.sub("", team.prefix).strip()
                if not is_team_letter(team_letter):
                    if self.in_bedwars_game():
                        self.logger.debug(
                            f"{team_letter} is not a valid team letter, skipping ({team.prefix})"
                        )

                    return

                player = GamePlayer(
                    username=username,
                    uuid=uuid.UUID(player.uuid),
                    team=BedWarsTeam.from_letter(team_letter),
                    status=GamePlayerStatus.ALIVE,
                    respawn_time=0,
                    mode=self.game.mode.removeprefix("bedwars_"),
                )
                self.game_players[username] = player
                self.logger.debug(
                    f"put {player.username!r} on {player.team!r}, {name}, {self.gamestate.teams[name].prefix}"
                )
                self.player_stats_queue.put_nowait(player)

    @listen_server(0x38, blocking=True)
    async def _packet_player_list_item(self: ProxhyPlugin, buff: Buffer):
        action = buff.unpack(VarInt)
        num_players = buff.unpack(VarInt)

        if action == 0:
            out = Buffer()
            out.write(VarInt.pack(action))
            out.write(VarInt.pack(num_players))

            for _ in range(num_players):
                _uuid = buff.unpack(UUID)
                out.write(UUID.pack(_uuid))

                if action == 0:  # add player
                    name = buff.unpack(String)

                    if _uuid == self.uuid and name != self.username:
                        self.nick = name

                    out.write(String.pack(name))

                    num_properties = buff.unpack(VarInt)
                    out.write(VarInt.pack(num_properties))
                    for _ in range(num_properties):
                        prop_name = buff.unpack(String)
                        prop_value = buff.unpack(String)
                        has_signature = buff.unpack(Boolean)
                        out.write(String.pack(prop_name))
                        out.write(String.pack(prop_value))
                        out.write(Boolean.pack(has_signature))
                        if has_signature:
                            out.write(String.pack(buff.unpack(String)))

                    gamemode = buff.unpack(VarInt)
                    ping = buff.unpack(VarInt)
                    has_display_name = buff.unpack(Boolean)
                    out.write(VarInt.pack(gamemode))
                    out.write(VarInt.pack(ping))

                    if (
                        player := self.game_players.get(name)
                    ) is not None and player.name_differs():
                        out.write(Boolean.pack(True))
                        out.write(Chat.pack(player.display_name))
                        if has_display_name:
                            buff.unpack(Chat)  # discard original
                    else:
                        out.write(Boolean.pack(has_display_name))
                        if has_display_name:
                            out.write(Chat.pack(buff.unpack(Chat)))
        else:
            out = buff

        self.downstream.send_packet(0x38, out.getvalue())

    async def _update_stats(self: ProxhyPlugin):
        await self.received_locraw.wait()

        if not self.in_bedwars_game():
            return

        while player := await self.player_stats_queue.get():
            self.create_task(self._update_player_stats(player))

    async def _update_player_stats(self: ProxhyPlugin, player: GamePlayer):
        fetch_response = await self.populate_player(player)
        if not fetch_response.ok:
            self.game_errors[player].append(fetch_response)
            return

        player.display_name = (display_name := self._build_player_display_name(player))
        self.game_players[player.username] = player

        show_stats = self.settings.bedwars.tablist.stats.show_stats.get() == "ON"

        if show_stats:
            if player.status in {
                GamePlayerStatus.ELIMINATED,
                GamePlayerStatus.RESPAWNING,
            }:
                self._send_tablist_update(
                    {player.offline_uuid: self._get_dead_display_name(player)}
                )
            else:
                self._send_tablist_update({player.uuid: display_name})

        await self.emit("statcheck:update", player)

    def _compile_errors(
        self: ProxhyPlugin, errors: Mapping[GamePlayer, list[FetchReport]]
    ) -> TextComponent:
        usernames_by_error: dict[tuple[type, str], list[str]] = defaultdict(list)
        for player, reports in errors.items():
            for report in reports:
                for error in report.errors:
                    detail = error.detail or error.status.name.lower()
                    usernames_by_error[(error.provider, detail)].append(player.username)

        msg = TextComponent(
            "The following errors occurred while fetching stats!"
        ).color("red")
        for (provider, detail), usernames in usernames_by_error.items():
            msg.append(
                TextComponent(f"\n- [{provider.display_name()}] {detail} ")
                .color("gray")
                .append(TextComponent(f"({', '.join(usernames)})").color("dark_gray"))
            )
        return msg

    @subscribe("statcheck:update")
    async def _event_statcheck_update(self: ProxhyPlugin, _match, data: GamePlayer):
        # TODO: can we really trust HypixelProvider's population as a source
        # of truth re. who has received stats here?
        if all(
            (pdata := player._provider_data[HypixelProvider]) is not None
            and pdata.data is not None  # TODO: is this correct?
            for player in self.game_players.values()
        ):
            # send collected errors
            if self.game_errors:
                self.downstream.chat(self._compile_errors(self.game_errors))
            self.game_errors.clear()  # since we are done with them (sent)
            self.who_players_statted.set()
            if self.settings.bedwars.display_top_stats.get() != "OFF":
                if not self.stats_highlighted:
                    await self.stat_highlights()

    # TODO: rewrite with new system
    async def highlight_adjacent_teams(self: ProxhyPlugin) -> None:
        """Displays a title card with stats of adjacent team(s)."""

        try:
            await asyncio.wait_for(self.who_players_statted.wait(), timeout=15)
        except builtins.TimeoutError:
            return

        if self.game.map is None:
            self.logger.warning("unknown map")
            return
        try:
            main_rush, alt_rush = self.get_adjacent_teams()
        except ValueError:  # player is not on a team
            return
        main_players = self.get_players_on_team(main_rush)
        alt_players = self.get_players_on_team(alt_rush)

        if self.game.map.rush_direction == "main":
            first_rush, first_players = main_rush, main_players
            other_adjacent_rush, other_adjacent_players = alt_rush, alt_players
        elif self.game.map.rush_direction == "alt":
            first_rush, first_players = alt_rush, alt_players
            other_adjacent_rush, other_adjacent_players = main_rush, main_players
        else:
            self.logger.warning(
                f"unexpected rush_direction {self.game.map.rush_direction!r}"
            )
            return

        empty_team_dialogue_first = (
            TextComponent(f"{first_rush.upper()} TEAM")
            .color(first_rush)  # type: ignore
            .appends(TextComponent("is empty!").color("red"))
        )
        empty_team_dialogue_alt = (
            TextComponent(f"{other_adjacent_rush.upper()} TEAM")
            .color(other_adjacent_rush)  # type: ignore
            .appends(TextComponent("is empty!").color("red"))
        )

        # key to sort player stats with sorted()
        key: Callable[[dict], float]
        if self.settings.bedwars.display_top_stats.get() in {"OFF", "INDEX"}:
            key = lambda fp: fp["raw_fkdr"] ** 2 * fp["raw_level"]  # noqa: E731
        elif self.settings.bedwars.display_top_stats.get() == "STAR":
            key = lambda fp: fp["raw_level"]  # noqa: E731
        elif self.settings.bedwars.display_top_stats.get() == "FKDR":
            key = lambda fp: fp["raw_fkdr"]  # noqa: E731
        else:
            self.logger.warning(
                f" unexpected display_top_stats value {self.settings.bedwars.display_top_stats.get()!r}"
            )
            return

        subtitle = None

        match len(first_players):
            case 0:  # team empty or disconnected
                title = empty_team_dialogue_first
            case 1:  # solos or doubles with 1 disconnect
                title = self.game_players[first_players[0]].display_name
            case (
                2
            ):  # team of 2; calculate which one has better stats based on user pref
                _fp1pd = self.game_players[first_players[0]]._provider_data[
                    HypixelProvider
                ]
                _fp2pd = self.game_players[first_players[1]]._provider_data[
                    HypixelProvider
                ]

                if (
                    # top 10 programmingn moments of all time
                    # PLEASE give us pep 505
                    _fp1pd is None
                    or _fp2pd is None
                    or _fp1pd.data is None
                    or _fp2pd.data is None
                ):
                    raise RuntimeError("This should not happen!")  # TODO: log

                fp1 = _fp1pd.data
                fp2 = _fp2pd.data

                better: dict[str, Any] | Nick
                worse: dict[str, Any] | Nick
                if isinstance(fp1, Nick):
                    better = fp1
                    worse = fp2
                elif isinstance(fp2, Nick):
                    better = fp2
                    worse = fp1
                else:
                    better, worse = sorted((fp1, fp2), key=key, reverse=True)

                if isinstance(better, Nick):
                    title = self.game_players[better.name].display_name
                else:
                    title = self.game_players[str(better["raw_name"])].display_name

                if self.settings.bedwars.announce_first_rush.get() == "FIRST RUSH":
                    # if we aren't showing alt rush team stats, we can show both players from first rush
                    if isinstance(worse, Nick):
                        subtitle = self.game_players[worse.name].display_name
                    else:
                        subtitle = self.game_players[
                            str(worse["raw_name"])
                        ].display_name
            case _:
                self.logger.warning(
                    f"unexpected first rush team size {len(first_players):d}: {first_players}"
                )
                return

        if self.settings.bedwars.announce_first_rush.get() == "BOTH ADJACENT":
            match len(other_adjacent_players):
                case 0:
                    subtitle = empty_team_dialogue_alt
                case 1:
                    subtitle = self.game_players[other_adjacent_players[0]].display_name
                case 2:
                    _fp1pd = self.game_players[
                        other_adjacent_players[0]
                    ]._provider_data[HypixelProvider]
                    _fp2pd = self.game_players[
                        other_adjacent_players[1]
                    ]._provider_data[HypixelProvider]

                    if (
                        _fp1pd is None
                        or _fp2pd is None
                        or _fp1pd.data is None
                        or _fp2pd.data is None
                    ):
                        raise RuntimeError("This should not happen!")  # TODO: log

                    fp1 = _fp1pd.data
                    fp2 = _fp2pd.data

                    better: dict[str, Any] | Nick
                    worse: dict[str, Any] | Nick
                    if isinstance(fp1, Nick):
                        better = fp1
                        worse = fp2
                    elif isinstance(fp2, Nick):
                        better = fp2
                        worse = fp1
                    else:
                        better, worse = sorted((fp1, fp2), key=key, reverse=True)

                    if isinstance(better, Nick):
                        subtitle = self.game_players[better.name].display_name
                    else:
                        subtitle = self.game_players[
                            str(better["raw_name"])
                        ].display_name
                case _:
                    self.logger.warning(
                        f"unexpected alt rush team size {len(other_adjacent_players):d}: {other_adjacent_players}"
                    )
                    return
        self.downstream.reset_title()
        self.downstream.set_title(title=title, subtitle=subtitle)

        self.adjacent_teams_highlighted = True

    def get_own_team_info(self: ProxhyPlugin) -> BedWarsTeam:
        """Get team name and color code for the current user."""
        sidebar_own_team = next(
            (team for team in self.gamestate.teams.values() if "YOU" in team.suffix),
            None,
        )
        if sidebar_own_team is None:
            raise ValueError(
                "Player is not on a team; cannot determine own team color."
            )

        match_ = re.search(r"§[a-f0-9](\w+)(?=§f:)", sidebar_own_team.prefix)
        if match_ is not None and is_team_name(team_name := match_.group(1)):
            return BedWarsTeam.from_name(team_name)
        elif match_ is None:
            raise ValueError(
                f"Could not determine own team color; regex did not match prefix {sidebar_own_team.prefix!r}"
            )
        else:
            raise ValueError(
                f"Could not determine own team color; {team_name!r} is not a valid team!"
            )

    def get_adjacent_teams(self: ProxhyPlugin) -> tuple[TeamName, TeamName]:
        team = self.get_own_team_info()
        # TODO will raise ValueError if player is not on a team; handle!

        if self.game.map is not None and self.game.map.name.lower() in RUSH_MAPPINGS:
            key = self.game.map.name.lower()
        else:
            key = "DEFAULT"

        main_rush = RUSH_MAPPINGS[key]["main"][team.name.lower()]
        alt_rush = RUSH_MAPPINGS[key]["alt"][team.name.lower()]

        return (main_rush, alt_rush)

    def get_players_on_team(self: ProxhyPlugin, color: str) -> list[str]:
        """Get a de-duplicated list of player names on the given team color.

        Args:
            color: Team color name (case-insensitive: 'green', 'Green', 'GREEN', etc.)

        Returns:
            List of player names on that team
        """
        target = color.lower()
        players: set[str] = set()
        for team in self.gamestate.teams.values():
            # team names like 'Green8', 'Green9' -> strip digits to get color
            base_color = re.sub(r"\d", "", team.name).lower()
            if base_color == target:
                players.update(team.members)
        return list(players)

    # TODO: rewrite with new system
    async def stat_highlights(self: ProxhyPlugin) -> None:
        """Display top 3 enemy players and nicked players."""

        if self.game.mode == "bedwars_two_one_duels":
            return

        try:
            own_team_color = self.get_own_team_info().name
        except ValueError as e:
            self.logger.warning(f"could not determine own team color: {e}")
            return

        enemy_players = []
        enemy_nicks = []

        # Process each player
        for player in self.game_players.values():
            if (
                player.username == self.nick_or_username
                or own_team_color == player.team.name
            ):
                continue

            _fppd = player._provider_data[HypixelProvider]
            if _fppd is None or _fppd.data is None:
                raise RuntimeError("This should not happen!")

            fdict = _fppd.data

            if isinstance(fdict, Nick):
                enemy_nicks.append(f"{player.team.code}{player.username}§f")
                continue

            if self.settings.bedwars.tablist.stats.is_mode_specific.get() == "ON":
                mode = self.game.mode[8:].lower()
                fkdr = fdict[f"{mode}_fkdr"]
                f_fkdr = fdict[f"{mode}_fkdr"]
            else:
                fkdr = fdict["raw_fkdr"]
                f_fkdr = fdict["fkdr"]

            fkdr = int(fdict["raw_fkdr"])
            stars = int(fdict["raw_level"])

            if self.settings.bedwars.display_top_stats.get() == "FKDR":
                rank_value = fkdr
            elif self.settings.bedwars.display_top_stats.get() == "STARS":
                rank_value = stars
            elif self.settings.bedwars.display_top_stats.get() == "INDEX":
                rank_value = fkdr**2 * stars
            else:
                rank_value = fkdr

            enemy_players.append(
                {
                    "name": player.username,
                    "star_formatted": fdict["star"],
                    "fkdr_formatted": f_fkdr,
                    "rank_value": rank_value,
                    "team_color": player.team.prefix,
                }
            )

        # Build output
        result = ""

        # Add nicks section
        if enemy_nicks:
            result += f"§5§lNICKS§r: {', '.join(enemy_nicks)}"
            if enemy_players:
                result += "\n\n"

        # Add top 3 enemy players
        if enemy_players:
            top_players = sorted(
                enemy_players, key=lambda x: x["rank_value"], reverse=True
            )[:3]
            for i, player in enumerate(top_players, 1):
                if i > 1:
                    result += "\n"
                result += f"§f§l{i}§r: {player['star_formatted']} {player['team_color']} {player['name']}; FKDR: {player['fkdr_formatted']}"
        elif not enemy_nicks:
            result = "No stats found!"

        self.downstream.chat(
            TextComponent("Top stats:\n\n")
            .color("gold")
            .bold()
            .append(result)
            .append("\n")
        )
        self.stats_highlighted = True

    @subscribe(r"chat:server:.* has joined .*!")
    async def _statcheck_event_chat_server_player_joined(
        self: ProxhyPlugin, _match, buff: Buffer
    ):
        self.downstream.send_packet(0x02, buff.getvalue())

        if self.settings.bedwars.api_key_reminder.get() == "ON":
            message = buff.unpack(Chat)
            m = JOIN_RE.match(message)
            if m and m.group("ign").casefold() == self.nick_or_username.casefold():
                if not await self.hypixel_provider.validate_key():
                    await self.send_api_key_err()

    @subscribe("chat:server:ONLINE: .*")
    async def _statcheck_event_chat_server_who(
        self: ProxhyPlugin, _match, buff: Buffer
    ):
        message = buff.unpack(Chat)

        if not self.received_who.is_set():
            self.received_who.set()
        else:
            self.downstream.send_packet(0x02, buff.getvalue())

        self.who_players.update(message.removeprefix("ONLINE: ").split(", "))

    def get_player_to_uuid_mapping(self: ProxhyPlugin) -> dict[str, uuid.UUID]:
        """Get a mapping of player names to UUIDs."""
        return {player.username: player.uuid for player in self.game_players.values()}

    @subscribe(
        "chat:server:(You will respawn in 10 seconds!|Your bed was destroyed so you are a spectator!)"
    )
    async def _statcheck_event_chat_server_bedwars_rejoin(
        self: ProxhyPlugin, _match, buff: Buffer
    ):
        self.downstream.send_packet(0x02, buff.getvalue())
        message = buff.unpack(Chat)

        status = GamePlayerStatus.RESPAWNING
        if "spectator" in message:
            status = GamePlayerStatus.ELIMINATED

        # refresh stats
        await asyncio.sleep(0.1)
        self_team = self.get_own_team_info()
        self_game_player = GamePlayer(
            self.nick_or_username,
            self.uuid,
            self_team,
            status=status,
            respawn_time=0,  # we set to 10 later
            mode=self.game.mode.removeprefix("bedwars_"),
        )
        self.game_players[self.nick_or_username] = self_game_player

        if "spectator" in message:
            # remove self from tab and replace with offline uuid self
            self.downstream.send_packet(
                0x38,
                VarInt.pack(4),
                VarInt.pack(1),
                UUID.pack(self_game_player.uuid),
            )
            # set self display name to dead
            self.downstream.send_packet(
                0x38,
                VarInt.pack(0),  # spawn player
                VarInt.pack(1),  # number of players
                UUID.pack(self_game_player.offline_uuid),
                String.pack(self_game_player.username),
                VarInt.pack(0),
                VarInt.pack(3),  # gamemode; spectator
                VarInt.pack(0),  # ping
                Boolean.pack(True),
                Chat.pack(self._get_dead_display_name(self_game_player)),
            )

        self.logger.debug(f"putting self: {self_game_player!r}")
        self.player_stats_queue.put_nowait(self_game_player)

        self.upstream.send_packet(0x01, String.pack("/who"))
        self.received_who.clear()

        self.game.started = True

        self._rebuild_display_names()

        if "respawn" in message:
            self.create_task(self.respawn_timer(self_game_player, reconnect=True))

    def in_bedwars_game(self: ProxhyPlugin):
        return self.game.gametype == "bedwars" and self.game.mode

    @subscribe(f"chat:server:({'|'.join(GAME_START_MESSAGES)})")
    async def _statcheck_event_chat_server_game_start(
        self: ProxhyPlugin, _match, buff: Buffer
    ):
        self.downstream.send_packet(0x02, buff.getvalue())

        message = buff.unpack(Chat)

        if message in {msg_set[-2] for msg_set in GAME_START_MESSAGE_SETS}:  # runs once
            self.create_task(self.highlight_adjacent_teams())
            self.upstream.chat("/who")
            self.received_who.clear()
            self.game.started = True

    @command("resetkey")
    async def _command_reset_key(self: ProxhyPlugin):
        """Reset your Hypixel API key."""
        self.hypixel_client.remove_key(self.hypixel_api_key)
        self.hypixel_api_key = ""
        return TextComponent("Reset your Hypixel API key!").color("green")

    @command("key", "apikey")
    async def _command_key(
        self: ProxhyPlugin,
        provider_or_hypixel_api_key: _LowerRegisteredProvider_T | str = "hypixel",
        key: str = "",
    ):
        """Set or view your active API keys."""

        if provider_or_hypixel_api_key not in get_args(_LowerRegisteredProvider_T):
            if (v := uuid_version(provider_or_hypixel_api_key)) is None:
                valid_options = get_args(_LowerRegisteredProvider_T)
                raise CommandException(
                    f"'{provider_or_hypixel_api_key}' is not a valid option! "
                    f"Enter either a valid provider ({'|'.join(valid_options)}) or your Hypixel API key."
                )
            elif v != 4:
                # probably not hypixel api key
                # TODO: is this a valid check?
                raise CommandException("Invalid Hypixel API Key!")

            # else
            key = provider_or_hypixel_api_key
            provider_or_hypixel_api_key = "hypixel"

        provider_name = typing.cast(
            _LowerRegisteredProvider_T, provider_or_hypixel_api_key
        )
        provider = self.active_providers[provider_name]

        if not key:
            if provider.api_key is not None:
                return (
                    TextComponent(f"{provider.display_name()} API Key:")
                    .color("yellow")
                    .appends(
                        TextComponent("[Click to Reveal]")
                        .color("green")
                        .click_event("suggest_command", provider.api_key)
                    )
                    .appends(
                        TextComponent("[Click to Reset]")
                        .color("red")
                        .click_event("run_command", "/resetkey")
                    )
                )
            else:
                raise CommandException(
                    f"You have not set your {provider.display_name()} API key yet!"
                )

        key_valid = await provider.validate_key(key)
        if not key_valid:
            raise CommandException(f"Invalid {provider.display_name()} API key!")

        provider.api_key = key

        for player in self.game_players.values():
            self.player_stats_queue.put_nowait(player)
        self.game_errors.clear()

        return self.downstream.chat(
            TextComponent(f"Updated {provider.display_name()} API Key!").color("green")
        )

    def match_kill_message(self: ProxhyPlugin, message: str) -> re.Match | None:
        """Match a kill message against known patterns.

        Returns:
            Match object if message matches a kill pattern, None otherwise
        """
        for pattern in KILL_MSGS:
            match = re.match(pattern, message)
            if match:
                return match  # Only 3 groups: victim, killer, final_kill
        return None

    async def respawn_timer(
        self: ProxhyPlugin, player: GamePlayer, reconnect: bool = False
    ) -> None:
        """Display a countdown timer in the tab list for respawning players."""
        if not self.settings.bedwars.tablist.show_respawn_timer.get() == "ON":
            return

        if player.respawn_timer_task is not None:
            player.respawn_timer_task.cancel()
            self.downstream.send_packet(
                0x38,
                VarInt.pack(4),
                VarInt.pack(1),
                UUID.pack(player.offline_uuid),
            )

        player.respawn_timer_task = self.create_task(
            self._respawn_timer(player, reconnect)
        )

    async def _respawn_timer(
        self: ProxhyPlugin, player: GamePlayer, reconnect: bool = False
    ):
        # remove player from tablist
        # hypixel already does this for other players
        # but not for the user themselves
        self.downstream.send_packet(
            0x38,
            VarInt.pack(4),
            VarInt.pack(1),
            UUID.pack(player.uuid),
        )

        # spawn player for timer
        self.downstream.send_packet(
            0x38,
            VarInt.pack(0),
            VarInt.pack(1),
            UUID.pack(player.offline_uuid),
            String.pack(player.username),
            VarInt.pack(0),  # 0 properties
            VarInt.pack(3),  # gamemode
            VarInt.pack(0),  # ping
            Boolean.pack(True),
            Chat.pack(self._get_dead_display_name(player)),
        )

        timer_duration = 10 if reconnect else 5

        for s in range(timer_duration, 0, -1):
            player.respawn_time = s
            self._send_tablist_update(
                {player.offline_uuid: self._get_respawning_display_name(player)}
            )
            await asyncio.sleep(1)

        player.respawn_time = 0
        if player.status != GamePlayerStatus.ELIMINATED:
            self.downstream.send_packet(
                0x38,
                VarInt.pack(4),  # remove player
                VarInt.pack(1),
                UUID.pack(player.offline_uuid),
            )

        await asyncio.sleep(
            0.5  # 0.5s works for most scenarios, but we could even sleep longer;
        )  # occasionally a lag spike will cause this to incorrectly fire
        if self.gamestate.get_player_by_name_from_player_list(player.username):
            player.status = GamePlayerStatus.ALIVE
        elif player.username in self.game_players:
            self.downstream.chat(
                f"{player.team.code}{player.username}§7 disconnected while respawning."
            )

    @subscribe(r"chat:server:(.+?) reconnected\.$")
    async def _statcheck_event_chat_server_player_recon(
        self: ProxhyPlugin, _match, buff: Buffer
    ):
        self.downstream.send_packet(0x02, buff.getvalue())

        await self.received_locraw.wait()  # so that we can run the next check
        if not self.in_bedwars_game():
            return

        message = buff.unpack(Chat)
        username = message.split(" ")[0]

        if (player := self.game_players.get(username)) is None:
            return self.logger.warning(
                f"{username} reconnected but was not found in self.game_players"
            )

        self.create_task(self.respawn_timer(player, reconnect=True))

    @subscribe(f"chat:server:{'|'.join(KILL_MSGS)}")
    async def _statcheck_event_chat_server_kill_msg(
        self: ProxhyPlugin, _match, buff: Buffer
    ):
        self.downstream.send_packet(0x02, buff.getvalue())

        if not self.in_bedwars_game():
            return

        message = buff.clone().unpack(Chat)
        fmted_message = Chat.unpack_component(buff).to_legacy()

        if message.startswith("BED DESTRUCTION >"):
            # some kill messages match bed destroy messages
            return

        m = self.match_kill_message(message)
        if not m:
            return

        fk = message.endswith("FINAL KILL!")

        username = m.group(1)
        if username not in self.game_players:
            color_code = match_player_color(username, fmted_message)
            if color_code is None:
                self.logger.warning(f"failed to find color code for {username}")
                return

            self.game_players[username] = GamePlayer(
                username,
                offline_uuid(username),
                BedWarsTeam.from_name(COLOR_CODE_TO_NAME[color_code]),
                status=GamePlayerStatus.ELIMINATED
                if fk
                else GamePlayerStatus.RESPAWNING,
                respawn_time=0,
                mode=self.game.mode.removeprefix("bedwars_"),
            )

        gplayer = self.game_players[username]

        if message.endswith("disconnected."):
            return

        if fk:
            gplayer.status = GamePlayerStatus.ELIMINATED

            if gplayer.respawn_timer_task is not None:
                gplayer.respawn_timer_task.cancel()

            if self.settings.bedwars.tablist.show_eliminated_players.get() == "ON":
                if gplayer.username == self.nick_or_username:
                    self.downstream.send_packet(
                        0x38,
                        VarInt.pack(4),
                        VarInt.pack(1),
                        UUID.pack(gplayer.uuid),
                    )
                self.downstream.send_packet(
                    0x38,
                    VarInt.pack(0),  # spawn player
                    VarInt.pack(1),  # number of players
                    UUID.pack(gplayer.offline_uuid),
                    String.pack(gplayer.username),
                    VarInt.pack(0),
                    VarInt.pack(3),  # gamemode; spectator
                    VarInt.pack(0),  # ping
                    Boolean.pack(True),
                    Chat.pack(self._get_dead_display_name(gplayer)),
                )
        else:
            self.create_task(self.respawn_timer(gplayer))
