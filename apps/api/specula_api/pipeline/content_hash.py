"""URL normalization + stable content hashing for crawled postings."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Tracking params to strip so the same posting doesn't hash differently across campaigns.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {"gh_src", "gh_jid", "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "_gl", "_ga"}


def normalize_url(url: str) -> str:
    """Lowercase host, drop fragment, strip tracking params, sort remaining query. Deterministic."""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    host = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_PARAMS
    )
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def content_hash(*, source_url: str, external_id: str | None, title_hint: str | None) -> str:
    """Sha256 hex over a stable key: prefer external_id (scoped to host), else url + title."""
    host = urlsplit(source_url).netloc.lower()
    if external_id:
        key = f"host:{host}|external_id:{external_id}"
    else:
        key = f"url:{normalize_url(source_url)}|title:{title_hint or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
