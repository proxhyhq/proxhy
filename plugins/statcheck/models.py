import uuid
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Literal

TeamName = Literal["Red", "Blue", "Green", "Yellow", "Aqua", "White", "Pink", "Gray"]
TeamLetter = Literal["R", "B", "G", "Y", "A", "W", "P", "S"]
TeamColorCode = Literal["§c", "§9", "§a", "§e", "§b", "§f", "§d", "§8"]

TEAM_NAME_TO_LETTER: dict[TeamName, TeamLetter] = {
    "Red": "R",
    "Blue": "B",
    "Green": "G",
    "Yellow": "Y",
    "Aqua": "A",
    "White": "W",
    "Pink": "P",
    "Gray": "S",
}

TEAM_LETTER_TO_CODE: dict[TeamLetter, TeamColorCode] = {
    "R": "§c",
    "B": "§9",
    "G": "§a",
    "Y": "§e",
    "A": "§b",
    "W": "§f",
    "P": "§d",
    "S": "§8",
}

COLOR_CODE_TO_NAME: dict[TeamColorCode, TeamName] = {
    "§c": "Red",
    "§9": "Blue",
    "§a": "Green",
    "§e": "Yellow",
    "§b": "Aqua",
    "§f": "White",
    "§d": "Pink",
    "§8": "Gray",
}


@dataclass
class BedWarsTeam:
    letter: TeamLetter
    code: str
    name: TeamName
    prefix: str = field(init=False)

    def __post_init__(self):
        self.prefix = f"{self.code}§l{self.letter}"

    @classmethod
    def from_letter(cls, letter: TeamLetter):
        if letter not in TEAM_LETTER_TO_CODE:
            raise ValueError(f"Invalid team letter: {letter}")

        code = TEAM_LETTER_TO_CODE[letter]
        name = COLOR_CODE_TO_NAME[code]

        return cls(letter=letter, code=code, name=name)

    @classmethod
    def from_name(cls, name: TeamName):
        if name not in TEAM_NAME_TO_LETTER:
            raise ValueError(f"Invalid team name: {name!r}")

        letter = TEAM_NAME_TO_LETTER[name]
        code = TEAM_LETTER_TO_CODE[letter]
        name = COLOR_CODE_TO_NAME[code]

        return cls(letter=letter, code=code, name=name)


class GamePlayerStatus(StrEnum):
    ALIVE = auto()
    RESPAWNING = auto()
    ELIMINATED = auto()


@dataclass
class Nick:
    name: str
    uuid: uuid.UUID
