"""Auth endpoints: login (with 2FA), token refresh, TOTP setup."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, CurrentUser
from app.core.security import verify_password, create_access_token
from app.core.auth import (
    generate_totp_secret, get_totp_uri, verify_totp, encrypt_totp_secret
)
from app.models.user import User
from app.schemas import LoginRequest, TokenResponse, TOTPSetupResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalars().first()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # 2FA check — if user has TOTP configured, code is required
    if user.totp_secret_enc:
        if not body.totp_code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="TOTP code required")
        if not verify_totp(user.totp_secret_enc, body.totp_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid TOTP code")

    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(current_user: CurrentUser, db: DBSession) -> TOTPSetupResponse:
    """Generate a new TOTP secret for the current user. Scan QR code in authenticator app."""
    secret = generate_totp_secret()
    current_user.totp_secret_enc = encrypt_totp_secret(secret)
    await db.commit()
    uri = get_totp_uri(secret, current_user.username)
    return TOTPSetupResponse(secret=secret, uri=uri)
