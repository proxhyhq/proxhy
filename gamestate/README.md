# Gamestate (Rust Extension)

This is a Rust-based rewrite of the original Python `gamestate` module for Proxhy, built using PyO3 and Maturin to maximize packet parsing performance.

## Overview
The `gamestate` extension listens to network packets (both clientbound and serverbound) and maintains an up-to-date representation of the Minecraft world, including:
- Entities, Players, and Block Entities
- Chunks and Block states
- Player stats, inventory, and health
- World time, dimension, and gamemode

## Architecture
- **Zero-Copy Parsing:** Instead of unmarshalling every packet into Python objects, we use a custom `PacketReader` with a `Cursor<&[u8]>` to efficiently read native types directly from the byte stream.
- **PyO3 Integration:** The module uses `#[pyclass]` and `#[pymethods]` macros to expose the `GameState` struct and its associated objects directly to Python without manual FFI overhead.
- **Type Stubs:** The module is shipped with automatically generated Python type stubs (`.pyi`), maintaining full IDE intellisense compatibility with the original Python implementation.

## Development

The module is integrated into the root `uv` workspace. To build and install it in your environment:

```bash
uv sync
# Or manually:
cd gamestate
uv run maturin develop
```

## To-Do
- Complete parsing for the remaining packet handlers (0x31 onwards).
- Optimize NBT parsing directly into native Rust data structures (currently using a fast-skip implementation).
- Complete the integration with the new Rust-based `petty` NBT library for block entity updates.
