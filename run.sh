#!/usr/bin/env bash
# ==============================================================================
# RegimeShift AI — Local Development Runner
# Starts both the FastAPI Backend (port 8000) and Next.js Frontend (port 3000)
# ==============================================================================

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

# Kill any existing processes running on ports 8000 or 3000
echo "🧹 Checking for existing instances on ports 8000 and 3000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Verify backend virtualenv exists
if [ ! -f "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
    echo "❌ Error: Backend virtualenv not found at $BACKEND_DIR/.venv"
    echo "   Please create it: cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

echo "🚀 Starting RegimeShift AI Backend (FastAPI on http://127.0.0.1:8000)..."
cd "$BACKEND_DIR"
"$BACKEND_DIR/.venv/bin/uvicorn" regimeshift.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

echo "⚡ Starting RegimeShift AI Frontend (Next.js on http://localhost:3000)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "🛑 Shutting down RegimeShift AI servers..."
    kill -TERM "$BACKEND_PID" 2>/dev/null || true
    kill -TERM "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    echo "✅ Shutdown complete."
}
trap cleanup SIGINT SIGTERM EXIT

echo ""
echo "======================================================================"
echo "  🌟 RegimeShift AI Terminal is LIVE!"
echo "  👉 Cockpit UI:  http://localhost:3000 (or http://127.0.0.1:3000)"
echo "  👉 Backend API: http://127.0.0.1:8000"
echo "  👉 API Docs:    http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to stop both servers."
echo "======================================================================"
echo ""

# Wait for both processes
wait
