"""Deterministic normalization of pasted job content (AJI-022).

A pasted job posting usually arrives as one blob. The existing Job
Intelligence (AJI-012) and Requirement Intelligence (AJI-020A) pipelines
read three separate `Job` columns - `description`, `requirements`, and
`responsibilities` - and deliberately scan `responsibilities` only for
responsibilities, never for requirements. This module does the minimum
needed to feed those columns from a blob, and nothing more:

- Lines are routed to a bucket only by an explicit, recognized section
  heading line ("Requirements", "What you'll do", "Benefits", ...). Text
  before the first heading, and any section whose heading is not
  recognized, stays where it is (description, or the current section).
- Heading lines are kept verbatim inside their section, so heading-driven
  behavior downstream (e.g. AJI-012 switching to "preferred" after a
  "Preferred Qualifications" heading) keeps working. The one exception is
  a responsibilities heading: both pipelines read every line of that
  column as a responsibility item, so a heading such as "What you'll do"
  would otherwise surface as a fake responsibility. It carries no signal
  there and is left out of that column (the raw paste still has it).
- Every line is copied verbatim; nothing is rewritten, summarized, or
  added. A posting with no recognized requirements/responsibilities
  heading is stored whole as the description, with `requirements`/
  `responsibilities` left empty - a missing section is never invented.

The complete raw paste is stored separately on the job
(`Job.raw_submitted_content`); this split is only the pipeline input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


Section = Literal["description", "requirements", "responsibilities"]

# Longest line still considered a possible heading. Real headings are
# short; anything longer is content even if it starts with a heading word.
_MAX_HEADING_WORDS = 8

_REQUIREMENT_HEADINGS = frozenset(
    {
        "requirements",
        "requirement",
        "job requirements",
        "minimum requirements",
        "basic requirements",
        "requirements and qualifications",
        "qualifications",
        "minimum qualifications",
        "basic qualifications",
        "required qualifications",
        "key qualifications",
        "your qualifications",
        "qualifications and experience",
        "preferred qualifications",
        "desired qualifications",
        "additional qualifications",
        "skills",
        "required skills",
        "preferred skills",
        "desired skills",
        "skills and experience",
        "skills & experience",
        "skills and qualifications",
        "skills & qualifications",
        "required experience",
        "preferred experience",
        "education and experience",
        "must have",
        "must-have",
        "must haves",
        "must-haves",
        "nice to have",
        "nice-to-have",
        "nice to haves",
        "nice-to-haves",
        "bonus points",
        "what you'll need",
        "what you will need",
        "what you need",
        "what you bring",
        "what you'll bring",
        "what we're looking for",
        "what we are looking for",
        "who you are",
        "about you",
        "you have",
    }
)

_RESPONSIBILITY_HEADINGS = frozenset(
    {
        "responsibilities",
        "key responsibilities",
        "job responsibilities",
        "your responsibilities",
        "primary responsibilities",
        "main responsibilities",
        "core responsibilities",
        "duties",
        "key duties",
        "duties and responsibilities",
        "roles and responsibilities",
        "role and responsibilities",
        "what you'll do",
        "what you will do",
        "what you'll be doing",
        "what you will be doing",
        "what you'll work on",
        "in this role you will",
        "in this role, you will",
        "day to day",
        "day-to-day",
        "a day in the life",
    }
)

# Headings that end a requirements/responsibilities section and return
# to general description text (company info, benefits, pay, EEO, ...).
_DESCRIPTION_HEADINGS = frozenset(
    {
        "about the job",
        "about the role",
        "about the position",
        "about the team",
        "about us",
        "about the company",
        "company overview",
        "overview",
        "job description",
        "description",
        "summary",
        "job summary",
        "position summary",
        "role overview",
        "who we are",
        "our mission",
        "why join us",
        "benefits",
        "perks",
        "perks and benefits",
        "benefits and perks",
        "what we offer",
        "compensation",
        "compensation and benefits",
        "salary",
        "pay",
        "location",
        "equal opportunity",
        "equal opportunity employer",
        "eeo statement",
    }
)

_MARKDOWN_DECORATION = re.compile(r"^[#>*_\s]+|[*_\s]+$")


def _heading_key(line: str) -> str | None:
    """The comparable form of a line if it could be a heading, else None."""
    stripped = _MARKDOWN_DECORATION.sub("", line.strip())
    stripped = stripped.rstrip(":").strip()
    stripped = _MARKDOWN_DECORATION.sub("", stripped)

    if not stripped or len(stripped.split()) > _MAX_HEADING_WORDS:
        return None

    key = stripped.replace("’", "'").replace("‘", "'").lower()
    return re.sub(r"\s+", " ", key)


def classify_heading(line: str) -> Section | None:
    """The section a heading line opens, or None when it is not one."""
    key = _heading_key(line)

    if key is None:
        return None

    if key in _REQUIREMENT_HEADINGS:
        return "requirements"

    if key in _RESPONSIBILITY_HEADINGS:
        return "responsibilities"

    if key in _DESCRIPTION_HEADINGS:
        return "description"

    return None


@dataclass(frozen=True)
class NormalizedJobContent:
    description: str | None
    requirements: str | None
    responsibilities: str | None


def _join(lines: list[str]) -> str | None:
    text = "\n".join(lines).strip()
    return text or None


def normalize_job_content(content: str) -> NormalizedJobContent:
    """Split pasted job content into the three `Job` text inputs."""
    text = content.replace("\r\n", "\n").replace("\r", "\n")

    buckets: dict[Section, list[str]] = {
        "description": [],
        "requirements": [],
        "responsibilities": [],
    }
    current: Section = "description"

    for line in text.split("\n"):
        section = classify_heading(line)

        if section is not None:
            current = section

            if section == "responsibilities":
                continue

        buckets[current].append(line)

    requirements = _join(buckets["requirements"])
    responsibilities = _join(buckets["responsibilities"])

    if requirements is None and responsibilities is None:
        # Nothing to separate: keep the whole posting as the description
        # rather than guessing at structure that is not there.
        return NormalizedJobContent(
            description=text.strip() or None,
            requirements=None,
            responsibilities=None,
        )

    return NormalizedJobContent(
        description=_join(buckets["description"]),
        requirements=requirements,
        responsibilities=responsibilities,
    )


UNTITLED_JOB_TITLE = "Untitled job"

_MAX_DERIVED_TITLE_LENGTH = 150


def resolve_title(title: str | None, content: str) -> str:
    """The job title to store.

    The user's own title wins. Otherwise the posting's first non-empty
    line is used verbatim when it is short enough to be a title and is
    not itself a section heading (pasted postings almost always open
    with the role name). Only when neither exists does the job get a
    neutral placeholder - `Job.title` is required, and Job Intelligence
    rejects an empty title.
    """
    if title and title.strip():
        return title.strip()

    for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        candidate = _MARKDOWN_DECORATION.sub("", line.strip()).strip()

        if not candidate:
            continue

        if (
            len(candidate) <= _MAX_DERIVED_TITLE_LENGTH
            and classify_heading(candidate) is None
        ):
            return candidate

        break

    return UNTITLED_JOB_TITLE
