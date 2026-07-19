from typing import Literal

from petty.protocol.datatypes import Item

from plugins.settings import Setting, SettingGroup, SettingsStorage, create_setting

_RED_PANE = Item.from_display_name("Red Stained Glass Pane")
_YELLOW_PANE = Item.from_display_name("Yellow Stained Glass Pane")
_LIME_PANE = Item.from_display_name("Lime Stained Glass Pane")
assert _RED_PANE and _YELLOW_PANE and _LIME_PANE


class BroadcastSettings(SettingGroup):
    def __init__(self, storage: SettingsStorage):
        super().__init__(
            key="broadcast",
            display_name="Broadcast",
            description="Broadcast peer settings.",
            item="minecraft:command_block",
        )
        self._storage = storage

        self.fly_speed: Setting[Literal["0.5x", "1x", "2x"]] = create_setting(
            key="broadcast.fly_speed",
            display_name="Fly Speed",
            description="The speed at which you fly at.",
            item="minecraft:feather",
            states={
                "0.5x": (_RED_PANE, "red"),
                "1x": (
                    _YELLOW_PANE,
                    "yellow",
                ),
                "2x": (_LIME_PANE, "green"),
            },
            default_state="1x",
            storage=self._storage,
        )

        self.titles: Setting[Literal["OFF", "ON"]] = create_setting(
            key="broadcast.titles",
            display_name="Titles",
            description="Show title messages on screen.",
            item="minecraft:sign",
            states={
                "OFF": (_RED_PANE, "red"),
                "ON": (_LIME_PANE, "green"),
            },
            default_state="ON",
            storage=self._storage,
        )

        self.hide_system_messages: Setting[Literal["OFF", "ON"]] = create_setting(
            key="broadcast.hide_system_messages",
            display_name="Hide System Messages",
            description="Hide messages that frequently come from automated client commands, "
            "like /tip, /who, and /locraw. May also suppress some user-originated output "
            "from these commands!",
            item="minecraft:book",
            states={
                "OFF": (_RED_PANE, "red"),
                "ON": (_LIME_PANE, "green"),
            },
            default_state="ON",
            storage=self._storage,
        )
