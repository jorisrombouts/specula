"""Extract stage: re-fetch each posting's page (no stored HTML) and LLM-extract structured
fields onto the Posting.

We do not store raw HTML, so extraction re-fetches `posting.source_url` via `deps.fetcher`
rather than reading a saved snapshot. A page that can't be fetched (non-200, or empty text)
gets `extraction_confidence=0` and a placeholder title derived from its `source_url` — the
confidence excludes it from Insights (`_is_trusted` requires >= low_confidence_threshold),
and the placeholder title stops it matching the `title IS NULL` "needs extraction" filter,
so it won't be re-selected forever. Salary is only ever set when the LLM result states it
(never invented) — `salary_text=None` in the result stays `None` on the posting. A low
`extraction_confidence` result is still stored in full (surfaced, not trusted) — the
posting is never dropped.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import Company, Posting
from specula_api.pipeline.deps import PipelineDeps
from specula_api.pipeline.util import html_to_text


async def extract_posting(session: AsyncSession, posting: Posting, deps: PipelineDeps) -> None:
    """Re-fetch the posting page (no stored HTML), LLM-extract structured fields onto the
    Posting. Salary only if explicitly stated (never invented). Low extraction_confidence
    still stored (surfaced-not-trusted, excluded from Insights) — don't drop the posting."""
    doc = await deps.fetcher.get(posting.source_url)
    if doc.status != 200 or not doc.text.strip():
        posting.title = f"(unfetched) {posting.source_url}"
        posting.extraction_confidence = 0
        await session.flush()
        return

    company_name = None
    if posting.company_id is not None:
        company = await session.get(Company, posting.company_id)
        company_name = company.name if company else None

    result = await deps.openai.extract_posting(
        page_text=html_to_text(doc.text), company_name=company_name
    )

    posting.title = result.title
    posting.role_family = result.role_family
    posting.city = result.city
    posting.country = result.country
    posting.hq_country = result.hq_country
    posting.work_mode = result.work_mode
    posting.seniority = result.seniority
    posting.education = result.education
    posting.required_skills = result.required_skills
    posting.nice_to_have = result.nice_to_have
    posting.visa = result.visa
    posting.languages = result.languages
    posting.contract = result.contract
    posting.geo = result.geo
    posting.salary_text = result.salary_text
    posting.deadline_at = result.deadline_at
    posting.posted_at = result.posted_at
    posting.responsibilities = result.responsibilities
    posting.summary = result.summary
    posting.extraction_confidence = result.extraction_confidence

    await session.flush()
