"""
Pre-fed country-level prevalence / incidence estimates for common indications.
Sources: GLOBOCAN 2022 (cancer), GBD 2021 (non-cancer), published epi literature.
Values = estimated prevalent cases (patients living with condition) unless noted.
All figures approximate — intended for feasibility directional analysis.
"""

import re
from typing import Optional, Dict
from services import epidemiology

# Generic disease-type tokens that are NOT distinctive on their own. Matching on
# these alone caused "Pancreatic Cancer" to silently return "breast cancer" data
# (both share the word "cancer"). Fuzzy matching must require a distinctive word.
_GENERIC_TOKENS = {
    "cancer", "carcinoma", "tumor", "tumour", "neoplasm", "disease", "syndrome",
    "disorder", "acute", "chronic", "malignant", "advanced", "metastatic",
    "recurrent", "refractory", "stage", "type", "cell", "large", "diffuse",
    "myeloid", "lymphoid", "solid", "primary", "secondary", "oncology",
}

# indication key → country → prevalent patients (approx)
_DATA: Dict[str, Dict[str, int]] = {
    "breast cancer": {
        "United States": 3_800_000, "China": 1_200_000, "Germany": 350_000,
        "France": 320_000, "United Kingdom": 650_000, "Italy": 280_000,
        "Spain": 210_000, "Brazil": 250_000, "Australia": 160_000,
        "Japan": 400_000, "India": 200_000, "Canada": 180_000,
        "Netherlands": 80_000, "Belgium": 70_000, "South Korea": 120_000,
        "Taiwan": 55_000, "Poland": 90_000, "Sweden": 70_000,
        "Switzerland": 45_000, "Turkey": 65_000,
    },
    "aml": {
        "United States": 22_000, "China": 80_000, "Germany": 3_800,
        "France": 3_000, "United Kingdom": 3_200, "Italy": 2_500,
        "Japan": 8_000, "India": 15_000, "Brazil": 4_000,
        "Australia": 1_200, "Canada": 1_500, "Spain": 2_000,
        "South Korea": 2_800, "Taiwan": 1_400, "Netherlands": 900,
        "Belgium": 800, "Poland": 1_800, "Turkey": 2_200,
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
        "South Korea": 35_000, "Taiwan": 18_000, "Turkey": 15_000,
    },
    "lung cancer": {
        "United States": 235_000, "China": 870_000, "Germany": 57_000,
        "France": 46_000, "United Kingdom": 48_000, "Italy": 40_000,
        "Japan": 125_000, "India": 72_000, "Brazil": 32_000,
        "Australia": 14_000, "Canada": 22_000, "Spain": 28_000,
        "South Korea": 42_000, "Poland": 22_000, "Turkey": 20_000,
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
        "South Korea": 3_200_000, "Turkey": 8_000_000,
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
    # Strip punctuation (e.g. "Alzheimer's Disease" → "alzheimers disease") so
    # apostrophes/commas don't block an otherwise-valid match.
    cleaned = re.sub(r"[^a-z0-9\s]", " ", indication.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _distinctive(phrase: str) -> set:
    """Words in a phrase that actually identify the disease (drop generic tokens)."""
    return {w for w in phrase.split() if len(w) > 3 and w not in _GENERIC_TOKENS}


# Umbrella searches (e.g. "Cancer") have no distinctive word, so they can't match a
# single indication. Instead we sum a curated, NON-OVERLAPPING set of member
# indications to approximate total prevalence for the family. Aliases (nsclc vs
# lung cancer, aml vs acute myeloid leukemia) are excluded to avoid double counting.
_CANCER_MEMBERS = [
    "breast cancer", "lung cancer", "prostate cancer", "colorectal cancer",
    "ovarian cancer", "melanoma", "multiple myeloma", "aml", "dlbcl",
]
_UMBRELLA: Dict[str, list] = {
    "cancer": _CANCER_MEMBERS, "oncology": _CANCER_MEMBERS, "tumor": _CANCER_MEMBERS,
    "tumour": _CANCER_MEMBERS, "carcinoma": _CANCER_MEMBERS, "neoplasm": _CANCER_MEMBERS,
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
    Returns country → {prevalence, source, confidence} for a given indication.
    Returns None if indication not confidently matched in the pre-fed table.
    """
    key = _normalize(indication)
    note = "5-yr prevalence estimate"
    data = None

    # 1) exact curated match
    if key in _DATA:
        data = _DATA[key]
    else:
        query_words = _distinctive(key)
        if not query_words:
            # No distinctive word → try an umbrella-family aggregate (e.g. "Cancer").
            member_key = next((tok for tok in key.split() if tok in _UMBRELLA), None)
            if member_key:
                members = [m for m in _UMBRELLA[member_key] if m in _DATA]
                agg = _aggregate(members)
                if agg:
                    data = agg
                    note = f"Aggregate of {len(members)} indications — approximate family total"
        else:
            # fuzzy: require a shared *distinctive* word so generic overlap (e.g. both
            # containing "cancer") can never silently serve the wrong indication's data.
            matched = next(
                (k for k in _DATA if _distinctive(_normalize(k)) & query_words),
                None
            )
            if matched:
                data = _DATA[matched]

    # 2) No curated figure → fall back to the deterministic epidemiology model so
    #    prevalence works for ANY indication with no external AI/LLM.
    if data is None:
        return epidemiology.estimate(indication)

    source = _source_for(key)
    return {
        country: {
            "prevalence": count,
            "source": source,
            "confidence": "high",
            "note": note,
            "method": "curated",
        }
        for country, count in data.items()
    }


def list_supported() -> list:
    return sorted(set(_DATA.keys()))
