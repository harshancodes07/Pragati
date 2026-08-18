"""Google Sign-In gate.

Deliberately not a user-accounts system: nothing in the app is scoped to a
specific person (documents, sessions and chats stay anonymous, same as
before). This module only answers one question — "did a real Google account
holder sign in?" — by verifying a Google ID token client-side flow produced,
then issuing our own short-lived JWT so the frontend and backend (different
domains: Vercel + Railway) don't need shared cookies to agree someone is
signed in.
"""

from __future__ import annotations

import time
from typing import Any

import jwt
from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from backend.config import settings

_JWT_ALGORITHM = "HS256"


class AuthError(Exception):
    pass


def verify_google_token(credential: str) -> dict[str, Any]:
    """Verifies a Google ID token (from Google Identity Services on the
    frontend) and returns the account's profile fields we care about."""
    if not settings.google_client_id:
        raise AuthError("GOOGLE_CLIENT_ID is not configured on the server.")
    try:
        claims = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError as exc:
        raise AuthError(f"Invalid Google token: {exc}") from exc

    return {
        "sub": claims["sub"],
        "email": claims.get("email", ""),
        "name": claims.get("name", claims.get("email", "")),
        "picture": claims.get("picture", ""),
    }


def issue_session_token(profile: dict[str, Any]) -> str:
    if not settings.jwt_secret:
        raise AuthError("JWT_SECRET is not configured on the server.")
    now = int(time.time())
    payload = {
        "sub": profile["sub"],
        "email": profile["email"],
        "name": profile["name"],
        "picture": profile["picture"],
        "iat": now,
        "exp": now + settings.jwt_expiry_hours * 3600,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def _decode_session_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid or expired session: {exc}") from exc


def require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPI dependency — attach to any route that should sit behind login."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in required.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return _decode_session_token(token)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
