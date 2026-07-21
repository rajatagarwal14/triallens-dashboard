import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import studies, similarity, landscape, competition, research, alerts, sites, cohorts
from services import ct_gov
from services.ct_gov import CTGovError

logger = logging.getLogger("triallens")

# Indications shown as quick-searches + the default Landscape/Geo condition.
_WARM_SEARCHES = [
    "Breast Cancer", "AML", "Lung Cancer", "Multiple Myeloma",
    "Type 2 Diabetes", "NSCLC", "Melanoma", "Alzheimer",
]


async def _warm_cache():
    """Pre-fill the TTL cache so the first demo click isn't a cold ~5s pull."""
    try:
        # Light Discovery-sized pulls for each quick-search (pageSize 25)
        await asyncio.gather(
            *[ct_gov.search_studies(condition=c, page_size=25) for c in _WARM_SEARCHES],
            return_exceptions=True,
        )
        # The heavy one: Landscape + Geo both default to "Cancer" @ pageSize 1000
        # (same cache key), so one warm covers both pages.
        await ct_gov.search_studies(condition="Cancer", page_size=1000)
        logger.info("Cache warm complete: %d searches", len(_WARM_SEARCHES) + 1)
    except Exception as e:  # never let warming crash startup
        logger.warning("Cache warm skipped: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fire-and-forget so the server starts accepting requests immediately.
    asyncio.create_task(_warm_cache())
    yield


app = FastAPI(title="TrialLens API", version="1.0.0", docs_url="/api/docs", lifespan=lifespan)


@app.exception_handler(CTGovError)
async def ctgov_error_handler(request: Request, exc: CTGovError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message, "upstream": "ClinicalTrials.gov"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(studies.router, prefix="/api/studies", tags=["studies"])
app.include_router(similarity.router, prefix="/api/similarity", tags=["similarity"])
app.include_router(landscape.router, prefix="/api/landscape", tags=["landscape"])
app.include_router(competition.router, prefix="/api/competition", tags=["competition"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(sites.router, prefix="/api/sites", tags=["sites"])
app.include_router(cohorts.router, prefix="/api/cohorts", tags=["cohorts"])


@app.get("/health")
async def health():
    return {"status": "ok", "source": "ClinicalTrials.gov API v2"}
