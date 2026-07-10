"""Idempotent demo seeder: `python -m specula_api.seed`.

Populates a single demo user with the full M1 frontend demo dataset (ported from
`apps/web/src/lib/seed/data.ts`) so the API-backed app renders equivalently to the
pre-M2 frontend-only prototype, before the M3/M4 discovery+scoring pipeline exists.
Safe to run repeatedly — it deletes the demo user's rows and reinserts.

RLS mechanics: the app connects as the non-superuser `specula_app` role, which OWNS
the schema. It owner-bypasses the (enabled-but-not-forced) `users` table, so the
demo user is found/created without a tenant context. The 10 per-user tables are
FORCE-RLS'd, so before touching any of them we set `app.user_id` to the demo user's
id — every seeded row's `user_id` must match it (the policy checks both USING and
WITH CHECK). `skills_taxonomy` is global (no RLS).
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from specula_api.db.models import (
    Approval,
    CandidateProfile,
    Company,
    Lens,
    Posting,
    PostingState,
    Run,
    Score,
    SkillsTaxonomy,
    Targeting,
    User,
    UserSettings,
)
from specula_api.db.session import async_session
from specula_api.pipeline.util import favicon_url

DEMO_GOOGLE_SUB = "demo-user"
DEMO_EMAIL = "demo@specula.app"
DEMO_NAME = "Joris Veldkamp"

# Per-user tables to clear on reseed, in FK-safe order (children before parents).
_TENANT_TABLES = [
    Score,
    PostingState,
    Posting,
    Company,
    Lens,
    Approval,
    Run,
    Targeting,
    CandidateProfile,
    UserSettings,
]


# Companies from data.ts's `companies` (mistral..wayve) plus three synthesized for
# postings whose company never got its own `companies` entry in the frontend seed
# (Parloa/Ada Health/Factorial — only referenced via their job's company/hq/hqConf
# fields). Their domain/ats are reasonable placeholders; hq_confidence is carried
# over from the job's `hqConf` field, the only real signal the frontend gave us.
_COMPANIES: dict[str, dict[str, Any]] = {
    "mistral": {
        "name": "Mistral AI",
        "domain": "mistral.ai",
        "ats": "greenhouse",
        "hq_country": "FR",
        "hq_confidence": 98,
        "comp_estimate": "€€€",
        "added_at": datetime(2026, 3, 1, tzinfo=UTC),
    },
    "aleph": {
        "name": "Aleph Alpha",
        "domain": "aleph-alpha.com",
        "ats": "greenhouse",
        "hq_country": "DE",
        "hq_confidence": 95,
        "comp_estimate": "€€€",
        "added_at": datetime(2026, 3, 1, tzinfo=UTC),
    },
    "helsing": {
        "name": "Helsing",
        "domain": "helsing.ai",
        "ats": "lever",
        "hq_country": "DE",
        "hq_confidence": 95,
        "comp_estimate": "€€€",
        "added_at": datetime(2026, 2, 1, tzinfo=UTC),
    },
    "deepl": {
        "name": "DeepL",
        "domain": "deepl.com",
        "ats": "greenhouse",
        "hq_country": "DE",
        "hq_confidence": 97,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 2, 1, tzinfo=UTC),
    },
    "elevenlabs": {
        "name": "ElevenLabs",
        "domain": "elevenlabs.io",
        "ats": "ashby",
        "hq_country": "GB",
        "hq_confidence": 91,
        "comp_estimate": "€€€",
        "added_at": datetime(2026, 4, 1, tzinfo=UTC),
    },
    "qonto": {
        "name": "Qonto",
        "domain": "qonto.com",
        "ats": "lever",
        "hq_country": "FR",
        "hq_confidence": 93,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 4, 1, tzinfo=UTC),
    },
    "synthesia": {
        "name": "Synthesia",
        "domain": "synthesia.io",
        "ats": "ashby",
        "hq_country": "GB",
        "hq_confidence": 90,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 4, 1, tzinfo=UTC),
    },
    "pigment": {
        "name": "Pigment",
        "domain": "pigment.com",
        "ats": "greenhouse",
        "hq_country": "FR",
        "hq_confidence": 96,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 1, 1, tzinfo=UTC),
    },
    "sereact": {
        "name": "Sereact",
        "domain": "sereact.ai",
        "ats": "ashby",
        "hq_country": "DE",
        "hq_confidence": 64,  # unverified in the frontend seed — kept low deliberately
        "comp_estimate": "€€",
        "added_at": datetime(2026, 5, 1, tzinfo=UTC),
    },
    "wayve": {
        "name": "Wayve",
        "domain": "wayve.ai",
        "ats": "greenhouse",
        "hq_country": "GB",
        "hq_confidence": 89,
        "comp_estimate": "€€€",
        "added_at": datetime(2026, 1, 1, tzinfo=UTC),
    },
    "parloa": {
        "name": "Parloa",
        "domain": "parloa.com",
        "ats": "greenhouse",
        "hq_country": "DE",
        "hq_confidence": 94,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 4, 1, tzinfo=UTC),
    },
    "ada": {
        "name": "Ada Health",
        "domain": "ada.com",
        "ats": "greenhouse",
        "hq_country": "DE",
        "hq_confidence": 93,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 3, 1, tzinfo=UTC),
    },
    "factorial": {
        "name": "Factorial",
        "domain": "factorialhr.com",
        "ats": "greenhouse",
        "hq_country": "ES",
        "hq_confidence": 92,
        "comp_estimate": "€€",
        "added_at": datetime(2026, 2, 1, tzinfo=UTC),
    },
}

# All 13 postings from data.ts's `jobs`, keyed by the frontend job id. `company_key`
# indexes `_COMPANIES`. `posted_days_ago`/`deadline_days` reproduce the frontend's
# "Xd ago" / deadline countdown relative to *today* (so the derived `posted`/
# `deadlineDays` read-model fields look right whenever this is run, not just once).
# `status`/`dismiss_reason` populate `PostingState` only when the frontend job had one.
#
# j5 (Sereact) is the frontend's flagged low-confidence/HQ-unverified role; its
# `confidence` (79) never actually dipped under 50 in the frontend mock, but the
# brief requires at least one sub-50 extraction_confidence to exercise the Insights
# "excluded" invariant, so it's deliberately lowered to 42 here (judgment call).
_POSTINGS: list[dict[str, Any]] = [
    {
        "key": "j1",
        "company_key": "mistral",
        "title": "Applied Scientist — LLM Agents",
        "role_family": "Applied Scientist",
        "city": "Paris",
        "country": "FR",
        "hq_country": "FR",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc preferred",
        "required_skills": ["PyTorch", "vLLM", "Python", "Kubernetes", "Ray", "LangGraph"],
        "nice_to_have": ["JAX", "Triton kernels"],
        "visa": "EU work auth required",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "EU timezone",
        "salary_text": "€95k-130k",
        "posted_days_ago": 4,
        "deadline_days": 9,
        "responsibilities": [
            "Design and evaluate tool-using LLM agents",
            "Build agent eval harnesses and traces",
            "Ship retrieval + planning into production",
            "Collaborate with research on new architectures",
        ],
        "summary": (
            "Build production-grade tool-using LLM agents — planning, retrieval and "
            "evaluation — alongside Mistral's research team in Paris, hybrid 2 days "
            "on-site."
        ),
        "extraction_confidence": 96,
        "factor_role": 96,
        "factor_skill": 89,
        "overlap_matched": 8,
        "overlap_total": 9,
        "rationale": (
            "Agentic-LLM focus maps directly onto your applied-LLM preference; "
            "remote-EU friendly with strong skill overlap (8 of 9 required)."
        ),
        "status": None,
    },
    {
        "key": "j2",
        "company_key": "helsing",
        "title": "Senior Machine Learning Engineer",
        "role_family": "Machine Learning Engineer",
        "city": "Munich",
        "country": "DE",
        "hq_country": "DE",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc / PhD",
        "required_skills": ["PyTorch", "C++", "CUDA", "ONNX", "Triton"],
        "nice_to_have": ["TensorRT", "Real-time systems"],
        "visa": "EU work auth required",
        "languages": ["English C1", "German nice"],
        "contract": "Permanent",
        "geo": "Munich hybrid",
        "salary_text": None,
        "posted_days_ago": 6,
        "deadline_days": 14,
        "responsibilities": [
            "Optimise model inference on edge hardware",
            "Own training-to-deployment pipelines",
            "Profile and accelerate PyTorch graphs",
        ],
        "summary": (
            "Systems-leaning ML role optimising real-time inference. Strong "
            "engineering depth; defense-adjacent mission and Munich hybrid "
            "expectation."
        ),
        "extraction_confidence": 92,
        "factor_role": 90,
        "factor_skill": 86,
        "overlap_matched": 7,
        "overlap_total": 9,
        "rationale": (
            "High overlap and strong systems-ML fit; Munich on-site bias and the "
            "defense-adjacent domain are mild fit risks against your stated "
            "preferences."
        ),
        "status": "Saved",
    },
    {
        "key": "j3",
        "company_key": "deepl",
        "title": "ML Engineer — Inference",
        "role_family": "ML Engineer",
        "city": "Remote · EU",
        "country": "NL",
        "hq_country": "DE",
        "work_mode": "Remote",
        "seniority": "Mid-Senior",
        "education": "BSc",
        "required_skills": ["PyTorch", "Triton", "AWS", "Python", "Docker"],
        "nice_to_have": ["Rust", "Quantisation"],
        "visa": "EU remote OK",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "EU remote",
        "salary_text": "€80k-110k",
        "posted_days_ago": 2,
        "deadline_days": 21,
        "responsibilities": [
            "Serve translation models at low latency",
            "Build autoscaling inference infra",
            "Quantise and distil production models",
        ],
        "summary": (
            "Fully remote-EU inference engineering at DeepL — latency, autoscaling "
            "and quantisation of large translation models."
        ),
        "extraction_confidence": 94,
        "factor_role": 84,
        "factor_skill": 88,
        "overlap_matched": 7,
        "overlap_total": 8,
        "rationale": (
            "Fully remote-EU with clean skill overlap (7 of 8); lighter on agentic "
            "work than you ideally want, but strong on the infra you enjoy."
        ),
        "status": None,
    },
    {
        "key": "j4",
        "company_key": "elevenlabs",
        "title": "Applied Research Engineer — Audio LLMs",
        "role_family": "Applied Research Engineer",
        "city": "Remote · EU",
        "country": "NL",
        "hq_country": "GB",
        "work_mode": "Remote",
        "seniority": "Senior",
        "education": "MSc preferred",
        "required_skills": ["PyTorch", "Python", "JAX", "AWS"],
        "nice_to_have": ["Audio DSP", "Diffusion"],
        "visa": "EU remote OK",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "EU/UK remote",
        "salary_text": None,
        "posted_days_ago": 8,
        "deadline_days": 30,
        "responsibilities": [
            "Train and fine-tune audio-language models",
            "Design evaluation for generative audio",
            "Collaborate across research and product",
        ],
        "summary": (
            "Foreign-HQ (UK) remote role on audio-language models — training, "
            "fine-tuning and eval, adjacent to your core LLM work."
        ),
        "extraction_confidence": 88,
        "factor_role": 80,
        "factor_skill": 79,
        "overlap_matched": 6,
        "overlap_total": 9,
        "rationale": (
            "Matches your Foreign-HQ lens; audio-LLM work is adjacent to your core "
            "and fully remote, with decent overlap (6 of 9)."
        ),
        "status": None,
    },
    {
        "key": "j5",
        "company_key": "sereact",
        "title": "Research Engineer — Robotics Foundation Models",
        "role_family": "Research Engineer",
        "city": "Remote · EU",
        "country": "NL",
        "hq_country": "DE",
        "work_mode": "Remote",
        "seniority": "Senior",
        "education": "PhD preferred",
        "required_skills": ["PyTorch", "ROS", "C++", "Isaac Sim"],
        "nice_to_have": ["RL", "Sim2real"],
        "visa": "EU remote OK",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "EU remote",
        "salary_text": None,
        "posted_days_ago": 11,
        "deadline_days": 5,
        "responsibilities": [
            "Train robot manipulation policies",
            "Build sim-to-real pipelines",
            "Scale multi-task robot learning",
        ],
        "summary": (
            "Robotics foundation-model research. Strong role and location fit, but "
            "the robotics/sim stack diverges sharply from your profile."
        ),
        "extraction_confidence": 42,  # see module docstring: deliberately <50
        "factor_role": 74,
        "factor_skill": 41,
        "overlap_matched": 2,
        "overlap_total": 8,
        "red_flag": "Low required-skill overlap",
        "rationale": (
            "Near-zero required-skill overlap (2 of 8) on a robotics/sim stack "
            "pulls this down as a one-way red flag despite good role and location "
            "fit. HQ origin unverified (64%)."
        ),
        "status": None,
    },
    {
        "key": "j6",
        "company_key": "pigment",
        "title": "Senior Data Scientist — Forecasting",
        "role_family": "Data Scientist",
        "city": "Paris",
        "country": "FR",
        "hq_country": "FR",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc",
        "required_skills": ["Python", "dbt", "Snowflake", "Prophet", "SQL"],
        "nice_to_have": ["Causal inference"],
        "visa": "EU work auth required",
        "languages": ["English C1", "French nice"],
        "contract": "Permanent",
        "geo": "Paris hybrid",
        "salary_text": "€70k-95k",
        "posted_days_ago": 9,
        "deadline_days": 18,
        "responsibilities": [
            "Build demand-forecasting models",
            "Partner with product on planning analytics",
            "Own metric pipelines",
        ],
        "summary": (
            "BI/forecasting-leaning data science at a planning platform. Solid but "
            "further from applied-LLM than you target."
        ),
        "extraction_confidence": 90,
        "factor_role": 66,
        "factor_skill": 72,
        "overlap_matched": 5,
        "overlap_total": 9,
        "rationale": (
            "Forecasting/BI lean sits further from your applied-LLM target, but "
            "overlap is reasonable (5 of 9) and it's a clean Paris hybrid you "
            "already applied to."
        ),
        "status": "Applied",
    },
    {
        "key": "j7",
        "company_key": "qonto",
        "title": "Machine Learning Engineer — Fraud",
        "role_family": "Machine Learning Engineer",
        "city": "Barcelona",
        "country": "ES",
        "hq_country": "FR",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc",
        "required_skills": ["Python", "PyTorch", "AWS", "SQL", "Kafka"],
        "nice_to_have": ["Graph ML", "Streaming"],
        "visa": "EU work auth required",
        "languages": ["English C1", "Spanish nice"],
        "contract": "Permanent",
        "geo": "Barcelona hybrid",
        "salary_text": "€68k-88k",
        "posted_days_ago": 3,
        "deadline_days": 12,
        "responsibilities": [
            "Build real-time fraud detection models",
            "Own streaming feature pipelines",
            "Reduce false positives at scale",
        ],
        "summary": (
            "Foreign-HQ (FR) fintech ML role in Barcelona — real-time fraud "
            "detection, streaming features. Matches both your Spain and "
            "Foreign-HQ lenses."
        ),
        "extraction_confidence": 91,
        "factor_role": 78,
        "factor_skill": 82,
        "overlap_matched": 6,
        "overlap_total": 8,
        "rationale": (
            "Appears in your Spain and Foreign-HQ lenses; fintech ML aligns with "
            "your Adyen/Mollie background and overlap is solid (6 of 8)."
        ),
        "status": None,
    },
    {
        "key": "j8",
        "company_key": "synthesia",
        "title": "AI Engineer — Generative Video",
        "role_family": "AI Engineer",
        "city": "Remote · EU",
        "country": "NL",
        "hq_country": "GB",
        "work_mode": "Remote",
        "seniority": "Mid-Senior",
        "education": "BSc",
        "required_skills": ["Python", "PyTorch", "Diffusion", "AWS", "FastAPI"],
        "nice_to_have": ["CUDA", "Video pipelines"],
        "visa": "EU remote OK",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "EU remote",
        "salary_text": "€75k-100k",
        "posted_days_ago": 5,
        "deadline_days": 25,
        "responsibilities": [
            "Productionise generative video models",
            "Build inference APIs for avatars",
            "Optimise generation latency",
        ],
        "summary": (
            "Foreign-HQ (UK) remote AI engineering on generative video — "
            "productionising diffusion models behind real APIs."
        ),
        "extraction_confidence": 87,
        "factor_role": 76,
        "factor_skill": 75,
        "overlap_matched": 6,
        "overlap_total": 9,
        "rationale": (
            "Foreign-HQ remote match; applied generative work with FastAPI/AWS "
            "overlaps your stack, though video is adjacent to your LLM focus."
        ),
        "status": None,
    },
    {
        "key": "j9",
        "company_key": "aleph",
        "title": "ML Engineer — Retrieval & RAG",
        "role_family": "ML Engineer",
        "city": "Heidelberg",
        "country": "DE",
        "hq_country": "DE",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc",
        "required_skills": ["Python", "PyTorch", "pgvector", "RAG", "LangGraph", "Docker"],
        "nice_to_have": ["Sparse retrieval", "Eval frameworks"],
        "visa": "EU work auth required",
        "languages": ["English C1", "German nice"],
        "contract": "Permanent",
        "geo": "Heidelberg hybrid",
        "salary_text": "€85k-115k",
        "posted_days_ago": 1,
        "deadline_days": 7,
        "responsibilities": [
            "Build sovereign-LLM retrieval systems",
            "Own RAG eval and grounding",
            "Ship enterprise retrieval at scale",
        ],
        "summary": (
            "Retrieval & RAG engineering for a European sovereign-LLM lab — "
            "exactly your pgvector/RAG/LangGraph wheelhouse. Heidelberg hybrid."
        ),
        "extraction_confidence": 93,
        "factor_role": 88,
        "factor_skill": 90,
        "overlap_matched": 8,
        "overlap_total": 9,
        "rationale": (
            "Highest skill overlap in your pool (8 of 9) — pgvector, RAG and "
            "LangGraph are core to your projects. Heidelberg hybrid is the only "
            "friction."
        ),
        "status": None,
    },
    {
        "key": "j10",
        "company_key": "wayve",
        "title": "Applied Scientist — Foundation Models",
        "role_family": "Applied Scientist",
        "city": "Remote",
        "country": "GB",
        "hq_country": "GB",
        "work_mode": "Remote",
        "seniority": "Senior",
        "education": "PhD preferred",
        "required_skills": ["PyTorch", "Python", "JAX", "Distributed training"],
        "nice_to_have": ["Autonomy", "Multimodal"],
        "visa": "EU remote OK",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "EU/UK remote",
        "salary_text": None,
        "posted_days_ago": 10,
        "deadline_days": 16,
        "responsibilities": [
            "Train large driving foundation models",
            "Scale distributed training",
            "Research multimodal architectures",
        ],
        "summary": (
            "Foreign-HQ remote applied science on driving foundation models — "
            "heavy research and autonomy-domain, lighter on your applied-LLM core."
        ),
        "extraction_confidence": 85,
        "factor_role": 75,
        "factor_skill": 68,
        "overlap_matched": 5,
        "overlap_total": 9,
        "rationale": (
            "Research-heavy and autonomy-domain — you dismissed it as 'not my "
            "field'. Logged as a negative signal to steer future scoring."
        ),
        "status": "Dismissed",
        "dismiss_reason": "Not my field",
    },
    {
        "key": "j11",
        "company_key": "parloa",
        "title": "ML Engineer — Voice Agents",
        "role_family": "ML Engineer",
        "city": "Berlin",
        "country": "DE",
        "hq_country": "DE",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc",
        "required_skills": ["Python", "PyTorch", "LangGraph", "vLLM", "AWS", "FastAPI"],
        "nice_to_have": ["Telephony", "Streaming ASR"],
        "visa": "EU work auth required",
        "languages": ["English C1", "German nice"],
        "contract": "Permanent",
        "geo": "Berlin hybrid",
        "salary_text": "€82k-108k",
        "posted_days_ago": 3,
        "deadline_days": 11,
        "responsibilities": [
            "Build production voice-agent pipelines",
            "Own LLM orchestration with LangGraph",
            "Optimise latency for real-time calls",
        ],
        "summary": (
            "Agentic voice-AI engineering in Berlin — LangGraph orchestration, "
            "real-time LLM agents. Squarely in your agentic-systems wheelhouse."
        ),
        "extraction_confidence": 92,
        "factor_role": 89,
        "factor_skill": 87,
        "overlap_matched": 7,
        "overlap_total": 9,
        "rationale": (
            "Strong agentic-systems match — LangGraph and vLLM are core to your "
            "projects (7 of 9). Berlin hybrid is the only friction against your "
            "remote preference."
        ),
        "status": None,
    },
    {
        "key": "j12",
        "company_key": "ada",
        "title": "AI Engineer — Clinical LLMs",
        "role_family": "AI Engineer",
        "city": "Berlin",
        "country": "DE",
        "hq_country": "DE",
        "work_mode": "Hybrid",
        "seniority": "Mid-Senior",
        "education": "MSc",
        "required_skills": ["Python", "PyTorch", "RAG", "pgvector", "AWS"],
        "nice_to_have": ["Healthcare data", "Eval"],
        "visa": "EU work auth required",
        "languages": ["English C1"],
        "contract": "Permanent",
        "geo": "Berlin hybrid",
        "salary_text": "€75k-98k",
        "posted_days_ago": 7,
        "deadline_days": 19,
        "responsibilities": [
            "Build retrieval over clinical knowledge",
            "Ground LLM outputs with citations",
            "Ship safe medical assistants",
        ],
        "summary": (
            "Clinical-LLM and RAG engineering in Berlin — grounded retrieval over "
            "medical knowledge, your pgvector/RAG core in a regulated domain."
        ),
        "extraction_confidence": 89,
        "factor_role": 80,
        "factor_skill": 78,
        "overlap_matched": 6,
        "overlap_total": 9,
        "rationale": (
            "RAG + pgvector overlap your projects well (6 of 9); regulated "
            "healthcare domain is new ground but adjacent. Berlin hybrid in your "
            "Berlin lens."
        ),
        "status": None,
    },
    {
        "key": "j13",
        "company_key": "factorial",
        "title": "Machine Learning Engineer — Recommendations",
        "role_family": "Machine Learning Engineer",
        "city": "Barcelona",
        "country": "ES",
        "hq_country": "ES",
        "work_mode": "Hybrid",
        "seniority": "Senior",
        "education": "MSc",
        "required_skills": ["Python", "PyTorch", "SQL", "AWS", "Airflow"],
        "nice_to_have": ["Recsys", "Feature stores"],
        "visa": "EU work auth required",
        "languages": ["English C1", "Spanish nice"],
        "contract": "Permanent",
        "geo": "Barcelona hybrid",
        "salary_text": "€60k-82k",
        "posted_days_ago": 6,
        "deadline_days": 23,
        "responsibilities": [
            "Build recommendation models for HR software",
            "Own feature pipelines",
            "Run online experiments",
        ],
        "summary": (
            "Recommendation-systems ML at a Barcelona HR-software scaleup — solid "
            "applied ML, lighter on LLM/agents than you target."
        ),
        "extraction_confidence": 88,
        "factor_role": 74,
        "factor_skill": 78,
        "overlap_matched": 6,
        "overlap_total": 8,
        "rationale": (
            "Appears in your Spain lens; applied ML with a familiar stack (6 of "
            "8), though recsys sits further from your applied-LLM focus."
        ),
        "status": None,
    },
]

# Lenses from data.ts's `lenses`. `origin_rule`/`modes`/`scope` drive
# `services/lens_filter.py`'s `lens_where`: `foreign_hq` compares a posting's
# hq_country to its own country (not to the candidate's home country — a narrower,
# mechanical rule than the frontend prototype's per-job "matches Foreign-HQ lens"
# narrative, which reasoned relative to the candidate's NL base; see seeder-expansion
# report for postings this reclassifies). A bare 2-letter `scope` filters by country
# ("ES"); a "City, CC" scope filters by city ("Berlin, DE"); anything else is a
# soft/display-only scope with no hard filter — NOTE this means the frontend's
# region label "EU" can't be used verbatim: `_scope_predicate`'s country-code
# regex is exactly `^[A-Z]{2}$`, so "EU" would itself be (mis)treated as a hard
# `country == "EU"` filter (matching nothing, since no posting's country is
# literally "EU"). The Remote/Foreign-HQ lenses below use "" instead, so only
# their `modes`/`origin_rule` do the (correct) filtering — a deliberate deviation
# from data.ts's literal "EU" scope string (see seeder-expansion report).
_LENSES: list[dict[str, Any]] = [
    {
        "name": "All",
        "short": "All",
        "scope": "Any region",
        "modes": ["Remote", "Hybrid", "On-site"],
        "origin_rule": None,
        "focus": "",
        "seeds": ["data scientist", "ML engineer", "applied scientist"],
        "active": True,
        "is_default": True,
    },
    {
        "name": "Remote · EU",
        "short": "Remote · EU",
        "scope": "",
        "modes": ["Remote"],
        "origin_rule": None,
        "focus": "fully-remote, async-first teams",
        "seeds": ["remote ML engineer EU", "fully remote applied scientist europe"],
        "active": True,
        "is_default": False,
    },
    {
        "name": "Foreign HQ",
        "short": "Foreign HQ",
        "scope": "",
        "modes": ["Remote", "Hybrid"],
        "origin_rule": "foreign_hq",
        "focus": "non-NL HQ — broaden beyond home market",
        "seeds": ["US startup hiring remote EU", "foreign AI lab europe team"],
        "active": True,
        "is_default": False,
    },
    {
        "name": "Spain",
        "short": "Spain",
        "scope": "ES",
        "modes": ["Remote", "Hybrid", "On-site"],
        "origin_rule": None,
        "focus": "Barcelona / Madrid relocation-optional",
        "seeds": ["machine learning engineer Barcelona", "data scientist Madrid"],
        "active": True,
        "is_default": False,
    },
    {
        "name": "Berlin core",
        "short": "Berlin",
        "scope": "Berlin, DE",
        "modes": ["Hybrid", "On-site"],
        "origin_rule": None,
        "focus": "Berlin AI scene, hybrid acceptable",
        "seeds": ["AI engineer Berlin", "LLM engineer Berlin hybrid"],
        "active": False,
        "is_default": False,
    },
]

# Approvals from data.ts's `approvals` (the undecided queue — decision stays NULL).
# `hq_confidence` isn't in the frontend `Approval` type (only a boolean `unverified`
# flag on Sereact); values here reuse the matching tracked company's confidence where
# one exists (Sereact: 64, below `_HQ_CONFIDENCE_THRESHOLD`=75 so it still renders as
# "unverified"), else a placeholder high-confidence value (judgment call).
_APPROVALS: list[dict[str, Any]] = [
    {
        "name": "Black Forest Labs",
        "domain": "blackforestlabs.ai",
        "ats": "ashby",
        "hq_country": "DE",
        "found_query": "diffusion model lab europe hiring",
        "why": (
            "Generative-image research lab (FLUX). Matches your applied-LLM/"
            "generative targeting; small team, Freiburg + remote."
        ),
        "open_roles": 4,
        "hq_confidence": 90,
    },
    {
        "name": "Lighthouse",
        "domain": "lighthouse.app",
        "ats": "greenhouse",
        "hq_country": "NL",
        "found_query": "machine learning amsterdam scaleup",
        "why": (
            "Amsterdam travel-tech scaleup with a growing ML team. NL-local, "
            "matches your home market and remote-EU lens."
        ),
        "open_roles": 3,
        "hq_confidence": 90,
    },
    {
        "name": "n8n",
        "domain": "n8n.io",
        "ats": "lever",
        "hq_country": "DE",
        "found_query": "AI workflow automation hiring engineer",
        "why": (
            "Workflow-automation platform investing in AI agents. Strong agentic "
            "angle aligned with your stated preference."
        ),
        "open_roles": 5,
        "hq_confidence": 90,
    },
    {
        "name": "Tractable",
        "domain": "tractable.ai",
        "ats": "greenhouse",
        "hq_country": "GB",
        "found_query": "applied computer vision europe remote",
        "why": (
            "Applied CV for insurance. Foreign-HQ remote-EU; CV-heavy, somewhat "
            "adjacent to your LLM focus."
        ),
        "open_roles": 2,
        "hq_confidence": 90,
    },
    {
        "name": "Sereact",
        "domain": "sereact.ai",
        "ats": "ashby",
        "hq_country": "DE",
        "found_query": "robotics foundation models hiring",
        "why": (
            "Robotics foundation-model startup. HQ origin only 64% confident — "
            "flagged 'origin unverified'."
        ),
        "open_roles": 3,
        "hq_confidence": 64,
    },
    {
        "name": "Poolside",
        "domain": "poolside.ai",
        "ats": "ashby",
        "hq_country": "US",
        "found_query": "code LLM lab hiring remote europe",
        "why": (
            "Code-generation LLM lab hiring across EU remotely. Foreign-HQ (US); "
            "applied-LLM core, strong on paper."
        ),
        "open_roles": 6,
        "hq_confidence": 90,
    },
]


async def _get_or_create_demo_user(session: AsyncSession) -> User:
    user = await session.scalar(select(User).where(User.google_sub == DEMO_GOOGLE_SUB))
    if user is None:
        user = User(google_sub=DEMO_GOOGLE_SUB, email=DEMO_EMAIL, name=DEMO_NAME)
        session.add(user)
        await session.flush()
    else:
        user.name = DEMO_NAME
    return user


async def _set_tenant(session: AsyncSession, user_id: object) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)").bindparams(uid=str(user_id))
    )


async def seed(session: AsyncSession) -> None:
    user = await _get_or_create_demo_user(session)
    uid = user.id

    # All per-user reads/writes below require the tenant GUC (FORCE RLS).
    await _set_tenant(session, uid)

    # Idempotent reset: clear the demo user's rows (RLS scopes each delete to them).
    for model in _TENANT_TABLES:
        await session.execute(delete(model))

    # candidate_profile + targeting, ported from data.ts's `candidate` + `targeting`.
    session.add(
        CandidateProfile(
            user_id=uid,
            headline="Data Scientist / ML Engineer",
            location="Amsterdam, NL",
            work_mode="Remote-first (EU)",
            visa="EU citizen — no sponsorship needed",
            years=6,
            education="MSc Artificial Intelligence — University of Amsterdam",
            languages=["English (native-level)", "Dutch (native)", "German (B1)"],
            skills=[
                "Python",
                "PyTorch",
                "LLM fine-tuning",
                "RAG",
                "LangGraph",
                "vLLM",
                "Pandas",
                "scikit-learn",
                "AWS",
                "Docker",
                "SQL",
                "FastAPI",
                "Weights & Biases",
                "Prompt engineering",
            ],
            projects=[
                {
                    "name": "Agentic research assistant",
                    "note": "LangGraph + vLLM multi-tool agent, self-hosted Llama-3 70B",
                },
                {
                    "name": "Churn forecasting pipeline",
                    "note": "Gradient-boosted ensemble, 0.91 AUC, productionised on AWS",
                },
                {
                    "name": "Semantic doc search",
                    "note": "pgvector RAG over 2M internal docs, sub-200ms p95",
                },
            ],
            experience=[
                {"role": "Senior Data Scientist", "org": "Mollie", "period": "2022 — now"},
                {"role": "ML Engineer", "org": "Adyen", "period": "2019 — 2022"},
            ],
        )
    )
    session.add(
        Targeting(
            user_id=uid,
            role_titles=[
                "Data Scientist",
                "ML Engineer",
                "Machine Learning Engineer",
                "AI Engineer",
                "AI Developer",
                "Applied Scientist",
                "Research Engineer",
            ],
            seniority=["Mid", "Senior", "Staff"],
            must_haves=[
                "Python",
                "Production ML or applied LLM work",
                "Remote-friendly within EU",
            ],
            avoid=[
                "Pure research / publish-or-perish",
                "Defense primary mission",
                "Relocation required",
                "On-call heavy SRE",
            ],
            preferences=(
                "Strongly prefer agentic-systems / applied-LLM engineering over pure "
                "research. Remote-EU friendly, async culture. Happy with hybrid in "
                "NL/DE. Interested in inference, retrieval, and agent infrastructure."
            ),
        )
    )
    session.add(UserSettings(user_id=uid, tweaks={"mstyle": "bars", "layout": "rows"}))

    # Lenses, ported from data.ts's `lenses`.
    session.add_all(Lens(user_id=uid, **fields) for fields in _LENSES)

    # Companies, ported from data.ts's `companies` (+ 3 synthesized — see _COMPANIES).
    companies = {
        key: Company(user_id=uid, logo_url=favicon_url(fields["domain"]), **fields)
        for key, fields in _COMPANIES.items()
    }
    session.add_all(companies.values())
    await session.flush()  # assign company ids for posting FKs

    # Postings + scores (+ states), ported from data.ts's `jobs`.
    scored_with = "specula-scoring/v0-demo"
    today = date.today()
    postings = {}
    for job in _POSTINGS:
        posting = Posting(
            user_id=uid,
            company_id=companies[job["company_key"]].id,
            source="scrape",
            source_url=f"https://jobs.{_COMPANIES[job['company_key']]['domain']}/{job['key']}",
            content_hash=f"hash-{job['key']}",
            title=job["title"],
            role_family=job["role_family"],
            city=job["city"],
            country=job["country"],
            hq_country=job["hq_country"],
            work_mode=job["work_mode"],
            seniority=job["seniority"],
            education=job["education"],
            required_skills=job["required_skills"],
            nice_to_have=job["nice_to_have"],
            visa=job["visa"],
            languages=job["languages"],
            contract=job["contract"],
            geo=job["geo"],
            salary_text=job["salary_text"],
            posted_at=today - timedelta(days=job["posted_days_ago"]),
            deadline_at=today + timedelta(days=job["deadline_days"]),
            responsibilities=job["responsibilities"],
            summary=job["summary"],
            still_open=True,
            extraction_confidence=job["extraction_confidence"],
        )
        postings[job["key"]] = posting
    session.add_all(postings.values())
    await session.flush()  # assign posting ids for score/state FKs

    for job in _POSTINGS:
        posting = postings[job["key"]]
        session.add(
            Score(
                posting_id=posting.id,
                user_id=uid,
                factor_role=job["factor_role"],
                factor_skill=job["factor_skill"],
                overlap_matched=job["overlap_matched"],
                overlap_total=job["overlap_total"],
                red_flag=job.get("red_flag"),
                rationale=job["rationale"],
                scored_with=scored_with,
            )
        )
        if job["status"] is not None:
            session.add(
                PostingState(
                    posting_id=posting.id,
                    user_id=uid,
                    status=job["status"],
                    dismiss_reason=job.get("dismiss_reason"),
                )
            )

    # Approval queue, ported from data.ts's `approvals` (decision NULL = undecided).
    session.add_all(
        Approval(
            user_id=uid,
            logo_url=favicon_url(fields["domain"]),
            decision=None,
            **fields,
        )
        for fields in _APPROVALS
    )

    session.add(
        Run(
            user_id=uid,
            kind="scheduled",
            status="done",
            started_at=datetime(2026, 7, 5, 8, 0, tzinfo=UTC),
            finished_at=datetime(2026, 7, 5, 8, 3, tzinfo=UTC),
            stats={"found": 13, "new": 7, "closed": 0, "low_conf_excluded": 1, "errors": 0},
        )
    )

    # Global taxonomy (unscoped; specula_app owns the table).
    for canonical, aliases in [("python", ["py"]), ("pytorch", ["torch"])]:
        exists = await session.scalar(
            select(SkillsTaxonomy).where(SkillsTaxonomy.canonical == canonical)
        )
        if exists is None:
            session.add(SkillsTaxonomy(canonical=canonical, aliases=aliases))


async def main() -> None:
    async with async_session() as session:
        await seed(session)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
