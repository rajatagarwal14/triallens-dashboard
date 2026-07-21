# TrialLens — Clinical Trial Intelligence Dashboard

A clinical-trial landscape and feasibility platform for clinical planning analysts and
therapy-area leads. Built on the live **ClinicalTrials.gov v2 API**, it turns raw registry
data into planning intelligence: competitive landscape, geographic strategy, site and
investigator selection, enrolment feasibility, and cohort comparison.

**No AI/LLM API key required.** Every analytic — including the epidemiology and NLP
components — is deterministic and runs entirely offline against public data.

---

## Quick start (plug and play)

**Prerequisites:** Python 3.9+ and Node 18+.

```bash
git clone https://github.com/rajatagarwal14/triallens-dashboard.git
cd triallens-dashboard
./start.sh
```

`start.sh` does everything: creates the Python venv, installs backend + frontend
dependencies, and launches both servers.

| Service | URL |
|---|---|
| Frontend (React + Vite) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/api/docs |

Press `Ctrl+C` to stop both.

<details>
<summary>Manual start (if you prefer running them separately)</summary>

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```
</details>

---

## Features

| Tab | What it does |
|---|---|
| **Discovery** | Live trial search with phase, status, study-type, sponsor-class, country and year filters. Filters are shared across every tab. |
| **Historical** | Trend analytics — trial volume, enrolment velocity (segmentable by phase/sponsor), status and phase breakdowns, plus the **Cohort Comparison** engine. |
| **Competition** | Sponsor leaderboard and a trial-completion timeline (monthly / bi-monthly / quarterly) showing when competitor studies finish. |
| **Research** | Planning insights: anticipated trial completions by year, time-to-completion, trial discontinuation rates, enrolment benchmarks and feasibility pace. |
| **Geo** | World choropleth with three layers — trial **Density**, disease **Prevalence**, and **Recruitment Competition** — plus country drill-down, site mapping, radius search and white-space analysis. |
| **Sites** | Site-activity leaderboard and investigator experience scorecards, with an enrolment-rate indicator. |
| **Protocol** | Eligibility-criteria analyzer with a restrictiveness percentile versus peer trials. |

### Cohort Comparison
Given the active search, the engine **auto-suggests 1–4 cohorts** and compares enrolment
pace, duration and discontinuation across them. Suggestions are editable (switch axis,
rename, drop). Available grouping axes:

- **Population scope** — exact (indication + qualifier) / indication-only / basket
- **Line of therapy** — first-line / relapsed-refractory / unspecified
- **Biomarker selection** — biomarker-selected vs all-comers
- **Regimen** — monotherapy vs combination
- **Geography** — China-only vs global (incl./excl. China)

---

## Architecture

```
triallens-dashboard/
├── backend/                 FastAPI service
│   ├── main.py              app + router registration
│   ├── routers/             studies · landscape · competition · research
│   │                        · cohorts · sites · similarity · alerts
│   └── services/
│       ├── ct_gov.py        ClinicalTrials.gov v2 client + normalizer
│       ├── prevalence.py    curated prevalence (GLOBOCAN/GBD-derived)
│       ├── epidemiology.py  deterministic rate × population model
│       ├── eligibility_nlp.py  rule-based criteria extraction
│       └── similarity.py    TF-IDF trial similarity
└── frontend/                React 18 + TypeScript + Vite
    └── src/
        ├── pages/           one page per tab
        ├── components/      shared UI + CohortPanel
        ├── context/         cross-tab shared filter state
        └── data/            bundled official India boundary GeoJSON
```

**Stack:** FastAPI · httpx · scikit-learn (TF-IDF) · React · TypeScript · Vite ·
TanStack Query · Recharts · React-Leaflet · Tailwind CSS

### How the data works
- **Trial data** — live from the ClinicalTrials.gov v2 API (up to 1,000 studies per query,
  with a coverage badge disclosing the analysed sample vs the total).
- **Prevalence** — two-tier: a curated table for common indications (GLOBOCAN 2022 /
  GBD 2021-derived), falling back to a deterministic `population × category-rate` model so
  any indication resolves. Every value is labelled *curated* or *modeled*, and is manually
  overridable in the White-Space panel.
- **Recruitment competition** — competing enrolment slots ÷ prevalent patients × 100,000.
- **Choropleths** — quantile classification into discrete, numerically-labelled classes
  (the GBD/WHO convention), so skewed data stays readable.

---

## Known limitations

These are inherent to the public registry data and are surfaced in the UI rather than hidden:

- **Competition intensity double-counts** — a trial's full global enrolment target is
  counted in every country it runs in, so it is a *relative* demand-pressure proxy, not an
  allocated per-country figure.
- **Prevalence is disease-level** — biomarker/stage-defined trials inherit the whole-disease
  pool, so prevalence is an upper bound for narrow populations. Use the manual override.
- **Site enrolment rate is an activity rate** (% of a site's trials currently recruiting),
  not recruitment efficiency — per-site actuals do not exist in ClinicalTrials.gov.
- **Cohort classification is rule-based** on condition and eligibility free text, so it is
  directional. Every cohort is editable for this reason.
- The world map outline is fetched at runtime from a public GeoJSON source; India is drawn
  from a bundled official-boundary file.

---

## License

Private project. Trial data © ClinicalTrials.gov (public domain); basemap © OpenStreetMap
contributors, © CARTO.
