"""
database/connection.py
──────────────────────
Single source of truth for the SQLAlchemy engine, session factory,
and the shared declarative Base that all ORM models inherit from.

Every other module should import from here — never create a second engine.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,    # Detect & recycle stale connections automatically
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,   # Print generated SQL in dev mode
)

# ── Session Factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this Base."""
    pass


# ── FastAPI Dependency ────────────────────────────────────────────────────────
def get_db():
    """
    Yield a database session for use in FastAPI route functions.
    Automatically closes the session when the request is done.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
