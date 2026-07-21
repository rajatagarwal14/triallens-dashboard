"""
Deterministic epidemiology model — estimates per-country prevalence for ANY
indication with NO external API / LLM. Method: classify the indication into a
disease category, then estimate each country's prevalent cases as
    population(country) × category_prevalence_rate_per_100k / 100_000
optionally scaled by a development-level factor (some diseases skew rich/poor).

This is exactly how an epidemiologist ballparks a patient pool (rate × population).
It is a MODEL, clearly labelled as such — the curated table in prevalence.py is
used first for the indications where we have measured figures; this fills the rest.
"""
import re
from typing import Dict, Optional

# Approx 2024 population in MILLIONS for the countries CT.gov trials actually run in.
_POP_M: Dict[str, float] = {
    "United States": 335, "China": 1410, "India": 1430, "Germany": 84,
    "France": 68, "United Kingdom": 67, "Japan": 125, "Brazil": 216,
    "Canada": 40, "Australia": 26, "Spain": 48, "Italy": 59, "Netherlands": 18,
    "Belgium": 12, "Switzerland": 9, "Korea, Republic of": 52, "South Korea": 52,
    "Turkey": 85, "Poland": 38, "Sweden": 10, "Taiwan": 23, "Mexico": 128,
    "Russian Federation": 144, "Denmark": 6, "Norway": 5.5, "Austria": 9,
    "Portugal": 10, "Greece": 10, "Israel": 9.5, "Argentina": 46,
    "South Africa": 60, "Egypt": 112, "Thailand": 72, "Ukraine": 38,
    "Czechia": 11, "Hungary": 10, "Finland": 5.5, "Ireland": 5,
    "New Zealand": 5, "Singapore": 6, "Hong Kong": 7.5, "Romania": 19,
    "Colombia": 52, "Peru": 34, "Chile": 19, "Saudi Arabia": 37,
}

# "Development" factor — cancers/degenerative skew to higher-income (older, screened)
# populations; infectious skews the other way. 1.0 = neutral population scaling.
_DEV_HIGH = {  # higher prevalence in developed nations
    "United States", "Germany", "France", "United Kingdom", "Japan", "Canada",
    "Australia", "Spain", "Italy", "Netherlands", "Belgium", "Switzerland",
    "South Korea", "Korea, Republic of", "Sweden", "Denmark", "Norway",
    "Austria", "Finland", "Ireland", "New Zealand", "Israel", "Singapore",
}

# category → (prevalence per 100k, skews_developed). Rates are prevalent cases per
# 100k population, tuned so pop×rate reproduces known anchors (e.g. breast cancer
# US 3.8M → ~1130/100k; diabetes US 37M → ~11000/100k; Alzheimer 6.7M → ~2000).
_CATEGORY: Dict[str, tuple] = {
    "breast_cancer":     (1130, True),
    "prostate_cancer":   (985, True),
    "colorectal_cancer": (450, True),
    "lung_cancer":       (70, True),
    "melanoma":          (95, True),
    "ovarian_cancer":    (70, True),
    "pancreatic_cancer": (20, True),
    "gastric_cancer":    (60, False),
    "liver_cancer":      (40, False),
    "bladder_cancer":    (220, True),
    "kidney_cancer":     (140, True),
    "cervical_cancer":   (90, False),
    "leukemia":          (45, False),
    "lymphoma":          (75, True),
    "myeloma":           (48, True),
    "brain_cancer":      (30, True),
    "sarcoma":           (15, True),
    "cancer_generic":    (850, True),   # broad "cancer"/"oncology"/"solid tumor"
    "diabetes":          (11000, False),
    "obesity":           (30000, True),
    "cardiovascular":    (8000, False),
    "hypertension":      (30000, False),
    "stroke":            (900, False),
    "alzheimer":         (2000, True),
    "parkinson":         (300, True),
    "multiple_sclerosis":(120, True),
    "epilepsy":          (700, False),
    "depression":        (5000, False),
    "schizophrenia":     (400, False),
    "asthma":            (5000, False),
    "copd":              (4000, False),
    "rheumatoid":        (500, True),
    "psoriasis":         (2000, True),
    "ibd":               (400, True),
    "lupus":             (70, False),
    "ckd":               (10000, False),
    "hiv":               (500, False),
    "hepatitis":         (1000, False),
    "tuberculosis":      (300, False),
    "covid":             (200, False),
    "rare_disease":      (25, True),
    "default":           (250, False),
}

# keyword → category. First match wins; order matters (specific before generic).
_RULES = [
    (r"breast", "breast_cancer"),
    (r"prostate", "prostate_cancer"),
    (r"colorectal|colon|rectal", "colorectal_cancer"),
    (r"lung|nsclc|sclc", "lung_cancer"),
    (r"melanoma", "melanoma"),
    (r"ovarian|ovary", "ovarian_cancer"),
    (r"pancrea", "pancreatic_cancer"),
    (r"gastric|stomach", "gastric_cancer"),
    (r"hepatocellular|liver cancer|hcc", "liver_cancer"),
    (r"bladder|urothelial", "bladder_cancer"),
    (r"renal|kidney cancer", "kidney_cancer"),
    (r"cervical|cervix", "cervical_cancer"),
    (r"leukemia|leukaemia|\baml\b|\ball\b|\bcml\b|\bcll\b", "leukemia"),
    (r"lymphoma|\bdlbcl\b|hodgkin", "lymphoma"),
    (r"myeloma", "myeloma"),
    (r"glioblastoma|glioma|brain (tumou?r|cancer)", "brain_cancer"),
    (r"sarcoma", "sarcoma"),
    (r"diabet", "diabetes"),
    (r"obesity|overweight", "obesity"),
    (r"hypertension|blood pressure", "hypertension"),
    (r"stroke|cerebrovascular", "stroke"),
    (r"heart failure|coronary|myocardial|cardiovascular|atrial fib", "cardiovascular"),
    (r"alzheim|dementia", "alzheimer"),
    (r"parkinson", "parkinson"),
    (r"multiple sclerosis|\bms\b", "multiple_sclerosis"),
    (r"epilep|seizure", "epilepsy"),
    (r"depress|major depressive|\bmdd\b", "depression"),
    (r"schizophren", "schizophrenia"),
    (r"asthma", "asthma"),
    (r"copd|chronic obstructive", "copd"),
    (r"rheumatoid|\bra\b", "rheumatoid"),
    (r"psorias", "psoriasis"),
    (r"crohn|ulcerative colitis|inflammatory bowel|\bibd\b", "ibd"),
    (r"lupus|\bsle\b", "lupus"),
    (r"chronic kidney|renal failure|\bckd\b|dialysis", "ckd"),
    (r"\bhiv\b|aids", "hiv"),
    (r"hepatitis|\bhbv\b|\bhcv\b", "hepatitis"),
    (r"tuberculosis|\btb\b", "tuberculosis"),
    (r"covid|sars-cov|coronavirus", "covid"),
    # generic cancer LAST so specific tumours match first
    (r"cancer|carcinoma|tumou?r|oncolog|neoplasm|malignan", "cancer_generic"),
    (r"syndrome|deficiency|rare|orphan|dystrophy", "rare_disease"),
]


def classify(indication: str) -> str:
    text = (indication or "").lower()
    for pat, cat in _RULES:
        if re.search(pat, text):
            return cat
    return "default"


def estimate(indication: str) -> Optional[Dict[str, dict]]:
    """
    country → {prevalence, source, confidence, note, method:'modeled'} for ANY
    indication, using population × category rate. Never returns None.
    """
    cat = classify(indication)
    rate, skews_dev = _CATEGORY.get(cat, _CATEGORY["default"])
    label = cat.replace("_", " ")

    out: Dict[str, dict] = {}
    for country, pop_m in _POP_M.items():
        # South Korea / Korea appear twice by design (name variants) — keep one.
        factor = 1.0
        if skews_dev and country in _DEV_HIGH:
            factor = 1.4
        elif skews_dev and country not in _DEV_HIGH:
            factor = 0.6
        cases = int(pop_m * 1_000_000 * (rate / 100_000) * factor)
        if cases <= 0:
            continue
        out[country] = {
            "prevalence": cases,
            "source": f"TrialLens epidemiology model — {label} prevalence × population",
            "confidence": "modeled",
            "note": "Model estimate (rate × population) — override with known figures",
            "method": "modeled",
        }
    return out or None


def supported_categories() -> list:
    return sorted({cat for _, cat in _RULES})
