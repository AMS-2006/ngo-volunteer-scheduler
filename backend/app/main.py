"""
app/main.py  –  FastAPI application entry point
─────────────────────────────────────────────────
Registers all routers, middleware, startup hooks, and system endpoints.

Module routing:
  /api/v1/auth/          → routers/auth.py          (Auth)
  /api/v1/ngo/           → routers/ngo.py           (Module 1 – NGO Profile)
  /api/v1/events/        → routers/events.py        (Module 1 – Events)
  /api/v1/events/*/shifts → routers/shifts.py       (Module 1 – Shifts)
  /api/v1/volunteers/    → routers/volunteers.py    (Module 2 – Volunteer Mgmt)
  /api/v1/registrations/ → routers/registrations.py (Module 3 – Scheduling)
  /api/v1/reminders/     → routers/reminders.py     (Module 6 – Notifications)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database.connection import Base, engine

# ── Import all models (registers tables with SQLAlchemy metadata) ─────────────
import app.database.models  # noqa: F401

# ── Import all routers ────────────────────────────────────────────────────────
from app.routers import (
    attendance,
    auth,
    events,
    matching,
    ngo,
    registrations,
    reminders,
    shifts,
    volunteers,
)
from app.services import expiry_worker
from app.services.errors import SchedulingError
from fastapi.responses import JSONResponse

settings = get_settings()

# ── Create FastAPI app ────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**NGO Volunteer Scheduling & Coordination Platform** — WEB-12\n\n"
        "REST API covering:\n"
        "- **Module 1**: NGO & Event Management\n"
        "- **Module 2**: Volunteer Management\n"
        "- **Module 3**: Conflict-Free Scheduling Engine *(coming soon)*\n"
        "- **Module 4**: Smart Volunteer Matching *(coming soon)*\n"
        "- **Module 5**: Coverage Dashboard *(coming soon)*\n"
        "- **Module 6**: Reminders & Notifications *(coming soon)*\n"
        "- **Module 7**: Attendance Tracking & Volunteer History"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routers under /api/v1 ───────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(auth.router,          prefix=PREFIX)
app.include_router(ngo.router,           prefix=PREFIX)
app.include_router(events.router,        prefix=PREFIX)
app.include_router(shifts.router,        prefix=PREFIX)   # nested under /events/{id}/shifts
app.include_router(volunteers.router,    prefix=PREFIX)
app.include_router(registrations.router, prefix=PREFIX)
app.include_router(reminders.router,     prefix=PREFIX)
app.include_router(attendance.router,    prefix=PREFIX)

# ── Module 4 router + domain-error handler ───────────────────────────────────
app.include_router(matching.router,      prefix=PREFIX)   # Module 4 – matching & invitations
app.add_event_handler("startup", expiry_worker.start)
app.add_event_handler("shutdown", expiry_worker.stop)


@app.exception_handler(SchedulingError)
async def scheduling_error_handler(_request, exc: SchedulingError):
    """Domain errors from the scheduling / matching services -> JSON {detail, code, context}."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


# ── Startup: auto-create tables (DEV only) ───────────────────────────────────
@app.on_event("startup")
def on_startup():
    """
    Create all database tables that don't exist yet.
    For local development with SQLite, creates tables automatically.
    For PostgreSQL, schema changes are managed via Alembic migrations.
    """
    if not settings.database_url.startswith("postgresql"):
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    """Health probe for deployment monitors (Render, Railway, etc.)."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", tags=["System"])
def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
        "version": settings.app_version,
    }
