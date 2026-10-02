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

    def __init__(self, message: str, status: int = 502, retry_after: Optional[float] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        # Seconds the server asked us to wait (HTTP Retry-After), when it said so.
        self.retry_after = retry_after


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Retry-After is either delta-seconds or an HTTP date. Returns seconds (capped), or None."""
    if not value:
        return None
    v = value.strip()
    try:
        return max(0.0, min(float(v), 300.0))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        import datetime as _dt
        when = parsedate_to_datetime(v)
        now = _dt.datetime.now(when.tzinfo) if when.tzinfo else _dt.datetime.utcnow()
        return max(0.0, min((when - now).total_seconds(), 300.0))
    except Exception:
        return None


def _explain_network_error(e: Exception) -> str:
    """Turn a low-level connection failure into something an analyst on a managed
    network can act on. TLS interception by a corporate proxy is the common cause."""
    blob = f"{type(e).__name__} {e}".lower()
    if "certificate" in blob or "ssl" in blob:
        return ("Couldn't establish a secure connection to ClinicalTrials.gov — this usually means "
                "your network inspects HTTPS traffic with a company certificate. Ask IT for the "
                "company root certificate (.pem) and set SSL_CERT_FILE to its path, or run "
                "diagnose.bat / ./diagnose.sh for details. TLS verification is never disabled.")
    if "proxy" in blob or "407" in blob:
        return ("Couldn't reach ClinicalTrials.gov through your network proxy. Set HTTPS_PROXY "
                "(e.g. http://proxy.company.com:8080) before starting TrialLens, or ask IT.")
    return ("Couldn't reach ClinicalTrials.gov. Check your internet connection; on a company "
            "network a proxy or firewall may be blocking clinicaltrials.gov (run diagnose.bat / ./diagnose.sh).")


async def _fetch(client: httpx.AsyncClient, url: str, **kwargs) -> dict:
    """GET with uniform timeout / rate-limit / upstream error translation."""
    try:
        r = await client.get(url, **kwargs)
    except httpx.TimeoutException:
        raise CTGovError("ClinicalTrials.gov timed out. Try again in a moment.", status=504)
    except httpx.RequestError as e:
        raise CTGovError(_explain_network_error(e), status=503)

    if r.status_code == 429:
        raise CTGovError("ClinicalTrials.gov is rate-limiting requests. Wait a few seconds and retry.",
                         status=429, retry_after=_parse_retry_after(r.headers.get("retry-after")))
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
    raw_locations = contacts_mod.get("locations", [])
    countries: Dict[str, int] = {}
    # `locations` = EVERY registered site (this is what site rankings and per-site
    # estimates must use). `sites` = only the geocoded subset, for map markers.
    # Dropping un-geocoded facilities silently removed real sites from rankings and
    # understated siteCount, which inflated every per-site enrolment-pace estimate.
    locations: List[dict] = []
    sites: List[dict] = []
    for loc in raw_locations:
        c = loc.get("country", "Unknown")
        countries[c] = countries.get(c, 0) + 1
        gp = loc.get("geoPoint") or {}
        # Accept lat/lon of exactly 0.0 too (falsy but valid); only skip if missing.
        has_geo = gp.get("lat") is not None and gp.get("lon") is not None
        entry = {
            "nctId": nct_id,
            "facility": loc.get("facility", ""),
            "city": loc.get("city", ""),
            "country": c,
            # Per-location recruiting status (may be absent on older records).
            "status": loc.get("status", ""),
            "lat": gp["lat"] if has_geo else None,
            "lon": gp["lon"] if has_geo else None,
        }
        locations.append(entry)
        if has_geo:
            sites.append(entry)

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
        "locations": locations,
        "sites": sites,
        "officials": officials,
        "countryCount": len(countries),
        "siteCount": len(locations),
        "geocodedSiteCount": len(sites),
    }


def build_params(
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
    last_update_from: Optional[str] = None,
    geo_lat: Optional[float] = None,
    geo_lng: Optional[float] = None,
    geo_miles: Optional[float] = None,
    sort: Optional[str] = None,
    page_size: int = 25,
    page_token: Optional[str] = None,
    fields: Optional[str] = None,
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
    if fields:
        params["fields"] = fields

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
    if last_update_from:
        # Records changed since a date — powers incremental dataset refresh.
        lo = _iso_date(last_update_from)
        if lo:
            advanced_clauses.append(f"AREA[LastUpdatePostDate]RANGE[{lo},MAX]")
    if first_posted_from:
        # Newly-registered trials since a date — powers the "new trials" alert.
        lo = _iso_date(first_posted_from)
        if lo:
            advanced_clauses.append(f"AREA[StudyFirstPostDate]RANGE[{lo},MAX]")
    if advanced_clauses:
        params["filter.advanced"] = " AND ".join(advanced_clauses)
    return params


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
    last_update_from: Optional[str] = None,
    geo_lat: Optional[float] = None,
    geo_lng: Optional[float] = None,
    geo_miles: Optional[float] = None,
    sort: Optional[str] = None,
    page_size: int = 25,
    page_token: Optional[str] = None,
    fields: Optional[str] = None,
) -> dict:
    params = build_params(
        condition=condition, status=status, phases=phases, study_types=study_types,
        sponsor_classes=sponsor_classes, country=country, from_year=from_year,
        completion_from=completion_from, completion_to=completion_to,
        first_posted_from=first_posted_from, last_update_from=last_update_from,
        geo_lat=geo_lat, geo_lng=geo_lng, geo_miles=geo_miles, sort=sort,
        page_size=page_size, page_token=page_token, fields=fields,
    )

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
        try:
            raw = await _fetch(client, f"{CT_BASE}/studies/{nct}")
        except CTGovError as e:
            if e.status == 404:
                raise CTGovError(f"No study with ID {nct} was found on ClinicalTrials.gov.", status=404)
            raise
        result = _norm_study(raw)
    _cache[cache_key] = result
    return result


async def get_studies_for_similarity(condition: str, limit: int = 60) -> List[dict]:
    result = await search_studies(condition=condition, page_size=min(limit, 100))
    return result["studies"]


# Fields the analytics actually use. Asking the API for only these shrinks a
# 1,000-study page from ~38 MB to ~6 MB at the same latency, which is what makes
# retrieving tens of thousands of studies practical.
SLIM_FIELDS = ",".join([
    "NCTId", "BriefTitle", "OfficialTitle", "OverallStatus", "Phase", "StudyType", "Condition",
    "InterventionType", "InterventionName", "LeadSponsorName", "LeadSponsorClass",
    "EnrollmentCount", "EnrollmentType", "StartDate", "PrimaryCompletionDate",
    "PrimaryCompletionDateType", "CompletionDate", "StudyFirstPostDate", "LastUpdatePostDate",
    "EligibilityCriteria", "Sex", "MinimumAge", "MaximumAge",
    "LocationFacility", "LocationCity", "LocationCountry", "LocationStatus", "LocationGeoPoint",
    "OverallOfficialName", "OverallOfficialRole", "OverallOfficialAffiliation",
])


async def fetch_page(
    *, page_size: int = 1000, page_token: Optional[str] = None, slim: bool = True,
    client: Optional[httpx.AsyncClient] = None, **filters,
) -> dict:
    """ONE page, uncached, for bulk retrieval. Returns normalized studies plus the
    server's totalCount and nextPageToken. Raises CTGovError (with .retry_after on 429)."""
    params = build_params(page_size=page_size, page_token=page_token,
                          fields=SLIM_FIELDS if slim else None, **filters)
    if client is not None:
        raw = await _fetch(client, f"{CT_BASE}/studies", params=params)
    else:
        async with httpx.AsyncClient(timeout=60.0) as c:
            raw = await _fetch(c, f"{CT_BASE}/studies", params=params)
    studies = await asyncio.to_thread(lambda: [_norm_study(x) for x in raw.get("studies", [])])
    return {"studies": studies, "totalCount": raw.get("totalCount", 0),
            "nextPageToken": raw.get("nextPageToken")}
