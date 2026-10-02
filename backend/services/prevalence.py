"""
Pre-fed country-level prevalence / incidence estimates for common indications.
Sources: GLOBOCAN 2022 (cancer), GBD 2021 (non-cancer), published epi literature.
Values = estimated prevalent cases (patients living with condition) unless noted.
All figures approximate — intended for feasibility directional analysis.
"""

import re
from typing import Optional, Dict
from services import epidemiology

# indication key → country → prevalent patients (approx)
_DATA: Dict[str, Dict[str, int]] = {
    "breast cancer": {
        "United States": 3_800_000, "China": 1_200_000, "Germany": 350_000,
        "France": 320_000, "United Kingdom": 650_000, "Italy": 280_000,
        "Spain": 210_000, "Brazil": 250_000, "Australia": 160_000,
        "Japan": 400_000, "India": 200_000, "Canada": 180_000,
        "Netherlands": 80_000, "Belgium": 70_000, "South Korea": 120_000,
        "Taiwan": 55_000, "Poland": 90_000, "Sweden": 70_000,
        "Switzerland": 45_000, "Turkey (Türkiye)": 65_000,
    },
    "aml": {
        "United States": 22_000, "China": 80_000, "Germany": 3_800,
        "France": 3_000, "United Kingdom": 3_200, "Italy": 2_500,
        "Japan": 8_000, "India": 15_000, "Brazil": 4_000,
        "Australia": 1_200, "Canada": 1_500, "Spain": 2_000,
        "South Korea": 2_800, "Taiwan": 1_400, "Netherlands": 900,
        "Belgium": 800, "Poland": 1_800, "Turkey (Türkiye)": 2_200,
    },
    "acute myeloid leukemia": {
        "United States": 22_000, "China": 80_000, "Germany": 3_800,
        "France": 3_000, "United Kingdom": 3_200, "Italy": 2_500,
        "Japan": 8_000, "India": 15_000, "Brazil": 4_000,
        "Australia": 1_200, "Canada": 1_500, "Spain": 2_000,
    },
    "nsclc": {
        "United States": 200_000, "China": 780_000, "Germany": 35_000,
        "France": 32_000, "United Kingdom": 42_000, "Italy": 28_000,
        "Japan": 120_000, "India": 65_000, "Brazil": 28_000,
        "Australia": 12_000, "Canada": 18_000, "Spain": 22_000,
        "South Korea": 35_000, "Taiwan": 18_000, "Turkey (Türkiye)": 15_000,
    },
    "lung cancer": {
        "United States": 235_000, "China": 870_000, "Germany": 57_000,
        "France": 46_000, "United Kingdom": 48_000, "Italy": 40_000,
        "Japan": 125_000, "India": 72_000, "Brazil": 32_000,
        "Australia": 14_000, "Canada": 22_000, "Spain": 28_000,
        "South Korea": 42_000, "Poland": 22_000, "Turkey (Türkiye)": 20_000,
    },
    "multiple myeloma": {
        "United States": 160_000, "Germany": 18_000, "France": 16_000,
        "United Kingdom": 23_000, "Italy": 14_000, "Japan": 30_000,
        "China": 120_000, "Brazil": 15_000, "Australia": 8_000,
        "Canada": 9_000, "Spain": 11_000, "South Korea": 14_000,
        "India": 25_000, "Netherlands": 5_500, "Taiwan": 7_000,
    },
    "melanoma": {
        "United States": 320_000, "Australia": 180_000, "Germany": 42_000,
        "France": 35_000, "United Kingdom": 55_000, "Italy": 28_000,
        "Netherlands": 18_000, "Canada": 32_000, "Norway": 15_000,
        "Sweden": 18_000, "Spain": 20_000, "Brazil": 25_000,
        "Switzerland": 12_000, "Denmark": 10_000,
    },
    "type 2 diabetes": {
        "United States": 37_000_000, "China": 140_000_000,
        "India": 101_000_000, "Germany": 7_500_000, "France": 4_000_000,
        "United Kingdom": 4_900_000, "Brazil": 16_000_000,
        "Japan": 10_000_000, "Australia": 1_300_000, "Canada": 3_000_000,
        "Italy": 3_500_000, "Spain": 3_700_000, "Mexico": 15_000_000,
        "South Korea": 3_200_000, "Turkey (Türkiye)": 8_000_000,
    },
    "alzheimer": {
        "United States": 6_700_000, "China": 9_830_000, "Germany": 1_700_000,
        "France": 1_200_000, "United Kingdom": 980_000, "Italy": 1_100_000,
        "Japan": 4_400_000, "India": 5_300_000, "Brazil": 2_700_000,
        "Australia": 500_000, "Spain": 900_000, "Canada": 750_000,
        "South Korea": 900_000, "Netherlands": 280_000, "Sweden": 200_000,
    },
    "dlbcl": {
        "United States": 50_000, "Germany": 7_500, "France": 7_000,
        "United Kingdom": 9_000, "Italy": 6_000, "Japan": 25_000,
        "China": 100_000, "Brazil": 8_000, "Australia": 3_500,
        "Canada": 4_000, "Spain": 5_000, "South Korea": 9_000,
    },
    "diffuse large b-cell lymphoma": {
        "United States": 50_000, "Germany": 7_500, "France": 7_000,
        "United Kingdom": 9_000, "Italy": 6_000, "Japan": 25_000,
        "China": 100_000,
    },
    "ovarian cancer": {
        "United States": 240_000, "China": 300_000, "Germany": 32_000,
        "France": 28_000, "United Kingdom": 45_000, "Italy": 30_000,
        "Japan": 55_000, "India": 60_000, "Brazil": 25_000,
        "Australia": 18_000, "Canada": 20_000, "Poland": 22_000,
    },
    "prostate cancer": {
        "United States": 3_300_000, "China": 600_000, "Germany": 450_000,
        "France": 380_000, "United Kingdom": 450_000, "Italy": 310_000,
        "Japan": 300_000, "Brazil": 230_000, "Australia": 210_000,
        "Canada": 220_000, "Spain": 190_000, "Sweden": 90_000,
    },
    "colorectal cancer": {
        "United States": 1_500_000, "China": 2_800_000, "Germany": 280_000,
        "France": 220_000, "United Kingdom": 300_000, "Italy": 260_000,
        "Japan": 500_000, "India": 150_000, "Brazil": 120_000,
        "Australia": 100_000, "Canada": 130_000, "Spain": 170_000,
    },
}

_SOURCES = {
    "cancer": "GLOBOCAN 2022 (IARC) — 5-year prevalence estimates",
    "diabetes": "IDF Diabetes Atlas 10th ed. 2021",
    "alzheimer": "Alzheimer's Disease International World Report 2021",
    "default": "GBD 2021 + published literature; directional estimates only",
}


def _normalize(indication: str) -> str:
    # Drop apostrophes ("Alzheimer's" -> "alzheimers"), then turn any other
    # punctuation into spaces so commas/hyphens don't block an otherwise-valid match.
    cleaned = re.sub(r"['\u2019`]", "", (indication or "").lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# ── Disease identity ────────────────────────────────────────────────────────
# A curated figure is served ONLY when the query names that disease. Sharing a word
# ("diabetes", "leukemia", "breast") is NOT identity — that mapped Type 1 Diabetes to
# Type 2 figures, ALL to AML, and breast fibroadenoma to breast cancer.
#
# For every curated key:
#   _ALIASES        other spellings of the SAME disease (exact or phrase match)
#   _EXACT_ONLY     aliases that are only valid when they are the WHOLE query: bare
#                   "diabetes" is the all-diabetes figure, but "type 1 diabetes"
#                   contains that word and must not inherit it
#   _EXCLUDED_WITH  words that make a phrase match a DIFFERENT disease than the one
#                   measured (uveal melanoma is not cutaneous melanoma)
_ALIASES: Dict[str, list] = {
    "breast cancer": ["breast carcinoma", "breast neoplasm", "breast neoplasms",
                      "carcinoma of the breast", "mammary carcinoma", "mammary cancer",
                      "triple negative breast cancer", "tnbc"],
    "aml": ["acute myeloid leukemia", "acute myeloid leukaemia", "acute myelogenous leukemia",
            "acute myelogenous leukaemia", "acute non lymphocytic leukemia"],
    "acute myeloid leukemia": ["aml", "acute myeloid leukaemia", "acute myelogenous leukemia"],
    "nsclc": ["non small cell lung cancer", "non small cell lung carcinoma",
              "non small cell carcinoma of the lung", "nonsmall cell lung cancer"],
    "lung cancer": ["lung carcinoma", "lung neoplasm", "lung neoplasms", "carcinoma of the lung"],
    "multiple myeloma": ["myeloma", "plasma cell myeloma", "kahler disease"],
    "melanoma": ["malignant melanoma", "cutaneous melanoma", "skin melanoma"],
    "type 2 diabetes": ["type ii diabetes", "type 2 diabetes mellitus", "type ii diabetes mellitus",
                        "diabetes mellitus type 2", "diabetes mellitus type ii", "t2dm", "t2d",
                        "non insulin dependent diabetes", "adult onset diabetes",
                        # The curated figures (IDF Atlas) are ALL-diabetes totals, so the
                        # un-typed terms resolve here — but only as the whole query.
                        "diabetes", "diabetes mellitus"],
    "alzheimer": ["alzheimers", "alzheimers disease", "alzheimer disease", "alzheimer s disease"],
    "dlbcl": ["diffuse large b cell lymphoma", "diffuse large b cell non hodgkin lymphoma",
              "diffuse large cell lymphoma"],
    "diffuse large b-cell lymphoma": ["dlbcl", "diffuse large b cell lymphoma"],
    "ovarian cancer": ["ovarian carcinoma", "ovarian neoplasm", "ovarian neoplasms",
                       "epithelial ovarian cancer", "carcinoma of the ovary"],
    "prostate cancer": ["prostate carcinoma", "prostatic neoplasm", "prostatic neoplasms",
                        "prostate adenocarcinoma", "carcinoma of the prostate"],
    "colorectal cancer": ["colorectal carcinoma", "colorectal neoplasm", "colorectal neoplasms",
                          "colon cancer", "rectal cancer", "colon carcinoma", "crc",
                          "bowel cancer", "colorectal adenocarcinoma"],
}
_EXACT_ONLY = {"diabetes", "diabetes mellitus"}
_EXCLUDED_WITH: Dict[str, set] = {
    "melanoma": {"uveal", "ocular", "choroidal", "conjunctival", "mucosal", "intraocular"},
}


def _contains_phrase(query: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", query) is not None


def _match_indication(q: str) -> Optional[tuple]:
    """(curated_key, match_type) for a normalized query, or None.

    match_type is "exact" (the query IS that disease) or "parent" (the query is a
    narrower population inside it, e.g. "metastatic breast cancer"). The longest
    matching phrase wins, so "non small cell lung cancer" prefers NSCLC over
    "lung cancer"."""
    best = None  # (rank, length, key, match_type)
    for key in _DATA:
        bad = _EXCLUDED_WITH.get(key, ())
        if any(_contains_phrase(q, w) for w in bad):
            continue
        for alias in {_normalize(key), *(_normalize(a) for a in _ALIASES.get(key, []))}:
            if q == alias:
                cand = (3, len(alias), key, "exact")
            elif alias not in _EXACT_ONLY and _contains_phrase(q, alias):
                cand = (2, len(alias), key, "parent")
            else:
                continue
            if best is None or cand[:2] > best[:2]:
                best = cand
    return (best[2], best[3]) if best else None


# Umbrella searches (e.g. "Cancer") have no distinctive word, so they can't match a
# single indication. Instead we sum a curated, NON-OVERLAPPING set of member
# indications to approximate total prevalence for the family. Aliases (nsclc vs
# lung cancer, aml vs acute myeloid leukemia) are excluded to avoid double counting.
_CANCER_MEMBERS = [
    "breast cancer", "lung cancer", "prostate cancer", "colorectal cancer",
    "ovarian cancer", "melanoma", "multiple myeloma", "aml", "dlbcl",
]
# Umbrella words, and the generic modifiers that may accompany them without changing
# which family is meant ("Advanced Solid Tumors" is still the cancer family; "Breast
# Cancer" is not — "breast" is not a modifier, so it never reaches this path).
_UMBRELLA_WORDS = {
    "cancer", "cancers", "oncology", "tumor", "tumors", "tumour", "tumours",
    "carcinoma", "carcinomas", "neoplasm", "neoplasms", "malignancy", "malignancies",
}
_UMBRELLA_MODIFIERS = {
    "advanced", "metastatic", "solid", "malignant", "recurrent", "refractory", "relapsed",
    "unresectable", "locally", "stage", "iii", "iv", "all", "any", "of", "and", "or", "the",
}


def _aggregate(members: list) -> Dict[str, int]:
    """Sum prevalence per country across a set of member indications."""
    totals: Dict[str, int] = {}
    for m in members:
        for country, count in _DATA.get(m, {}).items():
            totals[country] = totals.get(country, 0) + count
    return totals


def _source_for(key: str) -> str:
    is_cancer = any(w in key for w in ["cancer", "leukemia", "lymphoma", "myeloma", "melanoma", "carcinoma", "oncology", "tumor", "tumour"])
    return _SOURCES["cancer"] if is_cancer else (
        _SOURCES["diabetes"] if "diabet" in key else (
            _SOURCES["alzheimer"] if "alzheim" in key else _SOURCES["default"]
        )
    )


def lookup(indication: str) -> Optional[Dict[str, dict]]:
    """
    country → {prevalence, source, confidence, note, method, matchType, matchedIndication}.

    1. Curated figures — only when the query IS (or sits inside) a curated disease
       (see _match_indication). confidence="high".
    2. Umbrella family totals for "Cancer"/"Solid tumors"/"Oncology".
    3. Deterministic epidemiology model (confidence "modeled"), or — when no
       disease-specific model exists — an explicitly labelled placeholder.
    """
    q = _normalize(indication)
    note = "5-yr prevalence estimate"
    data = None
    match_type = "exact"
    matched = q

    hit = _match_indication(q)
    if hit:
        matched, match_type = hit
        data = _DATA[matched]
        if match_type == "parent":
            note = (f"Matched the broader indication '{matched}'. Your search may describe a "
                    f"narrower population (subtype, stage or biomarker) — treat as an upper bound.")
    else:
        core = [t for t in q.split() if t not in _UMBRELLA_MODIFIERS]
        if core and all(t in _UMBRELLA_WORDS for t in core):
            members = [m for m in _CANCER_MEMBERS if m in _DATA]
            agg = _aggregate(members)
            if agg:
                data = agg
                matched = "cancer (family aggregate)"
                match_type = "family"
                note = f"Aggregate of {len(members)} indications — approximate family total"

    # 3) No curated figure → deterministic epidemiology model (no AI/LLM).
    if data is None:
        return epidemiology.estimate(indication)

    source = _source_for(matched)
    return {
        country: {
            "prevalence": count,
            "source": source,
            "confidence": "high",
            "note": note,
            "method": "curated",
            "matchType": match_type,
            "matchedIndication": matched,
        }
        for country, count in data.items()
    }


def is_placeholder(data: Optional[Dict[str, dict]]) -> bool:
    """True when every entry is the generic catch-all rate (no disease-specific model).
    Such numbers must not feed maps, competition intensity or planning metrics."""
    return bool(data) and all(v.get("confidence") == "placeholder" for v in data.values())


def usable(data: Optional[Dict[str, dict]]) -> Optional[Dict[str, dict]]:
    """`data` if it is a real (curated or disease-specific modelled) estimate, else None."""
    return None if (not data or is_placeholder(data)) else data


def list_supported() -> list:
    return sorted(set(_DATA.keys()))
