import os
import time
import uuid
from typing import Optional, Dict, Any

import requests
from fastapi import Header, HTTPException
from jose import jwt, JWTError
from jose.utils import base64url_decode
from loguru import logger

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "https://evnuecsdjcxetcwxjuyj.supabase.co",
)

AUTH_VERIFY_MODE = os.getenv("AUTH_VERIFY_MODE", "jwks").lower()  # "jwks" or "hs256"
AUTH_DEBUG = os.getenv("AUTH_DEBUG", "true").lower() in ("1", "true", "yes")

# JWKS cache (simple in-memory cache)
_JWKS_CACHE: Dict[str, Any] = {"ts": 0, "jwks": None}
_JWKS_TTL_SECONDS = int(os.getenv("JWKS_TTL_SECONDS", "600"))  # default 10 minutes


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = parts[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    return token


# ------------------------------------------------------------
# JWKS Fetch + Cache
# ------------------------------------------------------------
def _fetch_jwks() -> Dict[str, Any]:
    """
    Fetch Supabase JWKS.
    Supabase requires apikey header (anon or service_role).
    """
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not anon_key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_ANON_KEY not set (required for JWKS mode)",
        )

    url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

    resp = requests.get(
        url,
        headers={"apikey": anon_key},
        timeout=10,
    )

    try:
        data = resp.json()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JWKS JSON response: HTTP {resp.status_code}",
        )

    if resp.status_code != 200 or "keys" not in data:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JWKS response: {data}",
        )

    return data


def _get_cached_jwks() -> Dict[str, Any]:
    now = time.time()

    if (
        _JWKS_CACHE["jwks"]
        and now - _JWKS_CACHE["ts"] < _JWKS_TTL_SECONDS
    ):
        return _JWKS_CACHE["jwks"]

    jwks = _fetch_jwks()
    _JWKS_CACHE["jwks"] = jwks
    _JWKS_CACHE["ts"] = now

    return jwks


# ------------------------------------------------------------
# JWK → Public Key
# ------------------------------------------------------------
def _public_key_from_jwk(jwk: Dict[str, Any]):
    """
    Supabase ES256 JWK contains x/y coordinates.
    Build EC public key for verification.
    """

    x = base64url_decode(jwk["x"].encode())
    y = base64url_decode(jwk["y"].encode())

    public_numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(x, "big"),
        int.from_bytes(y, "big"),
        ec.SECP256R1(),
    )

    return public_numbers.public_key(default_backend())


# ------------------------------------------------------------
# Verification Modes
# ------------------------------------------------------------
def _verify_jwt_hs256(token: str) -> Dict[str, Any]:
    """
    Legacy HS256 verification using SUPABASE_JWT_SECRET
    """
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET not set")

    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _verify_jwt_jwks(token: str) -> Dict[str, Any]:
    """
    ES256 verification using Supabase JWKS
    """
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token header")

    alg = header.get("alg")
    kid = header.get("kid")

    if AUTH_DEBUG:
        logger.debug(f"[auth] header.alg={alg} header.kid={kid}")

    if not kid:
        raise HTTPException(status_code=401, detail="Token missing kid")

    if alg != "ES256":
        raise HTTPException(status_code=401, detail=f"Unsupported JWT alg: {alg}")

    jwks = _get_cached_jwks()

    key_data = next(
        (k for k in jwks["keys"] if k.get("kid") == kid),
        None,
    )

    if not key_data:
        # Refresh cache once (key rotation case)
        _JWKS_CACHE["jwks"] = None
        jwks = _get_cached_jwks()

        key_data = next(
            (k for k in jwks["keys"] if k.get("kid") == kid),
            None,
        )

    if not key_data:
        raise HTTPException(status_code=401, detail="Public key not found for kid")

    public_key = _public_key_from_jwk(key_data)

    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ------------------------------------------------------------
# Main Dependency
# ------------------------------------------------------------
def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
) -> uuid.UUID:

    token = _get_bearer_token(authorization)

    if AUTH_DEBUG:
        logger.debug("========== AUTH DEBUG ==========")
        logger.debug(f"[auth] mode={AUTH_VERIFY_MODE}")
        logger.debug(f"[auth] token_len={len(token)}")
        logger.debug(f"[auth] token_prefix={token[:20]}...")

    if AUTH_VERIFY_MODE == "hs256":
        payload = _verify_jwt_hs256(token)
    elif AUTH_VERIFY_MODE == "jwks":
        payload = _verify_jwt_jwks(token)
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid AUTH_VERIFY_MODE: {AUTH_VERIFY_MODE}",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid sub claim (not a UUID)",
        )

    if AUTH_DEBUG:
        logger.debug(f"[auth] ✅ user_id={user_id}")
        logger.debug("========== AUTH DEBUG END ==========")

    return user_id