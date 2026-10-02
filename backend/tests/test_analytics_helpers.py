import datetime
from services import analytics as a
from conftest import make_study

TODAY = datetime.date(2026, 10, 3)


def test_phase_key_counts_a_trial_once():
    assert a.phase_key({"phases": ["PHASE2", "PHASE3"]}) == "PHASE2/PHASE3"
    assert a.phase_key({"phases": ["PHASE3", "PHASE2"]}) == "PHASE2/PHASE3"     # order-independent
    assert a.phase_key({"phases": []}) == "NA"                                   # finding 9
    assert a.phase_key({}) == "NA"
    assert a.phase_key({"phases": ["PHASE1"]}) == "PHASE1"


def test_period_end_uses_end_of_precision_window():
    assert a.period_end("2026-10") == datetime.date(2026, 10, 31)
    assert a.period_end("2026") == datetime.date(2026, 12, 31)
    assert a.period_end("2026-02-10") == datetime.date(2026, 2, 10)
    assert a.period_end("garbage") is None and a.period_end(None) is None


def test_upcoming_requires_a_pending_status_an_estimated_date_and_a_future_period():
    ok = make_study(status="RECRUITING", primaryCompletionDate="2027-06", primaryCompletionType="ESTIMATED")
    assert a.upcoming_completion(ok, TODAY) == datetime.date(2027, 6, 30)
    for status in ["COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED", "UNKNOWN"]:
        s = make_study(status=status, primaryCompletionDate="2027-06", primaryCompletionType="ESTIMATED")
        assert a.upcoming_completion(s, TODAY) is None, status                   # finding 6 + Fable #1
    done = make_study(status="ACTIVE_NOT_RECRUITING", primaryCompletionDate="2027-06", primaryCompletionType="ACTUAL")
    assert a.upcoming_completion(done, TODAY) is None
    past = make_study(status="RECRUITING", primaryCompletionDate="2026-01", primaryCompletionType="ESTIMATED")
    assert a.upcoming_completion(past, TODAY) is None                            # overdue ≠ upcoming
    this_month = make_study(status="RECRUITING", primaryCompletionDate="2026-10", primaryCompletionType="ESTIMATED")
    assert a.upcoming_completion(this_month, TODAY) is not None


def test_add_months_is_a_true_rolling_window():
    assert a.add_months(TODAY, 24) == datetime.date(2028, 10, 3)
    assert a.add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)
