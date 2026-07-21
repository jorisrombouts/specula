"""Enrich stage: best-effort fetch of the company's page, then LLM-enrich it."""

from specula_api.db.models import Company
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.openai_client import EnrichResult
from specula_api.pipeline.source import detect_ats
from specula_api.pipeline.util import html_to_text


async def enrich_company(company: Company, deps: PipelineDeps) -> EnrichResult:
    """Best-effort: fetch the company's careers/home page (tolerate 404 — RecordedFetcher/miss
    yields status 404), then LLM-enrich. Returns values to APPLY to the Company (caller applies
    them). Logo stays a favicon URL (never object storage)."""
    url = company.careers_url or f"https://{company.domain}"
    doc = await deps.fetcher.get(url)
    page_text = html_to_text(doc.text) if doc.status == 200 else None

    llm = await deps.openai.enrich_company(
        name=company.name, domain=company.domain, page_text=page_text
    )

    ats = detect_ats(
        domain=company.domain,
        careers_url=llm.careers_url or company.careers_url,
        ats_hint=company.ats or llm.ats,
    )

    return EnrichResult(
        hq_country=llm.hq_country or company.hq_country,
        hq_confidence=llm.hq_confidence,
        comp_estimate=llm.comp_estimate,
        careers_url=llm.careers_url or company.careers_url,
        ats=ats,
    )
