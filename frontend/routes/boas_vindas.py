"""Página /boas-vindas?launch_code=... — compras x automação de boas-vindas no dia
de abertura do carrinho, uma por lançamento (menu do lançamento, grupo Leads &
Audiências, ao lado de Campanhas (E-mails)).

O cálculo e o laço de 5 em 5 min ficam em frontend/services/monitor_boas_vindas.py.
No dia de abertura a página mostra o carrinho ao vivo; depois, o retrato daquele
dia; antes, a data em que o monitor começa.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from frontend.core import _base_ctx, get_launches, resolve_launch, templates
from frontend.services import monitor_boas_vindas as mbv
from logger import get_logger

router = APIRouter()
logger = get_logger("frontend")


@router.get("/boas-vindas", response_class=HTMLResponse)
async def boas_vindas_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    codigo = launch.code if launch else (launch_code or "").upper() or None
    hoje = datetime.now(mbv.BR).date()

    alvo, snap, erro = None, None, None
    if mbv.tem_monitor(codigo):
        try:
            alvo = await run_in_threadpool(mbv.abertura_de, codigo)
        except Exception:  # noqa: BLE001
            logger.exception("/boas-vindas: launch_config indisponível")
            erro = "Não deu para ler a configuração do lançamento agora. Tente de novo em instantes."
    if alvo and alvo["dia"] <= hoje:
        try:
            snap = await run_in_threadpool(mbv.obter, alvo)
        except Exception:  # noqa: BLE001
            logger.exception("/boas-vindas: cálculo falhou para %s", alvo["codigo"])
            erro = "Não deu para ler o Active Campaign ou as vendas agora. A página tenta de novo sozinha em 5 minutos."

    ctx = _base_ctx(
        request, "boas_vindas", f"Boas-vindas{' — ' + codigo if codigo else ''}", launch, launches,
        codigo=codigo, monitorado=mbv.tem_monitor(codigo),
        alvo=alvo, snap=snap, erro=erro, hoje=hoje,
        ao_vivo=bool(alvo and alvo["dia"] == hoje),
    )
    return templates.TemplateResponse("boas_vindas.html", ctx)
