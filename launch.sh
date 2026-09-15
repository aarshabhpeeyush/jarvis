#!/usr/bin/env bash
set -e

echo ""
echo "  ╔════════════════════════════════════════════╗"
echo "  ║  J.A.R.V.I.S. — System Boot               ║"
echo "  ╚════════════════════════════════════════════╝"
echo ""

# Copy .env if missing
if [ ! -f backend/.env ]; then
    cp .env.example backend/.env
    echo "[SETUP] Created backend/.env from template."
    echo "[SETUP] Edit backend/.env with your API keys, then re-run."
    exit 0
fi

# Install Python deps
echo "[BOOT] Installing dependencies..."
pip install -r backend/requirements.txt --quiet

# Launch
echo "[BOOT] Starting J.A.R.V.I.S. on http://localhost:8000"
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
