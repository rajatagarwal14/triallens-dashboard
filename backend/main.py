import asyncio
import logging
import pathlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from routers import studies, similarity, landscape, competition, research, alerts, sites, cohorts, datasets
from services import ct_gov
from services.datasets import manager as dataset_manager
from services.ct_gov import CTGovError

logger = logging.getLogger("triallens")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dataset_manager.shutdown()   # stop background retrievals cleanly


APP_VERSION = "1.2.0"
app = FastAPI(title="TrialLens API", version=APP_VERSION, docs_url="/api/docs", lifespan=lifespan)


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
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])


@app.get("/health")
async def health():
    return {"status": "ok", "app": "triallens", "version": APP_VERSION, "source": "ClinicalTrials.gov API v2"}


# ── Optional: serve the built frontend from this same process ───────────────
# Only active when frontend/dist exists (the Docker image builds it there). Registered
# LAST so it never shadows an /api/* route or /health; a catch-all can only be a fallback.
def mount_frontend(application: FastAPI, dist: pathlib.Path) -> None:
    dist = dist.resolve()
    if not dist.is_dir():
        return
    if (dist / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="frontend-assets")
    index = dist / "index.html"

    @application.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Resolve symlinks and ".." first, then require the result to stay inside dist.
        # Without this, /%2e%2e/%2e%2e/backend/main.py returned files outside the build.
        try:
            candidate = (dist / full_path).resolve()
            candidate.relative_to(dist)
        except (ValueError, OSError):
            return JSONResponse(status_code=404, content={"error": "Not found"})
        if candidate.is_file():
            return FileResponse(candidate)
        if full_path.startswith("api/"):          # unknown API path: a real 404, not the SPA
            return JSONResponse(status_code=404, content={"error": "Not found"})
        # Client-side routes resolve to the SPA shell.
        return FileResponse(index)


mount_frontend(app, pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist")
