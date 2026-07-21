# Eligibility-extraction gold set

Ground truth for measuring whether Claude's eligibility extraction is accurate
enough to group cohorts on. **Nothing here should be labelled by an LLM** — a
gold set produced by the model under test measures self-consistency, not
accuracy.

## Workflow

```bash
# 1. Generate unlabelled rows from real trials
python scripts/build_goldset.py --condition "myelofibrosis" --n 40

# 2. A clinical reviewer fills in every `label` field in goldset.jsonl
#    (leave a field null if you are unsure — nulls are skipped, not counted wrong)

# 3. Measure
export ANTHROPIC_API_KEY=...
python scripts/validate_extraction.py
```

Re-running step 1 with a different `--condition` appends without duplicating,
so the set can span several therapy areas.

## Label fields

| Field | Values |
|---|---|
| `line_of_therapy` | `treatment_naive` · `first_line` · `relapsed_refractory` · `later_line` · `unspecified` |
| `prior_therapy_required` | `true` / `false` — true only when prior systemic therapy is an explicit inclusion requirement |
| `refractory_to` | list of drugs/classes the patient must have failed; `[]` if none. A prohibited concomitant medication is **not** refractoriness |
| `biomarker_selected` | `true` / `false` — true only when a marker **gates** enrollment, not when it is merely measured or used for stratification |
| `biomarkers_required` | list of required markers as written, e.g. `["JAK2 V617F"]`; `[]` if all-comers |
| `disease_stage` | stage/phase term as written, e.g. `metastatic`, `blast phase`; `not_stated` if absent |
| `stage_system` | `tnm` · `iss` · `dipss` · `ann_arbor` · `binet_rai` · `other` · `not_stated` |

Label **only what the criteria state** — do not infer from the disease name or
from standard practice. The extractor is held to the same rule, so inferring
during labelling will unfairly penalise correct extractions.

## Reading the report

- **Per-field accuracy** — adopt a field for cohort grouping only when it clears
  the bar your planning decisions require. Fields are independent: `stage_system`
  being weak does not disqualify `line_of_therapy`.
- **Set fields** — precision matters more than recall for `refractory_to` and
  `biomarkers_required`; a hallucinated drug silently mis-assigns a trial.
- **Confidence calibration** — if high- and low-confidence rows score alike, the
  confidence value is noise and cohorts must be gated on human review instead.

## Size

~40 trials per therapy area is enough to spot a field that is clearly broken.
Move to a few hundred before relying on the numbers to compare prompt versions.

`goldset.jsonl` is gitignored by default — it may embed large criteria text and
is reviewer-specific. Commit it deliberately if you want it shared.
