-- Migration 0004: include scraped_body_text in the FTS5 index.
--
-- Rebuilds the articles_fts virtual table with a fourth column so that
-- full-article text fetched via the scraper is also searchable.

DROP TRIGGER IF EXISTS articles_au;
DROP TRIGGER IF EXISTS articles_ad;
DROP TRIGGER IF EXISTS articles_ai;

DROP TABLE IF EXISTS articles_fts;

CREATE VIRTUAL TABLE articles_fts USING fts5 (
    title, summary, body_text, scraped_body_text,
    content='articles',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 0'
);

-- Repopulate from all existing articles.
INSERT INTO articles_fts(articles_fts) VALUES('rebuild');

CREATE TRIGGER articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts (rowid, title, summary, body_text, scraped_body_text)
    VALUES (new.id, new.title, new.summary, new.body_text, new.scraped_body_text);
END;
CREATE TRIGGER articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts (articles_fts, rowid, title, summary, body_text, scraped_body_text)
    VALUES ('delete', old.id, old.title, old.summary, old.body_text, old.scraped_body_text);
END;
CREATE TRIGGER articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts (articles_fts, rowid, title, summary, body_text, scraped_body_text)
    VALUES ('delete', old.id, old.title, old.summary, old.body_text, old.scraped_body_text);
    INSERT INTO articles_fts (rowid, title, summary, body_text, scraped_body_text)
    VALUES (new.id, new.title, new.summary, new.body_text, new.scraped_body_text);
END;
