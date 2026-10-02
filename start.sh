#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "  TrialLens — Clinical Intelligence Dashboard"
echo "  ─────────────────────────────────────────────"
echo ""

hash_of() { shasum -a 256 "$1" | cut -d' ' -f1; }

# Node 20.19+ (or 22.12+) is required by the dashboard's build tool.
command -v node >/dev/null || { echo "  Node.js is not installed. Install the LTS version from https://nodejs.org/"; exit 1; }
node -e "const [a,b]=process.versions.node.split('.').map(Number);process.exit((a>22||(a===22&&b>=12)||(a===20&&b>=19))?0:1)" \
  || { echo "  Your Node.js ($(node --version)) is too old - TrialLens needs 20.19 or newer."; exit 1; }

# Never assume whatever is on a port is TrialLens.
port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
if port_busy 8000; then
  curl -s -m 3 http://127.0.0.1:8000/health | grep -q triallens \
    && { echo "  TrialLens backend is already running on :8000."; exit 0; } \
    || { echo "  Port 8000 is used by another program - not touching it. Free it and re-run."; exit 1; }
fi
if port_busy 5173; then
  echo "  Port 5173 is used by another program - not touching it. Free it and re-run."; exit 1
fi

# Backend setup
if [ ! -d "$BACKEND/.venv" ]; then
  echo "  [1/4] Creating Python virtual environment…"
  python3 -m venv "$BACKEND/.venv"
fi

# Install/refresh packages only when the dependency list changed.
REQ_HASH="$(hash_of "$BACKEND/requirements.txt")"
if [ "$REQ_HASH" != "$(cat "$BACKEND/.venv/.requirements.sha" 2>/dev/null)" ]; then
  echo "  [2/4] Installing Python dependencies…"
  "$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"
  echo "$REQ_HASH" > "$BACKEND/.venv/.requirements.sha"
else
  echo "  [2/4] Python dependencies are up to date."
fi

LOCK_HASH="$(hash_of "$FRONTEND/package-lock.json")"
if [ ! -d "$FRONTEND/node_modules" ] || [ "$LOCK_HASH" != "$(cat "$FRONTEND/node_modules/.triallens-lock.sha" 2>/dev/null)" ]; then
  echo "  [3/4] Installing Node dependencies…"
  (cd "$FRONTEND" && npm ci --no-audit --no-fund --silent)
  echo "$LOCK_HASH" > "$FRONTEND/node_modules/.triallens-lock.sha"
else
  echo "  [3/4] Node dependencies are up to date."
fi

echo "  [4/4] Starting servers…"
echo ""
echo "  Backend  → http://localhost:8000  (FastAPI + ClinicalTrials.gov)"
echo "  Frontend → http://localhost:5173  (React + Vite)"
echo "  API Docs → http://localhost:8000/api/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Start backend
cd "$BACKEND"
"$BACKEND/.venv/bin/uvicorn" main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
cd "$FRONTEND"
npm run dev &
FRONTEND_PID=$!

trap "echo ''; echo '  Stopping…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
