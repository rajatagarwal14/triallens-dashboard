"""
Single source of truth for what a ClinicalTrials.gov status MEANS.

Status values are matched EXACTLY. Never substring-match: "NOT_YET_RECRUITING",
"ACTIVE_NOT_RECRUITING" and "NOT_RECRUITING" all contain the text "RECRUIT".
"""
from typing import Optional

# Actively taking participants right now.
ENROLLING = frozenset({"RECRUITING", "ENROLLING_BY_INVITATION"})

# Competing for patients now or imminently: enrolling, plus registered-but-not-yet-open.
COMPETING = frozenset({"RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"})

# Still expected to produce a primary-completion event in the future.
# (SUSPENDED trials are paused, not finished; UNKNOWN trials are stale registrations —
# neither is a reliable "upcoming completion", so they are excluded.)
PENDING_COMPLETION = frozenset({
    "RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING",
})

# Ended early or never ran.
DISCONTINUED = frozenset({"TERMINATED", "WITHDRAWN", "SUSPENDED"})


def norm(status: Optional[str]) -> str:
    return (status or "").strip().upper()


def is_enrolling(status: Optional[str]) -> bool:
    return norm(status) in ENROLLING


def location_is_enrolling(location_status: Optional[str], trial_status: Optional[str]) -> bool:
    """A site's own status wins. The trial-level status is only a FALLBACK for
    registrations that carry no per-location status — it must never override an
    explicit site status such as ACTIVE_NOT_RECRUITING."""
    loc = norm(location_status)
    return (loc in ENROLLING) if loc else is_enrolling(trial_status)
