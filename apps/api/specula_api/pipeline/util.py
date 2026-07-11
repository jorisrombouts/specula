"""Small helpers shared across pipeline stages."""

from selectolax.parser import HTMLParser

# Raw fetched job/careers pages can be 100k+ tokens of HTML — far over the model
# context window. Strip to visible text and cap to a safe budget before any LLM call.
_MAX_PAGE_CHARS = 24000


def favicon_url(domain: str) -> str:
    return f"https://icons.duckduckgo.com/ip3/{domain}.ico"


def title_matches_roles(title: str | None, role_titles: list[str]) -> bool:
    """Cheap relevance gate on an ATS feed title before the expensive per-posting LLM
    extraction: keep a posting only if its title contains one of the user's target role
    titles (case-insensitive substring). Profile-driven — a big board (Nebius: 600+ jobs,
    mostly sales/ops) is narrowed to just the roles the user actually targets. No title
    (some generic-HTML adapters) or no profile → keep it (can't/shouldn't filter)."""
    if title is None or not role_titles:
        return True
    lowered = title.lower()
    return any(rt.strip().lower() in lowered for rt in role_titles if rt.strip())


def html_to_text(html: str, *, max_chars: int = _MAX_PAGE_CHARS) -> str:
    """Reduce an HTML page to collapsed visible text, truncated to `max_chars`.
    Drops script/style/noscript/svg noise so the LLM sees the readable content."""
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript, svg"):
        node.decompose()
    root = tree.body or tree.root
    text = root.text(separator=" ", strip=True) if root is not None else ""
    text = " ".join(text.split())
    return text[:max_chars]
