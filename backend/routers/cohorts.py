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
from fastapi import APIRouter, Depends, Query
from typing import Optional
from collections import defaultdict
from services import analytics as an, ontology, status as st
from services.datasets import Filters
from routers._common import common_filters, analyse

router = APIRouter()

_GENERIC = {
    "cancer", "carcinoma", "tumor", "tumour", "neoplasm", "disease", "syndrome",
    "disorder", "acute", "chronic", "malignant", "advanced", "metastatic",
    "recurrent", "refractory", "relapsed", "stage", "type", "cell", "solid",
    "primary", "secondary", "with", "and", "the", "trial", "study", "adult",
}
# Biomarker / molecular-selection tokens. Short gene symbols that are also ordinary words
# ("criteria are MET", "RET", "KIT", "SMO") are only counted when written in CAPITALS in
# the original text, so lower-case prose can never trigger them.
_BIOMARKERS = [
    "jak2", "calr", "egfr", "ros1", "braf", "kras", "nras", "her2",
    "brca", "brca1", "brca2", "pd-l1", "pdl1", "flt3", "idh1", "idh2",
    "tp53", "ntrk", "fgfr", "pik3ca", "pdgfra", "bcr-abl",
    "cd20", "cd19", "cd30", "cd38", "her2neu", "ntrk1", "hras",
]
_AMBIGUOUS_MARKERS = ["MPL", "ALK", "MSI", "MET", "RET", "KIT", "SMO"]
_BIOMARKER_RE = re.compile(r"\b(?:" + "|".join(re.escape(b) for b in _BIOMARKERS) + r")\b")
_AMBIGUOUS_RE = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(_AMBIGUOUS_MARKERS) + r")(?![A-Za-z0-9])")
_LINE_RULES = [
    ("Relapsed / refractory", r"relaps|refractor|\br/r\b|previously treated|prior (line|therap|treatment)|second[- ]line|third[- ]line|\b2l\b|\b3l\b"),
    ("First-line / naïve", r"treatment[- ]na[iï]ve|untreated|newly diagnosed|first[- ]line|front[- ]line|\b1l\b|no prior"),
]


def _csv(v: Optional[str]):
    return v.split(",") if v else None


def _study_raw(s: dict) -> str:
    parts = [s.get("title", ""), s.get("officialTitle", ""),
             (s.get("eligibility") or {}).get("criteria", "")]
    parts += (s.get("conditions") or [])
    return " ".join(p for p in parts if p)


def _regimen_text(s: dict) -> str:
    """Title-level text only: "combination" in eligibility prose says nothing about the regimen."""
    return " ".join([s.get("title") or "", s.get("officialTitle") or ""]).lower()


_NOT_ACTIVE = re.compile(r"placebo|sham|saline|vehicle|standard of care|best supportive|"
                         r"observation|no intervention|usual care|control", re.I)


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
    if _BIOMARKER_RE.search(ctx["text"][s["nctId"]]) or _AMBIGUOUS_RE.search(ctx["raw"][s["nctId"]]):
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
    # Active agents only: a placebo / comparator arm is not a second drug.
    drugs = {(i.get("name") or "").strip().lower() for i in (s.get("interventions") or [])
             if (i.get("type") or "").upper() in ("DRUG", "BIOLOGICAL")
             and (i.get("name") or "").strip() and not _NOT_ACTIVE.search(i.get("name") or "")}
    text = _regimen_text(s)
    combo = len(drugs) >= 2 or re.search(r"combination|\bplus\b|co[- ]administ", text)
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
        foreign = set()
        is_basket = len(distinct) >= 3

    # Ontology refinement (v2, optional). Without it the v1 result above stands.
    # With it, split "foreign" conditions into same-family (stages/siblings on one
    # disease continuum) vs genuinely unrelated families. A trial spanning
    # MF + PV + ET is a disease SPECTRUM, not a basket — only cross-family
    # recruitment earns the basket label.
    if is_basket and primary and ontology.loaded():
        cross = {c for c in foreign if not ontology.same_family(primary, c)}
        if len(cross) < 2:
            root = ontology.family_root(primary)
            label = f"{root.title()} spectrum" if root else "Disease spectrum"
            return ("spectrum", label)

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
        if st.norm(s.get("status")) in st.DISCONTINUED:
            dropped += 1
        c = (s.get("enrollment") or {}).get("count")
        sites = s.get("siteCount") or 0
        mo = an.months_between(s.get("startDate"), s.get("primaryCompletionDate"))
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
        "enrollPacePerSiteMonth": round(an.median(paces), 2) if paces else None,
        "enrollPaceN": len(paces),
        "medianDurationMonths": round(an.median(durs)) if durs else None,
        "medianEnrollment": round(an.median(enroll_targets)) if enroll_targets else None,
        "discontinuationRate": round(dropped / n * 100) if n else 0,
        "discontinued": dropped,
        "nctSample": [s["nctId"] for s in members[:8]],
    }


def _classify(s, axis, ctx):
    cache = ctx["cache"].setdefault(axis, {})
    hit = cache.get(s["nctId"])
    if hit is None:
        hit = cache[s["nctId"]] = _AXES[axis][1](s, ctx)
    return hit


def _apply_axis(studies, axis, ctx):
    buckets: dict = {}
    order: list = []
    for s in studies:
        key, label = _classify(s, axis, ctx)
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
    "spectrum": "Recruits across stages/siblings of ONE disease continuum (e.g. MF + PV + ET) — broader than a single stage, but not a cross-family basket.",
    "exact": "Eligibility requires the searched qualifier (narrowest, slowest-accruing pool).",
    "indication_only": "Recruits the core indication without the searched qualifier.",
    "focused": "Recruits a single focused indication.",
}


def _applicability(studies, axis, ctx) -> int:
    keys = set()
    for s in studies:
        k, _ = _classify(s, axis, ctx)
        if k != "unknown":
            keys.add(k)
    return len(keys)


_NOUNS = {"cancer", "carcinoma", "tumor", "tumour", "neoplasm", "sarcoma"}
_MODIFIERS = _GENERIC | {
    "small", "positive", "negative", "non", "early", "late", "line", "first", "second", "third",
    "mutant", "mutated", "mutation", "wild", "high", "low", "risk", "hormone", "receptor",
    "resistant", "locally", "newly", "diagnosed", "untreated", "naive", "naïve", "squamous",
    "nonsquamous", "triple", "hormonal", "positive", "negative", "unresectable", "operable",
}
# Common acronyms people type instead of the full disease name → a word that appears in
# the registry's condition strings, so the "basket vs focused" test recognises them.
_ACRONYM = {
    "aml": "myeloid", "all": "lymphoblastic", "cml": "myeloid", "cll": "lymphocytic",
    "nsclc": "lung", "sclc": "lung", "hcc": "hepatocellular", "crc": "colorectal",
    "mm": "myeloma", "mf": "myelofibrosis", "pv": "vera", "et": "thrombocythemia",
    "mds": "myelodysplastic", "dlbcl": "lymphoma", "t2d": "diabetes", "t2dm": "diabetes",
    "t1d": "diabetes", "ckd": "kidney", "copd": "pulmonary", "ra": "rheumatoid",
}


def _parse_query(condition: Optional[str]):
    """Split a free-text search into (primary indication word, qualifier words).

    "Non-small cell lung cancer" → primary "lung"; "HER2 positive breast cancer" → primary
    "breast", qualifier "her2"; "AML" → primary "myeloid". The old parse took the first
    4+-letter non-generic word, giving "small" / "positive" / nothing for these."""
    words = re.findall(r"[a-z0-9][a-z0-9\-]*", (condition or "").lower())
    words = [_ACRONYM.get(w, w) if w in _ACRONYM and len(words) == 1 else w for w in words]
    words = [w for w in words if not w.startswith("non-")]   # "non-small", "non-squamous"
    content = [w for w in words if w not in _MODIFIERS and len(w) >= 3]
    if not content:
        return None, []
    primary = None
    for i, w in enumerate(words):
        if w in _NOUNS:
            before = [x for x in words[:i] if x not in _MODIFIERS and len(x) >= 3]
            primary = before[-1] if before else None
            break
    if primary is None:
        primary = content[0]
    quals = [w for w in content if w != primary]
    return primary, quals


def _compute(studies: list, condition: Optional[str], axis: Optional[str]) -> dict:
    raw = {s["nctId"]: _study_raw(s) for s in studies}
    text = {k: v.lower() for k, v in raw.items()}
    primary, qualifiers = _parse_query(condition)
    ctx = {"text": text, "raw": raw, "primary": primary, "qualifiers": qualifiers, "cache": {}}

    available = []
    for key, (label, _) in _AXES.items():
        n = _applicability(studies, key, ctx)
        available.append({"key": key, "label": label, "groupCount": n, "applicable": n >= 2})

    if axis not in _AXES:
        if qualifiers and _applicability(studies, "population_scope", ctx) >= 2:
            axis = "population_scope"
        else:
            pref = ["biomarker", "line_of_therapy", "geography", "mono_combo", "population_scope"]
            axis = next((a for a in pref if _applicability(studies, a, ctx) >= 2), "geography")

    return {
        "query": {"primary": primary, "qualifiers": qualifiers},
        "axis": axis,
        "suggestedAxis": axis,
        "availableAxes": available,
        "groups": _apply_axis(studies, axis, ctx),
    }


@router.get("/")
async def get_cohorts(f: Filters = Depends(common_filters), axis: Optional[str] = Query(None)):
    return await analyse(f, "cohorts", lambda s: _compute(s, f.condition, axis), (f.condition, axis))
