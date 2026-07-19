"""Minecraft protocol data types — thin Python wrapper around the `_petty` Rust extension.

`Buffer` and `DataType` stay pure Python (I/O-bound BytesIO glue, not the hot path).
Everything else is implemented in Rust; `VarInt` gets one Python-level addition
(`unpack_stream`) since it awaits an asyncio stream, which belongs in Python, not Rust.
"""

import struct
from io import BytesIO
from typing import Protocol

from petty._petty import (
    UUID,
    Angle,
    Boolean,
    Byte,
    ByteArray,
    Chat,
    Double,
    Float,
    Int,
    Long,
    Position,
    Short,
    Slot,
    String,
    UnsignedByte,
    UnsignedShort,
)
from petty._petty import VarInt as _VarInt
from petty.models import Item, Pos, SlotData, TextComponent

from ._item_literals import Color_T, DisplayName, ItemID, ItemName

__all__ = [
    "UUID",
    "Angle",
    "AsyncReader",
    "Boolean",
    "Buffer",
    "Byte",
    "ByteArray",
    "Chat",
    "Color_T",
    "DataType",
    "DisplayName",
    "Double",
    "Float",
    "Int",
    "Item",
    "ItemID",
    "ItemName",
    "Long",
    "Pos",
    "Position",
    "Short",
    "Slot",
    "SlotData",
    "String",
    "TextComponent",
    "UnsignedByte",
    "UnsignedShort",
    "VarInt",
]


class AsyncReader[T](Protocol):
    async def read(self, n: int = -1) -> T: ...


class DataType[UT](Protocol):
    """Structural type for the Rust data-type classes: anything with a static `unpack`."""

    @staticmethod
    def unpack(buff: Buffer) -> UT: ...


class Buffer(BytesIO):
    def unpack[T](self, kind: type[DataType[T]]) -> T:
        return kind.unpack(self)

    def clone(self) -> Buffer:
        return Buffer(self.getvalue())


class VarInt(_VarInt):
    # https://gist.github.com/nickelpro/7312782
    @staticmethod
    async def unpack_stream(stream: AsyncReader[bytes]) -> int:
        total = 0
        shift = 0
        val = 0x80

        while (val & 0x80) and (data := await stream.read(1)):
            val = struct.unpack("B", data)[0]
            total |= (val & 0x7F) << shift
            shift += 7

        return total - (1 << 32) if total & (1 << 31) else total
