from __future__ import annotations
import os
import time as _time
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from frontend.core import (
    logger,
    WORKSPACE_ROOT, ANALISES_DIR,
    _APP_START_TIME, _HEALTH_CACHE_TTL,
    _THUMB_URL_TTL,
    _get_current_user, _invalidate, reset_launches_cache,
    get_launches,
    read_launch_config, save_launch_config,
    count_campaigns_for_filter, get_drive_thumbnails,
    KNOWN_META_ACCOUNTS, KNOWN_GOOGLE_ACCOUNTS,
    _compute_launch_defaults,
    get_user_by_id, list_users, update_user,
    create_invite, delete_invite,
)
import frontend.core as _core

router = APIRouter()


# ── Usuários ───────────────────────────────────────────────────────────────────

@router.get("/api/users")
def api_list_users(request: Request):
    user = _get_current_user(request)
    if user["role"] != "admin":
        return {"error": "Sem permissão"}, 403
    return {"users": list_users()}


@router.post("/api/users/{user_id}/toggle")
def api_toggle_user(request: Request, user_id: str):
    current = _get_current_user(request)
    if current["role"] != "admin":
        return {"error": "Sem permissão"}
    target = get_user_by_id(user_id)
    if not target:
        return {"error": "Usuário não encontrado"}
    update_user(user_id, is_active=not target["is_active"])
    return {"ok": True, "is_active": not target["is_active"]}


@router.post("/api/users/{user_id}/role")
async def api_update_role(request: Request, user_id: str):
    current = _get_current_user(request)
    if current["role"] != "admin":
        return {"error": "Sem permissão"}
    import json as _json
    body = await request.body()
    data = _json.loads(body)
    update_user(user_id, role=data.get("role"), products=data.get("products"))
    return {"ok": True}


# ── Convites ───────────────────────────────────────────────────────────────────

@router.post("/api/invites")
async def api_create_invite(request: Request):
    current = _get_current_user(request)
    if current["role"] != "admin":
        return {"error": "Sem permissão"}
    import json as _json
    body = await request.body()
    data = _json.loads(body)
    invite = create_invite(
        role=data.get("role", "leitura"),
        products=data.get("products", ["ALL"]),
        email=data.get("email") or None,
        created_by=current["user_id"] if current["user_id"] != "legacy" else None,
        expires_hours=data.get("expires_hours", 72),
    )
    return {"ok": True, "invite": invite}


@router.delete("/api/invites/{invite_id}")
def api_delete_invite(request: Request, invite_id: str):
    current = _get_current_user(request)
    if current["role"] != "admin":
        return {"error": "Sem permissão"}
    delete_invite(invite_id)
    return {"ok": True}


# ── Launch Config ──────────────────────────────────────────────────────────────

@router.get("/api/launch-config/{launch_code}")
def api_get_launch_config(launch_code: str):
    config = read_launch_config(launch_code)
    defaults = _compute_launch_defaults(launch_code)

    merged = {**defaults}
    for k, v in config.items():
        if v not in (None, "", [], {}):
            merged[k] = v

    return {
        "launch_code": launch_code,
        "config": merged,
        "meta_accounts": KNOWN_META_ACCOUNTS,
        "google_accounts": KNOWN_GOOGLE_ACCOUNTS,
    }


@router.post("/api/launch-config/{launch_code}")
async def api_save_launch_config(launch_code: str, request: Request):
    import json as _json
    body = await request.body()
    config = _json.loads(body)
    save_launch_config(launch_code, config)
    _invalidate(launch_code)
    reset_launches_cache()
    return {"ok": True, "launch_code": launch_code}


# ── Drive Thumbnails ───────────────────────────────────────────────────────────

@router.get("/api/drive-thumbnails/{launch_code}")
def api_drive_thumbnails(launch_code: str, subfolder: str = "captação"):
    try:
        thumbnails = get_drive_thumbnails(launch_code, subfolder)
        return {"ok": True, "thumbnails": thumbnails, "count": len(thumbnails)}
    except Exception:
        logger.exception("Erro ao buscar thumbnails Drive para %s", launch_code)
        return {"ok": False, "error": "Falha ao buscar thumbnails.", "thumbnails": {}}


@router.get("/api/creative-image/{launch_code}/{ad_code}")
def api_creative_image(launch_code: str, ad_code: str):
    from fastapi.responses import Response as _Response
    from sqlalchemy import text as _text
    from frontend.db import _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            _text("SELECT content_type, image_data FROM creative_thumbnails WHERE lancamento_codigo = :code AND ad_code = :ad_code"),
            {"code": launch_code, "ad_code": ad_code},
        ).fetchone()
    if not row:
        return _Response(status_code=404, content="thumbnail não encontrada")
    content_type, image_data = row
    return _Response(content=bytes(image_data), media_type=content_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/api/drive-thumb/{file_id}")
def api_drive_thumb(file_id: str):
    from fastapi.responses import RedirectResponse as _Redirect, Response as _Response
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    cached = _core._thumb_url_cache.get(file_id)
    if cached and (_time.time() - cached[0]) < _THUMB_URL_TTL:
        return _Redirect(url=cached[1], status_code=302)

    KEY_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "json",
                                              "uplifted-kit-499213-d8-6c09276f2753.json"))
    try:
        creds = service_account.Credentials.from_service_account_file(
            KEY_FILE, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        meta = service.files().get(fileId=file_id, fields="thumbnailLink").execute()
        thumb_url = meta.get("thumbnailLink", "")
        if thumb_url:
            thumb_url = thumb_url.replace("=s220", "=s800")
            _core._thumb_url_cache[file_id] = (_time.time(), thumb_url)
            return _Redirect(url=thumb_url, status_code=302)
        return _Response(status_code=404, content="no thumbnail")
    except Exception:
        logger.exception("Erro ao buscar thumbnail Drive para file_id=%s", file_id)
        return _Response(status_code=502, content="Falha ao buscar thumbnail.")


# ── Campaign Count ─────────────────────────────────────────────────────────────

@router.get("/api/campaign-count")
def api_campaign_count(launch_code: str, term: str = ""):
    result = count_campaigns_for_filter(launch_code, term)
    return result


# ── Cache ──────────────────────────────────────────────────────────────────────

@router.post("/api/clear-cache")
def clear_cache(launch_code: str | None = None):
    if launch_code:
        _invalidate(launch_code)
        return {"cleared": launch_code}
    _core._CACHE.clear()
    return {"cleared": "all"}


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check(request: Request):
    user = _get_current_user(request)
    if not user or user.get("role") not in ("admin", "analista"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "ok"}, status_code=200)
    now = _time.time()
    if _core._HEALTH_CACHE and (now - _core._HEALTH_CACHE_AT) < _HEALTH_CACHE_TTL:
        cached = dict(_core._HEALTH_CACHE)
        cached["uptime_seconds"] = int(now - _APP_START_TIME)
        return cached

    from sqlalchemy import text as sa_text
    from frontend.database_reader import _get_engine, _get_users_engine

    result: dict = {"status": "ok", "uptime_seconds": int(now - _APP_START_TIME)}

    try:
        with _get_engine().connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        result["db_analytics"] = "ok"
    except Exception:
        logger.exception("Health check: db_analytics indisponível")
        result["db_analytics"] = "error"
        result["status"] = "degraded"

    try:
        with _get_users_engine().connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        result["db_operational"] = "ok"
    except Exception:
        logger.exception("Health check: db_operational indisponível")
        result["db_operational"] = "error"
        result["status"] = "degraded"

    result["launches_cached"] = len(_core._LAUNCHES_CACHE)

    _core._HEALTH_CACHE = result
    _core._HEALTH_CACHE_AT = now
    return result


# ── ETL manual ─────────────────────────────────────────────────────────────────

@router.post("/api/run-etl")
def api_run_etl(request: Request):
    user = _get_current_user(request)
    if not user or user.get("role") != "admin":
        return {"error": "Sem permissão"}

    import subprocess
    import sys as _sys
    from datetime import datetime, timedelta
    from sqlalchemy import text as sa_text
    from frontend.database_reader import _get_engine

    try:
        with _get_engine().connect() as conn:
            row = conn.execute(sa_text(
                "SELECT source, started_at FROM etl_runs "
                "WHERE status = 'running' AND started_at > NOW() - INTERVAL '20 minutes' "
                "ORDER BY started_at DESC LIMIT 1"
            )).fetchone()
        if row:
            return {"error": f"Já existe uma rodada de ETL em andamento ({row[0]}, iniciada às {row[1]:%H:%M})."}
    except Exception:
        logger.exception("Falha ao checar etl_runs antes de disparar ETL manual")

    hoje = datetime.now()
    inicio = (hoje - timedelta(days=2)).strftime("%Y-%m-%d")
    fim = hoje.strftime("%Y-%m-%d")
    run_all_path = WORKSPACE_ROOT / "etl" / "run_all.py"

    subprocess.Popen(
        [_sys.executable, str(run_all_path), "--since", inicio, "--until", fim],
        cwd=str(WORKSPACE_ROOT),
    )
    logger.info("ETL manual disparado por %s (janela %s a %s)", user.get("email"), inicio, fim)
    return {"ok": True, "message": f"ETL disparado. Janela: {inicio} até {fim}. Pode levar alguns minutos."}


# ── Debug ──────────────────────────────────────────────────────────────────────

@router.get("/debug-path")
def debug_path(request: Request):
    user = _get_current_user(request)
    if not user or user.get("role") != "admin":
        return {"error": "Sem permissão"}
    launches = get_launches()
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "analises_dir": str(ANALISES_DIR),
        "analises_exists": ANALISES_DIR.exists(),
        "launches_found": [l.code for l in launches],
    }


# ── Redirects legados ──────────────────────────────────────────────────────────

@router.get("/campaigns")
def campaigns_redirect(request: Request, launch_code: str | None = None):
    return RedirectResponse(url=f"/meta?launch_code={launch_code or ''}", status_code=301)


@router.get("/ads")
def ads_redirect(request: Request, launch_code: str | None = None):
    return RedirectResponse(url=f"/criativos?launch_code={launch_code or ''}", status_code=301)


@router.get("/audiences")
def audiences_redirect(request: Request, launch_code: str | None = None):
    return RedirectResponse(url=f"/meta-audiences?launch_code={launch_code or ''}", status_code=301)


@router.get("/sales")
def sales_redirect(request: Request, launch_code: str | None = None):
    return RedirectResponse(url=f"/vendas?launch_code={launch_code or ''}", status_code=301)
