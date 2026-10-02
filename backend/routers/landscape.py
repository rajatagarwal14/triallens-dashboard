from fastapi import APIRouter, Depends, Query
from typing import Optional
from services import ct_gov, prevalence as prev_svc, analytics as an, status as st
from services.datasets import Filters, manager
from routers._common import common_filters, analyse
from collections import defaultdict

router = APIRouter()


def _csv(v: Optional[str]) -> Optional[list]:
    return v.split(",") if v else None


def _landscape(studies: list) -> dict:
    phase_counts: dict = defaultdict(int)
    status_counts: dict = defaultdict(int)
    sponsor_class_counts: dict = defaultdict(int)
    country_counts: dict = defaultdict(int)
    year_counts: dict = defaultdict(int)
    year_enroll: dict = defaultdict(list)
    year_by_phase: dict = defaultdict(lambda: defaultdict(int))
    year_by_sponsor: dict = defaultdict(lambda: defaultdict(int))
    sizes: list = []

    for s in studies:
        pk = an.phase_key(s)                      # one trial → one phase bucket
        phase_counts[pk] += 1
        status_counts[s.get("status") or "Unknown"] += 1
        sp_class = (s.get("sponsor") or {}).get("class") or "Unknown"
        sponsor_class_counts[sp_class] += 1
        for c_name in (s.get("countries") or {}):  # trials per country, not sites
            country_counts[c_name] += 1
        count = (s.get("enrollment") or {}).get("count")
        start = s.get("startDate")
        if start and start[:4].isdigit():
            year = start[:4]
            year_counts[year] += 1
            year_by_phase[year][pk] += 1
            year_by_sponsor[year][sp_class] += 1
            if count:
                year_enroll[year].append(count)
        if count:
            sizes.append(count)

    return {
        "phaseCounts": dict(phase_counts),
        "phaseLabels": {k: an.PHASE_LABEL.get(k, k) for k in phase_counts},
        "statusCounts": dict(status_counts),
        "sponsorClassCounts": dict(sponsor_class_counts),
        "countryCounts": dict(sorted(country_counts.items(), key=lambda x: -x[1])[:30]),
        "yearCounts": dict(sorted(year_counts.items())),
        # Median trial size per start year (means are dominated by a few huge trials).
        "enrollmentByYear": {y: round(an.median(v)) for y, v in sorted(year_enroll.items())},
        "yearByPhase": {y: dict(v) for y, v in sorted(year_by_phase.items())},
        "yearBySponsor": {y: dict(v) for y, v in sorted(year_by_sponsor.items())},
        "medianEnrollment": round(an.median(sizes)) if sizes else 0,
        "enrollmentN": len(sizes),
    }


@router.get("/")
async def get_landscape(f: Filters = Depends(common_filters)):
    snap = await manager.snapshot(f)
    payload = await manager.compute(snap, "landscape", (), _landscape)
    return {**payload, "totalCount": snap.total, "sampleSize": len(snap.studies),
            "coverage": snap.coverage}


GEO_SITES_PER_COUNTRY = 50


def _geo(studies: list, condition: Optional[str]) -> dict:
    country_data: dict = defaultdict(
        lambda: {"trialCount": 0, "siteCount": 0, "competingEnrollment": 0,
                 "sites": [], "_seen": set()})
    for s in studies:
        enroll = (s.get("enrollment") or {}).get("count") or 0
        # Only trials that are enrolling or about to are *current* demand for patients;
        # finished trials no longer compete for anyone.
        competing = st.norm(s.get("status")) in st.COMPETING
        for country, count in (s.get("countries") or {}).items():
            cd = country_data[country]
            cd["trialCount"] += 1
            cd["siteCount"] += count
            if competing:
                cd["competingEnrollment"] += enroll
        for site in s.get("sites") or []:
            cd = country_data[site.get("country") or "Unknown"]
            if len(cd["sites"]) >= GEO_SITES_PER_COUNTRY:
                continue
            key = (site.get("facility"), site.get("lat"), site.get("lon"))
            if key in cd["_seen"]:
                continue
            cd["_seen"].add(key)
            cd["sites"].append(site)

    prev = prev_svc.usable(prev_svc.lookup(condition)) if condition else None
    for cname, cdata in country_data.items():
        cdata.pop("_seen", None)
        pool = (prev or {}).get(cname, {}).get("prevalence") if prev else None
        cdata["prevalence"] = pool
        cdata["competitionIntensity"] = (
            round(cdata["competingEnrollment"] / pool * 100_000, 1) if pool else None)

    return {
        "hasPrevalence": prev is not None,
        "competitionNote": ("Competing enrollment sums the target size of trials that are recruiting, "
                            "enrolling by invitation or not yet recruiting, counting each trial's full "
                            "target in every country it runs. It is a demand-pressure proxy, not an "
                            "allocated per-country share."),
        "sitesPerCountryCap": GEO_SITES_PER_COUNTRY,
        "countries": [{"country": k, **v}
                      for k, v in sorted(country_data.items(), key=lambda x: -x[1]["trialCount"])],
    }


@router.get("/geo")
async def get_geo(f: Filters = Depends(common_filters)):
    return await analyse(f, "geo", lambda studies: _geo(studies, f.condition), (f.condition,))


def _age_years(value: Optional[str]) -> Optional[float]:
    """"18 Years" → 18, "6 Months" → 0.5, "N/A"/missing → None."""
    import re
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(year|month|week|day)", value or "", re.I)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2).lower()
    years = n / {"year": 1, "month": 12, "week": 52, "day": 365}[unit]
    return int(years) if years == int(years) else round(years, 2)


@router.get("/eligibility/{nct_id}")
async def get_eligibility(nct_id: str):
    from services import eligibility_nlp
    study = await ct_gov.get_study(nct_id)
    criteria = study.get("eligibility", {}).get("criteria", "")
    extracted = eligibility_nlp.extract(criteria)
    # The registry publishes structured min/max ages ("18 Years", "N/A"); prefer them to
    # regex-guessing from free text, which missed most protocols.
    elig = study.get("eligibility") or {}
    extracted["ageRange"] = {"min": _age_years(elig.get("minimumAge")),
                             "max": _age_years(elig.get("maximumAge"))}

    # ── Restrictiveness vs the market ────────────────────────────────────
    # Score this protocol's complexity against peer trials in the same
    # condition, so the user sees "more restrictive than X% of the field".
    market = None
    conds = study.get("conditions") or []
    my_score = extracted.get("complexityScore")
    if conds and my_score is not None:
        try:
            import asyncio
            from statistics import median as _median
            peers = await ct_gov.get_studies_for_similarity(conds[0], limit=60)

            # CPU-bound regex extraction over ~60 peers — run off the event loop so
            # it doesn't block other requests.
            def _peer_scores() -> list:
                out = []
                for p in peers:
                    if p.get("nctId") == nct_id:
                        continue
                    c = (p.get("eligibility") or {}).get("criteria", "")
                    if c:
                        out.append(eligibility_nlp.extract(c).get("complexityScore", 0))
                return out

            scores = await asyncio.to_thread(_peer_scores)
            if len(scores) >= 5:
                below = sum(1 for s in scores if s < my_score)
                market = {
                    "condition": conds[0],
                    "peerCount": len(scores),
                    "percentile": round(below / len(scores) * 100),
                    "marketMedian": round(_median(scores), 1),
                    "marketAvg": round(sum(scores) / len(scores), 1),
                    "myScore": my_score,
                }
        except Exception:
            market = None  # never let benchmarking break the core response

    return {"nctId": nct_id, "extracted": extracted, "study": study, "market": market}


@router.get("/prevalence")
async def get_prevalence(condition: str = Query(...)):
    data = prev_svc.lookup(condition)
    if not data or prev_svc.is_placeholder(data):
        # No disease-specific figures. We deliberately return NO numbers rather than a
        # generic catch-all rate: an invented ~250/100k looks like a measurement and
        # silently drives the prevalence map, competition intensity and white-space.
        return {"condition": condition, "found": False, "countries": {},
                "method": "none", "modeled": False, "placeholder": True,
                "confidence": "none", "matchType": "none",
                "note": ("No disease-specific prevalence model exists for this indication, so no "
                         "estimate is shown. Enter your own figures in the White-Space panel."),
                "warning": "No prevalence estimate available for this indication."}

    first = next(iter(data.values()))
    modeled = any(v.get("method") == "modeled" for v in data.values())
    match_type = first.get("matchType", "exact")
    warning = None
    if match_type == "parent":
        warning = first.get("note")
    elif modeled:
        warning = ("Modelled from a disease-category rate × population — directional only. "
                   "Check against a primary source before relying on it.")
    return {
        "condition": condition,
        "found": True,
        "method": "modeled" if modeled else "curated",
        "modeled": modeled,
        "placeholder": False,
        "confidence": first.get("confidence", "modeled"),
        "matchType": match_type,
        "matchedIndication": first.get("matchedIndication") or first.get("category"),
        "warning": warning,
        "countries": data,
        "note": ("Modeled estimate — TrialLens epidemiology engine (prevalence rate × population). "
                 "No AI/API key required; override any country."
                 if modeled else
                 "Curated estimates — GLOBOCAN 2022 / GBD 2021 / published literature."),
    }
