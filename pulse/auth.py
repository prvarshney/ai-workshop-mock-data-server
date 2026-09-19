"""
Instructor login.

The instructor types a password once; we hand back a signed token (a JWT) that
proves "this browser is the admin" for the next 12 hours. The token goes in an
HttpOnly cookie, so page JavaScript can never read it or leak it.

Nothing secret is ever put in the HTML, in a URL, or in localStorage.
"""

import hmac
import os
import secrets
import time
import uuid

import jwt
from fastapi import HTTPException, Request

from storage import db

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cu2026")
JWT_HOURS = int(os.environ.get("JWT_HOURS", "12"))
_ENV_SECRET = os.environ.get("JWT_SECRET")
JWT_SECRET = _ENV_SECRET or secrets.token_hex(32)
SECRET_FROM_ENV = bool(_ENV_SECRET)

COOKIE_NAME = "pulse_admin"
MAX_FAILURES = 5          # per IP, per minute


# --- password -------------------------------------------------------------

def password_ok(given) -> bool:
    """compare_digest takes the same time whatever the input, so a wrong
    password never leaks how much of it was right."""
    return hmac.compare_digest(str(given or ""), ADMIN_PASSWORD)


# --- brute-force limit ----------------------------------------------------

def _attempts_key(ip):
    return f"pulse:login_attempts:{ip}"


def locked_out(ip) -> bool:
    return int(db.get(_attempts_key(ip)) or 0) >= MAX_FAILURES


def record_failure(ip) -> None:
    key = _attempts_key(ip)
    if db.incr(key) == 1:
        db.expire(key, 60)        # the count forgets itself after a minute


def clear_failures(ip) -> None:
    db.delete(_attempts_key(ip))


# --- tokens ---------------------------------------------------------------

def make_token():
    """Return (token_string, claims). jti is a unique id so we can revoke it."""
    now = int(time.time())
    claims = {"sub": "admin", "jti": uuid.uuid4().hex, "iat": now,
              "exp": now + JWT_HOURS * 3600}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256"), claims


def revoke(claims) -> None:
    """Remember this token as dead until the moment it would have expired."""
    ttl = max(1, int(claims["exp"] - time.time()))
    db.setex(f"pulse:jwt_denylist:{claims['jti']}", ttl, "1")


def read_claims(request: Request):
    """Pull the token from the cookie or an Authorization header, and check it.
    Returns the claims, or None if there is no usable token."""
    token = request.cookies.get(COOKIE_NAME)
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()        # a header wins, so curl can override the cookie
    if not token:
        return None
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None                        # expired, tampered with, or signed by someone else
    if db.exists(f"pulse:jwt_denylist:{claims.get('jti', '')}"):
        return None                        # logged out
    return claims


def require_admin(request: Request):
    """FastAPI dependency: put this on any route only the instructor may call."""
    claims = read_claims(request)
    if not claims:
        raise HTTPException(401, "Admin login required")
    return claims
