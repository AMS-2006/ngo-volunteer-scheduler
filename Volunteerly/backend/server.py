import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from lib.db import client, ensure_indexes  # noqa: E402
from lib.logic import bump_live  # noqa: E402
from routers import auth, live, ngo, volunteer  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_task = asyncio.create_task(ensure_indexes())
    yield
    client.close()


app = FastAPI(lifespan=lifespan, title="Volunteer Connect API")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Volunteer Connect API"}


api_router.include_router(auth.router)
api_router.include_router(ngo.router)
api_router.include_router(volunteer.router)
api_router.include_router(live.router)

NO_BUMP = ("/api/auth", "/api/notifications", "/api/uploads", "/api/cron")


@app.middleware("http")
async def live_bump(request, call_next):
    """Any successful data change bumps the live counter so every open dashboard refreshes."""
    resp = await call_next(request)
    p = request.url.path
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and resp.status_code < 400 \
            and p.startswith("/api/") and not p.startswith(NO_BUMP):
        await bump_live()
    return resp

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Include the router in the main app — keep last
app.include_router(api_router)
