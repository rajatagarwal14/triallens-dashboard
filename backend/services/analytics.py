"""
Small shared definitions so every page uses the SAME meaning for the same word.
(Previously the Landscape pie counted a Phase 2/3 trial twice, while Research and
Competition counted it once as "Phase 2", and "upcoming" included finished trials.)
"""
import calendar
import datetime
from statistics import median as _median
from typing import Iterable, List, Optional

from services import status as st

# ── Phases ──────────────────────────────────────────────────────────────────
# One trial = ONE category. A trial registered as PHASE2+PHASE3 is "Phase 2/3", not
# half-counted in each, so slice totals equal trial counts on every page.
PHASE_ORDER = ["EARLY_PHASE1", "PHASE1", "PHASE1/PHASE2", "PHASE2", "PHASE2/PHASE3",
               "PHASE3", "PHASE4", "NA"]
PHASE_LABEL = {
    "EARLY_PHASE1": "Early Phase I", "PHASE1": "Phase I", "PHASE1/PHASE2": "Phase I/II",
    "PHASE2": "Phase II", "PHASE2/PHASE3": "Phase II/III", "PHASE3": "Phase III",
    "PHASE4": "Phase IV", "NA": "N/A",
}
_RANK = {"EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4, "NA": 9}


def phase_key(study: dict) -> str:
    phases = [p for p in (study.get("phases") or []) if p]
    if not phases:
        return "NA"                       # observational / unphased studies
    if len(phases) == 1:
        return phases[0]
    return "/".join(sorted(set(phases), key=lambda p: _RANK.get(p, 9)))


def is_late_stage(study: dict) -> bool:
    ph = study.get("phases") or []
    return "PHASE3" in ph or "PHASE4" in ph


# ── Dates ───────────────────────────────────────────────────────────────────
def period_end(date_str: Optional[str]) -> Optional[datetime.date]:
    """Last day of the period a registry date refers to. CT.gov dates are "YYYY",
    "YYYY-MM" or "YYYY-MM-DD"; a month-precision "2026-10" means "sometime in October",
    so on 3 Oct it is still ahead of us."""
    if not date_str:
        return None
    parts = date_str.strip().split("-")
    try:
        y = int(parts[0])
        if len(parts) == 1:
            return datetime.date(y, 12, 31)
        m = int(parts[1])
        if len(parts) == 2:
            return datetime.date(y, m, calendar.monthrange(y, m)[1])
        return datetime.date(y, m, int(parts[2][:2]))
    except (ValueError, IndexError):
        return None


def add_months(d: datetime.date, months: int) -> datetime.date:
    idx = d.year * 12 + (d.month - 1) + months
    y, m = divmod(idx, 12)
    m += 1
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def months_between(start: Optional[str], end: Optional[str]) -> Optional[int]:
    """Whole months from a start date to an end date, or None when unusable/negative."""
    try:
        sy, sm = int(start[:4]), int(start[5:7]) if len(start) >= 7 else 1
        ey, em = int(end[:4]), int(end[5:7]) if len(end) >= 7 else 1
    except (ValueError, IndexError, TypeError):
        return None
    m = (ey - sy) * 12 + (em - sm)
    return m if 0 <= m <= 240 else None


def upcoming_completion(study: dict, today: datetime.date) -> Optional[datetime.date]:
    """Date of a FUTURE primary completion, or None if this study should not be counted
    as an upcoming readout. Requires all of: a status that can still complete (not
    completed / terminated / withdrawn / suspended / unknown), an ESTIMATED (not
    ACTUAL) date, and a period that has not already ended."""
    if st.norm(study.get("status")) not in st.PENDING_COMPLETION:
        return None
    if (study.get("primaryCompletionType") or "").upper() == "ACTUAL":
        return None
    end = period_end(study.get("primaryCompletionDate"))
    return end if end and end >= today else None


# ── Statistics ──────────────────────────────────────────────────────────────
def median(values: Iterable[float]) -> Optional[float]:
    vals: List[float] = [v for v in values if v is not None]
    return _median(vals) if vals else None
