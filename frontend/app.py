"""
frontend/app.py — Brabo Analytics
Ponto de entrada do FastAPI: cria o app, registra middleware e inclui routers.
Toda a lógica de negócio está em frontend/core.py e frontend/routes/*.
"""
from __future__ import annotations
import sys
import urllib.parse
from pathlib import Path

# ── Paths (necessários antes de qualquer import local) ─────────────────────────
BASE_DIR       = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ANALISES_DIR   = WORKSPACE_ROOT / "analises"
IMG_DIR        = WORKSPACE_ROOT / "img"
SRC_DIR        = WORKSPACE_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
import html as _html
import traceback as _traceback

from frontend.core import (
    logger,
    ROUTE_PERMISSIONS, BRABO_PASS, BRABO_USER,
    _decode_session,
    get_launches, _fetch_all_data, find_previous_launch,
    _hash_password, bootstrap_admin_if_needed,
)
import os

from frontend.routes import auth, media, analytics, leads, vendas, settings_router, api

# ── App ────────────────────────────────────────────────────────────────────────
_SHOW_DOCS = os.environ.get("SHOW_API_DOCS", "false").lower() == "true"
app = FastAPI(
    title="Brabo Analytics",
    docs_url="/docs" if _SHOW_DOCS else None,
    redoc_url="/redoc" if _SHOW_DOCS else None,
    openapi_url="/openapi.json" if _SHOW_DOCS else None,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

if ANALISES_DIR.exists():
    app.mount("/analises", StaticFiles(directory=str(ANALISES_DIR)), name="analises")
app.mount("/img", StaticFiles(directory=str(IMG_DIR)), name="img")

# ── Security headers ───────────────────────────────────────────────────────────
_HSTS_MAX_AGE = int(os.environ.get("HSTS_MAX_AGE", "0"))  # 0 = desativado (ativar após confirmar HTTPS)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if _HSTS_MAX_AGE > 0:
        response.headers["Strict-Transport-Security"] = f"max-age={_HSTS_MAX_AGE}; includeSubDomains"
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response

# ── Middleware de autenticação ─────────────────────────────────────────────────
_ALL = ["admin", "analista", "trafego", "leitura"]

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if (
        path in ("/login", "/logout")
        or path.startswith("/invite/")
        or path.startswith("/img")
        or path.startswith("/analises")
        or path.startswith("/static")
    ):
        return await call_next(request)

    user = _decode_session(request.cookies.get("session_token"))

    if user is None:
        next_url = request.url.path
        if request.query_params:
            next_url += f"?{request.query_params}"
        return RedirectResponse(
            url=f"/login?next={urllib.parse.quote_plus(next_url)}",
            status_code=303,
        )

    allowed_roles = ROUTE_PERMISSIONS.get(path, _ALL)
    if user["role"] not in allowed_roles:
        return HTMLResponse(
            content="""<html><body style="font-family:Inter,sans-serif;display:flex;align-items:center;
            justify-content:center;height:100vh;background:#eef0f8">
            <div style="text-align:center"><h1 style="font-size:48px;color:#2f5ee3">403</h1>
            <p style="color:#6b7280">Você não tem permissão para acessar esta página.</p>
            <a href="/" style="color:#2f5ee3">← Voltar ao início</a></div></body></html>""",
            status_code=403,
        )

    request.state.user = user
    return await call_next(request)

# ── Startup events ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _bootstrap_admin():
    try:
        admin_email = os.environ.get("ADMIN_EMAIL", f"{BRABO_USER}@brabo.local")
        bootstrap_admin_if_needed(
            email=admin_email,
            name="Admin",
            password_hash=_hash_password(BRABO_PASS),
        )
    except Exception:
        logger.debug("bootstrap_admin_if_needed ignorado (tabela ainda não existe)")


@app.on_event("startup")
async def pre_warm_cache():
    if os.environ.get("PRE_WARM_CACHE", "true").lower() != "true":
        logger.info("Pre-warming de cache desativado")
        return

    import asyncio
    from datetime import date, timedelta
    from fastapi.concurrency import run_in_threadpool

    async def warm_one(launch, previous):
        logger.info("Pre-warming cache para %s...", launch.code)
        try:
            await _fetch_all_data(
                launch,
                needs_tf=True,
                needs_daily=True,
                needs_thumbnails=True,
                needs_comparativo=True,
                previous=previous,
                needs_vendas_con=True,
                needs_hotmart=True,
                needs_tmb=True,
                needs_ac_camps=True,
                needs_sales_attr=True,
            )
            logger.info("Pre-warming de %s concluído com sucesso!", launch.code)
        except Exception:
            logger.exception("Falha no pre-warming de %s", launch.code)

    async def warm():
        launches = await run_in_threadpool(get_launches)
        if not launches:
            return
        # Aquece o mais recente por produto + qualquer lançamento ainda em andamento
        # (data_fim no futuro ou nos últimos 7 dias). O mais recente de cada produto
        # nunca é cortado pelo teto; só o excedente de "em andamento" é limitado.
        cutoff = date.today() - timedelta(days=7)
        latest_by_product = {}
        for l in launches:
            latest_by_product[l.product] = l  # get_launches retorna em ordem cronológica; o último de cada produto fica
        to_warm_by_code = {l.code: l for l in latest_by_product.values()}
        active = [l for l in launches if l.data_fim and l.data_fim >= cutoff and l.code not in to_warm_by_code]
        remaining_slots = max(0, 5 - len(to_warm_by_code))
        for l in active[:remaining_slots]:
            to_warm_by_code[l.code] = l
        to_warm = list(to_warm_by_code.values())
        # Sequencial (não gather): cada warm_one já dispara ~15 leituras paralelas
        # via _fetch_all_data; aquecer vários lançamentos ao mesmo tempo satura o
        # pool de conexões do banco (pool_size=10+5, ver src/db_engine.py) e atrasa
        # as primeiras requisições reais logo após o deploy.
        for l in to_warm:
            await warm_one(l, find_previous_launch(l, launches))

    asyncio.create_task(warm())

# ── Handler global de erros ────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _global_error_handler(request: Request, exc: Exception):  # noqa: ARG001
    tb = _html.escape(_traceback.format_exc())
    logger.exception("Erro não tratado em %s", request.url.path)
    show_detail = os.environ.get("DEBUG_ERRORS", "false").lower() == "true"
    detail = f"<details><summary>Detalhes (somente em DEBUG)</summary><pre>{tb}</pre></details>" if show_detail else ""
    body = (
        "<html><head><meta charset='utf-8'>"
        "<style>body{font-family:Inter,sans-serif;display:flex;align-items:center;"
        "justify-content:center;height:100vh;background:#eef0f8;margin:0}"
        ".box{text-align:center;max-width:520px;padding:32px}"
        "h1{font-size:56px;color:#2f5ee3;margin:0}p{color:#6b7280}"
        "a{color:#2f5ee3;text-decoration:none}a:hover{text-decoration:underline}"
        "details{text-align:left;margin-top:16px}pre{font-size:11px;overflow:auto;"
        "background:#f6f8fa;padding:12px;border:1px solid #d0d7de;border-radius:6px}"
        "</style></head>"
        "<body><div class='box'>"
        "<h1>500</h1>"
        "<p>Ocorreu um erro ao carregar esta página.<br>"
        "Os dados podem estar temporariamente indisponíveis.</p>"
        f"<p><a href='{_html.escape(request.url.path)}'>↺ Tentar novamente</a> &nbsp;·&nbsp; "
        "<a href='/'>← Voltar ao início</a></p>"
        f"{detail}</div></body></html>"
    )
    return HTMLResponse(body, status_code=500)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(media.router)
app.include_router(leads.router)
app.include_router(vendas.router)
app.include_router(settings_router.router)
app.include_router(api.router)
