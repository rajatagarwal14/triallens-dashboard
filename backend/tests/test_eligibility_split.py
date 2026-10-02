"""Finding 8: no exclusion heading must not duplicate inclusion text as exclusion."""
from services import eligibility_nlp as e


def test_no_exclusion_heading_leaves_exclusion_empty():
    out = e.extract("Inclusion Criteria:\n- Age >= 18\n- Confirmed melanoma")
    assert out["exclusionText"] == ""
    assert "melanoma" in out["inclusionText"]
    assert out["hasExclusionSection"] is False


def test_both_sections_split_normally():
    out = e.extract("Inclusion Criteria:\n- Age >= 18\nExclusion Criteria:\n- Pregnant")
    assert "Pregnant" not in out["inclusionText"]
    assert "Age" not in out["exclusionText"]
    assert out["hasExclusionSection"] is True


def test_exclusion_only_text():
    out = e.extract("Exclusion Criteria:\n- Pregnant")
    assert out["inclusionText"] == ""
    assert "Pregnant" in out["exclusionText"]


def test_unlabelled_text_is_treated_as_inclusion_only():
    out = e.extract("Adults with confirmed EGFR mutation.")
    assert out["exclusionText"] == ""
    assert "EGFR" in out["inclusionText"]


def test_ordinary_words_are_not_biomarkers():
    from services import eligibility_nlp as e
    out = e.extract("Inclusion Criteria:\n* All entry criteria are met.\n* Participants will ret ...\n* kit supplied")
    assert out["biomarkers"] == []
    assert "MET" in e.extract("Inclusion Criteria:\n* MET exon 14 skipping")["biomarkers"]


def test_star_bullets_count_towards_complexity():
    from services import eligibility_nlp as e
    plain = e._complexity_score("one line")
    starred = e._complexity_score("\n".join("* item" for _ in range(20)))
    assert starred > plain


def test_structured_age_is_used():
    from routers.landscape import _age_years
    assert _age_years("18 Years") == 18 and _age_years("6 Months") == 0.5 and _age_years("N/A") is None
