"""
Site & Investigator Intelligence — aggregates the analyzed sample into a
site-activity database (which facilities run how many trials, with what
enrollment) and investigator experience scorecards (from overallOfficials).
"""
from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict
from services import ct_gov

router = APIRouter()


def _csv(v: Optional[str]):
    return v.split(",") if v else None


@router.get("/")
async def get_sites(
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

    # ── Site-activity database ───────────────────────────────────────────
    # facility -> trials run, enrollment handled, countries, phase mix, one NCT.
    sites: dict[str, dict] = {}
    for s in studies:
        enroll = (s.get("enrollment") or {}).get("count") or 0
        phase = (s.get("phases") or ["NA"])[0]
        seen_here = set()
        for site in s.get("sites", []):
            fac = site.get("facility") or ""
            # Key on facility + city + country so identically-named sites in different
            # cities (e.g. generic "Research Site") don't collapse into one row.
            key = (fac, site.get("city", ""), site.get("country", ""))
            if not fac or key in seen_here:
                continue
            seen_here.add(key)  # count a facility once per trial
            e = sites.setdefault(key, {
                "facility": fac, "trials": 0, "enrollment": 0,
                "countries": set(), "cities": set(), "phases": defaultdict(int),
                "recruiting": 0, "sampleNct": s["nctId"],
            })
            e["trials"] += 1
            e["enrollment"] += enroll
            e["countries"].add(site.get("country", ""))
            if site.get("city"):
                e["cities"].add(site["city"])
            e["phases"][phase] += 1
            if "RECRUIT" in (site.get("status") or "").upper() or s.get("status") == "RECRUITING":
                e["recruiting"] += 1

    site_rows = sorted(sites.values(), key=lambda x: (-x["trials"], -x["enrollment"]))[:25]
    for e in site_rows:
        e["country"] = next(iter(e["countries"]), "")
        e["city"] = next(iter(e["cities"]), "")
        e["avgEnrollment"] = round(e["enrollment"] / e["trials"]) if e["trials"] else 0
        # Enrolment rate = share of this site's trials that are actively
        # recruiting (open for enrolment right now) — an activity signal.
        e["enrollRate"] = round(e["recruiting"] / e["trials"] * 100) if e["trials"] else 0
        e["phases"] = dict(e["phases"])
        del e["countries"], e["cities"]

    # ── Investigator scorecards ──────────────────────────────────────────
    # PI -> # trials, therapeutic focus (top conditions), enrollment, affiliation.
    pis: dict[str, dict] = {}
    for s in studies:
        enroll = (s.get("enrollment") or {}).get("count") or 0
        for o in s.get("officials", []):
            name = o.get("name", "").strip()
            role = o.get("role", "")
            if not name or "PRINCIPAL" not in role:
                continue
            e = pis.setdefault(name, {
                "name": name, "trials": 0, "enrollment": 0, "recruiting": 0,
                "affiliations": set(), "conditions": defaultdict(int),
                "phases": defaultdict(int), "sampleNct": s["nctId"],
            })
            e["trials"] += 1
            e["enrollment"] += enroll
            if s.get("status") == "RECRUITING":
                e["recruiting"] += 1
            if o.get("affiliation"):
                e["affiliations"].add(o["affiliation"])
            for c in (s.get("conditions") or [])[:3]:
                e["conditions"][c] += 1
            e["phases"][(s.get("phases") or ["NA"])[0]] += 1

    pi_rows = sorted(pis.values(), key=lambda x: (-x["trials"], -x["enrollment"]))[:25]
    for e in pi_rows:
        e["affiliation"] = next(iter(e["affiliations"]), "")
        e["focus"] = [c for c, _ in sorted(e["conditions"].items(), key=lambda kv: -kv[1])[:3]]
        e["avgEnrollment"] = round(e["enrollment"] / e["trials"]) if e["trials"] else 0
        e["enrollRate"] = round(e["recruiting"] / e["trials"] * 100) if e["trials"] else 0
        e["phases"] = dict(e["phases"])
        del e["affiliations"], e["conditions"]

    total = result["totalCount"]
    analyzed = len(studies)
    return {
        "coverage": {"analyzed": analyzed, "total": total, "isComplete": analyzed >= total},
        "sites": site_rows,
        "investigators": pi_rows,
        "siteUniverse": len(sites),
        "investigatorUniverse": len(pis),
    }
