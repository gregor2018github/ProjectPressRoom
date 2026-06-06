-- Migration 0003: add scraped content columns for full-article download.
--
-- Three columns are added to articles:
--   scraped_body_html  — sanitised HTML extracted from the article's URL
--   scraped_body_text  — plain-text version of the scraped body
--   scraped_at         — ISO 8601 UTC timestamp of when the scrape ran

ALTER TABLE articles ADD COLUMN scraped_body_html TEXT;
ALTER TABLE articles ADD COLUMN scraped_body_text TEXT;
ALTER TABLE articles ADD COLUMN scraped_at        TEXT;
