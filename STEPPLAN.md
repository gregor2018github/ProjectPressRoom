# Build plan

A sequenced list of implementation steps for ProjectPressroom, sized for individual coding-agent sessions. Each step leaves the project in a working, committable state. Do not skip steps — later steps assume the outputs of earlier ones.

---

## How to use this with a coding agent

Before each session, paste into the agent:

1. This step's **Goal**, **Creates / Modifies**, and **Done when** sections.
2. The files listed under **Agent context** — not the entire docs, just those files or sections.
3. Any files the step says it **Modifies** (so the agent edits rather than recreates them).

Keep each session to one step. If the agent finishes early and asks what to do next, say "stop here — I'll start a new session for the next step."

---

## Phase A — Foundation

> Gets the repo to a state where tooling, config, and an empty database all work. No business logic yet.

---

### A1 · Project scaffold

**Goal:** Create the empty directory structure, `pyproject.toml`, tooling config, and a stub CLI entry point. Everything that comes later builds on top of this.

**Creates:**
```
ProjectPressroom/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── Makefile
│   └── src/
│       └── pressroom/
│           ├── __init__.py
│           └── cli.py              # stub: one `--help` command, nothing else
├── config/
│   └── sources.toml                # empty template with commented example
├── data/                           # gitignored
└── .gitignore
```

**Done when:**
- `pip install -e ".[dev]"` runs without errors.
- `ruff check .` and `mypy src` pass on the empty package.
- `pressroom --help` prints without crashing.

**Agent context:** `README.md` (§Stack, §Project structure, §Configuration), `ARCHITECTURE.md` (§6 Configuration, §12 Deployment model).

---

### A2 · Settings and Pydantic models

**Goal:** Define the two things every subsequent module will import: the runtime settings object and the core data models.

**Creates:**
```
src/pressroom/
├── config.py       # pydantic-settings Settings class; loads .env + PRESSROOM_* vars
└── models.py       # Source, Article, FetchedEntry, FetchRun, InsertResult (Pydantic v2)
```

**Done when:**
- `from pressroom.config import settings` works.
- All models are importable and have type hints + docstrings on every field.
- A quick `python -c "from pressroom.models import Article; print(Article.__fields__)"` lists fields without error.

**Agent context:** `ARCHITECTURE.md` (§5 Database schema — use the column names as the model field names), `README.md` (§Configuration table).

---

### A3 · Database init and migration runner

**Goal:** Create the SQLite schema and a small migration runner, wired to a `pressroom db init` CLI command.

**Creates:**
```
src/pressroom/
├── db/
│   ├── __init__.py
│   ├── schema.sql          # full DDL including FTS5 and triggers (copy from ARCHITECTURE §5)
│   ├── migrations/
│   │   └── 0001_initial.sql    # same content as schema.sql; migration 0001
│   └── connection.py       # returns a configured sqlite3.Connection; enables WAL mode and FK enforcement
```

**Modifies:** `cli.py` — adds `pressroom db init` subcommand.

**Done when:**
- `pressroom db init` creates `data/pressroom.sqlite` with all tables, indexes, and FTS triggers.
- Running it a second time is a no-op (migration table tracks applied versions).
- `sqlite3 data/pressroom.sqlite ".tables"` shows `sources`, `articles`, `articles_fts`, `fetch_runs`, `tags`.

**Agent context:** `ARCHITECTURE.md` (§5 full schema DDL — paste the entire SQL block), `ARCHITECTURE.md` (§3.3 Repository note on WAL and FK).

---

## Phase B — Ingestion pipeline

> The four modules that form the data path: HTTP → parse → normalise → store.

---

### B1 · HTTP client wrapper

**Goal:** A thin module that returns a pre-configured `httpx.AsyncClient` with the project user-agent, a global timeout, and `tenacity`-based retry logic. No feed parsing yet — just the transport layer.

**Creates:**
```
src/pressroom/
└── http_client.py      # get_client() context manager; retry decorator; timeout from settings
```

**Done when:**
- `get_client()` is an async context manager that yields an `httpx.AsyncClient`.
- Retries on 5xx, connection error, and timeout — not on 4xx.
- User-agent reads from `settings.user_agent`.
- A `pytest` test (can be a simple sync test using `httpx.MockTransport`) confirms the user-agent header is set correctly.

**Agent context:** `ARCHITECTURE.md` (§3.1 Fetcher adapters — retry and timeout rules, §8 Error handling and retries), `src/pressroom/config.py`.

---

### B2 · RSS fetcher adapter

**Goal:** Implement `RssFetcher` — takes a `Source`, returns a `FetchResult` containing a list of `FetchedEntry` objects (or an error). Handles conditional GET (ETag / Last-Modified).

**Creates:**
```
src/pressroom/fetchers/
├── __init__.py
├── base.py         # Fetcher Protocol; FetchResult dataclass
└── rss.py          # RssFetcher: httpx GET → feedparser → list[FetchedEntry]
```

**Done when:**
- `RssFetcher` correctly honours a `304 Not Modified` — returns `FetchResult` with `not_modified=True` and an empty entry list.
- `FetchedEntry` carries: `external_id` (raw guid/id/url from feed), `url`, `title`, `summary`, `body_html`, `author`, `published_at`, `etag`, `last_modified`.
- A `pytest` test using `httpx.MockTransport` serving a minimal RSS fixture (saved as `tests/fixtures/gamestar_sample.xml`) confirms entries are parsed correctly.

**Agent context:** `src/pressroom/models.py`, `src/pressroom/http_client.py`, `ARCHITECTURE.md` (§3.1 full section, §4 Data flow steps 3–5).

---

### B3 · Normaliser

**Goal:** Pure-function module that converts a `FetchedEntry` + `Source` into a validated `Article` ready for the repository. This is where the header / summary / body split is enforced.

**Creates:**
```
src/pressroom/
└── normalize.py    # normalize(entry, source) -> Article
```

**Done when:**
- `external_id` derivation follows the fallback chain: feed guid → canonical URL → SHA-256 of `(url + title)`.
- `title`, `summary`, and `body_html` / `body_text` are distinct fields; missing ones are `None`, not empty strings.
- `body_html` is sanitised (strip `<script>`, `<iframe>`, event handlers; keep `<p>`, `<a>`, `<ul>`, `<li>`, `<strong>`, `<em>`, `<blockquote>`, `<h2>`–`<h4>`). Raw original goes to `body_html_raw`.
- `body_text` is derived from `body_html` by stripping tags.
- `content_hash` is SHA-256 of `url + '\n' + title`.
- `published_at` is always timezone-aware UTC; `None` is acceptable if unparseable.
- Unit tests cover: full feed entry, summary-only entry, missing guid fallback, malicious HTML sanitisation.

**Agent context:** `src/pressroom/models.py`, `src/pressroom/fetchers/base.py`, `ARCHITECTURE.md` (§3.2 Normaliser, §5 schema — column names).

---

### B4 · Repository

**Goal:** The only module that touches SQLite. Implements the data-access methods needed for the ingestion pipeline and the API.

**Creates:**
```
src/pressroom/db/
└── repository.py   # Repository class with typed methods
```

**Done when:**
- Implements: `upsert_source`, `list_active_sources`, `get_source_by_id`, `insert_article`, `article_exists`, `log_fetch_run`, `update_fetch_run`, `update_source_fetch_meta`.
- `insert_article` wraps the `UNIQUE (source_id, external_id)` constraint — returns `InsertResult.NEW` or `InsertResult.DUPLICATE` without raising.
- `log_fetch_run` opens a `status='running'` row; `update_fetch_run` closes it.
- All SQL uses parameterised queries — no string formatting anywhere.
- Unit tests: insert two articles with the same `external_id` confirms `DUPLICATE` on the second; insert two articles with the same `content_hash` from different sources also returns `DUPLICATE`.

**Agent context:** `src/pressroom/models.py`, `src/pressroom/db/connection.py`, `ARCHITECTURE.md` (§3.3 Repository, §5 schema).

---

## Phase C — Orchestration and CLI

> Connects the pipeline modules together and exposes them to the command line.

---

### C1 · FetchOrchestrator and core CLI commands

**Goal:** The orchestrator is the only place where fetcher + normaliser + repository meet. Wire the three core CLI commands to it.

**Creates:**
```
src/pressroom/
└── orchestrator.py     # FetchOrchestrator.run_once(source) -> FetchRun
```

**Modifies:** `cli.py` — adds `pressroom sources sync`, `pressroom fetch [--source NAME | --all]`.

**Done when:**
- `pressroom sources sync` reads `config/sources.toml` and upserts each entry into the `sources` table.
- `pressroom fetch --all` fetches every active source sequentially, prints a one-line summary per source.
- `pressroom fetch --source "GameStar (Gaming)"` fetches exactly that source.
- The orchestrator correctly records a `fetch_runs` row even when the feed returns an error.
- Manual end-to-end test: after `pressroom fetch --all`, `sqlite3 data/pressroom.sqlite "SELECT COUNT(*) FROM articles"` returns a non-zero number.

**Agent context:** `src/pressroom/fetchers/rss.py`, `src/pressroom/normalize.py`, `src/pressroom/db/repository.py`, `src/pressroom/config.py`, `ARCHITECTURE.md` (§4 Data flow — full sequence), `config/sources.toml`.

---

### C2 · Scheduler and daemon

**Goal:** Add the `pressroom daemon` command, which starts APScheduler with one job per active source.

**Creates:**
```
src/pressroom/
└── scheduler.py    # build_scheduler(repo, orchestrator) -> BaseScheduler
```

**Modifies:** `cli.py` — adds `pressroom daemon`.

**Done when:**
- `pressroom daemon` starts without error and logs "scheduler started" with the number of registered jobs.
- Each job fires at the interval in `sources.fetch_interval_minutes`.
- `coalesce=True`, `max_instances=1`, `jitter=30` are set on every job.
- SIGINT / Ctrl-C shuts the scheduler down gracefully (waits for in-flight jobs).
- Starting the daemon a second time (with the first still running) does not cause a crash — the SQLite WAL mode handles the concurrent read from the daemon + any manual CLI calls.

**Agent context:** `src/pressroom/orchestrator.py`, `src/pressroom/db/repository.py`, `src/pressroom/config.py`, `ARCHITECTURE.md` (§7 Scheduling).

---

## Phase D — API

> Expose the stored data over a small FastAPI backend. Three focused steps.

---

### D1 · FastAPI app factory and health endpoint

**Goal:** The minimal FastAPI app shell with dependency injection for the repository and a working health endpoint.

**Creates:**
```
src/pressroom/api/
├── __init__.py
├── app.py          # create_app() factory; CORS config; mounts routers
└── deps.py         # get_repo() dependency; get_db() connection
```

**Modifies:** `cli.py` — adds `pressroom serve [--host] [--port]`.

**Done when:**
- `pressroom serve` starts uvicorn; `GET /api/health` returns `{"status": "ok", "articles": <count>}`.
- CORS is open to `http://localhost:5173` when `PRESSROOM_DEV=true`; closed otherwise.
- The OpenAPI docs are reachable at `/docs` in dev mode.

**Agent context:** `src/pressroom/db/repository.py`, `src/pressroom/config.py`, `ARCHITECTURE.md` (§3.5 API endpoint table, §9 Security CORS note).

---

### D2 · Sources API routes

**Goal:** All routes that let the frontend read and manage sources.

**Creates:**
```
src/pressroom/api/routes/
└── sources.py      # GET /api/sources, POST /api/sources, PATCH /api/sources/{id},
                    # POST /api/sources/{id}/fetch
```

**Done when:**
- `GET /api/sources` returns a list of sources enriched with last-run metadata (status, articles_new, finished_at) from `fetch_runs`.
- `POST /api/sources` adds a source; returns 409 if `feed_url` already exists.
- `PATCH /api/sources/{id}` allows toggling `is_active` and updating `fetch_interval_minutes`.
- `POST /api/sources/{id}/fetch` runs a fetch immediately (calls the orchestrator synchronously in a threadpool executor) and returns the resulting `FetchRun`.
- All inputs are Pydantic-validated; all errors return `{"detail": "..."}` with correct HTTP codes.
- API test covers each route's happy path and one error case.

**Agent context:** `src/pressroom/api/app.py`, `src/pressroom/api/deps.py`, `src/pressroom/models.py`, `src/pressroom/orchestrator.py`, `ARCHITECTURE.md` (§3.5 endpoint table).

---

### D3 · Articles and runs API routes

**Goal:** The routes the inbox, article reader, and search UI will call.

**Creates:**
```
src/pressroom/api/routes/
├── articles.py     # GET /api/articles, GET /api/articles/{id}, GET /api/articles/search
└── runs.py         # GET /api/runs
```

**Done when:**
- `GET /api/articles` supports query params: `source_id`, `language`, `from_date`, `to_date`, `is_read`, `is_starred`; returns paginated results (`page`, `page_size`, `total`).
- `GET /api/articles/search?q=<fts5 query>` returns results with a `snippet` field (from SQLite `snippet()`) and highlights matched terms.
- `GET /api/runs` returns the last 50 fetch runs across all sources, newest first.
- `PATCH /api/articles/{id}` allows setting `is_read` and `is_starred` (read-state updates from the frontend).
- API tests for pagination, FTS search with a known fixture, and a search returning zero results.

**Agent context:** `src/pressroom/api/deps.py`, `src/pressroom/db/repository.py`, `src/pressroom/models.py`, `ARCHITECTURE.md` (§5 schema — FTS5 and snippet() usage).

---

## Phase E — Frontend

> React + Vite + TypeScript UI, built in four focused steps. Each step is one page plus its API wiring.

---

### E1 · Frontend scaffold and API client

**Goal:** Vite + React + TypeScript project with a typed API client module, ESLint, Prettier, and a working dev server that talks to the backend.

**Creates:**
```
frontend/
├── package.json        # React, Vite, TypeScript, Recharts, ESLint, Prettier
├── vite.config.ts      # proxy /api → localhost:8000 in dev
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx         # top-level router (React Router or simple state switch)
│   └── api/
│       └── client.ts   # typed functions: getSources(), getArticles(), searchArticles(),
│                       #                  getArticle(), patchArticle(), triggerFetch(), getRuns()
```

**Done when:**
- `npm run dev` starts without errors.
- `npm run lint` passes.
- `client.ts` has a typed return type for every endpoint matching the Pydantic response shapes.
- A smoke-test component on the landing page calls `GET /api/health` and displays the article count.

**Agent context:** `README.md` (§Stack frontend table), `ARCHITECTURE.md` (§3.6 Frontend, §3.5 endpoint table — use this to define the TypeScript types).

---

### E2 · Sources page

**Goal:** A page that lists all configured sources with their last-fetch status and lets the user enable/disable them or trigger a manual fetch.

**Creates:**
```
frontend/src/
├── pages/SourcesPage.tsx
└── components/SourceCard.tsx
```

**Done when:**
- Each source shows: name, category, language, is_active toggle, last fetch time, last status badge (ok / error / not_modified), articles fetched in last run.
- The "Fetch now" button calls `POST /api/sources/{id}/fetch`, shows a spinner, then refreshes the card.
- The is_active toggle calls `PATCH /api/sources/{id}` immediately.
- Empty state (no sources configured yet) is handled gracefully.

**Agent context:** `frontend/src/api/client.ts`, the Sources-related TypeScript types.

---

### E3 · Inbox page

**Goal:** The main reading surface — a paginated, filterable list of articles.

**Creates:**
```
frontend/src/
├── pages/InboxPage.tsx
└── components/ArticleRow.tsx
```

**Done when:**
- Articles are listed newest-first, paginated (page size 50).
- Filter bar: multi-select by source, language dropdown, date-range picker (two `<input type="date">`), unread-only toggle.
- Filters update the URL query string so the state is bookmarkable.
- Clicking an article marks it read (`PATCH /api/articles/{id}`) and navigates to the Article page.
- Starring an article from the list view works without navigating away.

**Agent context:** `frontend/src/api/client.ts`, TypeScript Article type.

---

### E4 · Article reader and Search page

**Goal:** The two remaining pages.

**Creates:**
```
frontend/src/
├── pages/ArticlePage.tsx   # clean reader; renders sanitised body_html; star / archive buttons
└── pages/SearchPage.tsx    # search bar + results with snippet highlighting
```

**Done when:**
- The article reader shows: title, source name, author, published date, summary (if present), body HTML rendered safely. External links open in a new tab.
- The back button returns to the inbox with filters preserved.
- The search page calls `GET /api/articles/search?q=...` on input; results show the FTS snippet with matched terms visually highlighted.
- Searching while already on the search page updates results without a full page reload.
- Empty-result state is handled.

**Agent context:** `frontend/src/api/client.ts`, TypeScript Article and SearchResult types.

---

## Phase F — Tests and deployment polish

---

### F1 · Unit and integration tests

**Goal:** A test suite that gives enough confidence to refactor without fear. Normaliser and repository get the most coverage because they carry the most logic.

**Creates:**
```
backend/tests/
├── conftest.py                     # tmp-path SQLite fixture; sample Source fixture
├── fixtures/
│   ├── gamestar_sample.xml         # saved RSS fixture with full-body entry
│   └── summary_only.xml            # RSS fixture where entries have only <description>
├── test_normalize.py               # 6–8 unit tests
├── test_repository.py              # 5–6 unit tests
└── test_integration_fetch.py       # 1 end-to-end test using httpx.MockTransport
```

**Done when:**
- `normalize`: full entry, summary-only, missing guid (fallback chain), malicious HTML stripped, UTC date coercion.
- `repository`: insert new article returns NEW; second insert same `external_id` returns DUPLICATE; FTS search finds a known title.
- Integration: `MockTransport` serves `gamestar_sample.xml`; after `orchestrator.run_once(source)`, article count in DB equals entry count in fixture; running it again changes count by zero.
- `pytest` completes in under 10 seconds.

**Agent context:** `src/pressroom/normalize.py`, `src/pressroom/db/repository.py`, `src/pressroom/orchestrator.py`, `src/pressroom/db/connection.py`, `ARCHITECTURE.md` (§12 Testing strategy).

---

### F2 · Serve frontend from FastAPI and deployment polish

**Goal:** One single `pressroom serve` command that serves both the API and the built frontend. Plus final housekeeping.

**Creates:**
```
backend/src/pressroom/
└── (no new files)
```

**Modifies:**
- `api/app.py` — mount `frontend/dist` as static files at `/`; serve `index.html` for unknown routes (SPA fallback).
- `cli.py` — `pressroom serve` runs `npm run build` first if `--build-frontend` flag is passed.
- `README.md` — add a "Production run" section with the single-command workflow.
- `.gitignore` — ensure `frontend/dist` and `frontend/node_modules` are ignored.

**Done when:**
- `cd frontend && npm run build && cd ../backend && pressroom serve` serves the full app from `http://localhost:8000` with no separate Vite process.
- All API routes still work under `/api/`.
- `pressroom db backup --to data/pressroom_backup.sqlite` works (sqlite3 online-backup API).

**Agent context:** `src/pressroom/api/app.py`, `src/pressroom/cli.py`, FastAPI `StaticFiles` docs (instruct the agent to use `starlette.staticfiles.StaticFiles` with `html=True`).

---

## Summary table

| Step | Phase       | What you have after                                   | Est. size |
|------|-------------|-------------------------------------------------------|-----------|
| A1   | Foundation  | Empty repo with working tooling and `pressroom --help`| S         |
| A2   | Foundation  | Settings object and all Pydantic models               | S         |
| A3   | Foundation  | SQLite DB with full schema and `pressroom db init`    | S         |
| B1   | Ingestion   | Configured HTTP client with retries                   | S         |
| B2   | Ingestion   | RSS fetcher that returns parsed entries               | M         |
| B3   | Ingestion   | Normaliser that produces clean Article objects        | M         |
| B4   | Ingestion   | Repository with dedup and all storage methods         | M         |
| C1   | Orchestration | `pressroom fetch` works end-to-end                  | M         |
| C2   | Orchestration | `pressroom daemon` runs scheduled fetches           | M         |
| D1   | API         | `pressroom serve` + `/api/health`                     | S         |
| D2   | API         | Sources routes fully working                          | M         |
| D3   | API         | Articles, search, and runs routes                     | M         |
| E1   | Frontend    | Vite scaffold + typed API client                      | M         |
| E2   | Frontend    | Sources page (manage and trigger fetches)             | M         |
| E3   | Frontend    | Inbox page (browse and filter articles)               | L         |
| E4   | Frontend    | Article reader + Search page                          | M         |
| F1   | Tests       | Unit + integration test suite                         | M         |
| F2   | Polish      | Single-command deployment                             | S         |

S = straightforward, one or two files. M = a module plus a test. L = the largest single step; E3 has the most UI state.

---

## Commit strategy

Commit after every step — even if it takes two sessions to complete one step, commit at the end of the second. Useful commit message template:

```
[A1] Project scaffold

- pyproject.toml with pressroom entry point
- src layout, ruff/mypy config
- .gitignore, .env.example
- pressroom --help works
```

The bracket prefix makes `git log --oneline` read as a build narrative rather than a list of "fix stuff" messages.
