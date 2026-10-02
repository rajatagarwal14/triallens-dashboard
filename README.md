# TrialLens — Clinical Trial Intelligence Dashboard

A clinical-trial landscape and feasibility platform for clinical planning analysts and
therapy-area leads. Built on the live **ClinicalTrials.gov v2 API**, it turns raw registry
data into planning intelligence: competitive landscape, geographic strategy, site and
investigator selection, enrolment feasibility, and cohort comparison.

**No AI/LLM API key required.** Every analytic — including the epidemiology and NLP
components — is deterministic and runs entirely offline against public data.

---

## Quick start (plug and play)

**Prerequisites:** Python 3.9+ and Node 20.19+ (or 22.12+). If you don't have these yet, the
Windows steps below tell you exactly where to get them — no other setup needed.

### Windows (no command line required)

1. Download this project: green **Code** button above → **Download ZIP** → unzip it
   anywhere (e.g. your Desktop). *(Or `git clone` the repo if you have Git.)*
2. Double-click **`start.bat`** inside the unzipped folder.
3. First run only: it will ask you to install [Python](https://www.python.org/downloads/)
   and/or [Node.js](https://nodejs.org/) if either is missing — a short one-time
   install, no configuration needed (for Python, tick **"Add python.exe to PATH"**
   during setup). Once installed, double-click `start.bat` again.
4. Two windows will open (backend + dashboard) and your browser will open
   automatically to the dashboard. That's it.

To stop TrialLens, close those two windows, or double-click **`stop.bat`**.
Running `start.bat` again re-uses what's already running instead of erroring —
it's safe to double-click any time.

### macOS / Linux

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

Press `Ctrl+C` to stop both (macOS/Linux), or see the Windows steps above.

### Docker (one command, any OS — the option for sending this to someone else)

The only prerequisite is [Docker](https://www.docker.com/products/docker-desktop/)
itself — no Python, no Node, no version-matching. This builds the whole app
(backend + frontend) straight from GitHub and runs it as one container on one port:

```bash
docker run --rm -p 127.0.0.1:8000:8000 $(docker build -q https://github.com/rajatagarwal14/triallens-dashboard.git)
```

Open **http://localhost:8000** once it finishes (the first run takes a minute or
two to build; it's fast on every run after, since Docker caches the layers).

> This only works if the repo is **public** — a private repo needs the person
> running it to already have `git` access configured. If you've cloned it
> yourself, the equivalent single command from inside the folder is:
> ```bash
> docker compose up --build
> ```
> then open http://localhost:8000. `Ctrl+C` stops it; `docker compose down`
> also removes the container.

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
- **Trial data** — live from the ClinicalTrials.gov v2 API, the **only** external service
  TrialLens talks to (no API keys, no other third-party calls). For every search the backend
  retrieves **every matching study** page by page (`nextPageToken`), keeps one record per NCT
  ID, and stores them locally under `backend/.cache/datasets/`. Analytics are computed over the
  complete set. While retrieval runs the badge reads *"Retrieved 3,000 of 16,873 · partial"*
  and the charts refresh as pages arrive; when finished it reads *"Complete · 16,873 trials ·
  retrieved <time>"*. Failed pages are retried with back-off (honouring the server's
  `Retry-After`), everything already retrieved is kept, and changing the search starts or
  reloads the matching dataset. Repeating a search reuses the stored copy (fresh for 6 h);
  after that only records changed since the last retrieval are fetched and merged by NCT ID,
  with a full reconcile every 7 days to catch deletions. Very large searches stop at a safety
  limit of 20,000 studies and offer a **Retrieve all** button.
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
- **Prevalence has gaps by design.** Only indications with a curated or category-modelled
  rate get prevalence/competition-intensity maps; for anything else those layers are empty
  rather than showing an invented number. Matches are by disease identity (Type 1 diabetes
  is not Type 2; ALL is not AML); a *parent* match (e.g. a subtype matched to its parent
  disease) is flagged as an upper bound.
- **Sites tab "target enrolment" is the size of the trials a site participates in**, not
  patients that site recruited (the registry has no per-site accrual).
- **Upcoming readouts use sponsors' own estimated dates** for trials that are still active;
  they often slip.
- **Memory:** a 17,000-study dataset makes the backend use roughly 0.7 GB of RAM.

---

## Configuration

All optional; defaults work.

| Variable | Default | Meaning |
|---|---|---|
| `TRIALLENS_MAX_STUDIES` | `20000` | Safety cap per dataset (user can lift it with *Retrieve all*) |
| `TRIALLENS_DATASET_FRESH_HOURS` | `6` | Reuse a stored dataset without re-checking for this long |
| `TRIALLENS_RECONCILE_DAYS` | `7` | Full re-retrieval interval (catches deleted records) |
| `TRIALLENS_PAGE_DELAY` | `0.4` s | Pause between page requests (be polite to the API) |
| `TRIALLENS_CACHE_MB` | `1024` | Disk budget for stored datasets (least-recently-used evicted) |
| `HTTPS_PROXY` / `NO_PROXY` | — | Corporate proxy (standard variables) |
| `SSL_CERT_FILE` | — | Path to your company root certificate (.pem) |
| `TRIALLENS_USE_SYSTEM_CERTS` | off | `1` = trust the Windows/macOS certificate store (needs `pip install truststore`) |
| `VITE_CARTO_API_KEY` / `VITE_MAP_TILE_URL` | unset | Optional Geo basemap (frontend, build-time; see `frontend/.env.example`). The map works without one |

### Company networks

TrialLens needs HTTPS access to `clinicaltrials.gov`, plus (first install only) your approved
Python and npm package sources. If something fails, double-click **`diagnose.bat`** (or run
`./diagnose.sh`): it checks DNS, proxy and TLS and tells you what to ask IT for. TLS
verification is never disabled. `start.bat` may try `winget` to install Python/Node; on a
locked-down laptop have IT provide them instead.

### Security notes

There is **no login and no HTTPS** — it is built to run on your own computer and binds to
`127.0.0.1` only. Do not expose it on a network as-is; shared hosting needs an authenticated
reverse proxy. The packaged static server is protected against path traversal. Frontend
dependencies are locked (`npm ci`) and currently report 0 `npm audit` findings.

### Data provenance

- `frontend/src/data/world.json` — world country outlines (low resolution), originally from
  the public `holtzy/D3-graph-gallery` `world.geojson` (derived from Natural Earth); bundled
  so the map needs no external request. Names/properties reduced to `name`, coordinates
  rounded to 3 decimals. Confirm licence terms with your own compliance team if required.
- `frontend/src/data/india-official.json` — official India outline (see git history).
- Prevalence figures: curated from GLOBOCAN 2022 / GBD 2021 / literature; see `services/prevalence.py`.

### Tests

```bash
cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
```

CI (`.github/workflows/ci.yml`) runs them on Linux and Windows and builds the frontend.

---

## License

Private project. Trial data © ClinicalTrials.gov (public domain); basemap © OpenStreetMap
contributors, © CARTO.
