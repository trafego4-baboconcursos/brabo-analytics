from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool

from frontend.db_readers.lp_pagina import read_landing_pages, remover_oficial, salvar_oficial
from frontend.core import (
    templates, logger, get_launches, resolve_launch, _base_ctx,
    _fetch_all_data, _creative_overview, get_instagram_profiles,
    read_instagram_detail, read_perpetuo, PERPETUO_VERTICALS, read_distribuicao, _get_current_user,
)

router = APIRouter()


@router.get("/meta", response_class=HTMLResponse)
async def meta_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_thumbnails=True, needs_sales_attr=True)
    meta, google, vendas, sales_attr, drive_thumbnails = (
        d["meta"], d["google"], d["vendas"], d["sales_attr"], d["drive_thumbnails"]
    )
    creative_overview = None
    try:
        creative_overview = await run_in_threadpool(
            _creative_overview, meta, google, vendas, sales_attr,
            launch_code=launch.code if launch else ""
        )
    except Exception:
        logger.exception("Meta: falha ao montar creative overview")
    ctx = _base_ctx(request, "meta", "Meta Ads", launch, launches, meta=meta,
                    sales_attr=sales_attr,
                    creative_overview=creative_overview,
                    drive_thumbnails=drive_thumbnails,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("meta.html", ctx)


@router.get("/google", response_class=HTMLResponse)
async def google_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_thumbnails=True, needs_sales_attr=True)
    meta, google, vendas, sales_attr, drive_thumbnails = (
        d["meta"], d["google"], d["vendas"], d["sales_attr"], d["drive_thumbnails"]
    )
    creative_overview = None
    try:
        creative_overview = await run_in_threadpool(
            _creative_overview, meta, google, vendas, sales_attr,
            launch_code=launch.code if launch else ""
        )
    except Exception:
        logger.exception("Google: falha ao montar creative overview")
    ctx = _base_ctx(request, "google", "Google Ads", launch, launches, google=google,
                    sales_attr=sales_attr,
                    creative_overview=creative_overview,
                    drive_thumbnails=drive_thumbnails,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("google.html", ctx)


@router.get("/criativos", response_class=HTMLResponse)
async def criativos_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_thumbnails=True, needs_sales_attr=True)
    meta, google, vendas, sales_attr, typeform_count, drive_thumbnails = (
        d["meta"], d["google"], d["vendas"], d["sales_attr"], d["typeform_count"], d["drive_thumbnails"]
    )
    creative_overview = None
    try:
        creative_overview = await run_in_threadpool(
            _creative_overview, meta, google, vendas, sales_attr,
            launch_code=launch.code if launch else ""
        )
    except Exception:
        logger.exception("Criativos: falha ao montar creative overview")
    ctx = _base_ctx(request, "criativos", "Criativos", launch, launches,
        meta=meta, google=google, vendas=vendas, sales_attr=sales_attr,
        creative_overview=creative_overview, typeform_count=typeform_count,
        drive_thumbnails=drive_thumbnails,
        data_errors=d.get("_errors", []))
    return templates.TemplateResponse("criativos.html", ctx)


@router.get("/instagram", response_class=HTMLResponse)
async def instagram_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    ig = await run_in_threadpool(get_instagram_profiles)
    ctx = _base_ctx(request, "instagram", "Perfil Instagram", launch, launches,
                    instagram_profiles=ig["profiles"], instagram_api_configured=ig["api_configured"])
    return templates.TemplateResponse("instagram.html", ctx)


@router.get("/instagram/{username}", response_class=HTMLResponse)
async def instagram_detail_page(request: Request, username: str, launch_code: str | None = None,
                                 days: int = 30, compare: int = 0):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    detail = await run_in_threadpool(read_instagram_detail, username, days, bool(compare))
    ctx = _base_ctx(request, "instagram", f"@{username}", launch, launches, ig=detail)
    return templates.TemplateResponse("instagram_detail.html", ctx)


@router.get("/perpetuo/{vertical}", response_class=HTMLResponse)
async def perpetuo_page(request: Request, vertical: str, launch_code: str | None = None,
                         days: int = 30, compare: int = 0):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    detail = await run_in_threadpool(read_perpetuo, vertical, days, bool(compare))
    # Mês fechado, em paralelo ao seletor de dias corridos: o seletor nunca
    # responde "quanto o perpétuo deu em agosto?" — ver read_perpetuo_mensal.
    mensal = None
    try:
        from frontend.db_readers.perpetuo import read_perpetuo_mensal  # noqa: PLC0415
        mensal = await run_in_threadpool(read_perpetuo_mensal, 6)
    except Exception:
        logger.exception("Perpétuo: falha ao montar a visão mês a mês")
    nome = PERPETUO_VERTICALS.get(vertical, {}).get("nome", vertical)
    ctx = _base_ctx(request, "perpetuo", nome, launch, launches,
                    perpetuo=detail, perpetuo_mensal=mensal)
    return templates.TemplateResponse("perpetuo.html", ctx)


@router.get("/distribuicao/{username}", response_class=HTMLResponse)
async def distribuicao_page(request: Request, username: str, launch_code: str | None = None,
                             days: int = 30, compare: int = 0):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    detail = await run_in_threadpool(read_distribuicao, username, days, bool(compare))
    ctx = _base_ctx(request, "distribuicao", f"@{username}", launch, launches, distrib=detail)
    return templates.TemplateResponse("distribuicao.html", ctx)


@router.get("/meta-audiences", response_class=HTMLResponse)
async def meta_audiences(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_meta_vendas=True)
    meta = d["meta"]
    ctx = _base_ctx(request, "meta-audiences", "Meta Audiências", launch, launches, meta=meta,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("meta_audiences.html", ctx)


@router.get("/google-audiences", response_class=HTMLResponse)
async def google_audiences(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_google_vendas=True)
    google = d["google"]
    ctx = _base_ctx(request, "google-audiences", "Google Audiências", launch, launches, google=google,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("google_audiences.html", ctx)

@router.get("/analise-copys", response_class=HTMLResponse)
async def analise_copys_page(request: Request, launch_code: str | None = None):
    """Gancho falado x retencao x CPL x venda x ROAS, por familia de gancho.

    Precisa de needs_sales_attr: sem venda a pagina mostraria so CPL, e no
    PES-SET-26 o ranking por CPL e quase o inverso do ranking por CPA."""
    from frontend.services.copys import read_copys_page  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_sales_attr=True)
    copys = None
    try:
        copys = await run_in_threadpool(read_copys_page, launch, d.get("sales_attr"))
    except Exception:
        logger.exception("Analise de Copys: falha ao montar o confronto")
    ctx = _base_ctx(request, "analise-copys", "Analise de Copys", launch, launches,
                    copys=copys, data_errors=d.get("_errors", []))
    return templates.TemplateResponse("analise_copys.html", ctx)


# ── Landing Pages ──────────────────────────────────────────────────────────────
# Tudo de cada LP do lançamento: lista oficial, auditoria (form/tag/obrigado/GTM/pixel/velocidade/CrUX,
# gravada por `python -m scripts.ads.auditar_lps <LANC>`), Meta, Google e GA4.
_PODE_EDITAR_LPS = ("admin", "analista", "trafego")


@router.get("/landing-pages", response_class=HTMLResponse)
async def landing_pages_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    dados = await run_in_threadpool(read_landing_pages, launch.code) if launch else None
    user = _get_current_user(request)
    ctx = _base_ctx(request, "landing-pages", "Landing Pages", launch, launches, lp=dados,
                    pode_editar=bool(launch and _pode_editar_lps(user, launch.code)))
    return templates.TemplateResponse("landing_pages.html", ctx)


def _pode_editar_lps(user: dict | None, launch_code: str) -> bool:
    """Papel com edição e o produto do lançamento no escopo do usuário (mesma regra do menu de lançamentos)."""
    if not user or user.get("role") not in _PODE_EDITAR_LPS:
        return False
    produtos = user.get("products", ["ALL"])
    return "ALL" in produtos or launch_code.upper().split("-")[0] in produtos


async def _corpo_json(request: Request) -> dict:
    import json as _json
    try:
        return _json.loads(await request.body() or b"{}")
    except ValueError:
        return {}


@router.post("/api/landing-pages/{launch_code}/oficiais")
async def api_salvar_lp_oficial(launch_code: str, request: Request):
    from fastapi.responses import JSONResponse
    user = _get_current_user(request)
    if not _pode_editar_lps(user, launch_code):
        return JSONResponse({"ok": False, "error": "Sem permissão para editar a lista de LPs."}, status_code=403)
    b = await _corpo_json(request)
    try:
        url = await run_in_threadpool(salvar_oficial, launch_code.upper(), b.get("url", ""), b.get("tag"),
                                      b.get("funcao"), b.get("observacao"), user.get("email") or user.get("name") or "?")
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    logger.info("LP oficial salva em %s por %s: %s", launch_code, user.get("email"), url)
    return {"ok": True, "url": url}


@router.post("/api/landing-pages/{launch_code}/oficiais/remover")
async def api_remover_lp_oficial(launch_code: str, request: Request):
    from fastapi.responses import JSONResponse
    user = _get_current_user(request)
    if not _pode_editar_lps(user, launch_code):
        return JSONResponse({"ok": False, "error": "Sem permissão para editar a lista de LPs."}, status_code=403)
    b = await _corpo_json(request)
    removida = await run_in_threadpool(remover_oficial, launch_code.upper(), b.get("url", ""))
    logger.info("LP oficial removida de %s por %s: %s (%s)", launch_code, user.get("email"), b.get("url"), removida)
    return {"ok": removida}
