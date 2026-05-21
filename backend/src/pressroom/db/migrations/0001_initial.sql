-- Migration 0001: initial schema.

CREATE TABLE sources (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT    NOT NULL UNIQUE,
    feed_url               TEXT    NOT NULL UNIQUE,
    feed_type              TEXT    NOT NULL DEFAULT 'rss'
                                     CHECK (feed_type IN ('rss', 'atom', 'scraped')),
    homepage_url           TEXT,
    category               TEXT,
    language               TEXT,
    is_active              INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes INTEGER NOT NULL DEFAULT 60
                                     CHECK (fetch_interval_minutes >= 5),
    last_etag              TEXT,
    last_modified          TEXT,
    last_fetched_at        TEXT,
    last_status            TEXT,
    last_error             TEXT,
    created_at             TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id     TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    summary         TEXT,
    body_html       TEXT,
    body_text       TEXT,
    body_html_raw   TEXT,
    author          TEXT,
    language        TEXT,
    published_at    TEXT,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    content_hash    TEXT    NOT NULL,
    is_read         INTEGER NOT NULL DEFAULT 0,
    is_starred      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_id, external_id)
);

CREATE INDEX idx_articles_source_published    ON articles (source_id, published_at DESC);
CREATE INDEX idx_articles_published           ON articles (published_at DESC);
CREATE INDEX idx_articles_language            ON articles (language);
CREATE UNIQUE INDEX idx_articles_content_hash ON articles (content_hash);

CREATE VIRTUAL TABLE articles_fts USING fts5 (
    title, summary, body_text,
    content='articles',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

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

CREATE TABLE tags (
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag         TEXT    NOT NULL,
    score       REAL,
    source      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (article_id, tag, source)
);
