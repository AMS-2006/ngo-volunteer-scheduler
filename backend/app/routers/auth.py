"""
routers/auth.py  (moved from app/api/routes/auth.py)
─────────────────────────────────────────────────────
Authentication routes: register, login, get current user.

Endpoints:
  POST /api/v1/auth/register   – Create a new user account (admin or volunteer)
  POST /api/v1/auth/login      – Exchange credentials for a JWT
  GET  /api/v1/auth/me         – Return the currently authenticated user
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account (admin or volunteer)",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new User account.
    - **role**: `volunteer` (default) or `admin`.
    - Returns a JWT immediately so the client can make authenticated requests.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password and receive an access token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserOut, summary="Get current authenticated user")
def get_me(current_user: User = Depends(get_current_user)):
    """Return basic identity info for the currently authenticated user."""
    return current_user
