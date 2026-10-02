"""
Competitive intelligence keyed on PRIMARY completion dates — the "who reads out
when" view. Aggregates a single 1000-study pull into a sponsor leaderboard, a
readout timeline (by quarter), and an upcoming-readouts list.
"""
import dataclasses
import datetime
from fastapi import APIRouter, Depends, Query
from collections import defaultdict
from typing import Optional
from services import analytics as an, status as st
from services.datasets import Filters
from routers._common import common_filters, analyse

router = APIRouter()


_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _bucket(date: str, granularity: str) -> Optional[tuple]:
    """Bucket a 'YYYY-MM-DD'/'YYYY-MM' date into (sort_key, display_label) for the
    chosen granularity, so the Readout... trial-completion timeline can be viewed
    monthly, bi-monthly, or quarterly."""
    if not date or len(date) < 7:
        return None
    try:
        y, m = int(date[:4]), int(date[5:7])
    except ValueError:
        return None
    if granularity == "month":
        return f"{y}-{m:02d}", f"{_MONTH_ABBR[m]} {y}"
    if granularity == "bimonth":
        b = (m - 1) // 2  # 0..5
        start_m, end_m = b * 2 + 1, b * 2 + 2
        return f"{y}-{b:02d}", f"{_MONTH_ABBR[start_m]}–{_MONTH_ABBR[end_m]} {y}"
    # default: quarter
    q = (m - 1) // 3 + 1
    return f"{y}-{q}", f"{y} Q{q}"


def _window(frm: Optional[str], to: Optional[str]):
    def start(s):
        d = an.period_end(s)
        if not d:
            return None
        parts = s.split("-")
        return datetime.date(d.year, int(parts[1]) if len(parts) > 1 else 1, int(parts[2][:2]) if len(parts) > 2 else 1)
    return (start(frm) if frm else None), (an.period_end(to) if to else None)


def _counts(s: dict, today: datetime.date, lo, hi):
    """Does this trial's primary-completion date belong in the chosen window? A FUTURE date
    only counts for a trial that can still complete (not withdrawn/terminated/completed/
    suspended/stale) and is an estimate; a PAST date is history and counts as-is."""
    pcd = s.get("primaryCompletionDate")
    end = an.period_end(pcd)
    if end is None:
        return False
    if lo and end < lo:
        return False
    if hi and end > hi:
        return False
    if st.norm(s.get("status")) == "WITHDRAWN":
        return False
    if end >= today:
        return an.upcoming_completion(s, today) is not None
    return True


def _compute(studies: list, granularity: str, frm: Optional[str], to: Optional[str], today: datetime.date = None) -> dict:
    today = today or datetime.date.today()
    lo, hi = _window(frm, to)
    windowed = bool(frm or to)
    in_window = [s for s in studies if _counts(s, today, lo, hi)] if windowed else studies

    # ── Sponsor leaderboard ──────────────────────────────────────────────
    sponsors: dict = {}
    for s in studies:
        name = (s.get("sponsor") or {}).get("name") or "Unknown"
        cls = (s.get("sponsor") or {}).get("class") or "OTHER"
        e = sponsors.setdefault(name, {
            "sponsor": name, "class": cls, "trials": 0,
            "phases": defaultdict(int), "statuses": defaultdict(int),
            "enrollment": 0, "lateStage": 0,
        })
        e["trials"] += 1
        e["phases"][an.phase_key(s)] += 1
        if an.is_late_stage(s):
            e["lateStage"] += 1          # once per trial
        e["statuses"][s.get("status") or "Unknown"] += 1
        enroll = (s.get("enrollment") or {}).get("count")
        if enroll:
            e["enrollment"] += enroll

    leaderboard = sorted(sponsors.values(), key=lambda x: (-x["trials"], -x["lateStage"]))[:15]
    for e in leaderboard:
        e["phases"] = dict(e["phases"])
        e["statuses"] = dict(e["statuses"])

    # ── Completion timeline (by month / bi-month / quarter) ──────────────
    timeline: dict = {}
    for s in in_window:
        bucket = _bucket(s.get("primaryCompletionDate") or "", granularity)
        if bucket:
            key, label = bucket
            e = timeline.setdefault(key, {"period": label, "count": 0})
            e["count"] += 1
    timeline_sorted = [v for k, v in sorted(timeline.items(), key=lambda kv: kv[0])]

    # ── Readouts list (soonest first) ────────────────────────────────────
    # Default view = genuinely UPCOMING: still-active trials with an estimated date that
    # is still ahead. When the user picks an explicit completion window we show whatever
    # falls inside it (that is what they asked for), history included.
    rows = []
    for s in in_window:
        pcd = s.get("primaryCompletionDate")
        if not pcd:
            continue
        if not windowed and an.upcoming_completion(s, today) is None:
            continue
        rows.append({
            "nctId": s["nctId"], "title": s.get("title", ""),
            "sponsor": (s.get("sponsor") or {}).get("name", ""),
            "sponsorClass": (s.get("sponsor") or {}).get("class", ""),
            "phase": an.phase_key(s),
            "status": s.get("status", ""),
            "enrollment": (s.get("enrollment") or {}).get("count"),
            "primaryCompletionDate": pcd,
            "primaryCompletionType": s.get("primaryCompletionType") or None,
            "countryCount": s.get("countryCount", 0),
        })
    rows.sort(key=lambda r: r["primaryCompletionDate"])

    return {
        "leaderboard": leaderboard,
        "timeline": timeline_sorted,
        "readouts": rows[:80],
        "readoutCount": len(rows),
        "readoutMode": "window" if windowed else "upcoming",
        "phaseLabels": an.PHASE_LABEL,
    }


@router.get("/")
async def get_competition(
    f: Filters = Depends(common_filters),
    granularity: str = Query("quarter", pattern="^(month|bimonth|quarter)$"),
    completionFrom: Optional[str] = Query(None),
    completionTo: Optional[str] = Query(None),
):
    # The completion window is applied here, NOT as a registry filter: the window is part of
    # the view, so every window edit reuses the same stored dataset instead of triggering a
    # second full retrieval.
    base = dataclasses.replace(f, completion_from=None, completion_to=None)
    today = datetime.date.today()
    out = await analyse(base, "competition",
                        lambda s: _compute(s, granularity, completionFrom, completionTo, today),
                        (granularity, completionFrom, completionTo, today.isoformat()))
    return {**out, "totalCount": out["coverage"]["total"]}
