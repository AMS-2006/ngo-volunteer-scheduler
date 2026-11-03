"""
routers/ngo.py  –  NGO profile management
──────────────────────────────────────────
Endpoints:
  POST  /api/v1/ngo/          – Create NGO profile (admin only)
  GET   /api/v1/ngo/          – Get my NGO profile (admin only)
  PATCH /api/v1/ngo/          – Update my NGO profile (admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.deps import require_admin
from app.models.ngo import NGO
from app.models.user import User
from app.schemas.ngo import NGOCreate, NGOOut, NGOUpdate

router = APIRouter(prefix="/ngo", tags=["NGO Management"])


def _get_my_ngo_or_404(admin: User, db: Session) -> NGO:
    ngo = db.query(NGO).filter(NGO.admin_user_id == admin.id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO profile not found. Create one first.")
    return ngo


@router.post(
    "/",
    response_model=NGOOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create NGO profile (admin only)",
)
def create_ngo(
    payload: NGOCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin creates their NGO profile immediately after registration.
    One admin → one NGO profile.
    """
    existing = db.query(NGO).filter(NGO.admin_user_id == admin.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="NGO profile already exists. Use PATCH to update.")

    ngo = NGO(admin_user_id=admin.id, **payload.model_dump())
    db.add(ngo)
    db.commit()
    db.refresh(ngo)
    return ngo


@router.get("/", response_model=NGOOut, summary="Get my NGO profile")
def get_my_ngo(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _get_my_ngo_or_404(admin, db)


@router.patch("/", response_model=NGOOut, summary="Update my NGO profile (partial)")
def update_my_ngo(
    payload: NGOUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ngo = _get_my_ngo_or_404(admin, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ngo, field, value)
    db.commit()
    db.refresh(ngo)
    return ngo
