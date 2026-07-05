from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAPS_PATH = ROOT / "bedwars_maps.json"
TYPES_PATH = ROOT / "bedwars_map_types.json"
OUTPUT_PATH = ROOT / "output.json"


def main() -> None:
    maps = json.loads(MAPS_PATH.read_text(encoding="utf-8"))
    map_types = json.loads(TYPES_PATH.read_text(encoding="utf-8"))

    merged = {}
    for name, map_data in sorted(maps.items()):
        merged[name] = {**map_data, **map_types.get(name, {})}

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write("{\n")
        items = list(merged.items())
        for index, (map_name, map_data) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            f.write(
                f"  {json.dumps(map_name, ensure_ascii=False)}: "
                f"{json.dumps(map_data, ensure_ascii=False, separators=(',', ': '))}"
                f"{comma}\n"
            )
        f.write("}\n")


if __name__ == "__main__":
    main()