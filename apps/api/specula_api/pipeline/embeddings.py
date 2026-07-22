"""Embed stage: title/skills embeddings for an extracted posting."""

from specula_api.db.models import Posting
from specula_api.observability import get_logger
from specula_api.pipeline.deps import PipelineDeps

_log = get_logger("pipeline.embed")


async def embed_posting(posting: Posting, deps: PipelineDeps) -> None:
    """Embed title → title_vec and the required-skills text → skills_vec
    (text-embedding-3-small = 1536). No-op the skills_vec if no skills."""
    _log.info("pipeline.stage", extra={"stage": "embed", "posting_id": str(posting.id)})
    if posting.title:
        [title_vec] = await deps.openai.embed([posting.title])
        posting.title_vec = title_vec

    if posting.required_skills:
        [skills_vec] = await deps.openai.embed([" ".join(posting.required_skills)])
        posting.skills_vec = skills_vec
