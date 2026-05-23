-- Current schema snapshot for reference.
-- Do not run this file directly — apply migrations via `pressroom db init`.

-- Sources we pull from.
CREATE TABLE sources (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT    NOT NULL UNIQUE,
    feed_url               TEXT    NOT NULL UNIQUE,
    feed_type              TEXT    NOT NULL DEFAULT 'rss'
                                     CHECK (feed_type IN ('rss', 'atom', 'scraped')),
    homepage_url           TEXT,
    category               TEXT,                           -- 'tech', 'gaming', 'general', ...
    language               TEXT,                           -- BCP-47, e.g. 'en', 'de', 'nl'
    is_active              INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60
                                     CHECK (fetch_interval_minutes >= 5),
    last_etag              TEXT,
    last_modified          TEXT,
    last_fetched_at        TEXT,                           -- ISO 8601 UTC
    last_status            TEXT,                           -- 'ok' | 'error' | 'not_modified'
    last_error             TEXT,
    created_at             TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Articles. The header/summary/body split is intentional and load-bearing.
CREATE TABLE articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id     TEXT    NOT NULL,            -- feed guid / atom id / url-hash
    url             TEXT    NOT NULL,            -- canonical link
    title           TEXT    NOT NULL,            -- header
    summary         TEXT,                        -- feed-provided short description
    body_html       TEXT,                        -- cleaned HTML body
    body_text       TEXT,                        -- plain-text body (derived)
    body_html_raw   TEXT,                        -- pre-clean body, kept for debugging
    author          TEXT,
    language        TEXT,                        -- BCP-47, may be NULL pre-phase-2
    published_at    TEXT,                        -- ISO 8601 UTC, from feed
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    content_hash    TEXT    NOT NULL,            -- sha256(url || '\n' || title)
    is_read         INTEGER NOT NULL DEFAULT 0,
    is_starred      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_id, external_id)
);

CREATE INDEX idx_articles_source_published    ON articles (source_id, published_at DESC);
CREATE INDEX idx_articles_published           ON articles (published_at DESC);
CREATE INDEX idx_articles_language            ON articles (language);
CREATE UNIQUE INDEX idx_articles_content_hash ON articles (content_hash);

-- Full-text search index. SQLite FTS5 is built into the stdlib.
CREATE VIRTUAL TABLE articles_fts USING fts5 (
    title, summary, body_text,
    content='articles',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 0'
);

-- Keep FTS in sync via triggers.
CREATE TRIGGER articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts (rowid, title, summary, body_text)
    VALUES (new.id, new.title, new.summary, new.body_text);
END;
CREATE TRIGGER articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts (articles_fts, rowid, title, summary, body_text)
    VALUES ('delete', old.id, old.title, old.summary, old.body_text);
END;
CREATE TRIGGER articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts (articles_fts, rowid, title, summary, body_text)
    VALUES ('delete', old.id, old.title, old.summary, old.body_text);
    INSERT INTO articles_fts (rowid, title, summary, body_text)
    VALUES (new.id, new.title, new.summary, new.body_text);
END;

-- One row per scheduled or manual fetch attempt.
CREATE TABLE fetch_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    triggered_by        TEXT    NOT NULL CHECK (triggered_by IN ('scheduler', 'manual', 'cli')),
    started_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at         TEXT,
    status              TEXT    NOT NULL DEFAULT 'running'
                                  CHECK (status IN ('running', 'ok', 'error', 'not_modified')),
    http_status         INTEGER,
    articles_seen       INTEGER NOT NULL DEFAULT 0,
    articles_new        INTEGER NOT NULL DEFAULT 0,
    articles_duplicate  INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT
);

CREATE INDEX idx_fetch_runs_source_started ON fetch_runs (source_id, started_at DESC);

-- Reserved for phase 3+; no triggers, no constraints beyond the PK yet.
CREATE TABLE tags (
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag         TEXT    NOT NULL,
    score       REAL,                         -- e.g. keyword salience, sentiment magnitude
    source      TEXT    NOT NULL,             -- 'keyword' | 'sentiment' | 'llm' | ...
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (article_id, tag, source)
);
