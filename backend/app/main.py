"""
FastAPI application entry point.

Startup checklist:
  1. App is created with metadata.
  2. CORS middleware is configured.
  3. All API routes are mounted at /api/v1.
  4. A health-check endpoint is available at /health.
  5. Database tables are created automatically on startup (dev mode).
     In production, use Alembic migrations instead.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import Base, engine

# Import models so SQLAlchemy registers them before create_all
import app.models  # noqa: F401

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "REST API for the NGO Volunteer Scheduling and Coordination Platform. "
        "Covers volunteer management, event/shift creation, conflict-free scheduling, "
        "coverage analytics, smart matching, reminders, and attendance tracking."
    ),
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc UI
    openapi_url="/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ────────────────────────────────────────────────────────────────
app.include_router(api_router)


# ── Startup Event ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """
    Create all database tables if they don't exist.
    DEV ONLY – remove this in production and rely solely on Alembic.
    """
    Base.metadata.create_all(bind=engine)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    """Simple health check endpoint for deployment monitors."""
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["System"])
def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
    }
