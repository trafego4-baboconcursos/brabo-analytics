from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    templates, logger, get_launches, resolve_launch, _base_ctx,
    _fetch_all_data, _creative_overview, get_instagram_profiles,
    read_instagram_detail, read_perpetuo, PERPETUO_VERTICALS, read_distribuicao,
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
    nome = PERPETUO_VERTICALS.get(vertical, {}).get("nome", vertical)
    ctx = _base_ctx(request, "perpetuo", nome, launch, launches, perpetuo=detail)
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
