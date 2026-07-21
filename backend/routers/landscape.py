from fastapi import APIRouter, Query
from typing import Optional
from services import ct_gov, prevalence as prev_svc
from collections import defaultdict

router = APIRouter()


def _csv(v: Optional[str]) -> Optional[list]:
    return v.split(",") if v else None


@router.get("/")
async def get_landscape(
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

    phase_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    sponsor_class_counts: dict[str, int] = defaultdict(int)
    country_counts: dict[str, int] = defaultdict(int)
    year_counts: dict[str, int] = defaultdict(int)
    # For the enrollment-velocity overlay: sum + count of enrollment per start-year,
    # so the frontend can plot avg trial size alongside trial volume.
    year_enroll_sum: dict[str, int] = defaultdict(int)
    year_enroll_n: dict[str, int] = defaultdict(int)
    # Velocity segmentation (G): trial starts per year, split by phase / sponsor class.
    year_by_phase: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    year_by_sponsor: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    total_enrollment = 0
    enrollment_count = 0

    for s in studies:
        for phase in s.get("phases", ["N/A"]):
            phase_counts[phase] += 1
        status_counts[s.get("status", "Unknown")] += 1
        sp_class = s.get("sponsor", {}).get("class", "Unknown")
        sponsor_class_counts[sp_class] += 1
        # Count TRIALS per country (one per trial), not sites — matches /geo and the
        # "Top Countries by Trial Activity" label.
        for c_name in s.get("countries", {}):
            country_counts[c_name] += 1
        start = s.get("startDate")
        enroll = s.get("enrollment", {})
        if start:
            year = start[:4]
            year_counts[year] += 1
            year_by_phase[year][(s.get("phases") or ["NA"])[0]] += 1
            year_by_sponsor[year][sp_class] += 1
            if enroll and enroll.get("count"):
                year_enroll_sum[year] += enroll["count"]
                year_enroll_n[year] += 1
        if enroll and enroll.get("count"):
            total_enrollment += enroll["count"]
            enrollment_count += 1

    enrollment_by_year = {
        y: round(year_enroll_sum[y] / year_enroll_n[y])
        for y in year_enroll_sum if year_enroll_n[y]
    }

    total = result["totalCount"]
    analyzed = len(studies)
    return {
        "totalCount": total,
        "sampleSize": analyzed,
        "coverage": {
            "analyzed": analyzed,
            "total": total,
            "isComplete": analyzed >= total,
        },
        "phaseCounts": dict(phase_counts),
        "statusCounts": dict(status_counts),
        "sponsorClassCounts": dict(sponsor_class_counts),
        "countryCounts": dict(sorted(country_counts.items(), key=lambda x: -x[1])[:30]),
        "yearCounts": dict(sorted(year_counts.items())),
        "enrollmentByYear": dict(sorted(enrollment_by_year.items())),
        "yearByPhase": {y: dict(v) for y, v in sorted(year_by_phase.items())},
        "yearBySponsor": {y: dict(v) for y, v in sorted(year_by_sponsor.items())},
        "avgEnrollment": round(total_enrollment / enrollment_count) if enrollment_count else 0,
    }


@router.get("/geo")
async def get_geo(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
    geoLat: Optional[float] = Query(None, ge=-90, le=90),
    geoLng: Optional[float] = Query(None, ge=-180, le=180),
    geoMiles: Optional[float] = Query(None, gt=0, le=12000),
):
    result = await ct_gov.search_studies(
        condition=condition, status=_csv(status), phases=_csv(phases),
        study_types=_csv(studyTypes), sponsor_classes=_csv(sponsorClasses),
        country=country, from_year=fromYear,
        geo_lat=geoLat, geo_lng=geoLng, geo_miles=geoMiles, page_size=1000,
    )
    studies = result["studies"]

    country_data: dict[str, dict] = defaultdict(
        lambda: {"trialCount": 0, "siteCount": 0, "competingEnrollment": 0, "sites": []})
    for s in studies:
        enroll = (s.get("enrollment") or {}).get("count") or 0
        for country, count in s.get("countries", {}).items():
            country_data[country]["trialCount"] += 1
            country_data[country]["siteCount"] += count
            country_data[country]["competingEnrollment"] += enroll
        for site in s.get("sites", [])[:10]:
            c = site["country"]
            if len(country_data[c]["sites"]) < 100:
                country_data[c]["sites"].append(site)

    # Competition-intensity (D): competing enrollment ÷ patient pool, per country,
    # expressed as enrollment slots per 100k prevalent patients. Needs prevalence.
    prev = prev_svc.lookup(condition) if condition else None
    for cname, cdata in country_data.items():
        pool = (prev or {}).get(cname, {}).get("prevalence") if prev else None
        cdata["prevalence"] = pool
        cdata["competitionIntensity"] = (
            round(cdata["competingEnrollment"] / pool * 100_000, 1) if pool else None
        )

    total = result["totalCount"]
    analyzed = len(studies)
    return {
        "coverage": {
            "analyzed": analyzed,
            "total": total,
            "isComplete": analyzed >= total,
        },
        "hasPrevalence": prev is not None,
        "competitionNote": "Competing enrollment counts each trial's full target in every country it runs — a demand-pressure proxy, not an allocated per-country share.",
        "countries": [
            {"country": k, **v, "sites": v["sites"][:50]}
            for k, v in sorted(country_data.items(), key=lambda x: -x[1]["trialCount"])
        ]
    }


@router.get("/eligibility/{nct_id}")
async def get_eligibility(nct_id: str):
    from services import eligibility_nlp
    study = await ct_gov.get_study(nct_id)
    criteria = study.get("eligibility", {}).get("criteria", "")
    extracted = eligibility_nlp.extract(criteria)

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
    if not data:
        # Should not happen — the epidemiology model always returns something —
        # but keep a safe empty fallback.
        return {"condition": condition, "found": False, "countries": {},
                "method": "none", "note": "No estimate available.", "modeled": False}

    # Curated (measured figures) vs modeled (deterministic epidemiology model).
    modeled = any(v.get("method") == "modeled" for v in data.values())
    return {
        "condition": condition,
        "found": True,
        "method": "modeled" if modeled else "curated",
        "modeled": modeled,
        "countries": data,
        "note": ("Modeled estimate — TrialLens epidemiology engine (prevalence rate × population). "
                 "No AI/API key required; override any country."
                 if modeled else
                 "Curated estimates — GLOBOCAN 2022 / GBD 2021 / published literature."),
    }
