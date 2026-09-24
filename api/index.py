import sys
from pathlib import Path

# Add backend directory to sys.path so app and its packages can be imported
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.db.session import init_db

# Ensure SQLite schema and seed data are populated on serverless cold starts
init_db()

