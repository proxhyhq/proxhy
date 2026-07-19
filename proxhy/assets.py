from pathlib import Path
from typing import Any, overload

import orjson

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def get_asset_path(filename: str) -> Path:
    return _ASSETS_DIR / filename


@overload
def load_json_asset(filename: str) -> dict[str, Any]: ...


@overload
def load_json_asset(filename: str) -> list[Any]: ...


def load_json_asset(filename: str) -> dict[str, Any] | list[Any]:
    with get_asset_path(filename).open("rb") as f:
        return orjson.loads(f.read())
