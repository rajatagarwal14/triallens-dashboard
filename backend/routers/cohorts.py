"""
Cohort suggestion & comparison for Historical analysis.

There is no fixed way to segment a set of trials — the meaningful split depends
on what was searched. This engine looks at the current result set and SUGGESTS
1–4 cohorts along one of several axes, then reports feasibility metrics
(enrolment pace, duration, discontinuation) per cohort so a planner can compare
them side by side. Groupings are suggestions — the frontend lets the user rename,
drop or switch axis.

Axes:
  • population_scope  — exact (indication + qualifier) vs indication-only vs basket
  • line_of_therapy   — 1L / relapsed-refractory / later-line / unspecified
  • biomarker         — biomarker-selected vs all-comers
  • mono_combo        — monotherapy vs combination
  • geography         — China-only vs global (incl./excl. China)  ← highlighted split
"""
import re
from fastapi import APIRouter, Query
from typing import Optional
from collections import defaultdict
from statistics import median
from services import ct_gov

router = APIRouter()

_DEAD = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
_GENERIC = {
    "cancer", "carcinoma", "tumor", "tumour", "neoplasm", "disease", "syndrome",
    "disorder", "acute", "chronic", "malignant", "advanced", "metastatic",
    "recurrent", "refractory", "relapsed", "stage", "type", "cell", "solid",
    "primary", "secondary", "with", "and", "the", "trial", "study", "adult",
}
# biomarker / molecular-selection tokens (word-boundary matched)
_BIOMARKERS = [
    "jak2", "calr", "mpl", "egfr", "alk", "ros1", "braf", "kras", "nras", "her2",
    "brca", "brca1", "brca2", "pd-l1", "pdl1", "msi", "flt3", "idh1", "idh2",
    "tp53", "met", "ret", "ntrk", "fgfr", "pik3ca", "kit", "pdgfra", "bcr-abl",
    "cd20", "cd19", "cd30", "cd38", "her2neu", "ntrk1", "hras", "smo",
]
_LINE_RULES = [
    ("Relapsed / refractory", r"relaps|refractor|\br/r\b|previously treated|prior (line|therap|treatment)|second[- ]line|third[- ]line|\b2l\b|\b3l\b"),
    ("First-line / naïve", r"treatment[- ]na[iï]ve|untreated|newly diagnosed|first[- ]line|front[- ]line|\b1l\b|no prior"),
]


def _csv(v: Optional[str]):
    return v.split(",") if v else None


def _months_between(start: str, end: str):
    try:
        sy, sm = int(start[:4]), int(start[5:7]) if len(start) >= 7 else 1
        ey, em = int(end[:4]), int(end[5:7]) if len(end) >= 7 else 1
    except (ValueError, IndexError, TypeError):
        return None
    m = (ey - sy) * 12 + (em - sm)
    return m if 0 <= m <= 240 else None


def _study_text(s: dict) -> str:
    parts = [s.get("title", ""), s.get("officialTitle", ""),
             (s.get("eligibility") or {}).get("criteria", "")]
    parts += (s.get("conditions") or [])
    return " ".join(parts).lower()


# ── Axis classifiers: each returns (group_key, group_label) for one study ──────
def _cls_geography(s, ctx):
    countries = set(s.get("countries") or {})
    countries.discard("Unknown")
    has_cn = "China" in countries
    if has_cn and len(countries) == 1:
        return ("cn_only", "China-only")
    if has_cn:
        return ("cn_incl", "Global (incl. China)")
    if not countries:
        return ("unknown", "Region not reported")
    return ("ex_cn", "Global (ex-China)")


def _cls_biomarker(s, ctx):
    text = ctx["text"][s["nctId"]]
    for bm in _BIOMARKERS:
        if re.search(rf"\b{re.escape(bm)}\b", text):
            return ("biomarker", "Biomarker-selected")
    return ("all_comers", "All-comers")


def _cls_line(s, ctx):
    text = ctx["text"][s["nctId"]]
    for label, pat in _LINE_RULES:
        if re.search(pat, text):
            key = "rr" if "efractor" in label or "elapsed" in label else "first"
            return (key, label)
    return ("unspecified", "Line not specified")


def _cls_mono_combo(s, ctx):
    drugs = [i for i in (s.get("interventions") or [])
             if (i.get("type") or "").upper() in ("DRUG", "BIOLOGICAL")]
    text = ctx["text"][s["nctId"]]
    combo = len(drugs) >= 2 or re.search(r"combination|\bplus\b| in combination|co[- ]administ", text)
    return ("combo", "Combination") if combo else ("mono", "Monotherapy")


def _cls_population(s, ctx):
    primary = ctx["primary"]
    distinct = {c.strip().lower() for c in (s.get("conditions") or []) if c.strip()}
    # A true basket recruits diseases BEYOND the primary indication — count
    # conditions that don't contain the primary token, so disease subtypes
    # (Primary MF, Post-PV MF, …) don't get mistaken for a basket.
    if primary:
        foreign = {c for c in distinct if primary not in c}
        is_basket = len(foreign) >= 2
    else:
        is_basket = len(distinct) >= 3
    if is_basket:
        return ("basket", "Basket / umbrella")
    text = ctx["text"][s["nctId"]]
    quals = ctx["qualifiers"]
    plabel = (primary or "indication").title()
    if quals:
        has_q = any(q in text for q in quals)
        if has_q:
            return ("exact", f"{plabel} + {quals[0].title()}")
        return ("indication_only", f"{plabel} only")
    return ("focused", "Focused indication")


_AXES = {
    "population_scope": ("Population scope", _cls_population),
    "line_of_therapy": ("Line of therapy", _cls_line),
    "biomarker": ("Biomarker selection", _cls_biomarker),
    "mono_combo": ("Regimen", _cls_mono_combo),
    "geography": ("Geography", _cls_geography),
}


def _group_metrics(members: list) -> dict:
    paces, durs, dropped = [], [], 0
    enroll_targets = []
    for s in members:
        if s.get("status") in _DEAD:
            dropped += 1
        c = (s.get("enrollment") or {}).get("count")
        sites = s.get("siteCount") or 0
        mo = _months_between(s.get("startDate") or "", s.get("primaryCompletionDate") or "")
        if c and c > 0:
            enroll_targets.append(c)
            if sites > 0 and mo and mo > 0:
                rate = c / sites / mo
                if 0 < rate <= 50:
                    paces.append(rate)
        if mo:
            durs.append(mo)
    n = len(members)
    return {
        "trialCount": n,
        "enrollPacePerSiteMonth": round(median(paces), 2) if paces else None,
        "enrollPaceN": len(paces),
        "medianDurationMonths": round(median(durs)) if durs else None,
        "medianEnrollment": round(median(enroll_targets)) if enroll_targets else None,
        "discontinuationRate": round(dropped / n * 100) if n else 0,
        "discontinued": dropped,
        "nctSample": [s["nctId"] for s in members[:8]],
    }


def _apply_axis(studies, axis, ctx):
    fn = _AXES[axis][1]
    buckets: dict[str, dict] = {}
    order: list[str] = []
    for s in studies:
        key, label = fn(s, ctx)
        b = buckets.get(key)
        if not b:
            b = buckets[key] = {"key": key, "label": label, "members": []}
            order.append(key)
        b["members"].append(s)
    groups = [buckets[k] for k in order]
    # cap to 4 cohorts: keep the largest, so the comparison stays legible
    groups.sort(key=lambda g: -len(g["members"]))
    kept = groups[:4]
    out = []
    for g in kept:
        out.append({"key": g["key"], "label": g["label"],
                    "definition": _DEFINITIONS.get(g["key"], ""), **_group_metrics(g["members"])})
    return out


_DEFINITIONS = {
    "cn_only": "Sites are in mainland China only — separate accrual dynamics; usually analysed apart.",
    "cn_incl": "Multi-region trials that include China among their countries.",
    "ex_cn": "Multi-region trials with no China site.",
    "biomarker": "Eligibility gates on a molecular marker / mutation.",
    "all_comers": "No biomarker requirement — enrols all-comers.",
    "rr": "Enrols relapsed / refractory / previously-treated patients.",
    "first": "Enrols treatment-naïve / first-line patients.",
    "unspecified": "Line of therapy not stated in eligibility.",
    "combo": "Two or more active drugs, or an explicit combination regimen.",
    "mono": "Single active agent.",
    "basket": "Recruits several distinct conditions under one protocol — broadest pool.",
    "exact": "Eligibility requires the searched qualifier (narrowest, slowest-accruing pool).",
    "indication_only": "Recruits the core indication without the searched qualifier.",
    "focused": "Recruits a single focused indication.",
}


def _applicability(studies, axis, ctx) -> int:
    fn = _AXES[axis][1]
    keys = set()
    for s in studies:
        k, _ = fn(s, ctx)
        if k != "unknown":
            keys.add(k)
    return len(keys)


@router.get("/")
async def get_cohorts(
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    phases: Optional[str] = Query(None),
    studyTypes: Optional[str] = Query(None),
    sponsorClasses: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    fromYear: Optional[int] = Query(None, ge=2000, le=2030),
    axis: Optional[str] = Query(None),
):
    result = await ct_gov.search_studies(
        condition=condition, status=_csv(status), phases=_csv(phases),
        study_types=_csv(studyTypes), sponsor_classes=_csv(sponsorClasses),
        country=country, from_year=fromYear, page_size=1000,
    )
    studies = result["studies"]

    # Pre-compute each study's searchable text once.
    text_by_nct = {s["nctId"]: _study_text(s) for s in studies}

    # Parse the query into primary indication + qualifier(s). People search
    # disease-first ("myelofibrosis anemia"), so the first distinctive token is
    # the indication and the rest are qualifiers/comorbidities (e.g. "anemia").
    q_terms = [w for w in re.findall(r"[a-z]{4,}", (condition or "").lower()) if w not in _GENERIC]
    primary = q_terms[0] if q_terms else None
    qualifiers = q_terms[1:]
    ctx = {"text": text_by_nct, "primary": primary, "qualifiers": qualifiers}

    # Which axes actually split this set into ≥2 meaningful groups?
    available = []
    for key, (label, _) in _AXES.items():
        n = _applicability(studies, key, ctx)
        available.append({"key": key, "label": label, "groupCount": n, "applicable": n >= 2})

    # Auto-suggest: population scope when the query carries a qualifier; else the
    # axis that yields the most balanced split (prefer biomarker → line → geo).
    if axis not in _AXES:
        if qualifiers and _applicability(studies, "population_scope", ctx) >= 2:
            axis = "population_scope"
        else:
            pref = ["biomarker", "line_of_therapy", "geography", "mono_combo", "population_scope"]
            axis = next((a for a in pref if _applicability(studies, a, ctx) >= 2), "geography")

    groups = _apply_axis(studies, axis, ctx)

    return {
        "coverage": {"analyzed": len(studies), "total": result["totalCount"],
                     "isComplete": len(studies) >= result["totalCount"]},
        "query": {"primary": primary, "qualifiers": qualifiers},
        "axis": axis,
        "suggestedAxis": axis,
        "availableAxes": available,
        "groups": groups,
    }
