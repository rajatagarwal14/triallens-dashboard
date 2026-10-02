"""
Site & Investigator Intelligence — aggregates the analyzed sample into a
site-activity database (which facilities run how many trials, with what
enrollment) and investigator experience scorecards (from overallOfficials).
"""
from fastapi import APIRouter, Depends
from collections import defaultdict
from services import analytics as an, status as st
from services.datasets import Filters
from routers._common import common_filters, analyse

router = APIRouter()


def _compute(studies: list) -> dict:
    # ── Site-activity database ───────────────────────────────────────────
    # Built from `locations` = EVERY registered facility (un-geocoded ones included;
    # coordinates only matter for drawing the map).
    sites: dict = {}
    for s in studies:
        enroll = (s.get("enrollment") or {}).get("count") or 0
        phase = an.phase_key(s)
        seen_here = set()
        for loc in s.get("locations") or s.get("sites") or []:
            fac = (loc.get("facility") or "").strip()
            # Key on facility + city + country so identically-named sites in different
            # cities (e.g. generic "Research Site") don't collapse into one row.
            key = (fac, loc.get("city") or "", loc.get("country") or "")
            if not fac or key in seen_here:
                continue
            seen_here.add(key)  # count a facility once per trial
            e = sites.setdefault(key, {
                "facility": fac, "trials": 0, "enrollment": 0,
                "country": key[2], "city": key[1], "phases": defaultdict(int),
                "recruiting": 0, "sampleNct": s["nctId"],
            })
            e["trials"] += 1
            e["enrollment"] += enroll
            e["phases"][phase] += 1
            # Exact status match; the site's own status wins over the trial's.
            if st.location_is_enrolling(loc.get("status"), s.get("status")):
                e["recruiting"] += 1

    site_rows = sorted(sites.values(), key=lambda x: (-x["trials"], -x["enrollment"]))[:25]
    for e in site_rows:
        # NB: this is the TARGET enrolment of the trials the site participates in (whole-trial
        # figure), not patients the site recruited. Per-site accrual is not in the registry.
        e["avgEnrollment"] = round(e["enrollment"] / e["trials"]) if e["trials"] else 0
        e["enrollRate"] = round(e["recruiting"] / e["trials"] * 100) if e["trials"] else 0
        e["phases"] = dict(e["phases"])

    # ── Investigator scorecards ──────────────────────────────────────────
    pis: dict = {}
    for s in studies:
        enroll = (s.get("enrollment") or {}).get("count") or 0
        seen = set()
        for o in s.get("officials") or []:
            name = (o.get("name") or "").strip()
            role = (o.get("role") or "").upper()
            if not name or "PRINCIPAL" not in role or name in seen:
                continue
            seen.add(name)   # a PI listed twice on one trial counts once
            e = pis.setdefault(name, {
                "name": name, "trials": 0, "enrollment": 0, "recruiting": 0,
                "affiliations": set(), "conditions": defaultdict(int),
                "phases": defaultdict(int), "sampleNct": s["nctId"],
            })
            e["trials"] += 1
            e["enrollment"] += enroll
            if st.is_enrolling(s.get("status")):
                e["recruiting"] += 1
            if o.get("affiliation"):
                e["affiliations"].add(o["affiliation"])
            for c in (s.get("conditions") or [])[:3]:
                e["conditions"][c] += 1
            e["phases"][an.phase_key(s)] += 1

    pi_rows = sorted(pis.values(), key=lambda x: (-x["trials"], -x["enrollment"]))[:25]
    for e in pi_rows:
        e["affiliation"] = next(iter(sorted(e["affiliations"])), "")
        e["focus"] = [c for c, _ in sorted(e["conditions"].items(), key=lambda kv: -kv[1])[:3]]
        e["avgEnrollment"] = round(e["enrollment"] / e["trials"]) if e["trials"] else 0
        e["enrollRate"] = round(e["recruiting"] / e["trials"] * 100) if e["trials"] else 0
        e["phases"] = dict(e["phases"])
        del e["affiliations"], e["conditions"]

    return {
        "sites": site_rows,
        "investigators": pi_rows,
        "siteUniverse": len(sites),
        "investigatorUniverse": len(pis),
    }


@router.get("/")
async def get_sites(f: Filters = Depends(common_filters)):
    return await analyse(f, "sites", _compute)
