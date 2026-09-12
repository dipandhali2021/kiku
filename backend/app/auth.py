"""Firebase ID token verification.

The app signs users in with Firebase (anonymously at first, upgraded later by
linking a credential). The backend never issues its own tokens. It verifies
Google's RS256 ID tokens against Google's public JWKS and trusts the `sub`
claim as the stable user id.

Why verify manually instead of pulling in firebase-admin: verification needs
nothing but the public keys, and avoiding the admin SDK keeps the container
small and means no service-account key has to exist at all.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/"
    "securetoken@system.gserviceaccount.com"
)
_ISSUER_PREFIX = "https://securetoken.google.com/"
_JWKS_TTL_SECONDS = 3600


@dataclass(slots=True)
class CurrentUser:
    """The authenticated caller."""

    uid: str
    email: str | None = None
    is_anonymous: bool = True


class _JwksCache:
    """Google rotates signing keys; cache them but re-fetch on unknown kid."""

    def __init__(self) -> None:
        self._keys: dict[str, dict] = {}
        self._fetched_at: float = 0.0

    def get(self, kid: str) -> dict | None:
        expired = time.time() - self._fetched_at > _JWKS_TTL_SECONDS
        if kid not in self._keys or expired:
            self._refresh()
        return self._keys.get(kid)

    def _refresh(self) -> None:
        import httpx  # noqa: PLC0415

        response = httpx.get(_JWKS_URL, timeout=10)
        response.raise_for_status()
        self._keys = {item["kid"]: item for item in response.json()["keys"]}
        self._fetched_at = time.time()


_jwks = _JwksCache()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def verify_firebase_token(token: str) -> CurrentUser:
    """Validate signature, issuer, audience, and expiry."""
    try:
        from jose import jwt  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("python-jose is required to verify tokens") from exc

    if not settings.firebase_project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID is not configured")

    try:
        header = json.loads(_b64url_decode(token.split(".")[0]))
    except Exception as exc:  # noqa: BLE001
        raise _unauthorized("malformed token") from exc

    kid = header.get("kid")
    if not kid:
        raise _unauthorized("token has no key id")

    key = _jwks.get(kid)
    if key is None:
        raise _unauthorized("unknown signing key")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.firebase_project_id,
            issuer=f"{_ISSUER_PREFIX}{settings.firebase_project_id}",
        )
    except Exception as exc:  # noqa: BLE001 - jose raises several types
        logger.info("token rejected: %s", exc)
        raise _unauthorized("invalid or expired token") from exc

    uid = claims.get("sub")
    if not uid:
        raise _unauthorized("token has no subject")

    provider = (claims.get("firebase") or {}).get("sign_in_provider", "anonymous")
    return CurrentUser(
        uid=uid,
        email=claims.get("email"),
        is_anonymous=provider == "anonymous",
    )


async def current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """FastAPI dependency returning the authenticated caller."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized("empty bearer token")

    # Development shortcut: treat the token as a user id. Hard-disabled when
    # ENVIRONMENT=production so it can never be switched on by accident.
    if settings.dev_auth_allowed and token.startswith("dev:"):
        return CurrentUser(uid=token[4:] or "dev-user", is_anonymous=True)

    return verify_firebase_token(token)


AuthenticatedUser = Depends(current_user)
