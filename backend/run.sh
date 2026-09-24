#!/usr/bin/env bash
set -e
echo "Starting NammaSpace 3D Backend on http://localhost:8000..."
if [ -f ".venv/bin/python" ]; then
    .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
