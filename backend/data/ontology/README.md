# Disease ontology

One JSON file per indication, produced by the Claude Science `indication-dossier`
skill and imported with `scripts/import_dossier.py`.

`parent` links chain entries into a **progression continuum** — run the dossier
once per disease stage and the chain assembles itself:

    Blast phase MPN  ->  Myelofibrosis  ->  Myeloproliferative neoplasm

That chain is what lets the cohort engine tell a *continuum-spanning* trial from
a genuine cross-family basket, instead of calling both "basket".

`aliases` is the match key against ClinicalTrials.gov condition strings
("PMF", "Primary myelofibrosis", "MF" all resolve to one node).

**No entry is authoritative until `provenance.reviewed_by` is set by a
clinician.** The importer writes it as `null` deliberately.

Schema: see `scripts/import_dossier.py::import_meta`.
