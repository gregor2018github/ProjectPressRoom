-- Migration 0002: rebuild FTS index with remove_diacritics 0.
--
-- The previous tokenizer (remove_diacritics 2) stripped all diacritics from
-- both the document index and the query, so searching "ü" was equivalent to
-- searching "u" and matched every word containing that base letter.
-- With remove_diacritics 0, accented characters are preserved as distinct
-- tokens: "ü" only matches "ü"-containing words, "u" only matches "u" words.

DROP TRIGGER IF EXISTS articles_au;
DROP TRIGGER IF EXISTS articles_ad;
DROP TRIGGER IF EXISTS articles_ai;

DROP TABLE IF EXISTS articles_fts;

CREATE VIRTUAL TABLE articles_fts USING fts5 (
    title, summary, body_text,
    content='articles',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 0'
);

-- Repopulate from all existing articles.
INSERT INTO articles_fts(articles_fts) VALUES('rebuild');

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
