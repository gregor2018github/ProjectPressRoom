# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ProjectPressroom is a self-hosted RSS/Atom news collector with a FastAPI backend and React+Vite frontend. Articles from configured feeds are pulled into a local SQLite database; a web UI handles browsing, search, and (in later phases) LLM-backed weekly digests.

**Status:** Pre-alpha. No source code exists yet — the planning documents (README.md, ARCHITECTURE.md, FEATURES.md) are the source of truth for design decisions. The project layout described there is what must be built.

## Backend setup and commands

```powershell
# Windows (from backend/)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

```bash
# Linux / macOS (from backend/)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

```bash
# Lint
ruff check .

# Format
ruff format .

# Type-check
mypy src

# Run all tests
pytest

# Run a single test file
pytest tests/test_normalize.py

# Run a single test
pytest tests/test_normalize.py::test_external_id_fallback
```

## Frontend setup and commands

```bash
# From frontend/
npm install
npm run dev        # Vite dev server on http://localhost:5173
npm run build
npx eslint .
npx prettier --write .
```

## Running the application

```bash
# Initialise DB
pressroom db init

# Sync sources from config/sources.toml
pressroom sources sync

# Fetch all sources once
pressroom fetch

# Run the background daemon (APScheduler)
pressroom daemon

# Start the API (http://localhost:8000)
pressroom serve
```

## Architecture and key design decisions

### Module boundaries (enforced)

Each module has a single responsibility and communicates only through typed Pydantic models:

- **`fetchers/`** — HTTP + feed parsing only. Returns `FetchResult` with `FetchedEntry` objects; never touches the DB.
- **`normalize.py`** — pure functions. Converts `FetchedEntry` + `Source` → `Article`. No I/O.
- **`db/repository.py`** — the **only** module that touches SQLite. All SQL is parameterised; no string concatenation.
- **`scheduler.py`** — wires APScheduler to `FetchOrchestrator`. Never bypasses the orchestrator.
- **`api/`** — FastAPI routes. All inputs/outputs are Pydantic-validated. No inline SQL.
- **`analytics/`** — read-only on `articles`, writes into `tags`. Phase 3+.

### Data flow for a fetch run

Scheduler → Orchestrator (acquires per-source lock) → `RssFetcher` (conditional GET) → `Normaliser` → `Repository.insert_article` → `fetch_runs` row written (always, even on error).

### Deduplication is structural

`UNIQUE (source_id, external_id)` and `UNIQUE (content_hash)` in the DB are the dedup mechanism. `Repository.insert_article` wraps `IntegrityError` and returns `InsertResult.DUPLICATE`. Do not add application-level pre-checks.

`external_id` derivation order: feed `<guid>`/`<id>` → canonical URL → SHA-256 of `(url + title)`.

### HTML handling

Bodies arrive as third-party HTML. Always sanitise to an allowlist before storage (`body_html`). Keep the original in `body_html_raw`. The frontend must never use `dangerouslySetInnerHTML` without going through the sanitiser.

### Configuration layering

CLI flags > environment variables (`PRESSROOM_*`) > `.env` file > defaults. Loaded via `pydantic-settings` into a single `Settings` object in `config.py`. `config/sources.toml` is separate — it feeds the `sources` table via `pressroom sources sync`; once in the DB, the DB is the runtime source of truth.

### FTS5

The `articles_fts` virtual table is kept in sync by three triggers (`articles_ai`, `articles_ad`, `articles_au`). Never write to `articles_fts` directly outside those triggers.

### Frontend API client

A typed client in `frontend/src/api/` wraps every backend endpoint — one function per endpoint, hand-written TypeScript interfaces for now. All `fetch` calls go through this client.

### SQLite / single-writer rule

Only one process writes at a time. The daemon and `pressroom serve` are separate processes; do not co-host them unless using the `AsyncIOScheduler` path described in ARCHITECTURE.md §3.4.

## Key env vars

| Variable | Default | Purpose |
|---|---|---|
| `PRESSROOM_DB_PATH` | `./data/pressroom.sqlite` | SQLite file location |
| `PRESSROOM_FETCH_CONCURRENCY` | `4` | Max parallel fetches |
| `PRESSROOM_FETCH_TIMEOUT` | `15` | Per-request HTTP timeout (seconds) |
| `PRESSROOM_DEV` | unset | When truthy, enables CORS for `http://localhost:5173` |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend → API base URL |

## Testing approach

- Unit tests target `normalize.py` and `repository.py` at ~80% coverage.
- Integration test uses `httpx.MockTransport` to serve a fixture feed file; asserts DB state after one run, then asserts zero new articles on a second run.
- API tests use FastAPI's `TestClient`, one happy-path and one error per route.
- Pytest target: under 10 seconds total.
- Do not test APScheduler internals.
