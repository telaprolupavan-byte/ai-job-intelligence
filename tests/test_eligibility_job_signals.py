from services.eligibility.job_signals import extract_work_authorization_signals


def test_no_text_returns_all_unknown():
    signals = extract_work_authorization_signals(None)

    assert signals.sponsorship_available is None
    assert signals.authorization_required is False
    assert signals.citizenship_required is False
    assert signals.clearance_required is False


def test_detects_sponsorship_available():
    signals = extract_work_authorization_signals(
        "We are open to sponsoring visas for exceptional candidates."
    )

    assert signals.sponsorship_available is True


def test_detects_sponsorship_unavailable():
    signals = extract_work_authorization_signals(
        "We are unable to offer visa sponsorship for this role."
    )

    assert signals.sponsorship_available is False


def test_detects_authorization_required():
    signals = extract_work_authorization_signals(
        "Candidates must be authorized to work in the United States."
    )

    assert signals.authorization_required is True


def test_detects_citizenship_requirement():
    signals = extract_work_authorization_signals(
        "Applicants must be a U.S. citizen due to federal contract requirements."
    )

    assert signals.citizenship_required is True


def test_detects_security_clearance_requirement():
    signals = extract_work_authorization_signals(
        "Must hold an active Top Secret clearance."
    )

    assert signals.clearance_required is True


def test_unrelated_text_yields_no_signals():
    signals = extract_work_authorization_signals(
        "We build machine learning pipelines using Python and AWS."
    )

    assert signals.sponsorship_available is None
    assert signals.authorization_required is False
    assert signals.citizenship_required is False
    assert signals.clearance_required is False


def test_citizenship_preferred_is_not_interpreted_as_required():
    # "preferred" must never be conflated with "required" — a soft
    # preference stated by the employer is not an observable hard
    # requirement the engine may act on.
    signals = extract_work_authorization_signals(
        "U.S. citizenship is preferred but not required for this role."
    )

    assert signals.citizenship_required is False


def test_sponsorship_required_phrasing_is_not_interpreted_as_available():
    # Ambiguous/unexpected phrasing must never be guessed into
    # "available" — it should remain unknown (None) rather than being
    # misread as the opposite of what it might mean.
    signals = extract_work_authorization_signals(
        "Visa sponsorship required disclosures: none provided."
    )

    assert signals.sponsorship_available is None


def test_sponsorship_available_language_does_not_set_authorization_required():
    signals = extract_work_authorization_signals(
        "We are open to sponsoring visas for the right candidate."
    )

    assert signals.sponsorship_available is True
    assert signals.authorization_required is False
