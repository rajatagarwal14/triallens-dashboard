# Prevalence review stubs

Landing area for `epidemiology.json` from a Claude Science `indication-dossier`
run, via `scripts/import_dossier.py`.

**These are not prevalence data yet.** The dossier reports prevalence as
narrative prose plus citations; TrialLens needs `country -> prevalent patients`.
The importer therefore extracts the narrative, its sources, and the documented
gaps, and leaves `countries` **empty** rather than inventing a mapping.

Workflow: a reviewer reads `narrative` + `sources`, fills `countries`, sets
`provenance.reviewed_by`, then the values are merged into
`backend/services/prevalence.py::_DATA`.

Leave a country out rather than guessing — an absent country falls back to the
modeled estimate, which is labelled as modeled in the UI. A wrong hard number is
not.
