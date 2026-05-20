# Features

A phased roadmap for `ProjectPressroom`. Each phase delivers something useful on its own; the project should be pleasant to live with at every step, not just at the end. Features marked **Planned** have no implementation yet — they describe intent and acceptance criteria so future-you (or a coding agent) has something concrete to build against.

Legend: ✅ done · 🟡 in progress · ⏳ planned · 💭 idea, not committed

---

## Phase 1 — Collection (v0.1, MVP)

The smallest version that's still genuinely useful: feeds in, articles out, browse them in one place. No analytics, no summarisation, no scraping.

### 1.1 RSS / Atom fetching ⏳

Pull articles from a configurable list of RSS / Atom feeds.

**Acceptance:**

- Sources are defined in `config/sources.toml` and synced into the `sources` table via `pressroom sources sync`.
- `pressroom fetch` (manual) and `pressroom daemon` (scheduled) both work and produce identical results given the same feed state.
- Conditional GET (ETag / Last-Modified) is honoured; a feed that hasn't changed since the last fetch produces a `not_modified` run with zero database writes.
- Per-source minimum poll interval is enforced (default 30 min, configurable down to 5 min).

**Dependencies:** `feedparser`, `httpx`, `tenacity`, `APScheduler`.

### 1.2 Normalisation with header / summary / body split ⏳

Every article stores `title`, `summary`, `body_html`, and `body_text` in distinct columns. This is the foundation for later analytics — keyword work over titles behaves very differently from keyword work over bodies, and we want to be able to compare.

**Acceptance:**

- Feeds that ship full content (e.g. gamestar) populate `body_html` and `body_text`.
- Feeds that only ship summaries (common for paywalled-but-public-RSS outlets) populate `summary` and leave the body columns NULL.
- HTML is sanitised via an allowlist before storage; the raw original is kept in `body_html_raw` for debugging.
- A unit test covers each of these branches with real fixture data.

**Dependencies:** an HTML sanitiser (likely `bleach` or `nh3`).

### 1.3 Deduplication ⏳

Re-fetching a feed must never produce duplicate rows.

**Acceptance:**

- Unique constraint on `(source_id, external_id)` enforces dedup at the DB layer.
- `external_id` derivation order: feed `<guid>` / `<id>` → canonical URL → SHA-256 of `(url + title)`.
- A second unique constraint on the cross-source `content_hash` catches wire-syndicated stories duplicated across outlets; the duplicate is logged but does not error the run.

### 1.4 SQLite storage with FTS5 ⏳

Single-file local database, plain SQL behind a thin repository. Full-text-search index lives alongside the main table from day one — adding it later means rebuilding it later.

**Acceptance:**

- Schema is created via `pressroom db init`.
- Migrations live as numbered SQL files in `db/migrations/`. The init command is equivalent to running all migrations in order.
- FTS5 triggers keep the search index in sync on every insert / update / delete.

### 1.5 Fetch-run logging ⏳

Every fetch attempt — successful, unmodified, or failed — writes a row to `fetch_runs` with timing, counts, and any error message.

**Acceptance:**

- A run is recorded even if the fetch crashes mid-way.
- The UI's "Sources" page shows "last run: X ago, status: Y, new: N" per source, sourced from this table.

### 1.6 Web API ⏳

Minimal FastAPI surface, just enough to drive the v0.1 UI.

**Endpoints:** see [`ARCHITECTURE.md` §3.5](./ARCHITECTURE.md#35-api-pressroomapi).

**Acceptance:**

- All routes are Pydantic-validated in and out.
- An integration test using `TestClient` covers each route's happy path and one representative error.
- CORS is closed by default; the dev origin (`http://localhost:5173`) is allow-listed only when the `PRESSROOM_DEV` env var is truthy.

### 1.7 Browse and read UI ⏳

React frontend with three core pages: **Inbox**, **Article**, **Sources**.

**Acceptance:**

- The Inbox lists the most recent articles across all sources, paginated, filterable by source / language / date range.
- Selecting an article navigates to a clean reader view; sanitised body HTML renders inside a sandboxed component.
- The Sources page lets the user enable / disable each source, edit fetch intervals, and trigger a manual fetch with one click.
- Mark-as-read happens implicitly on article view; explicit star / archive lives in the article view as well.

### 1.8 CLI ⏳

Single `pressroom` entry point with subcommands:

```
pressroom db init
pressroom sources sync [--prune]
pressroom fetch [--source NAME | --all]
pressroom daemon
pressroom serve [--host 127.0.0.1] [--port 8000]
```

**Acceptance:**

- Every subcommand has a docstring rendered in `--help`.
- Errors print a one-line summary at log level WARNING and exit non-zero.

### 1.9 Configuration and packaging ⏳

A clean, modern Python project layout that doesn't need explaining a year from now.

**Acceptance:**

- `pyproject.toml` (PEP 621), `src/` layout, `[project.optional-dependencies].dev` for tooling.
- `pydantic-settings` loads `.env` and `PRESSROOM_*` env vars into a single `Settings` object.
- `pip install -e ".[dev]"` is the only setup step beyond creating a venv.

### 1.10 Baseline test suite ⏳

Small, focused, useful. The point is to learn what "enough" feels like without drowning in coverage targets.

**Acceptance:**

- Unit tests for `normalize.py`, `repository.py`, and the dedup logic.
- One integration test that runs a fetch against a fixture feed served via `httpx.MockTransport` and asserts the resulting DB state.
- API tests for each v0.1 endpoint.
- `pytest` runs in under 10 seconds.

(Greg, this is your gentle on-ramp into pytest. The Arrange-Act-Assert pattern is enough structure for everything here.)

---

## Phase 2 — Search and exploration (v0.2)

Once a few weeks of data have accumulated, "search the corpus" becomes the most useful operation.

### 2.1 Full-text search ⏳

FTS5 is already in the schema; the API and UI need to actually use it.

**Acceptance:**

- `/api/articles/search?q=...` supports SQLite FTS5 query syntax (phrase queries, prefix matches with `*`, `OR`).
- Results include snippet highlighting (FTS5's `snippet()` function).
- The UI exposes a search bar visible from every page; results page shows snippets and lets the user click through.

### 2.2 Faceted filters ⏳

On top of full-text search and on the Inbox list:

- By source (multi-select)
- By language
- By category
- By date range
- By starred / unread / archived state

**Acceptance:**

- Filters compose freely with text search.
- The UI URL encodes the active filter state so a search can be linked / bookmarked.

### 2.3 Language detection ⏳

Where the source doesn't declare a language, detect it at normalisation time.

**Acceptance:**

- `langdetect` is used during normalisation; the detected language is written to `articles.language`.
- Confidence threshold: only write the result if the top guess is well above the runner-up; otherwise leave NULL.
- A migration backfills existing rows.

### 2.4 Source health view ⏳

A small dashboard page summarising the last 7 days of fetch activity: success rate per source, articles per source per day, sources that haven't yielded a single article in a week (likely a feed-URL change).

**Acceptance:**

- One Recharts bar chart, one table. No deeper analytics yet.

---

## Phase 3 — Analytics (v0.3)

Now the data has shape. This phase extracts patterns without LLMs — the cheap, deterministic, explainable layer that should exist regardless of how good a summary model gets.

### 3.1 Keyword extraction ⏳

Per-article keyword scoring using a classical method (likely YAKE or RAKE — single-package, no model download, multilingual). Results land in the `tags` table with `source='keyword'`.

**Acceptance:**

- A scheduled job runs keyword extraction over articles missing a `keyword` tag.
- Keywords are stored with a salience score; the top *n* per article are exposed via the API.
- Works on all three of NL / EN / DE.

### 3.2 Keyword heatmap and trends ⏳

Aggregate keyword frequency across a configurable time window. The UI renders a heatmap (keywords × weeks) and a trends view (per-keyword line chart).

**Acceptance:**

- The heatmap is interactive: click a cell, jump to the articles that contributed.
- Both views are powered by a single `/api/analytics/keywords` endpoint with query parameters for the window, granularity (day / week / month), and any source / language filter.

### 3.3 Sentiment scoring ⏳

A per-article sentiment score in `tags` with `source='sentiment'`. Method to be chosen at implementation time — probably VADER for English and a separate multilingual model (e.g. a small Hugging Face transformer used via the `transformers` pipeline) for NL / DE. If the Hugging Face dependency feels too heavy, we'll fall back to a rule-based approach and accept the loss of nuance.

**Acceptance:**

- Each article gets a numeric score in [-1, +1] plus a categorical label (`negative` / `neutral` / `positive`).
- The UI shows the distribution over time and lets the user filter to "only negative recent news" or the inverse.

### 3.4 Header-vs-body comparison ⏳

A small analytical view that asks: how strongly does a title's sentiment / keyword set diverge from its body's? Sensationalist titles are exactly the kind of thing the curation goal is trying to dampen.

**Acceptance:**

- Per-article delta: `sentiment(title) - sentiment(body_text)`, similarly for keyword sets via Jaccard distance.
- A dashboard view ranks articles by absolute divergence; this is a useful "is this source baiting me" signal.

### 3.5 Read-state analytics ⏳

What did you actually read this week vs. what was published? A small loop that helps you tune which sources to keep and which to drop.

**Acceptance:**

- Per source: articles published, articles read, articles starred, read-through rate.
- Surfaced on the Source health view from 2.4.

---

## Phase 4 — Summarisation and weekly newsletter (v0.4)

The original motivation. By this phase the database is rich enough that an LLM can do useful summarisation work over a real, filtered corpus rather than over the open web.

### 4.1 LLM client abstraction ⏳

A small `Summariser` interface with one concrete implementation (whichever provider you choose). The interface accepts a list of `Article`s and a prompt template, and returns text plus token-usage metadata.

**Acceptance:**

- The API key loads from `.env` only.
- Every call is recorded in an `llm_calls` table with model, input / output token counts, and latency. This is what stops the newsletter quietly costing more than expected.
- A dry-run mode logs the prompt without sending it, for prompt iteration.

### 4.2 Per-article summaries ⏳

For the subset of articles the user starred or that pass a configurable salience filter (e.g. "tech category, in the top 20% of keyword salience this week"), produce a 2-3-sentence summary in the article's own language and store it in `summaries`.

**Acceptance:**

- Idempotent: re-summarising an article that already has a summary is a no-op unless `--force`.
- The UI shows the summary alongside the article header in the Inbox so triage becomes faster.

### 4.3 Weekly digest ⏳

A scheduled job runs once a week, picks the most interesting *n* articles from the prior seven days (using the analytics tags + read-state signals as inputs), generates a digest section per category, and writes the result to a `digests` table plus a rendered Markdown / HTML file on disk.

**Acceptance:**

- The selection logic is deterministic given the same inputs — testable.
- The digest mentions every article it cites with a link back to the local archive.
- A preview is viewable in the UI before the file is written; the UI shows the last *n* digests for re-reading.

### 4.4 Newsletter delivery (optional) 💭

Stretch: actually email the digest. SMTP via `smtplib` is the obvious path; configuration goes through `.env`. Skip this entirely if "read the digest in the UI" turns out to be enough.

---

## Phase 5 — Scraping fallback (v0.5)

Reserved for sites that genuinely don't expose a usable feed. None of the current target list needs this, so the phase may never ship — but the architecture is ready for it.

### 5.1 HTML scraper adapter ⏳

Implements the `Fetcher` protocol from §3.1. Uses `httpx` to fetch a listing page, `trafilatura` to extract article content per link.

**Acceptance:**

- `feed_type='scraped'` on a source routes to the scraper adapter.
- The same dedup, normalisation, and run-logging machinery applies — only the input side changes.
- The scraper respects `robots.txt` via `urllib.robotparser`. Sources whose robots.txt disallows the path are auto-disabled with an error message.

### 5.2 Selectors per source ⏳

Some sites need site-specific CSS / XPath selectors. A small `scrapers/<source-slug>.py` file per such source, each exporting a function that takes raw HTML and returns a list of `FetchedEntry`. Keeps the per-site fragility contained.

---

## Cross-cutting / housekeeping

These don't fit neatly into a phase but should happen alongside.

### CI ⏳

GitHub Actions workflow: lint, type-check, test on push and PR. Probably worth setting up around the v0.2 / v0.3 boundary, once the test suite is meaningful enough to fail on real regressions.

### Database backups ⏳

A `pressroom db backup --to PATH` command that runs `sqlite3 .backup` (the safe online-backup API, not a file copy). Recommend running it as a weekly Task Scheduler entry.

### Migration tooling 💭

For v0.1, hand-numbered SQL files plus a tiny migration runner in `db/migrate.py` are enough. If the schema starts churning meaningfully, consider switching to `yoyo-migrations` (small, file-based, no ORM coupling).

### Frontend component tests 💭

`vitest` over a handful of the more logic-heavy components once the UI stops being a moving target.

### TypeScript types from OpenAPI 💭

`openapi-typescript` against the FastAPI schema to auto-generate the frontend's API types. Drops a class of "frontend and backend drift apart" bugs and removes the manual interface declarations.

### Docker image 💭

Optional; useful if you ever want to run this on a small NAS. Backend in one container, frontend served as static files from the backend, single volume mount for the SQLite file.

---

## Explicit non-goals

Worth being clear about what this project is **not** trying to be:

- **A multi-user service.** One person, one machine.
- **A mobile app.** The web UI should be responsive enough to read on a phone in a pinch, but no native client.
- **A real-time feed.** Polling on a multi-minute cadence is the right granularity for news. Webhooks / push are out of scope.
- **A general-purpose web crawler.** The scraping phase, if it lands, targets a small hand-picked list of sources with bespoke selectors. No frontier queues, no domain expansion, no JavaScript rendering.
- **A replacement for a real newsletter platform.** Delivery, subscriptions, unsubscribe handling, GDPR-compliant logging — all out of scope.

Keeping these off the table is what keeps the project small enough to actually finish.
