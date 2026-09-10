#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "  TrialLens — Clinical Intelligence Dashboard"
echo "  ─────────────────────────────────────────────"
echo ""

# Backend setup
if [ ! -d "$BACKEND/.venv" ]; then
  echo "  [1/4] Creating Python virtual environment…"
  python3 -m venv "$BACKEND/.venv"
fi

echo "  [2/4] Installing Python dependencies…"
"$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"

# Frontend setup
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "  [3/4] Installing Node dependencies…"
  cd "$FRONTEND" && npm install --silent
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
