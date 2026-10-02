"""Findings 2 & 3: a shared word must never be enough to claim a disease identity."""
import pytest
from services import prevalence, epidemiology


def _method(res):
    return {v["method"] for v in res.values()}


@pytest.mark.parametrize("query", [
    "Type 1 Diabetes", "Acute Lymphoblastic Leukemia", "Breast Fibroadenoma",
    "Type 1 Diabetes Mellitus", "Benign Breast Disease",
])
def test_lookalike_diseases_never_get_curated_figures_of_another_disease(query):
    res = prevalence.lookup(query)
    assert res, "an estimate (or explicit placeholder) must still be returned"
    assert "curated" not in _method(res), f"{query!r} was served curated data for a different disease"
    assert all(v.get("confidence") != "high" for v in res.values())


def test_type1_diabetes_is_not_given_type2_scale_numbers():
    t2 = prevalence.lookup("Type 2 Diabetes")["United States"]["prevalence"]
    t1 = prevalence.lookup("Type 1 Diabetes")["United States"]["prevalence"]
    assert t1 < t2 / 5


@pytest.mark.parametrize("query,expected", [
    ("Type 2 Diabetes", "curated"), ("type 2 diabetes mellitus", "curated"),
    ("Diabetes Mellitus, Type 2", "curated"),
    ("Metastatic Breast Cancer", "curated"), ("HER2-positive Breast Cancer", "curated"),
    ("Non-Small Cell Lung Cancer", "curated"), ("NSCLC", "curated"),
    ("Acute Myeloid Leukemia", "curated"), ("AML", "curated"),
    ("Multiple Myeloma", "curated"), ("Alzheimer's Disease", "curated"),
])
def test_genuine_matches_and_subtypes_still_resolve_to_the_curated_parent(query, expected):
    assert _method(prevalence.lookup(query)) == {expected}


@pytest.mark.parametrize("query,category", [
    ("Renal Failure", "ckd"), ("Chronic Kidney Disease", "ckd"), ("End Stage Renal Disease", "ckd"),
    ("Kidney Transplant", "default"), ("Renal Cell Carcinoma", "kidney_cancer"),
    ("Kidney Cancer", "kidney_cancer"), ("Breast Fibroadenoma", "default"),
    ("Type 1 Diabetes", "diabetes_type1"), ("Type 2 Diabetes", "diabetes"),
    ("Acute Lymphoblastic Leukemia", "all_leukemia"),
])
def test_epidemiology_classification(query, category):
    assert epidemiology.classify(query) == category


def test_generic_placeholder_is_labelled_so_it_cannot_pass_as_a_real_estimate():
    res = epidemiology.estimate("Some Unmodelled Syndrome Xyz")
    assert {v["confidence"] for v in res.values()} == {"placeholder"}
    assert all("placeholder" in v["note"].lower() for v in res.values())


def test_country_tables_use_the_registry_spelling():
    """ClinicalTrials.gov says 'Turkey (Türkiye)' (26k trials) and 'Russia' — keying our
    tables on other spellings silently dropped those countries from every prevalence map."""
    for name in ["Turkey (Türkiye)", "Russia", "South Korea", "United States", "China", "India"]:
        assert name in epidemiology._POP_M, name
    assert "Turkey (Türkiye)" in prevalence.lookup("Type 2 Diabetes")
    assert "Turkey" not in epidemiology._POP_M and "Russian Federation" not in epidemiology._POP_M
