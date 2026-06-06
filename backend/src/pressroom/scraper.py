"""Fetch a URL and extract the main article body using trafilatura."""

import lxml.etree
import lxml.html
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

# Stable CSS class names that reliably wrap article body text across CMSes.
# Checked first; if any match, only that subtree is fed to trafilatura.
_CONTENT_CLASSES = [
    "StoryContent",       # Heise bestenlisten / review pages
    "article-body",
    "article__body",
    "article-content",
    "entry-content",
    "post-content",
    "story-body",
    "js-article-content",
]

# Tag names and class-name substrings whose elements are pure navigation noise.
_NOISE_TAGS = frozenset({"nav", "aside", "header", "footer"})
_NOISE_CLASSES = frozenset({
    "sidebar", "navigation", "related", "recommended",
    "trending", "popular", "advertisement", "banner",
    "linkOverlay", "linkWrapper",
})


def _preprocess_html(html: str) -> str:
    """Isolate article content before trafilatura runs.

    Strategy:
    1. If a known stable content-container class is present, return only
       that subtree wrapped in a minimal HTML document.
    2. Otherwise strip nav/aside/sidebar noise from the full document.

    Falls back to the original HTML on any lxml error.
    """
    try:
        tree = lxml.html.document_fromstring(html)

        # --- strategy 1: extract known content container ---
        for cls in _CONTENT_CLASSES:
            matches = tree.find_class(cls)
            if matches:
                fragment = lxml.etree.tostring(matches[0], encoding="unicode", method="html")
                return f"<html><body>{fragment}</body></html>"

        # --- strategy 2: strip known noise elements ---
        to_remove: list[lxml.html.HtmlElement] = []
        for el in tree.iter():
            if not isinstance(el.tag, str):
                continue
            if el.tag in _NOISE_TAGS:
                to_remove.append(el)
                continue
            classes = set((el.get("class") or "").split())
            if classes & _NOISE_CLASSES:
                to_remove.append(el)

        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                try:
                    parent.remove(el)
                except ValueError:
                    pass

        return lxml.etree.tostring(tree, encoding="unicode", method="html")
    except Exception:  # lxml may raise on severely malformed HTML
        return html


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

    clean_html = _preprocess_html(html)

    # Plain-text extraction (most reliable baseline)
    scraped_text: str | None = trafilatura.extract(
        clean_html,
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
            clean_html,
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
