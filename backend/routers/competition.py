"""
Competitive intelligence keyed on PRIMARY completion dates — the "who reads out
when" view. Aggregates a single 1000-study pull into a sponsor leaderboard, a
readout timeline (by quarter), and an upcoming-readouts list.
"""
from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict
from services import ct_gov

router = APIRouter()


def _csv(v: Optional[str]):
    return v.split(",") if v else None


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


@router.get("/")
async def get_competition(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
    completionFrom: Optional[str] = Query(None),
    completionTo: Optional[str] = Query(None),
    granularity: str = Query("quarter", pattern="^(month|bimonth|quarter)$"),
):
    result = await ct_gov.search_studies(
        condition=condition, status=_csv(status), phases=_csv(phases),
        study_types=_csv(studyTypes), sponsor_classes=_csv(sponsorClasses),
        country=country, from_year=fromYear,
        completion_from=completionFrom, completion_to=completionTo,
        page_size=1000,
    )
    studies = result["studies"]

    # ── Sponsor leaderboard ──────────────────────────────────────────────
    sponsors: dict[str, dict] = {}
    for s in studies:
        name = s.get("sponsor", {}).get("name") or "Unknown"
        cls = s.get("sponsor", {}).get("class") or "OTHER"
        e = sponsors.setdefault(name, {
            "sponsor": name, "class": cls, "trials": 0,
            "phases": defaultdict(int), "statuses": defaultdict(int),
            "enrollment": 0, "lateStage": 0,
        })
        e["trials"] += 1
        for ph in (s.get("phases") or ["NA"]):
            e["phases"][ph] += 1
            if ph in ("PHASE3", "PHASE4"):
                e["lateStage"] += 1
        e["statuses"][s.get("status", "Unknown")] += 1
        enroll = (s.get("enrollment") or {}).get("count")
        if enroll:
            e["enrollment"] += enroll

    leaderboard = sorted(sponsors.values(), key=lambda x: (-x["trials"], -x["lateStage"]))[:15]
    for e in leaderboard:
        e["phases"] = dict(e["phases"])
        e["statuses"] = dict(e["statuses"])

    # ── Completion timeline (by month / bi-month / quarter) ──────────────
    timeline: dict[str, dict] = {}
    for s in studies:
        bucket = _bucket(s.get("primaryCompletionDate") or "", granularity)
        if bucket:
            key, label = bucket
            e = timeline.setdefault(key, {"period": label, "count": 0})
            e["count"] += 1
    timeline_sorted = [v for k, v in sorted(timeline.items(), key=lambda kv: kv[0])]

    # ── Upcoming readouts (soonest primary completion first) ─────────────
    readouts = [
        {
            "nctId": s["nctId"], "title": s["title"],
            "sponsor": s.get("sponsor", {}).get("name", ""),
            "sponsorClass": s.get("sponsor", {}).get("class", ""),
            "phase": (s.get("phases") or ["NA"])[0],
            "status": s.get("status", ""),
            "enrollment": (s.get("enrollment") or {}).get("count"),
            "primaryCompletionDate": s.get("primaryCompletionDate"),
            "primaryCompletionType": s.get("primaryCompletionType"),
            "countryCount": s.get("countryCount", 0),
        }
        for s in studies if s.get("primaryCompletionDate")
    ]
    readouts.sort(key=lambda r: r["primaryCompletionDate"])

    total = result["totalCount"]
    analyzed = len(studies)
    return {
        "coverage": {"analyzed": analyzed, "total": total, "isComplete": analyzed >= total},
        "totalCount": total,
        "leaderboard": leaderboard,
        "timeline": timeline_sorted,
        "readouts": readouts[:80],
        "readoutCount": len(readouts),
    }
