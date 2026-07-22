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
from specula_api.pipeline.util import html_to_text, to_country_code, to_skill_tokens

# A real posting page yields well over this much readable text; anything less is a shell
# (JS-rendered board, interstitial, error page) with nothing worth extracting.
_MIN_EXTRACTABLE_CHARS = 200


async def extract_posting(session: AsyncSession, posting: Posting, deps: PipelineDeps) -> None:
    """Re-fetch the posting page (no stored HTML), LLM-extract structured fields onto the
    Posting. Salary only if explicitly stated (never invented). Low extraction_confidence
    still stored (surfaced-not-trusted, excluded from Insights) — don't drop the posting."""
    doc = await deps.fetcher.get(posting.source_url)
    # Guard on the REDUCED text, not the raw response. A JS-rendered board (Ashby returns a
    # ~7KB SPA shell with zero readable text) is a 200 with plenty of bytes but nothing to
    # extract — sending that to the model produced hallucinated postings titled after the
    # response schema itself. No extractable content is the same as no page: flag it, skip
    # the (wasted, billable) call.
    page_text = html_to_text(doc.text) if doc.status == 200 else ""
    if len(page_text.strip()) < _MIN_EXTRACTABLE_CHARS:
        posting.title = f"(no extractable content) {posting.source_url}"
        posting.extraction_confidence = 0
        await session.flush()
        return

    company_name = None
    if posting.company_id is not None:
        company = await session.get(Company, posting.company_id)
        company_name = company.name if company else None

    result = await deps.openai.extract_posting(page_text=page_text, company_name=company_name)

    posting.title = result.title
    posting.role_family = result.role_family
    posting.city = result.city
    posting.country = to_country_code(result.country)
    posting.hq_country = to_country_code(result.hq_country)
    posting.work_mode = result.work_mode
    posting.seniority = result.seniority
    posting.education = result.education
    posting.required_skills = to_skill_tokens(result.required_skills)
    # NOT to_skill_tokens: `nice_to_have` is display-only (services/jobs.py renders it and
    # nothing else reads it — never embedded, scored, aggregated or deduped). The reason
    # required_skills drops prose is that a sentence can never match a candidate skill and
    # so only distorts the score; with nothing comparing this field, dropping would lose
    # real information — "Familiarity with ML tooling such as MLflow, ZenML, or Metaflow"
    # names three tools, and showing nothing is worse than showing that sentence.
    posting.nice_to_have = [cleaned for item in result.nice_to_have if (cleaned := item.strip())]
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
