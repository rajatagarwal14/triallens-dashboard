# Eligibility extraction in Claude Science → TrialLens

A spec you can hand to **Claude Science** to produce the structured cohort fields
TrialLens needs, without TrialLens ever holding an API key.

**Why this route.** The hardest problem in the cohort engine is that staging,
line of therapy, refractoriness, and biomarker gating live in free-text
eligibility criteria. Rule-based parsing of that text is brittle. Claude Science
runs on your existing Claude plan and on your own machine, so the extraction can
happen there — and TrialLens just reads the resulting file.

```
Claude Science                          TrialLens
──────────────                          ─────────
run extraction over your trial   ──►    scripts/import_extractions.py
corpus, export JSONL                    → backend/.cache/extract/v1/*.json
                                        → cohort engine reads structured fields
                                          (no key, no network)
```

---

## 1. Input

Pull the trials you care about. Either use the ClinicalTrials.gov API directly,
or export the NCT-ID list from TrialLens and fetch each record. For each trial
you need three things:

| Field | Source |
|---|---|
| `nctId` | `protocolSection.identificationModule.nctId` |
| `conditions` | `protocolSection.conditionsModule.conditions` |
| `eligibility_criteria` | `protocolSection.eligibilityModule.eligibilityCriteria` |

Skip trials with no eligibility text — there is nothing to extract.

---

## 2. Extraction prompt

Use this verbatim as the system prompt. It is the same text TrialLens uses
(`backend/services/claude_extract.py` → `INSTRUCTIONS`), so results stay
consistent across both paths.

```
You extract structured cohort fields from clinical trial eligibility criteria.
Your output feeds a clinical-planning tool used for feasibility analysis, so
precision matters far more than completeness.

Rules:
- Extract ONLY what the criteria state. Never infer from the disease name, the
  trial title, or typical practice. If the criteria are silent on a field, use
  its "unspecified" / "not_stated" / empty-list / false default.
- Quote evidence verbatim from the criteria. Do not paraphrase in `snippet`.
- `line_of_therapy`: "relapsed_refractory" requires explicit relapsed/refractory
  or prior-progression language. "treatment_naive" requires explicit untreated /
  treatment-naive / newly-diagnosed language. Prior therapy merely being
  *permitted* is NOT "relapsed_refractory" — that is "unspecified".
- `refractory_to`: list only agents/classes the patient must have failed. An
  agent listed as prohibited concomitant medication is NOT refractoriness.
- `biomarker_selected`: true only when a marker gates enrollment. A marker
  measured as a baseline lab, stratification factor, or exploratory endpoint
  does NOT count as selection.
- `disease_stage`: copy the stage/phase term the criteria use. Do not translate
  between staging systems.
- `confidence`: reflect genuine uncertainty. Vague, templated, or internally
  contradictory criteria should score low. Do not default to a high value.

Set confidence below 0.5 whenever you are guessing; a low-confidence answer is
useful, a confidently wrong one is not.
```

User message per trial:

```
Conditions: {comma-separated conditions}
Title: {brief title}

ELIGIBILITY CRITERIA:
{eligibility criteria text}
```

---

## 3. Output schema

Every field is required. This mirrors `ExtractedEligibility` in
`backend/services/claude_extract.py` — the importer validates against it and
rejects anything that doesn't conform.

| Field | Type | Notes |
|---|---|---|
| `line_of_therapy` | enum | `treatment_naive` · `first_line` · `relapsed_refractory` · `later_line` · `unspecified` |
| `prior_therapy_required` | bool | true only when prior systemic therapy is an explicit inclusion requirement |
| `refractory_to` | string[] | drugs/classes the patient must have failed; `[]` if none |
| `biomarker_selected` | bool | true only when a marker **gates** enrollment |
| `biomarkers_required` | string[] | markers as written, e.g. `["JAK2 V617F"]`; `[]` if all-comers |
| `disease_stage` | string | stage/phase as written; `"not_stated"` if absent |
| `stage_system` | enum | `tnm` · `iss` · `dipss` · `ann_arbor` · `binet_rai` · `other` · `not_stated` |
| `confidence` | float | 0.0–1.0, self-assessed |
| `evidence` | object[] | `{ "field": "...", "snippet": "..." }`, one per non-default field |

---

## 4. Export format

**JSONL**, one record per line (a JSON array also works):

```json
{"nctId":"NCT01234567","prompt_version":"v1","extraction":{"line_of_therapy":"relapsed_refractory","prior_therapy_required":true,"refractory_to":["ruxolitinib"],"biomarker_selected":false,"biomarkers_required":[],"disease_stage":"not_stated","stage_system":"not_stated","confidence":0.86,"evidence":[{"field":"line_of_therapy","snippet":"relapsed or refractory to ruxolitinib"}]}}
```

A flat record (extraction fields alongside `nctId`) is also accepted.

`prompt_version` is optional but recommended — the importer warns if it doesn't
match the schema version this build expects, so a stale extraction can't be
silently mixed in.

---

## 5. Import into TrialLens

```bash
cd backend
python scripts/import_extractions.py ../extractions.jsonl --dry-run   # validate first
python scripts/import_extractions.py ../extractions.jsonl            # write to cache
```

Re-running is safe: already-cached trials are skipped unless you pass
`--overwrite`. The cache lives at `backend/.cache/extract/v1/` and is
gitignored — it is derived data, regenerable from the JSONL.

---

## 6. Validate before trusting it

**Do this before grouping cohorts on any extracted field.** Accuracy is not
self-evident, and a confidently wrong field is worse than no field.

```bash
python scripts/build_goldset.py --condition "myelofibrosis" --n 40
# a clinician labels the `label` blocks in backend/goldset/goldset.jsonl
python scripts/validate_extraction.py
```

The report gives per-field accuracy, precision/recall on the list fields, and
**confidence calibration** — it flags the case where high- and low-confidence
rows score alike, meaning the confidence number is noise and cohorts should be
gated on human review instead.

Adopt a field only when its accuracy clears the bar your planning decisions
require. Fields are independent — `stage_system` being weak doesn't disqualify
`line_of_therapy`.

---

## 7. Scale notes

- ~1,000 trials is the TrialLens per-search ceiling; extraction is **one-time per
  NCT ID**, so cost does not recur when the same trial appears in later searches.
- Eligibility text is effectively immutable, so the cache does not go stale.
- Changing the prompt or schema means bumping `PROMPT_VERSION` in
  `claude_extract.py`, which changes the cache path and forces clean
  re-extraction rather than mixing versions.
- Keep the exported JSONL — it is the source of truth. The cache is disposable.

---

## What this does *not* fix

Being explicit, because these were on an earlier list of mine and don't belong
to this workflow:

- **Site "enrolment rate"** stays a %-recruiting proxy. Real per-site
  productivity needs a licensed operational dataset (e.g. Medidata), not
  extraction from public registry text.
- **Competition-intensity double-counting** likewise needs allocated per-country
  enrollment actuals.
- **Prevalence for biomarker/stage-defined subpopulations** is a separate
  curated-data task, not an eligibility-extraction one.
