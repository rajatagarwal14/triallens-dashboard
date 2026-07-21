import re
from dataclasses import dataclass, field


BIOMARKER_PATTERNS = [
    r'\bHER2[+-]?\b', r'\bBRCA\d?\b', r'\bEGFR\b', r'\bALK\b', r'\bPD-L1\b',
    r'\bFLT3\b', r'\bIDH[12]\b', r'\bKRAS\b', r'\bNRAS\b', r'\bBRAF\b',
    r'\bPIK3CA\b', r'\bTP53\b', r'\bMET\b', r'\bRET\b', r'\bNTRK\b',
    # CD markers, but NOT "CD4 count"/"CD8 cells" (immune labs, not tumour biomarkers)
    r'\bCD\d+\b(?!\+?\s*(?:cells?|count|t[\s-]?cell|lymph))',
    r'\bPD-?1\b', r'\bCTLA-?4\b', r'\bMMR\b', r'\bMSI-?H?\b',
    r'\bTMB\b', r'\bER[+-]\b', r'\bPR[+-]\b', r'\bHR[+-]\b',
]

STAGE_PATTERNS = [
    r'\bStage\s+(?:I{1,3}V?|[1-4])\b',
    r'\bstage\s+(?:I{1,3}V?|[1-4])(?:\s*[ABC])?\b',
    r'\b(?:early|advanced|metastatic|locally advanced|relapsed|refractory|recurrent)\b',
]

PRIOR_TX_PATTERNS = [
    r'(?:prior|previous|received)\s+(?:\w+\s+){0,3}(?:therapy|treatment|chemotherapy|radiation)',
    r'\d+\s+(?:prior|previous)\s+(?:lines?|regimens?)',
    r'(?:treatment[- ]naive|treatment[- ]experienced|chemotherapy[- ]naive)',
]

COMPLEXITY_KEYWORDS = [
    'mutation', 'positive', 'negative', 'expression', 'prior treatment',
    'refractory', 'relapsed', 'stage', 'grade', 'specific', 'documented',
    'confirmed', 'required', 'must have', 'adequate', 'performance status',
    'ecog', 'biomarker', 'measurable disease', 'biopsy',
]


def _extract_age_range(text: str) -> dict:
    min_age = max_age = None
    m = re.search(r'(\d+)\s*(?:year|yr)s?\s*(?:of\s+age\s+)?(?:to|through|[-–])\s*(\d+)\s*(?:year|yr)', text, re.I)
    if m:
        min_age, max_age = int(m.group(1)), int(m.group(2))
    else:
        m2 = re.search(r'(?:≥|>=|at\s+least|minimum\s+age[^:]*?)\s*(\d+)\s*(?:year|yr)', text, re.I)
        if m2:
            min_age = int(m2.group(1))
        m3 = re.search(r'(?:≤|<=|no\s+more\s+than|maximum\s+age[^:]*?)\s*(\d+)\s*(?:year|yr)', text, re.I)
        if m3:
            max_age = int(m3.group(1))
    return {"min": min_age, "max": max_age}


def _extract_biomarkers(text: str) -> list[str]:
    found = set()
    for pat in BIOMARKER_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            found.add(m.group(0).upper())
    return sorted(found)


def _extract_stage(text: str) -> list[str]:
    found = set()
    for pat in STAGE_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            found.add(m.group(0).strip())
    return list(found)[:6]


def _extract_prior_treatment(text: str) -> list[str]:
    found = []
    for pat in PRIOR_TX_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            snippet = m.group(0).strip()
            if snippet not in found:
                found.append(snippet)
    return found[:5]


def _complexity_score(text: str) -> float:
    lower = text.lower()
    count = sum(lower.count(kw) for kw in COMPLEXITY_KEYWORDS)
    # count exclusion bullets as additional complexity
    excl_lines = len([l for l in text.split('\n') if l.strip().startswith('-') or l.strip().startswith('•')])
    score = min(10.0, round((count / 2.5) + (excl_lines * 0.15), 1))
    return score


def _split_criteria(text: str) -> dict[str, str]:
    inc = exc = text
    m = re.split(r'(?i)exclusion\s+criteria[:\s]*', text, maxsplit=1)
    if len(m) == 2:
        inc_raw = m[0]
        exc = m[1]
        inc_m = re.split(r'(?i)inclusion\s+criteria[:\s]*', inc_raw, maxsplit=1)
        inc = inc_m[-1]
    return {"inclusion": inc.strip(), "exclusion": exc.strip()}


def extract(criteria_text: str) -> dict:
    if not criteria_text:
        return {}
    split = _split_criteria(criteria_text)
    inclusion = split["inclusion"]
    exclusion = split["exclusion"]
    # When no exclusion header was found, inclusion == exclusion == full text;
    # treat the whole blob as inclusion so we don't double-count.
    has_split = inclusion != exclusion

    inc_biomarkers = _extract_biomarkers(inclusion)
    exc_biomarkers = _extract_biomarkers(exclusion) if has_split else []
    # A biomarker that appears ONLY in exclusion is a rule-out, not a selection
    # marker — surface those separately instead of mislabeling them as required.
    excluded_only = sorted(set(exc_biomarkers) - set(inc_biomarkers))

    return {
        "ageRange": _extract_age_range(criteria_text),
        # Selection biomarkers = detected in the inclusion section
        "biomarkers": inc_biomarkers,
        "biomarkersExcluded": excluded_only,
        "diseaseStage": _extract_stage(criteria_text),
        # Prior-treatment signals come from inclusion only, so "no prior therapy"
        # in the exclusion list is never reported as a requirement.
        "priorTreatment": _extract_prior_treatment(inclusion),
        "complexityScore": _complexity_score(criteria_text),
        "inclusionText": inclusion,
        "exclusionText": exclusion,
    }
