from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    templates, get_launches, resolve_launch, _base_ctx, _fetch_all_data,
)

router = APIRouter()


@router.get("/vendas", response_class=HTMLResponse)
async def vendas_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_vendas_con=True)
    vendas_con = d["vendas_con"]
    ctx = _base_ctx(request, "vendas", "Vendas", launch, launches, vendas=vendas_con,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("vendas.html", ctx)


@router.get("/hotmart", response_class=HTMLResponse)
async def hotmart_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_hotmart=True)
    hotmart = d["hotmart"]
    ctx = _base_ctx(request, "hotmart", "Hotmart", launch, launches, hotmart=hotmart,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("hotmart.html", ctx)


@router.get("/tmb", response_class=HTMLResponse)
async def tmb_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_tmb=True)
    tmb = d["tmb"]
    ctx = _base_ctx(request, "tmb", "TMB", launch, launches, tmb=tmb,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("tmb.html", ctx)
