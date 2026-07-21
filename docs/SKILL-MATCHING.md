# Skill matching

How `factor_skill`'s overlap count is computed, and why the threshold is what it is.

## The defect this replaced

Skill overlap was set intersection on casefolded strings. A requirement counted as met only
when both sides happened to word it identically, so a candidate with PyTorch, scikit-learn
and Pandas scored **zero** against `Machine Learning`. Every posting in the live pool landed
on the same two matches — `Python` and `SQL`, the only skills phrased the same on both sides
— giving 2/5, 2/6, 2/7, 2/11.

That is 40% of the match score, and it also crossed a threshold: the read model
(`services/jobs.py::score_match`) red-flags anything under `factor_skill 45` with "Low
required-skill overlap" and caps its match at 72. Observed scores ran 23–40, so genuinely
strong roles were being flagged and capped.

## How it works now

A required skill counts as covered when its embedding's cosine to **any** candidate skill
clears `settings.skill_match_similarity`. Per requirement, so one broad candidate skill may
cover several requirements and is never "used up".

Vectors are cached globally in `skills_taxonomy.vec`, keyed by the **canonical** form. Two
consequences worth stating:

- Exact and aliased skills resolve to the same cache entry, so they share one vector and
  compare at exactly 1.0. Exact matching is subsumed by the embedding path rather than
  being a second code path beside it.
- Skills repeat heavily across postings, so the cache means each distinct skill is embedded
  once ever, not once per posting.

## Why 0.55

Measured against the live pool — every distinct required skill embedded against every
candidate skill with the production model. The boundary is where real coverage stops and
token collision starts:

| cosine | required skill | best candidate match | verdict |
|---|---|---|---|
| 1.000 | python, sql, docker, aws, … | itself | exact |
| 0.710 | python coding | python | real |
| 0.613 | cloud engineering | prompt engineering | right verdict, wrong pair |
| 0.597 | machine learning | scikit-learn | real |
| 0.578 | api development | fastapi | real |
| — 0.55 threshold — | | | |
| 0.524 | ros | rag | **token collision** |
| 0.501 | supervised learning | scikit-learn | real, missed |
| 0.472 | mlops | vllm | token collision |
| 0.470 | ray | rag | token collision |
| 0.469 | graph analytics | langgraph | token collision |
| 0.460 | data mining | scikit-learn | real, missed |
| 0.451 | statistical models | scikit-learn | real, missed |

Raising to 0.60 would drop `machine learning` and `api development` — the two matches that
motivated the change. Lowering to 0.45 would pick up `supervised learning`, `data mining`
and `statistical models`, but at the cost of `ros`←`rag`, `ray`←`rag`, `mlops`←`vllm` and
`graph analytics`←`langgraph`. 0.55 is the widest setting that admits no false pair.

### Known limitation

Short skill strings are the hard case: embeddings of 1–2 word technical terms reward shared
substrings, which is why `ros`/`rag` and `langgraph`/`graph analytics` score near genuinely
related pairs. A single global threshold cannot separate them. The tail between roughly
0.45 and 0.55 is genuinely ambiguous and currently resolves as "not covered" — deliberately,
since a missed match understates a score while a false match misleads.

`cloud engineering`←`prompt engineering` (0.613) is above the line and is a false *pair*,
though the verdict is defensible: the candidate has AWS and Docker.

## Provenance guard

`skills_taxonomy` is global and unscoped, and cached vectors are only comparable within one
embedding provenance. Two ways that bites, both of which the `vec_model` column prevents:

1. **Recorded/test runs.** `RecordedOpenAIClient` returns deterministic *pseudo*-vectors for
   any text without a fixture. They carry no semantics. A test run against a shared database
   wrote them into the same rows live scoring reads, and every semantic cosine silently
   collapsed to noise (`machine learning`↔`scikit-learn` measured 0.023 instead of 0.597).
   Recorded runs now cache under the `recorded` provenance and never serve a live run.
2. **Model upgrades.** Vectors from a different embedding model live in a different space.
   Changing `openai_embed_model` now invalidates the cache instead of silently comparing
   across spaces.

Rows whose `vec_model` doesn't match the current provenance are re-embedded and overwritten,
so the cache is self-healing — including the already-poisoned rows this replaced.

## Measured effect

On the genuinely crawled postings (`source='greenhouse'`):

| Posting | Overlap | factor_skill | Low-skill flag |
|---|---|---|---|
| Data Scientist | 2/6 → 4/6 | 42 → 62 | cleared |
| Data Scientist (10 reqs) | 0/10 → 2/10 | 21 → 33 | stays |
| Data Scientist (m/f/d) | 3/8 → 4/8 | 43 → 50 | cleared |
| Senior Data Scientist (m/f/d) | 3/6 → 3/6 | 48 → 48 | none |

The two unchanged results are correct: that candidate has no Spark, Hadoop, Airflow,
computer vision or NLP. The fix removes spurious flags without inventing coverage.

## Open: recalibration

The read model's 45-point flag and the 0.6/0.4 overlap-vs-cosine blend in
`pipeline/score.py` were both tuned when overlap counts were systematically understated.
They should be re-checked against a larger real pool now that matching is honest.
