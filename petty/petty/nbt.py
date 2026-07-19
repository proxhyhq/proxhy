"""
petty.nbt — Minecraft NBT library.

This module re-exports the Rust-native NBT implementation from petty._petty.
The API is identical to the previous pure-Python implementation.
"""

from petty._petty import (  # type: ignore
    TagByte,
    TagByteArray,
    TagCompound,
    TagDouble,
    TagEnd,
    TagFloat,
    TagInt,
    TagIntArray,
    TagList,
    TagLong,
    TagLongArray,
    TagShort,
    TagString,
    dumps,
    from_dict,
    loads,
    read_nbt_size,
    to_dict,
)

# Re-export everything for wildcard imports
__all__ = [
    "TagEnd",
    "TagByte",
    "TagShort",
    "TagInt",
    "TagLong",
    "TagFloat",
    "TagDouble",
    "TagByteArray",
    "TagString",
    "TagList",
    "TagCompound",
    "TagIntArray",
    "TagLongArray",
    "loads",
    "dumps",
    "from_dict",
    "to_dict",
    "read_nbt_size",
    # Legacy exception names for compatibility
    "NBTError",
    "NBTParseError",
    "NBTWriteError",
]


# Legacy exception shims (Python callers may catch these)
class NBTError(Exception):
    """Base NBT exception."""


class NBTParseError(NBTError):
    """Raised when NBT data cannot be parsed."""


class NBTWriteError(NBTError):
    """Raised when NBT data cannot be written."""


def load(file_path: str, little_endian: bool = False) -> TagCompound:
    """Load NBT data from a file."""
    with open(file_path, "rb") as f:
        data = f.read()
    return loads(data)


def dump(
    tag: TagCompound,
    file_path: str,
    compression: str | None = None,
    little_endian: bool = False,
) -> None:
    """Save NBT data to a file."""
    data = dumps(tag, compression)
    with open(file_path, "wb") as f:
        f.write(data)
