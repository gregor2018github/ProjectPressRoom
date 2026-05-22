# ProjectPressroom

> A personal, self-hosted news collector and curation tool. Pulls articles from RSS/Atom feeds into a local SQLite database, with a small web UI for browsing, searching, and (later) summarising what you've collected.

`ProjectPressroom` is the working title — matching the naming convention of your other projects (ProjectWarehouse, project-ledger).

---

## Why this exists

Following the news in any serious way produces more noise than signal. Browsing dozens of sites daily is expensive in attention and tends to leave you worse-informed than reading a few articles carefully. The goal here is the inverse: **collect broadly, read narrowly.** A background process pulls articles into a private database; a simple UI helps you triage, search, and eventually receive a once-a-week summary built from what was actually published — not from algorithmic outrage curation.

The project is also a vehicle for some adjacent things worth getting right: clean Python project layout, type-hinted modules, a small but real test suite, and a SQLite schema you can grow into.

---

## What it does

### Today (v0.1, MVP)

- Fetches RSS / Atom feeds from a configurable list of sources.
- Parses each feed, normalises article records, and inserts new ones into SQLite.
- Deduplicates by stable identifiers (feed `guid` first, URL hash second).
- Stores header, summary, full body (where the feed provides it), author, publish date, and source metadata as distinct fields.
- Logs every fetch run with status, count of new articles, and error details if any.
- Exposes a small FastAPI backend and a React + Vite + Recharts frontend for browsing and searching the local archive.
- Runs on Windows (developed there), Linux, and macOS.

### Roadmap

The phased plan lives in [`FEATURES.md`](./FEATURES.md). Short version:

1. **Collection** (this version) — fetch, store, browse.
2. **Search & exploration** — full-text search (SQLite FTS5), filters by source / date / language.
3. **Analytics** — keyword frequency over time, simple sentiment scoring, header-vs-body comparison.
4. **Summarisation & weekly newsletter** — LLM-backed digest of the previous seven days.
5. **Optional scraping adapter** for sites without a usable feed.

---

## Tech stack

Deliberately conservative — standard, well-maintained packages, nothing exotic.

**Backend (Python 3.11+)**

| Concern         | Choice                                    |
| --------------- | ----------------------------------------- |
| Feed parsing    | `feedparser`                              |
| HTTP            | `httpx`                                   |
| Retries         | `tenacity`                                |
| Database        | `sqlite3` (stdlib) + `FTS5` (built-in)    |
| Models / config | `pydantic` v2 + `pydantic-settings`       |
| Scheduling      | `APScheduler`                             |
| Web API         | `FastAPI` + `uvicorn`                     |
| Testing         | `pytest` + `pytest-asyncio` + `httpx`     |
| Lint / format   | `ruff` (lint + format)                    |
| Types           | `mypy`                                    |

**Frontend**

| Concern        | Choice                                 |
| -------------- | -------------------------------------- |
| Framework      | React 18                               |
| Tooling        | Vite                                   |
| Language       | TypeScript                             |
| Charts         | Recharts                               |
| HTTP           | `fetch` + a thin typed client          |
| Styling        | Plain CSS modules to start; revisit later |
| Lint           | ESLint + Prettier                      |

Everything in the backend table is widely used, actively maintained, and has been around long enough to be uncontroversial. None of it requires native compilation on Windows.

---

## Project status

Pre-alpha. Treat the schema and module boundaries as still moving until v0.2 ships. Once a feed has been fetched into a real database, breaking schema changes will go through migrations rather than `DROP TABLE`.

---

## Getting started

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer (for the frontend)
- Git
- Windows, Linux, or macOS

### 1. Clone and set up the backend

```powershell
# Windows PowerShell
git clone https://github.com/<you>/ProjectPressroom.git
cd ProjectPressroom\backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

```bash
# Linux / macOS
git clone https://github.com/<you>/ProjectPressroom.git
cd ProjectPressroom/backend

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Initialise the database

```bash
pressroom db init
```

This creates `data/pressroom.sqlite` with all tables and indexes. The path is configurable via `PRESSROOM_DB_PATH` (see [Configuration](#configuration)).

### 3. Configure your sources

Sources live in `config/sources.toml`. A starter file is shipped in the repo:

```toml
[[source]]
name = "GameStar (Gaming)"
feed_url = "https://www.gamestar.de/rss/gaming.rss"
category = "gaming"
language = "de"

[[source]]
name = "Ars Technica"
feed_url = "https://feeds.arstechnica.com/arstechnica/index"
category = "tech"
language = "en"

[[source]]
name = "Heise Online"
feed_url = "https://www.heise.de/rss/heise-atom.xml"
category = "tech"
language = "de"
```

After editing the file, sync it into the database:

```bash
pressroom sources sync
```

Sources can also be added / disabled directly via the web UI later, but the TOML file is the source of truth for the default set.

### 4. Fetch articles

Manually:

```bash
pressroom fetch          # fetch all active sources
pressroom fetch --source "Ars Technica"
```

Scheduled (runs the in-process APScheduler, polls each source per its configured interval):

```bash
pressroom daemon
```

### 5. Run the API and frontend

**Development** (two terminals, hot-reload):

```bash
# Terminal 1
pressroom serve          # FastAPI on http://localhost:8000

# Terminal 2
cd ../frontend
npm install
npm run dev            # Vite dev server on http://localhost:5173
```

The frontend talks to the API via a configurable base URL (`VITE_API_BASE_URL`, defaults to `http://localhost:8000`).

---

## Production run

Single command — builds the frontend and serves everything from one process on port 8000:

```bash
# From the repo root
cd frontend && npm install && cd ../backend

# Build and serve in one step
pressroom db init
pressroom sources sync
pressroom serve --build-frontend
```

Or build separately and then serve:

```bash
cd frontend && npm run build && cd ../backend
pressroom serve          # http://localhost:8000 serves API + UI
```

The built UI lives at `frontend/dist/` and is mounted at `/` by FastAPI's StaticFiles. All `/api/*` routes remain available alongside it. Unknown paths fall back to `index.html` so the React router handles client-side navigation.

### Database backup

```bash
pressroom db backup data/pressroom_backup.sqlite
```

Uses SQLite's online-backup API — safe to run while the daemon is fetching.

---

## Project structure

```
ProjectPressroom/
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   └── ProjectPressroom/
│   │       ├── __init__.py
│   │       ├── cli.py              # Typer/argparse entry points
│   │       ├── config.py           # Pydantic settings, .env loading
│   │       ├── models.py           # Pydantic article/source models
│   │       ├── db/
│   │       │   ├── schema.sql      # DDL, kept in version control
│   │       │   ├── migrations/     # Numbered SQL migrations
│   │       │   └── repository.py   # Thin data-access layer
│   │       ├── fetchers/
│   │       │   ├── base.py         # Adapter protocol
│   │       │   ├── rss.py          # feedparser-based fetcher
│   │       │   └── scraper.py      # Stub for future HTML fallback
│   │       ├── normalize.py        # Feed entry → Article
│   │       ├── scheduler.py        # APScheduler wiring
│   │       ├── api/
│   │       │   ├── app.py          # FastAPI app factory
│   │       │   └── routes/
│   │       └── analytics/          # Phase 3 (keywords, sentiment)
│   ├── tests/
│   └── config/
│       └── sources.toml
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                    # Typed API client
│       ├── components/
│       └── pages/
├── data/                           # Local DB lives here, gitignored
├── ARCHITECTURE.md
├── FEATURES.md
└── README.md
```

The `src/` layout (rather than a flat package next to `tests/`) is the standard Python convention now and avoids a class of `PYTHONPATH` accidents.

---

## Configuration

Configuration is layered, in order of precedence (highest wins):

1. CLI flags
2. Environment variables (prefix `PRESSROOM_`)
3. `.env` file in the backend root
4. Defaults baked into `config.py`

Important variables:

| Variable                    | Default                     | Purpose                              |
| --------------------------- | --------------------------- | ------------------------------------ |
| `PRESSROOM_DB_PATH`           | `./data/pressroom.sqlite`     | SQLite file location                 |
| `PRESSROOM_USER_AGENT`        | `pressroom/0.1 (+github URL)` | Identifies the fetcher to feed hosts |
| `PRESSROOM_FETCH_TIMEOUT`     | `15` (seconds)              | Per-request HTTP timeout             |
| `PRESSROOM_FETCH_CONCURRENCY` | `4`                         | Max parallel feed fetches            |
| `PRESSROOM_LOG_LEVEL`         | `INFO`                      | Standard logging level               |

No API keys are required for v0.1. When the LLM phase lands, an `PRESSROOM_LLM_API_KEY` variable will be added — loaded only at runtime, never logged.

---

## Development

```bash
# Lint and format
ruff check .
ruff format .

# Type-check
mypy src

# Run tests
pytest

# All of the above
make check          # if you use the provided Makefile
```

Testing approach is deliberately gentle for v0.1 — a handful of focused unit tests around normalisation and the repository layer, plus an integration test that points the RSS fetcher at a checked-in XML fixture rather than the live internet. See [`ARCHITECTURE.md`](./ARCHITECTURE.md#testing-strategy) for the rationale.

---

## Security & politeness notes

A self-hosted news fetcher is a tiny web client, but a few things still matter:

- Every outbound HTTP call carries a descriptive `User-Agent` so feed operators can identify it.
- Each source has a minimum-poll-interval (default 30 minutes); the scheduler refuses to fetch a source more often than that.
- HTTPS is preferred; HTTP is allowed but warned in logs.
- Per-request timeouts are mandatory; `tenacity` handles retries with exponential backoff and a cap.
- All SQL goes through parameterised queries — no string concatenation.
- All API inputs are Pydantic-validated.
- The SQLite file is local to the user's machine; no auth layer in v0.1 because nothing is exposed beyond `localhost`. If the API ever binds to a non-loopback interface, that becomes a real concern; see [`ARCHITECTURE.md`](./ARCHITECTURE.md#security).

---

## Licence

TBD — `MIT` is the obvious default for a personal project; choose before publishing.

## Author

Greg ([github.com/gregor2018github](https://github.com/gregor2018github))
