from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import jwt
from fastapi import HTTPException, Request, status

from redactor.config import get_settings

logger = logging.getLogger(__name__)

_CACHE_TTL = timedelta(hours=24)
_STALE_RETRY_INTERVAL = timedelta(seconds=60)


@dataclass
class CurrentUser:
    user_id: str
    email: str
    name: str


class JwksCache:
    def __init__(self) -> None:
        self._jwks_by_kid: dict[str, dict[str, Any]] = {}
        self._expires_at: datetime | None = None
        self._stale_retry_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def get_signing_key(self, kid: str) -> Any:
        keys = await self._get_keys()
        jwk = keys.get(kid)
        if jwk is None:
            keys = await self._refresh_keys(force=True)
            jwk = keys.get(kid)

        if jwk is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signing key")

        return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    async def _get_keys(self) -> dict[str, dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if self._jwks_by_kid and self._expires_at and now < self._expires_at:
            return self._jwks_by_kid

        async with self._lock:
            now = datetime.now(timezone.utc)
            if self._jwks_by_kid and self._expires_at and now < self._expires_at:
                return self._jwks_by_kid

            should_retry = self._stale_retry_at is None or now >= self._stale_retry_at
            if should_retry:
                try:
                    return await self._refresh_keys(force=True)
                except Exception as exc:
                    if self._jwks_by_kid:
                        logger.warning("Failed to refresh Azure AD JWKS; serving stale cache: %s", exc)
                        self._stale_retry_at = now + _STALE_RETRY_INTERVAL
                        return self._jwks_by_kid
                    raise

            if self._jwks_by_kid:
                return self._jwks_by_kid

            return await self._refresh_keys(force=True)

    async def _refresh_keys(self, force: bool = False) -> dict[str, dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if not force and self._jwks_by_kid and self._expires_at and now < self._expires_at:
            return self._jwks_by_kid

        settings = get_settings()
        tenant_id = settings.AZURE_AD_TENANT_ID.strip()
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Azure AD tenant is not configured")

        jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        payload = await asyncio.to_thread(self._fetch_jwks_payload, jwks_url)
        keys = payload.get("keys")
        if not isinstance(keys, list) or not keys:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Azure AD signing keys unavailable")

        self._jwks_by_kid = {
            key["kid"]: key
            for key in keys
            if isinstance(key, dict) and isinstance(key.get("kid"), str)
        }
        self._expires_at = now + _CACHE_TTL
        self._stale_retry_at = self._expires_at
        return self._jwks_by_kid

    def _fetch_jwks_payload(self, jwks_url: str) -> dict[str, Any]:
        try:
            with urlopen(jwks_url, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to fetch JWKS from {jwks_url}") from exc


@lru_cache
def get_jwks_cache() -> JwksCache:
    return JwksCache()


def _unauthorized(detail: str = "Unauthorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _allowed_issuers(tenant_id: str) -> list[str]:
    tenant = tenant_id.strip()
    return [
        f"https://login.microsoftonline.com/{tenant}/v2.0",
        f"https://login.microsoftonline.com/{tenant}/",
        f"https://sts.windows.net/{tenant}/",
    ]


async def get_current_user(request: Request) -> CurrentUser:
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Missing bearer token")

    settings = get_settings()
    if settings.DEV_BYPASS and settings.ENV == "development" and token == "dev-token-bypass":
        return CurrentUser(user_id="dev-user-123", email="dev@example.com", name="Developer")

    if not settings.AZURE_AD_TENANT_ID or not settings.AZURE_AD_CLIENT_ID:
        raise _unauthorized("Azure AD is not configured")

    audience = settings.AZURE_AD_AUDIENCE.strip() or f"api://{settings.AZURE_AD_CLIENT_ID}"

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise _unauthorized("Token is missing signing key information")

        signing_key = await get_jwks_cache().get_signing_key(kid)
        claims = jwt.decode(
            token,
            key=signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=_allowed_issuers(settings.AZURE_AD_TENANT_ID),
        )
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise _unauthorized("Invalid token") from exc
    except Exception as exc:
        logger.exception("Unexpected authentication failure")
        raise _unauthorized("Authentication failed") from exc

    oid = claims.get("oid")
    if not isinstance(oid, str) or not oid:
        raise _unauthorized("Token is missing oid claim")

    email = claims.get("email") or claims.get("preferred_username") or ""
    name = claims.get("name") or ""
    return CurrentUser(user_id=oid, email=str(email), name=str(name))