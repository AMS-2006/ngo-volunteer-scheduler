from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ─── Password Hashing ─────────────────────────────────────────────────────────
# Uses Argon2 as the primary scheme (memory-hard, resistant to GPU attacks).
# bcrypt is kept as a fallback for any legacy hashes.
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using Argon2."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT Token Handling ───────────────────────────────────────────────────────

def create_access_token(
    subject: str | Any,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:      Usually the user's UUID string.
        role:         'admin' or 'volunteer' — embedded in the token payload.
        expires_delta: Custom expiry. Defaults to settings value.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT. Raises JWTError on failure.
    Returns the full payload dict.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
