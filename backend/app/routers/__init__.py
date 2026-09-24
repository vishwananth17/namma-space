from app.routers.health import router as health_router
from app.routers.navigation import router as navigation_router
from app.routers.pois import router as pois_router
from app.routers.search import router as search_router
from app.routers.venues import router as venues_router

__all__ = [
    "health_router",
    "venues_router",
    "pois_router",
    "search_router",
    "navigation_router",
]
