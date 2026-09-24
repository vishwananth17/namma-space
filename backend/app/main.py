import mimetypes
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.session import init_db
from app.routers import (
    health_router,
    navigation_router,
    pois_router,
    search_router,
    venues_router,
)
from app.services.venue_service import venue_service
from app.utils.logger import logger

# Ensure accurate MIME types for 3D model streaming
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("application/octet-stream", ".ply")
mimetypes.add_type("text/plain", ".obj")


class ModelStaticFiles(StaticFiles):
    """Static file handler with custom headers for 3D model caching and CORS."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            # Enable aggressive browser caching for large 3D models
            if path.endswith((".glb", ".gltf", ".bin", ".ply", ".obj", ".png", ".jpg")):
                response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENV} | Port: {settings.PORT}")
    # Ensure data and venues directory exist
    settings.VENUES_DIR.mkdir(parents=True, exist_ok=True)
    # Initialize SQLite tables
    init_db()
    logger.info("Initialized SQLite database schema.")
    venue_service.load_all_venues()
    logger.info(f"Loaded {len(venue_service.list_venues())} venues on startup.")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}.")


# Initialize SQLite schema and seed data for serverless/local execution
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-grade backend, spatial data layer, POI search, "
        "and obstacle-aware pathfinding API for indoor 3D digital twins."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# 1. CORS Configuration for Three.js frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Timing and Request Logging Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    logger.info(
        f"{request.method} {request.url.path} -> status={response.status_code} "
        f"latency={duration_ms:.2f}ms"
    )
    return response


# 3. Standardized Error Handlers: { "error": ..., "message": ..., "details": ... }
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    error_code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_code,
            "message": str(exc.detail),
            "details": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request parameters or payload structure.",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred.",
            "details": str(exc) if settings.DEBUG else None,
        },
    )


app.include_router(health_router)
app.include_router(venues_router)
app.include_router(pois_router)
app.include_router(search_router)
app.include_router(navigation_router)


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to Swagger UI documentation."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")



# 5. Static file serving for venue models, maps, and textures
settings.VENUES_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    f"{settings.STATIC_URL_PREFIX}/venues",
    ModelStaticFiles(directory=str(settings.VENUES_DIR)),
    name="venue_models",
)
