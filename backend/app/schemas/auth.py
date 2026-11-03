"""
Pydantic schemas for authentication flows.
Covers registration, login, and the token response format.
"""

from pydantic import BaseModel, EmailStr, Field


# ── Request: Register ─────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120, examples=["Rahul Sharma"])
    email: EmailStr = Field(..., examples=["rahul@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["Str0ng!Pass"])
    role: str = Field(
        default="volunteer",
        pattern="^(admin|volunteer)$",
        examples=["volunteer"],
        description="Account type: 'admin' or 'volunteer'",
    )


# ── Request: Login (form-encoded, compatible with OAuth2PasswordRequestForm) ──
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Response: Token ───────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str


# ── Response: Current user info (returned from /me) ──────────────────────────
class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
