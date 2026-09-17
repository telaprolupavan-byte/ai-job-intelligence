from __future__ import annotations

import re

from services.eligibility.contracts import WorkAuthorizationSignals


# Deterministic, explicit keyword/phrase detection — never inference.
# A signal is only ever set when matching language is actually present
# in the job text; absence of a match always means "not disclosed", not
# "explicitly does not apply".

_SPONSORSHIP_AVAILABLE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"visa sponsorship\s+(?:is\s+|are\s+)?available",
        r"sponsorship\s+(?:is\s+|are\s+)?(?:offered|provided)",
        r"(?:will|can|are able to|open to)\s+sponsor",
    ]
]

_SPONSORSHIP_UNAVAILABLE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"sponsorship\s+(?:is\s+|are\s+)?not\s+(?:available|offered|provided)",
        r"no\s+(?:visa\s+)?sponsorship",
        r"(?:do not|does not|will not|won't|unable to|not able to"
        r"|cannot|can not)\s+(?:offer\s+|provide\s+)?(?:visa\s+)?sponsor",
    ]
]

_AUTHORIZATION_REQUIRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"authorized to work in the (?:u\.?s\.?|united states)",
        r"work authorization (?:is\s+)?required",
    ]
]

_CITIZENSHIP_REQUIRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"(?:u\.?s\.?|united states) citizenship\s+(?:is\s+)?required",
        r"must be a (?:u\.?s\.?|united states) citizen",
        r"(?:u\.?s\.?|united states) citizens only",
    ]
]

_CLEARANCE_REQUIRED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"security clearance",
        r"(?:secret|top secret|ts/sci)\s+clearance",
    ]
]


def extract_work_authorization_signals(
    text: str | None,
) -> WorkAuthorizationSignals:
    """
    Deterministically detect work-authorization-related signals from job
    text using explicit keyword/phrase patterns.

    This never guesses: a signal is only set when matching language is
    actually present. No LLM call, no inference from unrelated text and
    no immigration/legal determination — it only surfaces what the job
    posting itself states so the eligibility engine can compare it
    against the user's own declared requirement.
    """
    if not text:
        return WorkAuthorizationSignals()

    sponsorship_available: bool | None = None

    # Unavailable patterns are checked first: an explicit negative
    # statement like "No visa sponsorship available" would otherwise also
    # satisfy the "available" pattern's bare "visa sponsorship ...
    # available" substring match, silently flipping a negative statement
    # into a positive signal. A negative statement is always the more
    # specific/decisive read, so it takes precedence.
    if any(
        pattern.search(text) for pattern in _SPONSORSHIP_UNAVAILABLE_PATTERNS
    ):
        sponsorship_available = False
    elif any(pattern.search(text) for pattern in _SPONSORSHIP_AVAILABLE_PATTERNS):
        sponsorship_available = True

    return WorkAuthorizationSignals(
        sponsorship_available=sponsorship_available,
        authorization_required=any(
            pattern.search(text) for pattern in _AUTHORIZATION_REQUIRED_PATTERNS
        ),
        citizenship_required=any(
            pattern.search(text) for pattern in _CITIZENSHIP_REQUIRED_PATTERNS
        ),
        clearance_required=any(
            pattern.search(text) for pattern in _CLEARANCE_REQUIRED_PATTERNS
        ),
    )
