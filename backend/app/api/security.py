"""Autenticação single-user por senha única (cookie de sessão assinado).

App pessoal: uma senha (`APP_PASSWORD`) protege toda a API. A sessão é um cookie
HttpOnly assinado por HMAC com a própria senha como chave — stateless, sem store de
sessão e sem dependências externas. Comparações em tempo constante (`hmac.compare_digest`).

Rotas abertas (sem auth): `/api/health`, `/api/login`, `/api/logout`, `/api/auth/status`.
Sem `APP_PASSWORD` configurada, as rotas protegidas respondem 503 (servidor não
configurado) — nunca "abertas por omissão".
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

COOKIE_NAME = "pomar_session"
# Rotas que NÃO exigem autenticação (prefixo /api).
OPEN_PATHS = {"/api", "/api/health", "/api/login", "/api/logout", "/api/auth/status"}


def _sign(payload: dict, key: str) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_token(token: str, key: str) -> dict | None:
    """Retorna o payload se a assinatura confere e não expirou; senão None."""
    if not token or not key:
        return None
    try:
        raw, sig = token.rsplit(".", 1)
        expected = hmac.new(key.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
        if float(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


def is_authenticated(request: Request) -> bool:
    settings = get_settings()
    if not settings.app_password:
        return False
    return verify_token(request.cookies.get(COOKIE_NAME, ""), settings.app_password) is not None


class AuthMiddleware(BaseHTTPMiddleware):
    """Exige sessão válida para todas as rotas /api/* fora de OPEN_PATHS."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if path.startswith("/api") and path not in OPEN_PATHS:
            settings = get_settings()
            if not settings.app_password:
                return JSONResponse(
                    {"detail": "Servidor sem APP_PASSWORD configurado. Defina a senha no .env."},
                    status_code=503,
                )
            if not is_authenticated(request):
                return JSONResponse({"detail": "Não autenticado."}, status_code=401)
        return await call_next(request)


router = APIRouter()


class LoginBody(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginBody, response: Response) -> dict:
    settings = get_settings()
    if not settings.app_password:
        raise HTTPException(status_code=503, detail="Servidor sem APP_PASSWORD configurado.")
    if not hmac.compare_digest(body.password, settings.app_password):
        raise HTTPException(status_code=401, detail="Senha incorreta.")
    ttl = settings.session_ttl_hours * 3600
    token = _sign({"exp": time.time() + ttl}, settings.app_password)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=ttl,
        httponly=True,
        samesite="strict",
        secure=not settings.debug,  # em dev (DEBUG, http) o cookie precisa funcionar sem TLS
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/auth/status")
async def auth_status(request: Request) -> dict:
    settings = get_settings()
    return {
        "auth_required": bool(settings.app_password),
        "authenticated": is_authenticated(request),
    }
