from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    templates, logger, get_launches, resolve_launch, _base_ctx,
    list_users, list_invites, ROLE_LABELS, PRODUCT_LABELS,
)

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    users_list, invites_list = [], []
    try:
        users_list   = list_users()
        invites_list = list_invites()
    except Exception:
        logger.exception("Falha ao carregar usuários/convites para /settings")
    ctx = _base_ctx(
        request, "settings", "Configurações", launch, launches,
        users_list=users_list, invites_list=invites_list,
        role_labels=ROLE_LABELS, product_labels=PRODUCT_LABELS,
        all_products=["PBB", "PES", "PI", "PERPETUO"],
    )
    return templates.TemplateResponse("settings.html", ctx)
