"""OpenAI client seam: result models, Protocol, live (Responses API) and recorded impls."""

import hashlib
import json
import random
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Protocol, TypeVar

from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseFunctionWebSearch, WebSearchToolParam
from openai.types.responses.response_function_web_search import ActionSearch
from pydantic import BaseModel, TypeAdapter

from specula_api.config import Settings

_EMBED_DIM = 1536

# ---------------------------------------------------------------------------
# Result models (internal — snake_case, not exposed over the API directly)
# ---------------------------------------------------------------------------


class Source(BaseModel):
    url: str
    title: str | None = None


class EnrichResult(BaseModel):
    hq_country: str | None = None
    hq_confidence: int | None = None
    comp_estimate: str | None = None
    careers_url: str | None = None
    ats: str | None = None


class ExtractionResult(BaseModel):
    """Mirrors the postings insight fields. `still_open` is NOT here — fetch owns it."""

    title: str
    role_family: str | None = None
    city: str | None = None
    country: str | None = None
    hq_country: str | None = None
    work_mode: str | None = None
    seniority: str | None = None
    education: str | None = None
    required_skills: list[str] = []
    nice_to_have: list[str] = []
    visa: str | None = None
    languages: list[str] = []
    contract: str | None = None
    geo: str | None = None
    salary_text: str | None = None
    deadline_at: date | None = None
    posted_at: date | None = None
    responsibilities: list[str] = []
    summary: str = ""
    extraction_confidence: int  # 0-100


class OpenAIClient(Protocol):
    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]: ...

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult: ...

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str: ...

    async def aclose(self) -> None: ...


class FixtureMissing(Exception):
    """Raised by RecordedOpenAIClient when a call has no matching fixture on disk."""


# ---------------------------------------------------------------------------
# Live implementation — exercised only by the live smoke test, never in CI.
# ---------------------------------------------------------------------------

_ResultT = TypeVar("_ResultT", bound=BaseModel)


class OpenAIResponsesClient:
    """Live OpenAI implementation backed by `AsyncOpenAI`."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        sources: list[Source] = []
        seen: set[str] = set()
        for query in queries:
            for source in await self._search(query, allowed_domains):
                if source.url not in seen:
                    seen.add(source.url)
                    sources.append(source)
        return sources

    async def _search(self, query: str, allowed_domains: Sequence[str] | None) -> list[Source]:
        # verified against installed SDK (openai 2.45,
        # openai/types/responses/response_includable.py): `web_search_call` output items only
        # populate `action.sources` when the response explicitly asks for it via
        # `include=["web_search_call.action.sources"]` — without this, `action.sources` is
        # always None and `_sources_from_response` silently returns [].
        tool: WebSearchToolParam = {"type": "web_search"}
        if allowed_domains:
            tool["filters"] = {"allowed_domains": list(allowed_domains)}
        response = await self._client.responses.create(
            model=self._settings.openai_search_model,
            input=query,
            tools=[tool],
            include=["web_search_call.action.sources"],
        )
        return _sources_from_response(response)

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        # verified by live smoke
        user = f"Company: {name}\nDomain: {domain or 'unknown'}\n\n{page_text or ''}"
        return await self._structured(
            model=self._settings.openai_extract_model,
            result_type=EnrichResult,
            system=(
                "Enrich the company record below with HQ country, comp estimate, careers URL "
                "and ATS if determinable from the page text. Leave fields null when not "
                "evidenced — never guess."
            ),
            user=user,
        )

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        # verified by live smoke
        user = page_text if company_name is None else f"Company: {company_name}\n\n{page_text}"
        return await self._structured(
            model=self._settings.openai_extract_model,
            result_type=ExtractionResult,
            system=(
                "Extract structured job posting fields from the page text below. Set "
                "extraction_confidence (0-100) to reflect how much of the schema was directly "
                "evidenced in the text rather than inferred."
            ),
            user=user,
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # verified by live smoke
        response = await self._client.embeddings.create(
            model=self._settings.openai_embed_model, input=list(texts)
        )
        return [list(item.embedding) for item in response.data]

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        # verified by live smoke
        user = (
            f"Factors: {json.dumps(factors, sort_keys=True)}\n"
            f"Skill overlap: {overlap[0]}/{overlap[1]}\n"
            f"Red flag: {red_flag or 'none'}"
        )
        response = await self._client.chat.completions.create(
            model=self._settings.openai_rationale_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a one-paragraph, salary-blind rationale for this match score "
                        "from the given factors."
                    ),
                },
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    async def aclose(self) -> None:
        await self._client.close()

    async def _structured(
        self, *, model: str, result_type: type[_ResultT], system: str, user: str
    ) -> _ResultT:
        # verified by live smoke
        completion = await self._client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=result_type,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError(f"OpenAI returned no structured output for {result_type.__name__}")
        return parsed


def _sources_from_response(response: Response) -> list[Source]:
    """Harvest URLs from `web_search_call` output items. # verified by live smoke"""
    sources: list[Source] = []
    for item in response.output:
        if not isinstance(item, ResponseFunctionWebSearch):
            continue
        action = item.action
        if not isinstance(action, ActionSearch) or not action.sources:
            continue
        sources.extend(Source(url=result.url) for result in action.sources)
    return sources


# ---------------------------------------------------------------------------
# Recorded implementation — fixture-backed, no network. Used in tests + recorded pipeline mode.
# ---------------------------------------------------------------------------


class RecordedOpenAIClient:
    """Reads recorded OpenAI results from `<fixtures_dir>/openai/<kind>/<key>.json`. No network.

    Keying mirrors `RecordedFetcher`'s `sha256(url)` scheme, except `enrich` (keyed by the
    literal domain/name, not a hash, so fixtures are easy to find and hand-edit) and `embed`
    (keyed per-string, with a deterministic pseudo-vector fallback instead of FixtureMissing —
    see `_pseudo_vector`).
    """

    def __init__(self, fixtures_dir: str | Path) -> None:
        self._dir = Path(fixtures_dir) / "openai"

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        key = _hash_key("\n".join(queries) + "|" + ",".join(sorted(allowed_domains or [])))
        data = self._load("discover", key)
        return TypeAdapter(list[Source]).validate_python(data)

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        key = _slug(domain or name)
        return EnrichResult.model_validate(self._load("enrich", key))

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        key = _hash_key(page_text)
        return ExtractionResult.model_validate(self._load("extract", key))

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            path = self._dir / "embed" / f"{_hash_key(text)}.json"
            if path.exists():
                vectors.append(TypeAdapter(list[float]).validate_json(path.read_text()))
            else:
                vectors.append(_pseudo_vector(text))
        return vectors

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        key = _hash_key(json.dumps(factors, sort_keys=True))
        data = self._load("rationale", key)
        assert isinstance(data, str), f"Rationale fixture for key {key!r} must be a JSON string"
        return data

    async def aclose(self) -> None:
        return None

    def _load(self, kind: str, key: str) -> object:
        path = self._dir / kind / f"{key}.json"
        if not path.exists():
            raise FixtureMissing(
                f"No recorded OpenAI '{kind}' fixture at {path}. Record one via the live smoke "
                "test (see apps/api/tests/fixtures/pipeline/openai/README.md)."
            )
        return json.loads(path.read_text())


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    """Filesystem-safe fixture key. Dots/hyphens (valid domain characters) pass through
    unchanged so a domain like "acme.com" keys straight to "acme.com.json"; any other
    separator (spaces, etc. — for the `name` fallback) collapses to a single hyphen."""
    return re.sub(r"[^a-z0-9.-]+", "-", value.strip().lower()).strip("-") or "unknown"


def _pseudo_vector(text: str) -> list[float]:
    """Deterministic placeholder embedding used when no fixture is recorded for `text`.

    This is NOT a real embedding — it carries no semantic meaning. It exists so pipeline
    stages that score/dedup via embeddings can run against RecordedOpenAIClient without a
    hand-authored fixture per skill/summary string; the only properties tests rely on are
    that it's deterministic (same text → same vector, across processes) and length 1536.
    Seeded from sha256(text) rather than Python's `hash()` so it doesn't depend on PYTHONHASHSEED.
    """
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(_EMBED_DIM)]


# ---------------------------------------------------------------------------
# Recording implementation — wraps a live client and mirrors each result to fixtures,
# keyed identically to RecordedOpenAIClient. Used by pipeline_mode="record" so a live run
# regenerates the committed fixtures for a later "recorded" run/CI to replay deterministically.
# ---------------------------------------------------------------------------


class RecordingOpenAIClient:
    """Wraps a live `OpenAIClient` and writes every result to
    `<fixtures_dir>/openai/<kind>/<key>.json`, using the exact key scheme `RecordedOpenAIClient`
    reads from (see its docstring). Delegates first, then records — a write failure never masks
    the underlying result."""

    def __init__(self, live: OpenAIClient, fixtures_dir: str | Path) -> None:
        self._live = live
        self._dir = Path(fixtures_dir) / "openai"

    async def discover_sources(
        self, queries: Sequence[str], *, allowed_domains: Sequence[str] | None = None
    ) -> list[Source]:
        sources = await self._live.discover_sources(queries, allowed_domains=allowed_domains)
        key = _hash_key("\n".join(queries) + "|" + ",".join(sorted(allowed_domains or [])))
        self._write("discover", key, [source.model_dump() for source in sources])
        return sources

    async def enrich_company(
        self, *, name: str, domain: str | None, page_text: str | None
    ) -> EnrichResult:
        result = await self._live.enrich_company(name=name, domain=domain, page_text=page_text)
        self._write("enrich", _slug(domain or name), result.model_dump())
        return result

    async def extract_posting(
        self, *, page_text: str, company_name: str | None = None
    ) -> ExtractionResult:
        result = await self._live.extract_posting(page_text=page_text, company_name=company_name)
        # mode="json" so date fields serialize to ISO strings RecordedOpenAIClient can re-parse.
        self._write("extract", _hash_key(page_text), result.model_dump(mode="json"))
        return result

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = await self._live.embed(texts)
        for text, vector in zip(texts, vectors, strict=True):
            self._write("embed", _hash_key(text), vector)
        return vectors

    async def rationale(
        self, *, factors: dict[str, int], overlap: tuple[int, int], red_flag: str | None
    ) -> str:
        result = await self._live.rationale(factors=factors, overlap=overlap, red_flag=red_flag)
        key = _hash_key(json.dumps(factors, sort_keys=True))
        self._write("rationale", key, result)
        return result

    async def aclose(self) -> None:
        await self._live.aclose()

    def _write(self, kind: str, key: str, data: object) -> None:
        path = self._dir / kind / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
