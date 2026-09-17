# Canonical Skill Identity

`services/skills` is the single source of truth for what a "skill" is
across AJI. It replaces two vocabularies that previously existed
independently and had started to drift:

- `apps/api/services/resume_ai/deterministic.py` (`SKILL_CATALOG`, a flat
  set of literal detection strings with no aliasing)
- `services/job_matching/skill_normalizer.py` (`SKILL_ALIASES`, a
  surface-form -> canonical mapping)

For example, before this module existed, a resume containing "Python 3"
was never recognized as evidence of "Python" at all (the resume-side
catalog had no such alias), while the job-matching side already knew
`"python 3" -> "python"`. "GenAI", "generative ai", "LLM", "LLMs", and
"large language models" were also tracked as independent, unrelated
skills instead of one identity.

## What lives here

- `CANONICAL_SKILLS: dict[str, frozenset[str]]` — canonical skill name ->
  its known aliases (surface-form variations).
- `SKILL_ALIASES: dict[str, str]` — flat surface-form -> canonical lookup,
  derived from `CANONICAL_SKILLS`.
- `normalize_skill(text) -> str` / `normalize_skills(list) -> list[str]` —
  resolve arbitrary skill text to its canonical form (case/whitespace
  normalized; unknown skills are returned as-is rather than guessed).
- `find_skills(text) -> list[str]` — detect which canonical skills are
  present in free-form text (resume or job description), matching on the
  canonical name or any of its aliases as a whole word/phrase.
- `count_skill_mentions(text, canonical_skill) -> int` — count how many
  times a canonical skill (in any of its surface forms) appears in text;
  used to build evidence (e.g. "demonstrated" vs. "skills only").
- `AMBIGUOUS_SURFACE_FORMS` — short forms ("ai", "ml", "js", "ts", "py")
  that are valid `normalize_skill()` inputs but are excluded from
  `find_skills()`'s free-text scanning, since they collide with common
  English/acronym text.

## Who imports this

- `apps/api/services/resume_ai/deterministic.py` — resume-side skill
  detection and evidence (`extract_skills`, `analyze_skill_evidence`,
  `_project_signals`).
- `services/job_matching/extractor.py` — job-description-side skill
  extraction (`extract_job_skills`).
- `services/job_matching/{matcher,scorer,evidence,resume_adapter}.py` —
  skill/title normalization.
- `services/job_matching/skill_normalizer.py` is kept only as a
  backward-compatible re-export of `SKILL_ALIASES`/`normalize_skill`/
  `normalize_skills` so any existing import of that path keeps working.

Future Job/JD Intelligence and ATS Alignment work should import from
`services.skills` directly rather than introducing another vocabulary.

## Design notes

- This module has no dependency on `apps.api` or `services.job_matching`,
  so it can be imported from either side without a circular import.
- Evidence concepts (`demonstrated` / `skills_only` / `weakly_supported`
  on the resume side, `explicit` / `experience` / `inferred` on the job
  matching side) are unchanged by this module — it only unifies *skill
  identity*, not the evidence/matching logic built on top of it.
- Keep the catalog to skills the product actually needs to detect. Don't
  add an alias "just in case" — every alias is a small ongoing false-
  positive risk in free-text scanning.
