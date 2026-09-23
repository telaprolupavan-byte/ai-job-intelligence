"""AJI-025 - the pure, DB-free Job Priority Ranking engine.

Eligibility inputs come from the real services.eligibility engine rather
than hand-built results, so these tests exercise priority against the
authoritative ELIGIBLE / INELIGIBLE / UNKNOWN semantics.
"""

import random
from dataclasses import fields
from datetime import datetime

import pytest

from services.ats_alignment.engine import ENGINE_VERSION as ATS_ENGINE_VERSION
from services.eligibility import (
    JobEligibilitySignals,
    UserEligibilityCriteria,
    evaluate_eligibility,
)
from services.job_matching.scorer import ENGINE_VERSION as MATCH_ENGINE_VERSION
from services.priority_ranking import (
    ENGINE_VERSION,
    ORDERING,
    AtsAlignmentEvidence,
    JobMatchEvidence,
    PriorityCandidate,
    PriorityResult,
    PriorityState,
    rank_jobs,
)


FULL_TIME_ONLY = UserEligibilityCriteria(allowed_employment_types=["full_time"])


def eligible_no_constraints():
    return evaluate_eligibility(UserEligibilityCriteria(), JobEligibilitySignals())


def eligible():
    return evaluate_eligibility(
        FULL_TIME_ONLY, JobEligibilitySignals(employment_type="full_time")
    )


def unknown():
    # The job does not disclose its employment type.
    return evaluate_eligibility(FULL_TIME_ONLY, JobEligibilitySignals())


def ineligible():
    return evaluate_eligibility(
        FULL_TIME_ONLY, JobEligibilitySignals(employment_type="contract")
    )


def match(score, *, ji="ji-1", engine=MATCH_ENGINE_VERSION, matched=2, total=3):
    return JobMatchEvidence(
        id=f"match-{score}",
        score=score,
        engine_version=engine,
        job_intelligence_id=ji,
        must_have_matched=matched,
        must_have_total=total,
    )


def ats(score, *, ji="ji-1", ri="ri-1", engine=ATS_ENGINE_VERSION, matched=3, total=5):
    return AtsAlignmentEvidence(
        id=f"ats-{score}",
        overall_score=score,
        engine_version=engine,
        job_intelligence_id=ji,
        requirement_intelligence_id=ri,
        must_have_matched=matched,
        must_have_total=total,
    )


def candidate(job_id, *, eligibility=None, job_match=None, ats_alignment=None,
              posting_date=None, latest_ji="ji-1", latest_ri="ri-1"):
    return PriorityCandidate(
        job_id=job_id,
        posting_date=posting_date,
        eligibility=eligibility or eligible(),
        job_match=job_match,
        ats_alignment=ats_alignment,
        latest_job_intelligence_id=latest_ji,
        latest_requirement_intelligence_id=latest_ri,
    )


def order(results):
    return [result.job_id for result in results]


def by_id(results):
    return {result.job_id: result for result in results}


def codes(result):
    return [reason.code for reason in result.reasons]


# ---------------------------------------------------------------------------
# Determinism, versioning, bounds
# ---------------------------------------------------------------------------


def test_engine_version_and_ordering_rule_are_declared():
    assert ENGINE_VERSION == "1.0.0"
    assert ORDERING == (
        "hard_eligibility",
        "job_match_score",
        "ats_alignment_score",
        "posting_date",
        "job_id",
    )


def _mixed_candidates():
    return [
        candidate("a", job_match=match(81), ats_alignment=ats(40)),
        candidate("b", job_match=match(81), ats_alignment=ats(70)),
        candidate("c", job_match=match(95)),
        candidate("d", eligibility=unknown(), job_match=match(99), ats_alignment=ats(99)),
        candidate("e", ats_alignment=ats(90)),
        candidate("f", eligibility=ineligible(), job_match=match(100), ats_alignment=ats(100)),
        candidate("g", job_match=match(12), ats_alignment=ats(12),
                  posting_date=datetime(2026, 9, 1)),
    ]


def test_same_inputs_produce_identical_results():
    assert rank_jobs(_mixed_candidates()) == rank_jobs(_mixed_candidates())


def test_input_order_never_changes_the_output():
    expected = rank_jobs(_mixed_candidates())

    for seed in range(20):
        shuffled = _mixed_candidates()
        random.Random(seed).shuffle(shuffled)
        assert rank_jobs(shuffled) == expected


def test_full_ordering_of_a_mixed_set():
    results = rank_jobs(_mixed_candidates())

    assert order(results) == ["c", "b", "a", "g", "d", "e", "f"]
    assert [r.rank for r in results] == [1, 2, 3, 4, 5, None, None]


def test_ranks_are_contiguous_and_bounded():
    results = rank_jobs(_mixed_candidates())
    ranks = [r.rank for r in results if r.rank is not None]

    assert ranks == list(range(1, len(ranks) + 1))
    assert all(
        r.rank is None
        for r in results
        if r.state in (PriorityState.NOT_READY, PriorityState.EXCLUDED)
    )


def test_priority_has_no_score_of_its_own():
    # Job Match and ATS Alignment are never blended into one number.
    names = {f.name for f in fields(PriorityResult)}
    assert not any("score" in name for name in names)


def test_empty_input():
    assert rank_jobs([]) == []


# ---------------------------------------------------------------------------
# Hard Eligibility gate
# ---------------------------------------------------------------------------


def test_ineligible_job_is_excluded_whatever_its_scores():
    results = by_id(rank_jobs([
        candidate("perfect", eligibility=ineligible(),
                  job_match=match(100), ats_alignment=ats(100)),
        candidate("weak", job_match=match(5), ats_alignment=ats(5)),
    ]))

    excluded = results["perfect"]
    assert excluded.state == PriorityState.EXCLUDED
    assert excluded.rank is None
    assert excluded.eligibility_status == "ineligible"
    assert results["weak"].rank == 1


def test_excluded_job_is_explained_by_its_failed_constraint_only():
    result = rank_jobs([
        candidate("x", eligibility=ineligible(),
                  job_match=match(100), ats_alignment=ats(100)),
    ])[0]

    assert [f.code for f in result.blocking_factors] == ["eligibility_failed"]
    assert result.blocking_factors[0].message == ineligible().reasons[0]
    assert codes(result) == ["eligibility_ineligible"]
    assert result.job_match_current is None
    assert result.ats_alignment_current is None


def test_eligible_jobs_rank():
    result = rank_jobs([candidate("x", job_match=match(60), ats_alignment=ats(60))])[0]

    assert result.state == PriorityState.RANKED
    assert result.rank == 1
    assert result.eligibility_status == "eligible"
    assert result.blocking_factors == []


def test_unknown_stays_unknown_and_follows_every_eligible_job():
    results = rank_jobs([
        candidate("unknown-high", eligibility=unknown(),
                  job_match=match(99), ats_alignment=ats(99)),
        candidate("eligible-low", job_match=match(10), ats_alignment=ats(10)),
    ])

    assert order(results) == ["eligible-low", "unknown-high"]
    unknown_result = results[1]
    assert unknown_result.eligibility_status == "unknown"
    assert unknown_result.state == PriorityState.RANKED
    assert unknown_result.rank == 2
    assert "eligibility_unknown" in codes(unknown_result)
    # The engine's own check reason is quoted, never paraphrased.
    unknown_messages = [
        r.message for r in unknown_result.reasons
        if r.code == "eligibility_unknown_check"
    ]
    assert unknown_messages == ["Job does not disclose an employment type."]


def test_unknown_jobs_are_ordered_among_themselves_by_job_match():
    results = rank_jobs([
        candidate("u-low", eligibility=unknown(), job_match=match(20)),
        candidate("u-high", eligibility=unknown(), job_match=match(70)),
    ])

    assert order(results) == ["u-high", "u-low"]


def test_eligibility_explanations_quote_passed_checks():
    result = rank_jobs([candidate("x", job_match=match(50), ats_alignment=ats(50))])[0]

    assert codes(result)[:2] == ["eligibility_eligible", "eligibility_pass"]
    assert result.reasons[1].message == "Employment type 'full_time' is accepted."


def test_no_configured_constraints_is_said_plainly():
    result = rank_jobs([
        candidate("x", eligibility=eligible_no_constraints(),
                  job_match=match(50), ats_alignment=ats(50)),
    ])[0]

    assert codes(result)[0] == "eligibility_no_constraints"
    assert "eligibility_pass" not in codes(result)


# ---------------------------------------------------------------------------
# Job Match primary, ATS tie-break, listing order
# ---------------------------------------------------------------------------


def test_job_match_orders_eligible_jobs():
    results = rank_jobs([
        candidate("low", job_match=match(40), ats_alignment=ats(99)),
        candidate("high", job_match=match(80), ats_alignment=ats(10)),
    ])

    # A higher ATS score never lifts a job over a higher Job Match.
    assert order(results) == ["high", "low"]


def test_ats_only_breaks_exact_job_match_ties():
    results = rank_jobs([
        candidate("a", job_match=match(75), ats_alignment=ats(50)),
        candidate("b", job_match=match(75), ats_alignment=ats(90)),
    ])

    assert order(results) == ["b", "a"]


def test_missing_ats_only_matters_inside_a_tie():
    results = rank_jobs([
        candidate("tie-no-ats", job_match=match(75)),
        candidate("tie-ats", job_match=match(75), ats_alignment=ats(1)),
        candidate("higher-no-ats", job_match=match(76)),
        candidate("lower-ats", job_match=match(74), ats_alignment=ats(100)),
    ])

    assert order(results) == ["higher-no-ats", "tie-ats", "tie-no-ats", "lower-ats"]


def test_full_ties_fall_back_to_the_listing_order():
    results = rank_jobs([
        candidate("undated", job_match=match(50), ats_alignment=ats(50)),
        candidate("old", job_match=match(50), ats_alignment=ats(50),
                  posting_date=datetime(2026, 1, 1)),
        candidate("new", job_match=match(50), ats_alignment=ats(50),
                  posting_date=datetime(2026, 9, 1)),
        candidate("aaa", job_match=match(50), ats_alignment=ats(50)),
    ])

    assert order(results) == ["new", "old", "aaa", "undated"]


# ---------------------------------------------------------------------------
# Missing / incomplete analysis - never fabricated
# ---------------------------------------------------------------------------


def test_missing_job_match_is_not_ready_not_low_priority():
    results = rank_jobs([
        candidate("zero", job_match=match(0), ats_alignment=ats(0)),
        candidate("no-match", ats_alignment=ats(95)),
    ])

    assert order(results) == ["zero", "no-match"]
    not_ready = results[1]
    assert not_ready.state == PriorityState.NOT_READY
    assert not_ready.rank is None
    assert [f.code for f in not_ready.blocking_factors] == ["job_match_missing"]
    # No Job Match value is invented for it.
    assert "job_match_score" not in codes(not_ready)
    assert not_ready.job_match_current is None


def test_not_ready_jobs_keep_their_eligibility_status():
    result = rank_jobs([
        candidate("x", eligibility=unknown(), ats_alignment=ats(50)),
    ])[0]

    assert result.state == PriorityState.NOT_READY
    assert result.eligibility_status == "unknown"


def test_missing_ats_is_partial_and_says_so():
    result = rank_jobs([candidate("x", job_match=match(70))])[0]

    assert result.state == PriorityState.PARTIAL
    assert result.rank == 1
    assert "ats_missing" in codes(result)
    assert "ats_score" not in codes(result)
    assert result.ats_alignment_current is None


def test_job_with_no_analysis_at_all_is_not_ready():
    result = rank_jobs([candidate("x")])[0]

    assert result.state == PriorityState.NOT_READY
    assert "job_match_score" not in codes(result)
    assert "ats_score" not in codes(result)


# ---------------------------------------------------------------------------
# Current vs. out-of-date analyses
# ---------------------------------------------------------------------------


def test_current_analyses_are_ranked_and_marked_current():
    result = rank_jobs([candidate("x", job_match=match(70), ats_alignment=ats(70))])[0]

    assert result.state == PriorityState.RANKED
    assert result.job_match_current is True
    assert result.ats_alignment_current is True


@pytest.mark.parametrize(
    "kwargs, expected_code",
    [
        ({"job_match": match(70, engine="0.9.0")}, "job_match_outdated_engine"),
        ({"job_match": match(70, ji=None)}, "job_match_legacy_source"),
        ({"job_match": match(70, ji="ji-old")}, "job_match_outdated_job_intelligence"),
    ],
)
def test_out_of_date_job_match_is_partial_with_a_caution(kwargs, expected_code):
    result = rank_jobs([candidate("x", ats_alignment=ats(70), **kwargs)])[0]

    assert result.state == PriorityState.PARTIAL
    assert result.rank == 1
    assert result.job_match_current is False
    assert expected_code in codes(result)


@pytest.mark.parametrize(
    "ats_kwargs, expected_code",
    [
        ({"engine": "1.0.0"}, "ats_outdated_engine"),
        ({"ri": None}, "ats_legacy_source"),
        ({"ri": "ri-old"}, "ats_outdated_requirement_intelligence"),
        ({"ji": "ji-old"}, "ats_outdated_job_intelligence"),
    ],
)
def test_out_of_date_ats_is_partial_with_a_caution(ats_kwargs, expected_code):
    result = rank_jobs([
        candidate("x", job_match=match(70), ats_alignment=ats(70, **ats_kwargs)),
    ])[0]

    assert result.state == PriorityState.PARTIAL
    assert result.ats_alignment_current is False
    assert expected_code in codes(result)


def test_out_of_date_evidence_still_orders_the_job():
    results = rank_jobs([
        candidate("stale-high", job_match=match(90, ji="ji-old"), ats_alignment=ats(50)),
        candidate("current-low", job_match=match(60), ats_alignment=ats(50)),
    ])

    assert order(results) == ["stale-high", "current-low"]


# ---------------------------------------------------------------------------
# Explanations come from the same inputs as the ordering
# ---------------------------------------------------------------------------


def test_explanations_quote_the_inputs():
    result = rank_jobs([
        candidate("x", job_match=match(82.5, matched=4, total=5),
                  ats_alignment=ats(71.2, matched=3, total=5)),
    ])[0]

    messages = {r.code: r.message for r in result.reasons}
    # Rounded half up, exactly like the Jobs UI's Math.round display.
    assert messages["job_match_score"] == "Job Match 83%."
    assert messages["job_match_must_have"] == "Job Match found 4 of 5 required skills."
    assert messages["ats_score"] == (
        "ATS Alignment 71% - 3 of 5 must-have requirements demonstrated."
    )
    assert all(r.kind == "evidence" for r in result.reasons)


def test_counts_are_omitted_when_there_is_nothing_to_count():
    result = rank_jobs([
        candidate("x", job_match=match(100, matched=0, total=0),
                  ats_alignment=ats(100, matched=0, total=0)),
    ])[0]

    messages = {r.code: r.message for r in result.reasons}
    assert "job_match_must_have" not in messages
    assert messages["ats_score"] == "ATS Alignment 100%."


def test_reason_sources_are_the_three_inputs_only():
    results = rank_jobs(_mixed_candidates())

    sources = {
        r.source for result in results for r in [*result.reasons, *result.blocking_factors]
    }
    assert sources <= {"eligibility", "job_match", "ats_alignment"}
