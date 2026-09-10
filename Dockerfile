# TrialLens — single-image build. Produces one container that serves both the
# API and the built frontend on port 8000, so a friend with only Docker
# installed can run the whole dashboard with one command — no Python, no
# Node, no version-matching, nothing else to install.

# ── Stage 1: build the frontend (React + Vite) ───────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: backend (FastAPI) + the built frontend, one process ────────────
FROM python:3.11-slim AS final
WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
EXPOSE 8000

# 0.0.0.0 is correct and required here — it's what makes the container's
# port reachable through Docker's own port mapping (-p 8000:8000). This is not
# the same as exposing it on the host machine's network: use
# `docker run -p 127.0.0.1:8000:8000 ...` to keep it local-machine-only, or
# `-p 8000:8000` to allow other devices on the same LAN to reach it too.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
