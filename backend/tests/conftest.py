import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app
from app.services.venue_service import venue_service


@pytest.fixture(scope="session", autouse=True)
def init_venues():
    """Ensure venues are loaded before tests run."""
    venue_service.load_all_venues()


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client
