"""Small helpers shared across pipeline stages."""

import pycountry
from selectolax.parser import HTMLParser

# Raw fetched job/careers pages can be 100k+ tokens of HTML — far over the model
# context window. Strip to visible text and cap to a safe budget before any LLM call.
_MAX_PAGE_CHARS = 24000

# Words the LLM sometimes puts in a country field that are regions/remote markers, not
# countries. Must be rejected BEFORE consulting pycountry — its fuzzy search would
# otherwise happily map e.g. "EU" onto some unrelated country (see `to_country_code`).
_NON_COUNTRY_WORDS = {
    "global",
    "remote",
    "worldwide",
    "emea",
    "eu",
    "europe",
    "anywhere",
    "latam",
    "apac",
}

# Common variants that pycountry's exact lookup() doesn't resolve and whose fuzzy search
# is ambiguous (e.g. "UK" fuzzy-matches 20+ countries sharing a substring) rather than
# genuinely unresolvable — handled explicitly instead of trusting the fuzzy guard.
_COUNTRY_ALIASES = {
    "uk": "GB",
}


def to_country_code(value: str | None) -> str | None:
    """Normalize a country as extracted/enriched by the LLM to an ISO 3166-1 alpha-2 code.

    None/blank -> None. An existing valid alpha-2 code passes through (uppercased). Full
    names and common variants ("Spain", "United Kingdom", "UK", "USA") resolve via
    `pycountry`'s exact lookup, a small alias map for cases lookup/fuzzy don't cover, and
    finally a guarded fuzzy search (accepted only when it returns a single, unambiguous
    match — fuzzy search can otherwise match loosely on unrelated countries). Non-country
    words (region/remote markers like "Global", "EU") and anything else unresolved become
    None — never a bogus code.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if lowered in _NON_COUNTRY_WORDS:
        return None
    if len(cleaned) == 2 and cleaned.isalpha():
        country = pycountry.countries.get(alpha_2=cleaned.upper())
        if country is not None:
            return str(country.alpha_2)
    if lowered in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[lowered]
    try:
        return str(pycountry.countries.lookup(cleaned).alpha_2)
    except LookupError:
        pass
    try:
        matches = pycountry.countries.search_fuzzy(cleaned)
    except LookupError:
        return None
    if len(matches) == 1:
        return str(matches[0].alpha_2)
    return None


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
