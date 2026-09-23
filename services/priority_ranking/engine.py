"""Deterministic Job Priority Ranking engine (AJI-025).

No database access, no AI/LLM call, no randomness: a pure function of
already-loaded evidence (``PriorityCandidate``) to an ordered list of
``PriorityResult``. The same candidates, in any input order, always
produce the same output.

Why an ordering and not a score
-------------------------------
docs/ARCHITECTURE.md forbids blending Job Match and ATS Alignment into a
single number ("Job Match vs. ATS Alignment (do not merge these)"), and
AJI-014 records that no weighting formula for combining them was ever
approved. A weighted "priority score" would be exactly that blend, with
invented weights. So priority is a *lexicographic ordering* over the
existing results, applied in the same order the AJI-023 decision workflow
already runs them:

1. Hard Eligibility gate. INELIGIBLE jobs are EXCLUDED and never ranked
   (a high Job Match or ATS score can never override a failed hard
   constraint). Among the rest, ELIGIBLE jobs come before UNKNOWN ones:
   UNKNOWN is never converted to ELIGIBLE, it stays a separate, labelled
   group.
2. Job Match score, highest first - "how well does this job fit you?" is
   the question closest to "which job deserves attention first". A job
   with no Job Match for the selected resume version is NOT_READY: it is
   listed after every ranked job with no rank at all, never scored as if
   its fit were zero.
3. ATS Alignment score, highest first - only decides between jobs whose
   Job Match scores are exactly equal (with equal fit, the job your
   selected resume already demonstrates better needs less work). A job
   without ATS Alignment sorts after one that has it only within such a
   tie; it can never fall below a job with a lower Job Match.
4. Posting date, newest first, then job id - the existing Jobs listing
   order, so otherwise-equal jobs keep their familiar relative order.

Two scores are never added, averaged, or weighted together; each stays
visible on its own. No threshold is used: there is no "strong"/"weak"
band anywhere, because no such band has been approved for either score.

Current vs. out-of-date evidence
--------------------------------
Stored Job Match / ATS Alignment rows are immutable snapshots. A row is
"current" exactly when recalculating it now would return that same row -
i.e. it matches the existing idempotency keys of
``calculate_job_match`` (Job Intelligence snapshot + engine version) and
``calculate_ats_alignment`` (Job Intelligence + Requirement Intelligence
snapshots + engine version). An out-of-date row is still used for ordering
(dropping it would silently discard real evidence) but the job becomes
PARTIAL and carries a caution saying exactly what changed.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from services.ats_alignment.engine import ENGINE_VERSION as ATS_ENGINE_VERSION
from services.eligibility.contracts import (
    ConstraintStatus,
    EligibilityStatus,
)
from services.job_matching.scorer import ENGINE_VERSION as MATCH_ENGINE_VERSION
from services.priority_ranking.contracts import (
    AtsAlignmentEvidence,
    BlockingFactor,
    JobMatchEvidence,
    PriorityCandidate,
    PriorityReason,
    PriorityResult,
    PriorityState,
)


# Version of the ordering rule below. Bump whenever a key, its direction,
# or a state rule changes, so a consumer can tell which rule produced an
# ordering. Priority is not persisted (see
# apps/api/services/priority_ranking_service.py), so there is no stored
# history to migrate - this only labels each response.
ENGINE_VERSION = "1.0.0"

# The ordering keys, in precedence order. Returned with every response so
# the rule is visible to the client, never hidden.
ORDERING: tuple[str, ...] = (
    "hard_eligibility",
    "job_match_score",
    "ats_alignment_score",
    "posting_date",
    "job_id",
)

_EPOCH = datetime(1970, 1, 1)

# Group order: eligible-and-ordered, unknown-eligibility-and-ordered,
# not ready (no Job Match), excluded (ineligible).
_GROUP_ELIGIBLE = 0
_GROUP_UNKNOWN = 1
_GROUP_NOT_READY = 2
_GROUP_EXCLUDED = 3


def rank_jobs(candidates: list[PriorityCandidate]) -> list[PriorityResult]:
    """Order ``candidates`` for the user's attention (see module docstring).

    Returns one ``PriorityResult`` per candidate, already in priority
    order. RANKED/PARTIAL results get a contiguous 1-based ``rank``;
    NOT_READY and EXCLUDED results get ``rank = None``.
    """
    evaluated = [(_sort_key(candidate), candidate) for candidate in candidates]
    evaluated.sort(key=lambda pair: pair[0])

    results: list[PriorityResult] = []
    next_rank = 1

    for _, candidate in evaluated:
        state = _state_for(candidate)
        rank: int | None = None

        if state in (PriorityState.RANKED, PriorityState.PARTIAL):
            rank = next_rank
            next_rank += 1

        results.append(_build_result(candidate, state, rank))

    return results


# ---------------------------------------------------------------------------
# State and ordering
# ---------------------------------------------------------------------------


def job_match_stale_codes(
    match: JobMatchEvidence, latest_job_intelligence_id: str | None
) -> list[str]:
    """Why ``match`` would not be returned by calculate_job_match today."""
    codes: list[str] = []

    if match.engine_version != MATCH_ENGINE_VERSION:
        codes.append("job_match_outdated_engine")

    if match.job_intelligence_id is None:
        codes.append("job_match_legacy_source")
    elif (
        latest_job_intelligence_id is not None
        and match.job_intelligence_id != latest_job_intelligence_id
    ):
        codes.append("job_match_outdated_job_intelligence")

    return codes


def ats_stale_codes(
    ats: AtsAlignmentEvidence,
    latest_job_intelligence_id: str | None,
    latest_requirement_intelligence_id: str | None,
) -> list[str]:
    """Why ``ats`` would not be returned by calculate_ats_alignment today."""
    codes: list[str] = []

    if ats.engine_version != ATS_ENGINE_VERSION:
        codes.append("ats_outdated_engine")

    if ats.requirement_intelligence_id is None:
        codes.append("ats_legacy_source")
    elif (
        latest_requirement_intelligence_id is not None
        and ats.requirement_intelligence_id != latest_requirement_intelligence_id
    ):
        codes.append("ats_outdated_requirement_intelligence")

    if (
        latest_job_intelligence_id is not None
        and ats.job_intelligence_id != latest_job_intelligence_id
    ):
        codes.append("ats_outdated_job_intelligence")

    return codes


def _state_for(candidate: PriorityCandidate) -> PriorityState:
    if candidate.eligibility.status == EligibilityStatus.INELIGIBLE:
        return PriorityState.EXCLUDED

    if candidate.job_match is None:
        return PriorityState.NOT_READY

    if candidate.ats_alignment is None:
        return PriorityState.PARTIAL

    stale = job_match_stale_codes(
        candidate.job_match, candidate.latest_job_intelligence_id
    ) or ats_stale_codes(
        candidate.ats_alignment,
        candidate.latest_job_intelligence_id,
        candidate.latest_requirement_intelligence_id,
    )

    return PriorityState.PARTIAL if stale else PriorityState.RANKED


def _group_for(candidate: PriorityCandidate, state: PriorityState) -> int:
    if state == PriorityState.EXCLUDED:
        return _GROUP_EXCLUDED

    if state == PriorityState.NOT_READY:
        return _GROUP_NOT_READY

    if candidate.eligibility.status == EligibilityStatus.UNKNOWN:
        return _GROUP_UNKNOWN

    return _GROUP_ELIGIBLE


def _posting_key(posting_date: datetime | None) -> tuple[int, float]:
    """Newest first, undated last (the /jobs listing's nullslast order)."""
    if posting_date is None:
        return (1, 0.0)

    if posting_date.tzinfo is not None:
        posting_date = posting_date.astimezone(timezone.utc).replace(tzinfo=None)

    return (0, -(posting_date - _EPOCH).total_seconds())


def _sort_key(candidate: PriorityCandidate) -> tuple:
    state = _state_for(candidate)
    group = _group_for(candidate, state)

    match_key = 0.0
    ats_missing = 0
    ats_key = 0.0

    # Scores only order jobs that are actually ranked; NOT_READY and
    # EXCLUDED jobs fall straight through to the listing order.
    if group in (_GROUP_ELIGIBLE, _GROUP_UNKNOWN):
        match_key = -float(candidate.job_match.score)

        if candidate.ats_alignment is None:
            ats_missing = 1
        else:
            ats_key = -float(candidate.ats_alignment.overall_score)

    return (
        group,
        match_key,
        ats_missing,
        ats_key,
        _posting_key(candidate.posting_date),
        candidate.job_id,
    )


# ---------------------------------------------------------------------------
# Explanations - built only from the same inputs the ordering used
# ---------------------------------------------------------------------------


def _percent(score: float) -> int:
    """Round half up, matching the Jobs UI's Math.round display."""
    return int(math.floor(float(score) + 0.5))


def _eligibility_explanation(
    candidate: PriorityCandidate,
) -> tuple[list[PriorityReason], list[BlockingFactor]]:
    eligibility = candidate.eligibility
    reasons: list[PriorityReason] = []
    blocking: list[BlockingFactor] = []

    if eligibility.status == EligibilityStatus.INELIGIBLE:
        reasons.append(
            PriorityReason(
                code="eligibility_ineligible",
                source="eligibility",
                kind="caution",
                message=(
                    "Excluded from priority: at least one of your hard "
                    "requirements rules this job out. Job Match and ATS "
                    "Alignment never override that."
                ),
            )
        )

        for check in eligibility.checks:
            if check.status == ConstraintStatus.FAIL:
                blocking.append(
                    BlockingFactor(
                        code="eligibility_failed",
                        source="eligibility",
                        message=check.reason,
                    )
                )

        return reasons, blocking

    passed = [
        check for check in eligibility.checks
        if check.status == ConstraintStatus.PASS
    ]
    unknown = [
        check for check in eligibility.checks
        if check.status == ConstraintStatus.UNKNOWN
    ]

    if eligibility.status == EligibilityStatus.UNKNOWN:
        reasons.append(
            PriorityReason(
                code="eligibility_unknown",
                source="eligibility",
                kind="caution",
                message=(
                    "Hard Eligibility is unknown, so this job is ordered "
                    "after jobs confirmed eligible."
                ),
            )
        )
        for check in unknown:
            reasons.append(
                PriorityReason(
                    code="eligibility_unknown_check",
                    source="eligibility",
                    kind="caution",
                    message=check.reason,
                )
            )
    elif passed:
        reasons.append(
            PriorityReason(
                code="eligibility_eligible",
                source="eligibility",
                kind="evidence",
                message=(
                    "Hard Eligibility: eligible - none of your configured "
                    "hard requirements rule this job out."
                ),
            )
        )
    else:
        reasons.append(
            PriorityReason(
                code="eligibility_no_constraints",
                source="eligibility",
                kind="evidence",
                message=(
                    "Hard Eligibility: eligible - you have no hard "
                    "requirements configured."
                ),
            )
        )

    for check in passed:
        reasons.append(
            PriorityReason(
                code="eligibility_pass",
                source="eligibility",
                kind="evidence",
                message=check.reason,
            )
        )

    return reasons, blocking


_JOB_MATCH_STALE_MESSAGES = {
    "job_match_outdated_engine": (
        "Job Match was calculated by an earlier Job Match engine version; "
        "recalculate it to refresh."
    ),
    "job_match_legacy_source": (
        "Job Match was calculated before Job Intelligence existed for this "
        "job; recalculate it to refresh."
    ),
    "job_match_outdated_job_intelligence": (
        "Job Match was calculated from an earlier Job Intelligence "
        "snapshot of this job; recalculate it to refresh."
    ),
}

_ATS_STALE_MESSAGES = {
    "ats_outdated_engine": (
        "ATS Alignment was calculated by an earlier ATS engine version; "
        "recalculate it to refresh."
    ),
    "ats_legacy_source": (
        "ATS Alignment was calculated before Requirement Intelligence "
        "existed for this job; recalculate it to refresh."
    ),
    "ats_outdated_requirement_intelligence": (
        "ATS Alignment was calculated from an earlier Requirement "
        "Intelligence snapshot; recalculate it to refresh."
    ),
    "ats_outdated_job_intelligence": (
        "ATS Alignment was calculated from an earlier Job Intelligence "
        "snapshot of this job; recalculate it to refresh."
    ),
}


def _analysis_explanation(
    candidate: PriorityCandidate,
) -> tuple[list[PriorityReason], list[BlockingFactor], bool | None, bool | None]:
    reasons: list[PriorityReason] = []
    blocking: list[BlockingFactor] = []
    match_current: bool | None = None
    ats_current: bool | None = None

    match = candidate.job_match
    ats = candidate.ats_alignment

    if match is None:
        blocking.append(
            BlockingFactor(
                code="job_match_missing",
                source="job_match",
                message=(
                    "Job Match has not been calculated for this resume "
                    "version, so this job cannot be ordered by fit yet."
                ),
            )
        )
    else:
        reasons.append(
            PriorityReason(
                code="job_match_score",
                source="job_match",
                kind="evidence",
                message=f"Job Match {_percent(match.score)}%.",
            )
        )

        if match.must_have_total > 0:
            reasons.append(
                PriorityReason(
                    code="job_match_must_have",
                    source="job_match",
                    kind="evidence",
                    message=(
                        f"Job Match found {match.must_have_matched} of "
                        f"{match.must_have_total} required skills."
                    ),
                )
            )

        stale = job_match_stale_codes(match, candidate.latest_job_intelligence_id)
        match_current = not stale

        for code in stale:
            reasons.append(
                PriorityReason(
                    code=code,
                    source="job_match",
                    kind="caution",
                    message=_JOB_MATCH_STALE_MESSAGES[code],
                )
            )

    if ats is None:
        reasons.append(
            PriorityReason(
                code="ats_missing",
                source="ats_alignment",
                kind="caution",
                message=(
                    "ATS Alignment has not been calculated for this resume "
                    "version."
                ),
            )
        )
    else:
        message = f"ATS Alignment {_percent(ats.overall_score)}%"

        if ats.must_have_total > 0:
            message += (
                f" - {ats.must_have_matched} of {ats.must_have_total} "
                f"must-have requirements demonstrated"
            )

        reasons.append(
            PriorityReason(
                code="ats_score",
                source="ats_alignment",
                kind="evidence",
                message=f"{message}.",
            )
        )

        stale = ats_stale_codes(
            ats,
            candidate.latest_job_intelligence_id,
            candidate.latest_requirement_intelligence_id,
        )
        ats_current = not stale

        for code in stale:
            reasons.append(
                PriorityReason(
                    code=code,
                    source="ats_alignment",
                    kind="caution",
                    message=_ATS_STALE_MESSAGES[code],
                )
            )

    return reasons, blocking, match_current, ats_current


def _build_result(
    candidate: PriorityCandidate,
    state: PriorityState,
    rank: int | None,
) -> PriorityResult:
    reasons, blocking = _eligibility_explanation(candidate)

    match_current: bool | None = None
    ats_current: bool | None = None

    # An excluded job's scores are deliberately not offered as reasons:
    # nothing about them can change its place, and presenting them next
    # to an exclusion would suggest otherwise. They stay available on the
    # job's own Match/ATS results.
    if state != PriorityState.EXCLUDED:
        (
            analysis_reasons,
            analysis_blocking,
            match_current,
            ats_current,
        ) = _analysis_explanation(candidate)
        reasons.extend(analysis_reasons)
        blocking.extend(analysis_blocking)

    return PriorityResult(
        job_id=candidate.job_id,
        state=state,
        rank=rank,
        eligibility_status=candidate.eligibility.status.value,
        reasons=reasons,
        blocking_factors=blocking,
        job_match_current=match_current,
        ats_alignment_current=ats_current,
    )
