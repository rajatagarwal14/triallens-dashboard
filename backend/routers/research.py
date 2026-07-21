"""
Strategy-oriented analytics for clinical planning: auto-generated insights, an
ACCURATE forward view of when trials are scheduled to read out (based on real
registered primary-completion dates, not a statistical projection), plus
duration, discontinuation, enrollment-size and enrollment-pace benchmarks and
geographic activity. All derived from the same 1000-study pull.
"""
import datetime
from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict
from statistics import median
from services import ct_gov

router = APIRouter()

_PHASE_ORDER = ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"]
_PHASE_LABEL = {
    "EARLY_PHASE1": "Early Phase 1", "PHASE1": "Phase 1", "PHASE2": "Phase 2",
    "PHASE3": "Phase 3", "PHASE4": "Phase 4", "NA": "N/A",
}


def _csv(v: Optional[str]):
    return v.split(",") if v else None


def _months_between(start: str, end: str) -> Optional[int]:
    try:
        sy, sm = int(start[:4]), int(start[5:7]) if len(start) >= 7 else 1
        ey, em = int(end[:4]), int(end[5:7]) if len(end) >= 7 else 1
    except (ValueError, IndexError):
        return None
    m = (ey - sy) * 12 + (em - sm)
    return m if m >= 0 else None


@router.get("/")
async def get_research(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
):
    result = await ct_gov.search_studies(
        condition=condition, status=_csv(status), phases=_csv(phases),
        study_types=_csv(studyTypes), sponsor_classes=_csv(sponsorClasses),
        country=country, from_year=fromYear, page_size=1000,
    )
    studies = result["studies"]
    n = len(studies)
    this_year = datetime.date.today().year

    # ── Phase-3 momentum (for the competitive-heat insight) ──────────────
    phase3_by_year: dict[int, int] = defaultdict(int)
    for s in studies:
        sd = s.get("startDate")
        if sd and sd[:4].isdigit():
            y = int(sd[:4])
            if 2005 <= y <= 2030 and "PHASE3" in (s.get("phases") or []):
                phase3_by_year[y] += 1
    hist_years = sorted(y for y in phase3_by_year if y <= this_year - 1)

    # ── Expected trial readouts by year (ACCURATE — real scheduled dates) ─
    # Count trials whose PRIMARY completion is registered in each upcoming year,
    # split by phase. This is a forward count of already-scheduled readouts, NOT
    # an extrapolation — it tells a planner when competitor data will land.
    HORIZON = 5
    readout_years = list(range(this_year, this_year + HORIZON))
    readout_by_year: dict[int, dict] = {
        y: {"year": y, **{p: 0 for p in _PHASE_ORDER}} for y in readout_years
    }
    upcoming_total = upcoming_phase3 = 0
    for s in studies:
        pcd = s.get("primaryCompletionDate")
        if not (pcd and pcd[:4].isdigit()):
            continue
        y = int(pcd[:4])
        if y in readout_by_year:
            p = (s.get("phases") or ["NA"])[0]
            if p not in _PHASE_ORDER:
                p = "NA"
            readout_by_year[y][p] += 1
            # "upcoming" = within the next 24 months
            if y <= this_year + 1:
                upcoming_total += 1
                if p == "PHASE3":
                    upcoming_phase3 += 1
    for y in readout_by_year:
        readout_by_year[y]["total"] = sum(readout_by_year[y][p] for p in _PHASE_ORDER)
    readout_forecast = [readout_by_year[y] for y in readout_years]
    # phases actually present (non-zero anywhere), for the chart legend/stacking
    readout_phases = [p for p in _PHASE_ORDER
                      if any(readout_by_year[y][p] for y in readout_years)]

    # ── Time-to-completion (months, start → primary completion) by phase ─
    dur_by_phase: dict[str, list] = defaultdict(list)
    for s in studies:
        start, pcd = s.get("startDate"), s.get("primaryCompletionDate")
        if start and pcd:
            m = _months_between(start, pcd)
            if m is not None and m <= 240:
                dur_by_phase[(s.get("phases") or ["NA"])[0]].append(m)
    time_to_completion = [
        {"phase": _PHASE_LABEL.get(p, p), "medianMonths": round(median(v)), "n": len(v)}
        for p in _PHASE_ORDER if (v := dur_by_phase.get(p))
    ]

    # ── Trial discontinuation by phase (terminated + withdrawn + suspended) ─
    # NB: this is TRIAL-level early-stop, the correct clinical-ops term is
    # "discontinuation/termination" — NOT "attrition" (which means patient dropout).
    total_by_phase: dict[str, int] = defaultdict(int)
    dropped_by_phase: dict[str, int] = defaultdict(int)
    dead = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
    for s in studies:
        p = (s.get("phases") or ["NA"])[0]
        total_by_phase[p] += 1
        if s.get("status") in dead:
            dropped_by_phase[p] += 1
    discontinuation = [
        {"phase": _PHASE_LABEL.get(p, p), "rate": round(dropped_by_phase[p] / total_by_phase[p] * 100),
         "dropped": dropped_by_phase[p], "total": total_by_phase[p]}
        for p in _PHASE_ORDER if total_by_phase.get(p)
    ]

    # ── Enrollment size benchmarks (median target) by phase ──────────────
    enroll_by_phase: dict[str, list] = defaultdict(list)
    # ── Enrollment PACE: patients per site per month (feasibility) by phase ─
    pace_by_phase: dict[str, list] = defaultdict(list)
    for s in studies:
        p = (s.get("phases") or ["NA"])[0]
        c = (s.get("enrollment") or {}).get("count")
        if c and c > 0:
            enroll_by_phase[p].append(c)
            sites = s.get("siteCount") or 0
            mo = _months_between(s.get("startDate") or "", s.get("primaryCompletionDate") or "")
            if sites > 0 and mo and mo > 0:
                rate = c / sites / mo
                if 0 < rate <= 50:  # drop implausible outliers
                    pace_by_phase[p].append(rate)
    enrollment_benchmarks = [
        {"phase": _PHASE_LABEL.get(p, p), "median": round(median(v)), "n": len(v)}
        for p in _PHASE_ORDER if (v := enroll_by_phase.get(p))
    ]
    enrollment_rate = [
        {"phase": _PHASE_LABEL.get(p, p), "perSiteMonth": round(median(v), 2), "n": len(v)}
        for p in _PHASE_ORDER if (v := pace_by_phase.get(p))
    ]

    # ── Geographic activity ──────────────────────────────────────────────
    country_counts: dict[str, int] = defaultdict(int)
    for s in studies:
        for c in (s.get("countries") or {}):
            if c and c != "Unknown":
                country_counts[c] += 1
    country_sorted = sorted(country_counts.items(), key=lambda kv: -kv[1])
    placements = sum(country_counts.values()) or 1
    top3_share = round(sum(c for _, c in country_sorted[:3]) / placements * 100)
    country_activity = {
        "top": [{"country": c, "trials": v} for c, v in country_sorted[:10]],
        "top3Share": top3_share,
        "totalCountries": len(country_counts),
    }

    # ── Auto-generated insights (plain-language, planner-oriented) ───────
    insights = []

    # 1. Upcoming trial completions — accurate, from registered completion dates
    if upcoming_total:
        insights.append({
            "kind": "trend", "title": "Upcoming trial completions",
            "detail": f"{upcoming_total} trial{'s' if upcoming_total != 1 else ''} in this indication "
                      f"{'are' if upcoming_total != 1 else 'is'} scheduled to reach primary completion in the next ~24 months"
                      + (f", including {upcoming_phase3} Phase 3 trial{'s' if upcoming_phase3 != 1 else ''}" if upcoming_phase3 else "")
                      + " — key competitor studies finishing soon.",
        })

    # 2. Phase 3 momentum (late-stage activity)
    p3_recent = sum(phase3_by_year[y] for y in hist_years[-3:]) if len(hist_years) >= 3 else 0
    p3_prior = sum(phase3_by_year[y] for y in hist_years[-6:-3]) if len(hist_years) >= 6 else 0
    if p3_prior > 0:
        chg = round((p3_recent - p3_prior) / p3_prior * 100)
        insights.append({
            "kind": "latestage", "title": "Late-stage (Phase 3) momentum",
            "detail": f"Phase 3 trial starts are {'up' if chg >= 0 else 'down'} {abs(chg)}% over the last 3 years "
                      f"vs the prior 3 — the late-stage pipeline is {'heating up' if chg >= 0 else 'cooling'}.",
        })

    # 3. Geographic concentration
    if country_activity["top"]:
        names = ", ".join(t["country"] for t in country_activity["top"][:3])
        insights.append({
            "kind": "geo", "title": "Geographic footprint",
            "detail": f"Trials are spread across {country_activity['totalCountries']} countries; the top 3 ({names}) "
                      f"account for {top3_share}% of activity — a {'concentrated' if top3_share >= 50 else 'broad'} footprint "
                      f"to weigh for country and site strategy.",
        })

    # 4. Enrollment feasibility (pace)
    p3_pace = next((e for e in enrollment_rate if e["phase"] == "Phase 3"), None) or (enrollment_rate[0] if enrollment_rate else None)
    if p3_pace:
        insights.append({
            "kind": "feasibility", "title": "Enrollment feasibility",
            "detail": f"{p3_pace['phase']} trials enrol a median of ~{p3_pace['perSiteMonth']} patients per site per month "
                      f"(n={p3_pace['n']}) — use this to size the number of sites and study timeline.",
        })

    # 5. Trial discontinuation risk (correct clinical term for early-stopped trials)
    if discontinuation:
        worst = max(discontinuation, key=lambda a: a["rate"])
        if worst["rate"] >= 5:
            insights.append({
                "kind": "risk", "title": "Trial discontinuation risk",
                "detail": f"{worst['phase']} has the highest early-discontinuation rate at {worst['rate']}% "
                          f"({worst['dropped']} of {worst['total']} trials terminated, withdrawn, or suspended before completion) "
                          f"— build risk buffer into planning here.",
            })

    # 6. Enrollment sizing
    if enrollment_benchmarks:
        p3 = next((e for e in enrollment_benchmarks if e["phase"] == "Phase 3"), None)
        if p3:
            insights.append({
                "kind": "enrollment", "title": "Enrollment size benchmark",
                "detail": f"Median Phase 3 target enrollment is ~{p3['median']:,} patients (n={p3['n']}) — "
                          f"a reference point for sizing your own study.",
            })

    total = result["totalCount"]
    return {
        "coverage": {"analyzed": n, "total": total, "isComplete": n >= total},
        "insights": insights,
        "readoutForecast": {
            "byYear": readout_forecast,
            "phases": readout_phases,
            "phaseLabels": {p: _PHASE_LABEL.get(p, p) for p in readout_phases},
            "upcomingTotal": upcoming_total,
            "upcomingPhase3": upcoming_phase3,
        },
        "timeToCompletion": time_to_completion,
        "discontinuation": discontinuation,
        "enrollmentBenchmarks": enrollment_benchmarks,
        "enrollmentRate": enrollment_rate,
        "countryActivity": country_activity,
    }
