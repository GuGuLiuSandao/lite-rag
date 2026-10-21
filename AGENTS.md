# AGENTS.md

## Purpose

This repository contains a local, serverless, lightweight RAG implementation in Python.
This file is for coding agents that read, modify, test, or review code in this repo.

## Repository overview

- `src/lite_rag/config.py` — environment config, storage paths, supported file types
- `src/lite_rag/providers.py` — lazy local model loading and HTTP embeddings/rerank adapters
- `src/lite_rag/store.py` — knowledge base and file CRUD, indexing, retrieval
- `src/lite_rag/cli.py` — `argparse` CLI entrypoint and JSON output contract
- `src/lite_rag/utils.py` — file helpers, chunking, JSON, timestamps
- `src/lite_rag/models.py` — LanceDB schema factory
- `tests/` — pytest-based tests
- `skill/local-lite-rag/` — reusable local skill wrapper
- `README.md` — install, config, and CLI usage examples
- `pyproject.toml` — package metadata, dependencies, build backend, CLI script

## Rules files status

No repository-specific Cursor or Copilot instruction files were found:

- `.cursor/rules/` — not present
- `.cursorrules` — not present
- `.github/copilot-instructions.md` — not present

If any of those files are added later, update this document and follow them.

## Environment and setup

- Required Python: `>=3.10` from `pyproject.toml`
- Local inference install: `pip install -e '.[local]'`
- HTTP-only install: `pip install -e .` (no local inference dependencies)
- CLI/API load repository `.env` without overriding existing environment variables
- Model providers are independently configurable via `LITE_RAG_EMBED_PROVIDER` / `LITE_RAG_RERANK_PROVIDER` (`local` or `http`)
- HTTP providers require full `*_API_URL`; optional `*_API_KEY` is sent as a Bearer token
- Changing embedding provider/model/URL requires a new storage root and reimport; do not bypass index identity checks
- For the skill wrapper, create `.env` first:

```bash
cp skill/local-lite-rag/.env.example skill/local-lite-rag/.env
```

- Minimum env: none required (`LITE_RAG_STORAGE_ROOT` is optional)

```env
LITE_RAG_STORAGE_ROOT=/absolute/path/to/local-lite-rag-data
```

If unset, storage defaults to `<repo_root>/.lite-rag`.

- `LITE_RAG_ENABLE_RERANKER` is optional and defaults to `true`; set it to `false` if you need the most minimal local path

## Build, run, and test commands

### Packaging / build

- Build backend: `setuptools.build_meta`
- Package root: `src/`
- Editable install: `pip install -e .`
- No `Makefile`, `tox`, `nox`, `poetry`, `uv`, or custom build script was found

### Run the CLI

Installed entrypoint:

```bash
lite-rag kb list
```

Examples:

```bash
lite-rag kb create --name "产品文档"
lite-rag file add --kb "产品文档" --path ./demo.md
lite-rag search --kb "产品文档" --query "怎么做混合检索" --mode hybrid
python -X utf8 skill/local-lite-rag/tool.py kb list
```

### Tests

Run the full suite:

```bash
pytest
python -m pytest
```

Run a single test file:

```bash
python -m pytest tests/test_utils.py
python -m pytest tests/test_config.py
```

Run a single test function:

```bash
python -m pytest tests/test_utils.py::test_chunk_text_returns_non_empty_chunks
python -m pytest tests/test_config.py::test_config_builds_paths_from_env
```

### Lint / format / type check

No dedicated lint, formatter, or static type checker configuration was found.
No config was found for Ruff, Black, isort, Flake8, or mypy.

- Do not invent repo-specific lint commands
- Keep formatting consistent with existing source
- If you add tooling config later, update this file with exact commands

### Verification expectations

When changing Python logic:

1. Run the smallest relevant pytest target first
2. Run `python -m pytest` for broader changes crossing module boundaries
3. Prefer targeted verification before expensive end-to-end flows

### Local dev server restart policy

- After any code change that affects the backend API or the web frontend, agents should default to restarting the relevant local dev servers without waiting for an extra user instruction
- In this repository, the default expectation is to restart both backend and frontend after modifications unless the user explicitly says not to
- Backend default restart command: `python -m uvicorn lite_rag.api:app --host 127.0.0.1 --port 8000`
- Frontend default restart command (from `web/`): `npm run dev -- --host 127.0.0.1 --port 5173`
- After restart, verify the backend health or relevant endpoint and confirm the frontend dev server process is running

## Code style guidelines

These conventions are inferred from the current codebase and should be preserved.

### General style

- Use Python 3.10+ syntax
- Prefer straightforward, explicit, imperative code
- Keep functions and modules focused
- Avoid unnecessary abstractions and indirection
- Preserve current behavior unless the task explicitly changes it

### Imports

- Start Python modules with `from __future__ import annotations`
- Group imports as: standard library, third-party, local package
- Separate groups with one blank line
- Prefer explicit imports over wildcard imports
- Use relative imports within `src/lite_rag/`

### Formatting

- Follow existing PEP 8-style formatting
- Use 4-space indentation
- Keep blank lines and spacing similar to neighboring code
- Break long calls over multiple lines instead of over-compressing logic
- Prefer f-strings for interpolation

### Types

- Add type hints on public functions and methods
- Match the existing style: `list[str]`, `dict[str, Any]`, `str | None`
- Prefer concrete types over broad ones when practical
- Use `Any` sparingly at dynamic boundaries
- Keep explicit return annotations, including `-> None`

### Naming and structure

- Classes: `PascalCase`
- Functions, methods, variables, attributes: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: leading underscore
- Use `@dataclass(slots=True)` for lightweight config-style containers
- Preserve the LanceDB schema factory pattern in `models.py`

### Error handling

- Raise specific built-in exceptions when possible
- Use `ValueError` for invalid input, config, or state
- Use `FileNotFoundError` for missing files
- Keep error messages direct and actionable
- Avoid broad `except Exception` unless intentionally acting as a boundary
- In CLI code, preserve JSON error output and exit status `1`

### Paths and filesystem

- Use `pathlib.Path` rather than string path manipulation
- Normalize external paths with `.expanduser().resolve()`
- Create directories with `mkdir(parents=True, exist_ok=True)` when needed
- Preserve UTF-8 handling, including `utf-8-sig` fallback where already used

### CLI and testing conventions

- Keep the CLI based on `argparse`
- Add new flags and subcommands in the existing parser style
- Keep `run()` returning structured Python objects and serialize once in `main()`
- Preserve the JSON output contract:
  - success: `{"ok": true, "result": ...}`
  - failure: `{"ok": false, "error": "..."}`
- Keep command names consistent with existing groups: `kb`, `file`, `search`
- Tests use `pytest`; files follow `tests/test_*.py`; functions follow `test_*`
- Prefer focused unit tests unless filesystem or index integration is required
- Use `monkeypatch` for environment-related tests

### Change guidance for agents

- Prefer minimal, localized edits
- Do not rename commands, env vars, or JSON fields without strong reason
- Do not add dependencies unless necessary
- If you add a command, toolchain config, or workflow convention, update this file
- Preserve current behavior around supported text file types
- Do not assume OCR, PDF parsing, or image parsing support unless the task explicitly adds it
