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
    "Turkey (Türkiye)": 85, "Poland": 38, "Sweden": 10, "Taiwan": 23, "Mexico": 128,
    "Russia": 144, "Denmark": 6, "Norway": 5.5, "Austria": 9,
    "Portugal": 10, "Greece": 10, "Israel": 9.5, "Argentina": 46,
    "South Africa": 60, "Egypt": 112, "Thailand": 72, "Ukraine": 38,
    "Czechia": 11, "Hungary": 10, "Finland": 5.5, "Ireland": 5,
    "New Zealand": 5, "Singapore": 6, "Hong Kong": 7.5, "Romania": 19,
    "Colombia": 52, "Peru": 34, "Chile": 19, "Saudi Arabia": 37,
    # Added so that every country with a meaningful number of registered trials gets a
    # prevalence layer (names are ClinicalTrials.gov's exact spellings). Approximate
    # 2024 populations in millions (UN World Population Prospects, rounded).
    "Pakistan": 240, "Bulgaria": 6.4, "Puerto Rico": 3.2, "Malaysia": 34, "Slovakia": 5.4,
    "Serbia": 6.7, "Indonesia": 278, "Croatia": 3.9, "Lithuania": 2.9, "Iran": 89,
    "Philippines": 117, "Vietnam": 100, "Slovenia": 2.1, "Estonia": 1.4, "Latvia": 1.9,
    "Uganda": 49, "Georgia": 3.7, "Kenya": 55, "Bangladesh": 173, "Lebanon": 5.5,
    "Jordan": 11.3, "Tunisia": 12.4, "United Arab Emirates": 10, "Tanzania": 67, "Iraq": 46,
    "Nigeria": 224, "Ethiopia": 126, "Ghana": 34, "Morocco": 37.5, "Algeria": 46,
    "Kazakhstan": 20, "Belarus": 9.2, "Nepal": 30, "Sri Lanka": 22, "Cuba": 11,
    "Venezuela": 28, "Ecuador": 18, "Bolivia": 12, "Uruguay": 3.4, "Costa Rica": 5.2,
    "Panama": 4.5, "Guatemala": 18, "Dominican Republic": 11.3, "Cambodia": 17,
    "Myanmar": 54, "Armenia": 2.8, "Azerbaijan": 10.1, "Moldova": 2.5, "North Macedonia": 1.8,
    "Bosnia and Herzegovina": 3.2, "Albania": 2.8, "Luxembourg": 0.66, "Iceland": 0.38,
    "Malta": 0.53, "Cyprus": 1.3, "Kuwait": 4.3, "Qatar": 2.7, "Oman": 4.6, "Bahrain": 1.5,
    "Zimbabwe": 16.3, "Zambia": 20.5, "Malawi": 21, "Mozambique": 33, "Cameroon": 28,
    "Senegal": 17.7, "Sudan": 48, "Libya": 7, "Mongolia": 3.4,
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
    # Acute lymphoblastic leukaemia is far rarer than leukaemia overall (~10/100k
    # prevalent) — it must not inherit the all-leukaemia rate or AML's figures.
    "all_leukemia":      (10, False),
    "lymphoma":          (75, True),
    "myeloma":           (48, True),
    "brain_cancer":      (30, True),
    "sarcoma":           (15, True),
    "cancer_generic":    (850, True),   # broad "cancer"/"oncology"/"solid tumor"
    "diabetes":          (11000, False),
    # Type 1 is roughly 5-10% of all diabetes; ~300/100k is an order-of-magnitude
    # figure (US ~570, UK ~600, much lower in low-income settings).
    "diabetes_type1":    (300, True),
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

# regex → category. First match wins, so SPECIFIC rules come before general ones.
#
# Identity rules (these were the source of real mislabels):
#   * Site-specific cancer rules require a cancer word. A bare site name is NOT a
#     cancer: "overactive bladder", "pancreatitis", "benign prostatic hyperplasia",
#     "breast fibroadenoma", "cervical dystonia", "gastric ulcer" are not cancers.
#   * Kidney-cancer terms are matched explicitly; "renal"/"kidney" alone is not
#     (renal failure is chronic kidney disease, not kidney cancer).
#   * "\ball\b" is the English word "all" ("all-comers", "all solid tumors") — never
#     treated as the leukaemia abbreviation; only the full phrase is.
#   * Generic words like "syndrome" / "deficiency" no longer imply a rare disease
#     (metabolic syndrome, IBS, vitamin D deficiency are very common).
_C = r"(?:cancer|carcinoma|adenocarcinoma|neoplasm|neoplasms|tumou?rs?|malignan\w*)"
_RULES = [
    (rf"breast {_C}|mammary {_C}|\btnbc\b|triple[- ]negative|\bdcis\b|ductal carcinoma|lobular carcinoma|"
     r"her2[- ](?:positive|low|\+)|\bhr[- ]?positive", "breast_cancer"),
    (rf"prostat\w* {_C}|\bm?crpc\b|\bmhspc\b|\bmcspc\b", "prostate_cancer"),
    (rf"(?:colorectal|colon|rectal|rectum|bowel) {_C}|\bcrc\b", "colorectal_cancer"),
    (rf"lung {_C}|\bnsclc\b|\bsclc\b|non[- ]small[- ]cell|small[- ]cell lung", "lung_cancer"),
    (r"(?:uveal|ocular|choroidal|conjunctival|mucosal|intraocular) melanoma", "default"),   # not skin melanoma
    (r"melanoma", "melanoma"),
    (rf"ovarian {_C}|fallopian {_C}|primary peritoneal|epithelial ovarian", "ovarian_cancer"),
    (rf"pancreatic {_C}|\bpdac\b|pancreatic ductal", "pancreatic_cancer"),
    (rf"(?:gastric|stomach) {_C}|gastroesophageal junction|gastro-?oesophageal junction|\bgej\b", "gastric_cancer"),
    (r"hepatocellular|liver (?:cancer|carcinoma)|\bhcc\b", "liver_cancer"),
    (rf"bladder {_C}|urothelial|transitional cell", "bladder_cancer"),
    (rf"renal cell|kidney {_C}|renal {_C}|\brcc\b|wilms", "kidney_cancer"),
    (rf"cervical {_C}|cervical intraepithelial|cancer of the cervix|cervix {_C}", "cervical_cancer"),
    (r"acute lymphoblastic|acute lymphocytic|lymphoblastic leuk\w*|\bb-all\b|\bt-all\b|\bph\+ all\b", "all_leukemia"),
    (r"leukemia|leukaemia|\baml\b|\bcml\b|\bcll\b", "leukemia"),
    (r"lymphoma|\bdlbcl\b|hodgkin", "lymphoma"),
    (r"myeloma", "myeloma"),
    (r"glioblastoma|glioma|brain (?:tumou?r|cancer)", "brain_cancer"),
    (r"sarcoma", "sarcoma"),
    # Type 1 BEFORE the general diabetes rule, otherwise it inherits type-2 scale.
    (r"type 1 diabet|type i diabet|diabetes,? type 1|diabetes mellitus,? type 1|\bt1d\b|\bt1dm\b|"
     r"juvenile diabet|insulin[- ]dependent diabet", "diabetes_type1"),
    (r"diabet", "diabetes"),
    (r"obesity|overweight", "obesity"),
    # Specific "hypertension" that is NOT systemic high blood pressure → no category
    # (generic placeholder), instead of inheriting hypertension's ~30,000/100k.
    (r"pulmonary (?:arterial )?hypertension|\bpah\b|portal hypertension|intracranial hypertension|ocular hypertension",
     "default"),
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
    # Chronic kidney disease: explicit terms only. Kidney TRANSPLANT, kidney stones,
    # etc. are different populations and fall through to the generic placeholder.
    (r"chronic kidney|kidney disease|renal (?:failure|insufficiency|impairment|disease)|end[- ]stage renal|"
     r"\besrd\b|\bckd\b|dialysis|diabetic nephropathy", "ckd"),
    (r"\bhiv\b|acquired immunodeficiency", "hiv"),
    (r"hepatitis|\bhbv\b|\bhcv\b", "hepatitis"),
    (r"tuberculosis|\btb\b", "tuberculosis"),
    (r"covid|sars-cov|coronavirus", "covid"),
    # generic cancer LAST so specific tumours match first
    (r"cancer|carcinoma|tumou?r|oncolog|neoplasm|malignan", "cancer_generic"),
    (r"rare disease|rare disorder|orphan|dystrophy|\brare\b", "rare_disease"),
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

    When no disease-specific category matches, the generic placeholder rate is used
    and EVERY entry is labelled confidence="placeholder" with an explicit note, so a
    number invented from a catch-all rate can never be mistaken for a real estimate.
    """
    cat = classify(indication)
    placeholder = cat == "default"
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
            "source": (f"TrialLens epidemiology model — {label} prevalence × population"
                       if not placeholder else
                       "Generic placeholder rate — no disease-specific model for this indication"),
            "confidence": "placeholder" if placeholder else "modeled",
            "note": ("PLACEHOLDER: this indication has no disease-specific model, so a generic rate "
                     "was applied. Do not use for planning — enter your own prevalence."
                     if placeholder else
                     "Model estimate (rate × population) — override with known figures"),
            "method": "modeled",
            "category": cat,
        }
    return out or None


def supported_categories() -> list:
    return sorted({cat for _, cat in _RULES})
