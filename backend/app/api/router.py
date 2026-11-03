"""
Central API router.
All route modules are registered here and mounted under /api/v1.
"""

from fastapi import APIRouter

from app.api.routes import auth, volunteers

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(volunteers.router)

# Future modules – add here as you build them:
# from app.api.routes import events, shifts, matching, notifications, attendance
# api_router.include_router(events.router)
# api_router.include_router(shifts.router)
# api_router.include_router(matching.router)
# api_router.include_router(notifications.router)
# api_router.include_router(attendance.router)
