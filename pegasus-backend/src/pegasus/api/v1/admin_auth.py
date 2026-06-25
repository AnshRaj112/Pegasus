# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:27:19Z
# --- END GENERATED FILE METADATA ---

"""Session-based admin authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Response, status

from pegasus.api.deps import AppSettings, DbSession
from pegasus.core.admin_auth import (
    expires_at_from_now,
    hash_admin_password,
    new_session_token,
    session_token_hash,
    utc_now,
    verify_admin_password,
)
from pegasus.models.admin_user import AdminUser
from pegasus.repositories.admin_auth_repository import AdminAuthRepository
from pegasus.schemas.admin_auth import (
    AdminAuthUserResponse,
    AdminLoginRequest,
    AdminSessionStatusResponse,
    AdminSignupRequest,
)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

ADMIN_SESSION_COOKIE = "pegasus_admin_session"


def _normalized_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _set_admin_cookie(response: Response, token: str, settings: AppSettings) -> None:
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.admin_session_cookie_secure,
        samesite="lax",
        max_age=settings.admin_session_ttl_minutes * 60,
        path="/",
    )


def _clear_admin_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE,
        httponly=True,
        secure=settings.admin_session_cookie_secure,
        samesite="lax",
        path="/",
    )


async def get_current_admin_user(
    session: DbSession,
    admin_session_token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> AdminUser:
    token = (admin_session_token or "").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required.")
    hashed = session_token_hash(token)
    session_row = await AdminAuthRepository.get_session_by_hash(session, hashed)
    if session_row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid admin session.")
    now = utc_now()
    if session_row.expires_at < now:
        await AdminAuthRepository.delete_session_by_hash(session, hashed)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Admin session expired.")
    user = await AdminAuthRepository.get_user_by_id(session, session_row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Admin user not found.")
    return user


require_admin_session = Depends(get_current_admin_user)


@router.post("/signup", response_model=AdminAuthUserResponse)
async def admin_signup(
    response: Response,
    settings: AppSettings,
    session: DbSession,
    body: Annotated[AdminSignupRequest, Body()],
) -> AdminAuthUserResponse:
    email = _normalized_email(body.email)
    if "@" not in email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Please provide a valid email.")
    user_count = await AdminAuthRepository.count_users(session)
    if user_count > 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin signup is already completed.")
    existing = await AdminAuthRepository.get_user_by_email(session, email)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Admin user already exists.")
    user = await AdminAuthRepository.create_user(
        session,
        email=email,
        password_hash=hash_admin_password(body.password),
    )
    token = new_session_token()
    await AdminAuthRepository.create_session(
        session,
        user_id=user.id,
        token_hash=session_token_hash(token),
        expires_at=expires_at_from_now(settings.admin_session_ttl_minutes),
    )
    await session.commit()
    _set_admin_cookie(response, token, settings)
    return AdminAuthUserResponse(email=user.email)


@router.post("/login", response_model=AdminAuthUserResponse)
async def admin_login(
    response: Response,
    settings: AppSettings,
    session: DbSession,
    body: Annotated[AdminLoginRequest, Body()],
) -> AdminAuthUserResponse:
    email = _normalized_email(body.email)
    user = await AdminAuthRepository.get_user_by_email(session, email)
    if user is None or not verify_admin_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    await AdminAuthRepository.delete_expired_sessions(session, utc_now())
    token = new_session_token()
    await AdminAuthRepository.create_session(
        session,
        user_id=user.id,
        token_hash=session_token_hash(token),
        expires_at=expires_at_from_now(settings.admin_session_ttl_minutes),
    )
    await session.commit()
    _set_admin_cookie(response, token, settings)
    return AdminAuthUserResponse(email=user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(
    response: Response,
    settings: AppSettings,
    session: DbSession,
    admin_session_token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> None:
    token = (admin_session_token or "").strip()
    if token:
        await AdminAuthRepository.delete_session_by_hash(session, session_token_hash(token))
        await session.commit()
    _clear_admin_cookie(response, settings)


@router.get("/me", response_model=AdminAuthUserResponse)
async def admin_me(current_user: Annotated[AdminUser, Depends(get_current_admin_user)]) -> AdminAuthUserResponse:
    return AdminAuthUserResponse(email=current_user.email)


@router.get("/session", response_model=AdminSessionStatusResponse)
async def admin_session_status(
    session: DbSession,
    current_user: Annotated[AdminUser, Depends(get_current_admin_user)],
    admin_session_token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> AdminSessionStatusResponse:
    token = (admin_session_token or "").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required.")
    row = await AdminAuthRepository.get_session_by_hash(session, session_token_hash(token))
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid admin session.")
    return AdminSessionStatusResponse(email=current_user.email, expires_at=row.expires_at)


@router.post("/extend", response_model=AdminSessionStatusResponse)
async def admin_extend_session(
    response: Response,
    settings: AppSettings,
    session: DbSession,
    current_user: Annotated[AdminUser, Depends(get_current_admin_user)],
    admin_session_token: Annotated[str | None, Cookie(alias=ADMIN_SESSION_COOKIE)] = None,
) -> AdminSessionStatusResponse:
    token = (admin_session_token or "").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required.")
    token_hash = session_token_hash(token)
    row = await AdminAuthRepository.get_session_by_hash(session, token_hash)
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid admin session.")
    row.expires_at = expires_at_from_now(settings.admin_session_ttl_minutes)
    await session.commit()
    _set_admin_cookie(response, token, settings)
    return AdminSessionStatusResponse(email=current_user.email, expires_at=row.expires_at)
