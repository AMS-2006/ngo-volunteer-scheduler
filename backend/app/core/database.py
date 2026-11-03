"""
Compatibility shim: the Module 3 models import `Base` from `app.core.database`,
while the project's single engine / Base / get_db live in `app.database.connection`.
Re-exporting keeps ONE Base (one metadata) for every model.
"""

from app.database.connection import Base, SessionLocal, engine, get_db  # noqa: F401
