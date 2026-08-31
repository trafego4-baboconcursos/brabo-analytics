from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    templates, get_launches, resolve_launch, _base_ctx, _fetch_all_data,
    AcCampaignSummary,
)

router = APIRouter()


@router.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch)
    vendas, leads = d["vendas"], d["leads"]
    ctx = _base_ctx(request, "leads", "Leads & Confronto", launch, launches,
        leads=leads, vendas=vendas,
        data_errors=d.get("_errors", []))
    return templates.TemplateResponse("leads.html", ctx)


@router.get("/pesquisas", response_class=HTMLResponse)
async def pesquisas_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_tf=True)
    tf_data = d["tf"]
    ctx = _base_ctx(request, "pesquisas", "Pesquisas", launch, launches, tf=tf_data,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("pesquisas.html", ctx)


@router.get("/typeform", response_class=HTMLResponse)
async def typeform_page_legacy(request: Request, launch_code: str | None = None):
    """Link antigo — a página foi renomeada pra "Pesquisas" (cobre Typeform + sistema interno)."""
    qs = f"?launch_code={launch_code}" if launch_code else ""
    return RedirectResponse(url=f"/pesquisas{qs}", status_code=307)


@router.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request, launch_code: str | None = None):
    from frontend.db_readers.whatsapp_groups import read_whatsapp_groups  # noqa: PLC0415
    from frontend.db_readers.whatsapp_messages import read_whatsapp_messages  # noqa: PLC0415
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    wa = await run_in_threadpool(read_whatsapp_groups, launch.code if launch else "") if launch else None
    wa_msgs = await run_in_threadpool(read_whatsapp_messages, launch) if launch else None
    launch_cfg = await run_in_threadpool(read_launch_config, launch.code) if launch else {}
    ctx = _base_ctx(request, "whatsapp", "Grupos de WhatsApp", launch, launches,
                    wa=wa, wa_msgs=wa_msgs, launch_cfg=launch_cfg, data_errors=[])
    return templates.TemplateResponse("whatsapp.html", ctx)


@router.get("/crm-campanhas", response_class=HTMLResponse)
async def crm_campanhas_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_ac_camps=True)
    ac_summary = d["ac_summary"] or AcCampaignSummary()

    ctx = _base_ctx(
        request, "crm_campanhas", "E-mails (CRM) - Campanhas",
        launch, launches,
        ac_summary=ac_summary,
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("ac_campanhas.html", ctx)
