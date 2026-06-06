"""Fetch a URL and extract the main article body using trafilatura."""

import nh3
import httpx
import trafilatura

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
}

_ALLOWED_TAGS: set[str] = {
    "p", "br",
    "a",
    "ul", "ol", "li",
    "strong", "em", "b", "i",
    "blockquote",
    "h1", "h2", "h3", "h4",
    "pre", "code",
    "img", "figure", "figcaption",
    "table", "thead", "tbody", "tr", "th", "td",
}

_ALLOWED_ATTRS: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def scrape_article(
    url: str, timeout: float = 20.0
) -> tuple[str | None, str | None, str | None]:
    """Fetch *url* and extract the main article text.

    Returns ``(scraped_body_html, scraped_body_text, error_message)``.
    On success ``error_message`` is ``None``; on failure both body fields are ``None``.
    """
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPStatusError as exc:
        return None, None, f"HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        return None, None, str(exc)

    # Plain-text extraction (most reliable baseline)
    scraped_text: str | None = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=True,
    )
    if not scraped_text:
        return None, None, "Could not extract article content from the page"

    # HTML extraction — may return None for some sites; fall back to wrapped text
    scraped_html: str | None = None
    try:
        raw_html: str | None = trafilatura.extract(
            html,
            output_format="html",
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
            include_links=True,
        )
        if raw_html:
            cleaned = nh3.clean(raw_html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS).strip()
            scraped_html = cleaned or None
    except Exception:  # trafilatura may raise on malformed input
        pass

    if scraped_html is None:
        scraped_html = "\n".join(
            f"<p>{para.strip()}</p>"
            for para in scraped_text.split("\n\n")
            if para.strip()
        )

    return scraped_html, scraped_text, None
