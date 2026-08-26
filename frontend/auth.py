"""
frontend/auth.py — Autenticação, sessão HMAC e rate limiting de login.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time as _time_module

from fastapi import Request
from passlib.context import CryptContext

from frontend.models import Launch
from logger import get_logger

logger = get_logger("frontend")

# ── Constantes de auth ─────────────────────────────────────────────────────────
BRABO_USER = os.environ.get("ADMIN_USERNAME") or os.environ.get("BRABO_USER", "brabo")
BRABO_PASS = os.environ.get("ADMIN_PASSWORD") or os.environ.get("BRABO_PASS", "pbb2026")
SECRET_KEY = os.environ.get("SECRET_KEY", "brabo-dev-secret-change-me")
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", str(86400 * 7)))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Permissões por rota ────────────────────────────────────────────────────────
_ALL   = ["admin", "analista", "trafego", "leitura"]
_MEDIA = ["admin", "analista", "trafego"]
_ANLT  = ["admin", "analista", "leitura"]
_DTLD  = ["admin", "analista"]
_ADM   = ["admin"]

ROUTE_PERMISSIONS: dict[str, list[str]] = {
    "/":                  _ALL,
    "/funil":             _ANLT,
    "/insights":          _ANLT,
    "/comparativo":       _DTLD,
    "/comparativo-v1-v2": _DTLD,
    "/meta":              _MEDIA,
    "/google":            _MEDIA,
    "/criativos":         _MEDIA,
    "/instagram":         _MEDIA,
    "/meta-audiences":    _MEDIA,
    "/google-audiences":  _MEDIA,
    "/leads":             _DTLD,
    "/crm-campanhas":     _DTLD,
    "/typeform":          _DTLD,
    "/vendas":            _DTLD,
    "/hotmart":           _DTLD,
    "/tmb":               _DTLD,
    "/settings":          _ADM,
}

# ── Hashing de senha ───────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)

# ── Sessão HMAC ────────────────────────────────────────────────────────────────

def _sign_session(user_id: str, role: str, products: list[str], email: str) -> str:
    issued_at    = str(int(_time_module.time()))
    products_str = ",".join(products) if products else "ALL"
    email_b64    = base64.urlsafe_b64encode(email.encode()).decode()
    payload      = f"{user_id}|{role}|{products_str}|{email_b64}|{issued_at}"
    sig          = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode("ascii")


def _decode_session(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        payload, sig = decoded.rsplit("|", 1)
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        parts = payload.split("|")
        if len(parts) != 5:
            return None
        user_id, role, products_str, email_b64, issued_at = parts
        if _time_module.time() - int(issued_at) > SESSION_MAX_AGE:
            return None
        email    = base64.urlsafe_b64decode(email_b64.encode()).decode()
        products = products_str.split(",")
        return {"user_id": user_id, "role": role, "products": products, "email": email}
    except Exception:
        logger.debug("Cookie de sessão inválido ou expirado")
        return None


def _set_session_cookie(response, user_id: str, role: str, products: list[str], email: str):
    response.set_cookie(
        key="session_token",
        value=_sign_session(user_id, role, products, email),
        httponly=True,
        max_age=SESSION_MAX_AGE,
        samesite="lax",
        secure=COOKIE_SECURE,
    )

# ── Helpers de usuário ─────────────────────────────────────────────────────────

def _get_current_user(request: Request) -> dict:
    return getattr(request.state, "user", {
        "user_id": "legacy",
        "role": "admin",
        "products": ["ALL"],
        "email": BRABO_USER,
    })


def _filter_launches_for_user(launches: list[Launch], user: dict) -> list[Launch]:
    products = user.get("products", ["ALL"])
    if "ALL" in products:
        return launches
    return [l for l in launches if l.code.split("-")[0] in products]

# ── Rate limiting de login ─────────────────────────────────────────────────────
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_LAST_CLEANUP: float = 0.0


def _check_login_rate_limit(ip: str) -> bool:
    global _LOGIN_LAST_CLEANUP
    now = _time_module.time()
    if now - _LOGIN_LAST_CLEANUP > 300:
        stale = [k for k, v in list(_LOGIN_ATTEMPTS.items())
                 if not any(now - t < _LOGIN_WINDOW_SECONDS for t in v)]
        for k in stale:
            del _LOGIN_ATTEMPTS[k]
        _LOGIN_LAST_CLEANUP = now
    attempts = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < _LOGIN_WINDOW_SECONDS]
    _LOGIN_ATTEMPTS[ip] = attempts
    return len(attempts) < _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(ip: str) -> None:
    _LOGIN_ATTEMPTS.setdefault(ip, []).append(_time_module.time())
