from typing import Literal

from petty._petty import Item, Pos, SlotData, TextComponent

type ClickEvent_T = Literal[
    "open_url",
    "run_command",
    "suggest_command",
    "change_page",
    # "copy_to_clipboard", # does not seem to work in 1.8
]

__all__ = ["Item", "Pos", "SlotData", "TextComponent"]
