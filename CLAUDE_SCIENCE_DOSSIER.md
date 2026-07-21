# Indication dossiers: Claude Science → TrialLens

How to use the Claude Science **`indication-dossier`** skill to fix two real
TrialLens gaps, with no API key and no runtime dependency.

**Which gaps.** (1) The cohort engine mislabels progression-continuum trials as
"basket" because it has no disease ontology. (2) The prevalence model covers ~15
indications and everything else falls back to a generic `250/100k` placeholder.

**Why this skill.** It is the one skill in Claude Science that overlaps clinical
planning — it covers *"the patient population, epidemiology, disease biology,
standard of care, regulatory precedent, and landmark clinical trials"*, and it
frames indications with **population nesting** (*"all patients in {child} are
patients in {parent}"*) — exactly the structure a progression ontology needs.

---

## 1. Run the dossier — once per disease stage

The chaining is the trick: run it per **stage**, not per disease, and the
`parent_indication` field links the stages into a continuum automatically.

For the myeloid pathway:

| Run | `indication` | expected `parent_indication` |
|---|---|---|
| 1 | `Myeloproliferative neoplasm` | *(none — top of chain)* |
| 2 | `Polycythemia vera` | Myeloproliferative neoplasm |
| 3 | `Essential thrombocythemia` | Myeloproliferative neoplasm |
| 4 | `Myelofibrosis` | Myeloproliferative neoplasm |
| 5 | `Blast phase MPN` | Myelofibrosis |

In Claude Science:

> Run the `indication-dossier` skill for the indication **"Myelofibrosis"**.
> Additional context: I am building a disease-progression ontology for clinical
> trial cohort analysis. Be precise about `parent_indication` and about which
> populations nest inside which — including secondary forms (post-PV MF,
> post-ET MF) and the transition to blast phase.

Phase 1 pauses to confirm the resolved indication identity — check it before
letting the expensive phases run. Each run writes to
`./do_not_commit/indication-dossier-<slug>/waypoints/`.

**If the `clinical-trials` / `pubmed` MCPs aren't connected**, the skill says so
and falls back to WebSearch against the public sources. Output is still usable;
sourcing is just less structured.

---

## 2. Import

```bash
cd backend
python scripts/import_dossier.py <dossier_workdir> --dry-run   # inspect first
python scripts/import_dossier.py <dossier_workdir>
```

Point it at the directory containing `waypoints/` (or at `waypoints/` itself).

---

## 3. What maps where — and what doesn't

The two waypoint files are **not** equally machine-readable. This is the single
most important thing to understand about this pipeline.

### `meta.json` → ontology — a real, structured import

| Waypoint field | Becomes | Used for |
|---|---|---|
| `indication_name` | `indication` / `slug` | node identity |
| `parent_indication` | `parent` | **the progression chain** |
| `aliases` | `aliases` | matching CT.gov condition strings ("PMF", "MF" → one node) |
| `icd_codes` | `icd_codes` | cross-referencing |
| `definition` | `definition` | reviewer context |
| `is_standard_diagnosis` | flagged on import | a non-standard indication changes trial matching |

Written to `backend/data/ontology/<slug>.json`. Chains assemble on read:

```
Blast phase MPN  ->  Myelofibrosis  ->  Myeloproliferative neoplasm
```

### `epidemiology.json` → prevalence — a **review stub**, not data

`prevalence_incidence` is **free-text prose plus sources**, with a `coverage`
flag. TrialLens needs `country -> prevalent patients`. Those are different
shapes, and no amount of parsing bridges them safely.

So the importer writes `backend/data/prevalence_review/<slug>.json` with the
narrative, its citations, the documented gaps — and **`countries` left empty for
a human to fill**. It does not infer numbers.

Leave a country out rather than guessing: an absent country falls back to the
modeled estimate, which the UI labels as modeled. A wrong hard number is not
labelled at all.

---

## 4. Review gate

Both importers write `provenance.reviewed_by: null`. **Nothing is authoritative
until a clinician sets it.** The dossier skill has anti-fabrication rules
(`references/00-research-standards.md`) and the `literature-review` skill is
built to avoid fabricated citations — but neither is a substitute for sign-off
on data that feeds planning decisions.

---

## 5. What this does *not* touch

- **Site "enrolment rate"** — stays a %-recruiting proxy. Real per-site
  productivity needs licensed operational data, which no dossier provides.
- **Competition-intensity double-counting** — needs allocated per-country
  enrolment actuals. Same.
- **Eligibility extraction** — a separate pipeline; see
  `CLAUDE_SCIENCE_EXTRACTION.md`.

---

## 6. Suggested first run

Do **Myelofibrosis** alone. It exercises the whole path, and it is the case where
the current basket rule is provably wrong — so you get a verifiable before/after
rather than a change you have to take on faith.
