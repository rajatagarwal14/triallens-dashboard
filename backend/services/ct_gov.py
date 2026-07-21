import asyncio
import re
import httpx
from cachetools import TTLCache
from typing import Optional, Dict, List

CT_BASE = "https://clinicaltrials.gov/api/v2"
_cache: TTLCache = TTLCache(maxsize=500, ttl=300)

# Per-key locks so N concurrent identical requests (e.g. Landscape + Geo fired
# together before cache warmup) collapse into a single upstream fetch instead of
# all missing the cache and stampeding ClinicalTrials.gov.
_inflight: Dict[str, asyncio.Lock] = {}


def _lock_for(key: str) -> asyncio.Lock:
    lock = _inflight.get(key)
    if lock is None:
        lock = _inflight[key] = asyncio.Lock()
    return lock

# NCT IDs are exactly "NCT" + 8 digits. Validating before interpolating into the
# request URL prevents path/query injection (e.g. "NCT123?format=csv", "../studies").
_NCT_RE = re.compile(r"^NCT\d{8}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso_date(value: Optional[str]) -> Optional[str]:
    """Return value only if it's a clean YYYY-MM-DD, else None (blocks injection)."""
    v = (value or "").strip()
    return v if _DATE_RE.match(v) else None


class CTGovError(Exception):
    """Upstream ClinicalTrials.gov failure, with a user-facing message + status."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


async def _fetch(client: httpx.AsyncClient, url: str, **kwargs) -> dict:
    """GET with uniform timeout / rate-limit / upstream error translation."""
    try:
        r = await client.get(url, **kwargs)
    except httpx.TimeoutException:
        raise CTGovError("ClinicalTrials.gov timed out. Try again in a moment.", status=504)
    except httpx.RequestError:
        raise CTGovError("Couldn't reach ClinicalTrials.gov. Check your connection.", status=503)

    if r.status_code == 429:
        raise CTGovError("ClinicalTrials.gov is rate-limiting requests. Wait a few seconds and retry.", status=429)
    if r.status_code >= 500:
        raise CTGovError("ClinicalTrials.gov is having problems. Try again shortly.", status=502)
    if r.status_code in (400, 404):
        raise CTGovError("ClinicalTrials.gov couldn't process that request. Check the search term or filters.", status=r.status_code)
    try:
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPStatusError, ValueError):
        raise CTGovError("ClinicalTrials.gov returned an unexpected response. Try again shortly.", status=502)


def _norm_study(raw: dict) -> dict:
    ps = raw.get("protocolSection", {})
    id_mod = ps.get("identificationModule", {})
    stat_mod = ps.get("statusModule", {})
    desc_mod = ps.get("descriptionModule", {})
    cond_mod = ps.get("conditionsModule", {})
    design_mod = ps.get("designModule", {})
    elig_mod = ps.get("eligibilityModule", {})
    contacts_mod = ps.get("contactsLocationsModule", {})
    sponsor_mod = ps.get("sponsorCollaboratorsModule", {})
    arms_mod = ps.get("armsInterventionsModule", {})

    nct_id = id_mod.get("nctId", "")
    locations = contacts_mod.get("locations", [])
    countries: Dict[str, int] = {}
    sites: List[dict] = []
    for loc in locations:
        c = loc.get("country", "Unknown")
        countries[c] = countries.get(c, 0) + 1
        gp = loc.get("geoPoint", {})
        # Accept lat/lon of exactly 0.0 too (falsy but valid); only skip if missing.
        if gp.get("lat") is not None and gp.get("lon") is not None:
            sites.append({
                "nctId": nct_id,
                "facility": loc.get("facility", ""),
                "city": loc.get("city", ""),
                "country": c,
                # Per-location recruiting status (may be absent on older records).
                "status": loc.get("status", ""),
                "lat": gp["lat"],
                "lon": gp["lon"],
            })

    enroll = stat_mod.get("enrollmentInfo") or design_mod.get("enrollmentInfo") or {}

    # Principal investigators / study officials — for site & investigator intelligence.
    officials = [
        {"name": o.get("name", ""), "role": o.get("role", ""), "affiliation": o.get("affiliation", "")}
        for o in contacts_mod.get("overallOfficials", [])
        if o.get("name")
    ]

    return {
        "nctId": nct_id,
        "title": id_mod.get("briefTitle", ""),
        "officialTitle": id_mod.get("officialTitle", ""),
        "status": stat_mod.get("overallStatus", ""),
        "phases": design_mod.get("phases", []),
        "studyType": design_mod.get("studyType", ""),
        "summary": desc_mod.get("briefSummary", ""),
        "conditions": cond_mod.get("conditions", []),
        "keywords": cond_mod.get("keywords", []),
        "interventions": [
            {"type": i.get("type", ""), "name": i.get("name", "")}
            for i in arms_mod.get("interventions", [])
        ],
        "sponsor": {
            "name": sponsor_mod.get("leadSponsor", {}).get("name", ""),
            "class": sponsor_mod.get("leadSponsor", {}).get("class", ""),
        },
        "enrollment": {
            "count": enroll.get("count"),
            "type": enroll.get("type", ""),
        },
        "startDate": (stat_mod.get("startDateStruct") or {}).get("date"),
        "completionDate": (stat_mod.get("completionDateStruct") or {}).get("date"),
        "primaryCompletionDate": (stat_mod.get("primaryCompletionDateStruct") or {}).get("date"),
        "primaryCompletionType": (stat_mod.get("primaryCompletionDateStruct") or {}).get("type"),
        "firstPostDate": (stat_mod.get("studyFirstPostDateStruct") or {}).get("date"),
        "lastUpdateDate": (stat_mod.get("lastUpdatePostDateStruct") or {}).get("date"),
        "eligibility": {
            "criteria": elig_mod.get("eligibilityCriteria", ""),
            "healthyVolunteers": elig_mod.get("healthyVolunteers", False),
            "sex": elig_mod.get("sex", "ALL"),
            "minimumAge": elig_mod.get("minimumAge", "N/A"),
            "maximumAge": elig_mod.get("maximumAge", "N/A"),
        },
        "countries": countries,
        "sites": sites,
        "officials": officials,
        "countryCount": len(countries),
        "siteCount": len(sites),
    }


async def search_studies(
    condition: Optional[str] = None,
    status: Optional[List[str]] = None,
    phases: Optional[List[str]] = None,
    study_types: Optional[List[str]] = None,
    sponsor_classes: Optional[List[str]] = None,
    country: Optional[str] = None,
    from_year: Optional[int] = None,
    completion_from: Optional[str] = None,
    completion_to: Optional[str] = None,
    first_posted_from: Optional[str] = None,
    geo_lat: Optional[float] = None,
    geo_lng: Optional[float] = None,
    geo_miles: Optional[float] = None,
    sort: Optional[str] = None,
    page_size: int = 25,
    page_token: Optional[str] = None,
) -> dict:
    params: dict = {"format": "json", "pageSize": page_size, "countTotal": "true"}
    if condition:
        params["query.cond"] = condition
    if status:
        params["filter.overallStatus"] = "|".join(status)
    if sort:
        # Server-side global sort, e.g. "EnrollmentCount:desc", "StartDate:desc"
        params["sort"] = sort
    if geo_lat is not None and geo_lng is not None and geo_miles:
        # Radius search — trials with a site within N miles of a point.
        params["filter.geo"] = f"distance({float(geo_lat)},{float(geo_lng)},{float(geo_miles)}mi)"
    if page_token:
        params["pageToken"] = page_token

    # Build filter.advanced clauses (combined with AND). Every clause is a
    # native CT.gov filter, so totalCount and pagination stay correct.
    advanced_clauses: List[str] = []
    if phases:
        # CT.gov v2 has no filter.phase param — phase filtering goes via AREA[Phase]
        valid_phases = {"EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"}
        ph_clauses = [f"AREA[Phase]{p.upper()}" for p in phases if p.upper() in valid_phases]
        if ph_clauses:
            advanced_clauses.append(f"({' OR '.join(ph_clauses)})")
    if study_types:
        # OR within the group: AREA[StudyType]Interventional OR AREA[StudyType]Observational
        valid_types = {"INTERVENTIONAL": "Interventional", "OBSERVATIONAL": "Observational",
                       "EXPANDED_ACCESS": "Expanded Access"}
        type_clauses = [f'AREA[StudyType]"{valid_types[t.upper()]}"'
                        for t in study_types if t.upper() in valid_types]
        if type_clauses:
            advanced_clauses.append(f"({' OR '.join(type_clauses)})")
    if sponsor_classes:
        # Native lead-sponsor class filter
        valid_classes = {"INDUSTRY", "NIH", "FED", "OTHER", "INDIV", "NETWORK", "OTHER_GOV", "UNKNOWN"}
        sc_clauses = [f"AREA[LeadSponsorClass]{s.upper()}"
                      for s in sponsor_classes if s.upper() in valid_classes]
        if sc_clauses:
            advanced_clauses.append(f"({' OR '.join(sc_clauses)})")
    if country:
        # Strip quotes so user input can't terminate the quoted term and
        # inject extra AREA[] clauses into filter.advanced
        safe_country = country.replace('"', "").strip()
        if safe_country:
            advanced_clauses.append(f'AREA[LocationCountry]"{safe_country}"')
    if from_year:
        # CT.gov v2 Essie expects ISO dates (YYYY-MM-DD) in RANGE, not MM/DD/YYYY.
        advanced_clauses.append(f"AREA[StartDate]RANGE[{int(from_year)}-01-01,MAX]")
    if completion_from or completion_to:
        # Filter by PRIMARY completion date — the competitive "readout" window.
        lo = _iso_date(completion_from) or "MIN"
        hi = _iso_date(completion_to) or "MAX"
        advanced_clauses.append(f"AREA[PrimaryCompletionDate]RANGE[{lo},{hi}]")
    if first_posted_from:
        # Newly-registered trials since a date — powers the "new trials" alert.
        lo = _iso_date(first_posted_from)
        if lo:
            advanced_clauses.append(f"AREA[StudyFirstPostDate]RANGE[{lo},MAX]")
    if advanced_clauses:
        params["filter.advanced"] = " AND ".join(advanced_clauses)

    key = str(sorted(params.items()))
    if key in _cache:
        return _cache[key]

    async with _lock_for(key):
        try:
            # Re-check inside the lock: a concurrent request may have populated it
            # while we were waiting, so only the first caller hits the network.
            if key in _cache:
                return _cache[key]

            async with httpx.AsyncClient(timeout=30.0) as client:
                raw = await _fetch(client, f"{CT_BASE}/studies", params=params)

            studies = [_norm_study(s) for s in raw.get("studies", [])]

            result = {
                "studies": studies,
                "totalCount": raw.get("totalCount", 0),
                "nextPageToken": raw.get("nextPageToken"),
            }
            _cache[key] = result
            return result
        finally:
            # Always drop the lock entry — even on error — so the dict can't grow
            # unbounded for failed queries.
            _inflight.pop(key, None)


async def get_study(nct_id: str) -> dict:
    nct = (nct_id or "").strip().upper()
    if not _NCT_RE.match(nct):
        raise CTGovError(f"Invalid NCT ID '{nct_id}'. Expected format: NCT00000000.", status=400)
    cache_key = f"study:{nct}"
    if cache_key in _cache:
        return _cache[cache_key]
    async with httpx.AsyncClient(timeout=30.0) as client:
        raw = await _fetch(client, f"{CT_BASE}/studies/{nct}")
        result = _norm_study(raw)
    _cache[cache_key] = result
    return result


async def get_studies_for_similarity(condition: str, limit: int = 60) -> List[dict]:
    result = await search_studies(condition=condition, page_size=min(limit, 100))
    return result["studies"]
