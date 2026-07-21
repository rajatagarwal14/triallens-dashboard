# TrialLens — Requirements Feasibility & Completeness Review

Reviewed against the FA-SA spec photos (use cases D–J) + verified against the live
ClinicalTrials.gov v2 API. **No code changed — feasibility assessment only.**

Legend — **Status:** ✅ done · ⚠️ partial · ❌ not built.
**Feasibility:** 🟢 buildable now (public API) · 🟡 buildable but needs infra/data you provide · 🔴 blocked (needs IQVIA-internal systems).

---

## Intro requirement — Protocol complexity score → Design Analytics (SDA/DIPA)
- **Status ✅** — complexity score built in Protocol Analyzer; feeds the analytics narrative.

## D. Automated Protocol Similarity / Comparator Identification
- **Similarity ranking (TF-IDF, top 10–20 + score):** ✅ done (Protocol Analyzer).
- **Design-parameter extraction (phase, condition, intervention model, endpoint, age):** ✅ mostly (shown in Protocol header + eligibility). 🟢 can add primary-endpoint extraction.
- **Competition intensity score = competing enrollment ÷ patient pool per country:** ❌ not built. 🟡 **buildable** — we have per-country enrollment; the "patient pool" needs prevalence. We have prevalence for ~14 indications only, so it works for those and needs an epi source (or AI lookup) for the rest.

## E. Site & Investigator Intelligence Pipeline
- **Extract facilities per indication+country:** ✅ done (Geo site panel).
- **Site-activity database (which sites ran how many trials, enrollment performance):** ❌ not built. 🟢 **buildable now** — aggregate facility across trials (count + summed enrollment). Pure API.
- **Investigator (PI) extraction + experience scorecard (# trials, therapeutic focus, enrollment track record):** ❌ not built. 🟢 **buildable now** — *verified* the API exposes `overallOfficials` (PI name, role `PRINCIPAL_INVESTIGATOR`, affiliation) + per-location contacts. Aggregate per PI.
- **Cross-reference IQVIA CTMS/IEP → "high-performing sites NOT yet in IQVIA's network":** 🔴 **blocked** — the public half (site performance) is buildable, but "not in IQVIA's network" requires the internal IQVIA network list. Needs your internal data feed.

## F. Real-Time Trial Landscape Monitoring (Watchdog Alerts)
- **New competitor trials registered:** ✅ done (bell alert, filter-aware, `StudyFirstPostDate`).
- **Status-change detection (Recruiting→Completed) + enrollment-target amendments:** ❌ not built. 🟡 **buildable + needs persistence** — `LastUpdatePostDate` flags changed records; to know *what* changed you must store prior snapshots and diff them (small DB).
- **Scheduled daily script (cron / Azure Function):** ❌. 🟡 **buildable + needs infra** — a serverless/cron job, not a static frontend.
- **Email / Teams push alerts:** ❌. 🟡 **buildable + needs infra** — SMTP or a Teams webhook + credentials.

## G. Enrollment Velocity Trend Analysis
- **Pull ≤10-yr trials with enrollment/start/completion:** ✅ done.
- **Historical velocity trend (faster/slower over time):** ✅ done (Historical chart + Research forecast).
- **Segment by phase, geography, sponsor type:** ⚠️ partial — those breakdowns exist as separate panels; 🟢 **buildable now** to add a segmentation toggle directly on the velocity chart (data already present).

## H. Eligibility Criteria NLP Engine
- **Full-text inclusion/exclusion criteria:** ✅ done.
- **Structured entities (age, biomarkers, prior treatment, disease stage):** ✅ done.
- **Protocol complexity score:** ✅ done.
- **Compare criteria across competing trials → "how restrictive vs the market":** ❌ not built. 🟢 **buildable now** — compute complexity across all indication trials, show this protocol's percentile vs market.

## I. Geospatial Enrollment Heatmaps
- **Extract all sites globally + interactive heatmap:** ✅ done (Leaflet; equivalent to Folium/Plotly).
- **Trial density by region:** ✅ done (choropleth).
- **Competing demand vs available patient population + white-space:** ✅ done (prevalence layer + white-space score).
- **`filter.geo` (lat/lng/distance):** ⚠️ we use country-level, not radius. 🟢 **buildable now** — *verified* `filter.geo=distance(lat,lng,100mi)` works (1,586 NSCLC within 100mi of NYC). Could add "sites within X mi of a point."

## J. Automated GAI Template Pre-Population  *(spec calls this the highest-value daily automation)*
- **Take CRM#, indication, phase, target countries → auto-fill a GAI template:** ❌ not built.
  - 🟢 **Buildable now (public-data content):** auto-populate indication landscape, competitor trials, enrollment benchmarks, country/site recommendations, and export to docx/pdf.
  - 🔴 **Needs you to provide:** (a) the actual IQVIA **GAI template format**, and (b) the **CRM number** is an internal identifier — we can accept it as a label but cannot look it up in IQVIA systems.

---

## Bottom line — can it all be implemented?

**Yes, ~85% is buildable now on the public API.** Everything currently missing that depends only on ClinicalTrials.gov data is feasible:
- 🟢 **Buildable immediately (no new inputs):** E site-activity DB, E investigator scorecards, H restrictiveness-percentile, G velocity segmentation, I radius search, D competition-intensity (for the ~14 covered indications), J template-generator scaffold.

**Four things require inputs only you/IQVIA can supply (not a code limitation):**
1. 🔴 **IQVIA internal CTMS/IEP/SiteTrove data** — for E's "sites not yet in IQVIA's network" cross-reference.
2. 🟡 **Prevalence / patient-pool data beyond ~14 indications** — for D competition-intensity and richer white-space (epi source or AI key).
3. 🟡 **Deployment infra + secrets** — for F's scheduled job + email/Teams push (cron/Azure + SMTP/Teams webhook).
4. 🔴 **The real GAI template + CRM system access** — for J's full end-to-end.

**Nothing in the spec is technically impossible.** The blockers are data-access and infra, not capability.

## Sanity check on what's already built
- ✅ Backends compile, endpoints return correct data, TypeScript + Vite build pass, live smoke-tested, 0 console/render errors.
- ⚠️ Analytics run on the top-1000 sample per query (coverage badge discloses this); exact once the 121k backfill runs.
- ⚠️ Forecast is an explainable linear trend (labeled as such), not an ML model.
