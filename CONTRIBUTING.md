# Contributing

## Setup

Proxhy is a [uv](https://docs.astral.sh/uv/) project. To set it up:

```bash
uv sync --group dev
```

You will also need [rust installed](https://rust-lang.org/tools/install/) for `maturin` to build the rust extensions.

Proxhy uses `pre-commit` to help verify changes. Install the hooks with `pre-commit install`.

## Before opening a PR

Make sure to run pre-commit if you don't have the hooks installed:

```bash
uv run pre-commit run --all-files --hook-stage pre-push
```

Exclude `--all-files` to run it on only changes that you've added with `git add`.

To auto-fix lint and format issues:

```bash
uv run ruff check --fix . && uv run ruff format .
```

Type errors from pyrefly must be fixed manually.
