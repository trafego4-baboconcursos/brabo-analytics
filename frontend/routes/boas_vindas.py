"""Página /boas-vindas — compras x automação de boas-vindas no dia de abertura do carrinho.

O cálculo e o laço de 5 em 5 min ficam em frontend/services/monitor_boas_vindas.py.
Sem ?lancamento, mostra o carrinho que abre hoje; com ?lancamento=PES-NOV-26,
mostra o dia de abertura daquele lançamento (pra conferir um carrinho que já passou).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from frontend.core import _base_ctx, get_launches, templates
from frontend.services import monitor_boas_vindas as mbv
from logger import get_logger

router = APIRouter()
logger = get_logger("frontend")


@router.get("/boas-vindas", response_class=HTMLResponse)
async def boas_vindas_page(request: Request, lancamento: str | None = None):
    hoje = datetime.now(mbv.BR).date()
    erro = None
    try:
        lista = await run_in_threadpool(mbv.aberturas)
    except Exception:  # noqa: BLE001
        logger.exception("/boas-vindas: launch_config indisponível")
        lista, erro = [], "Não deu para ler a configuração dos lançamentos agora. Tente de novo em instantes."

    if lancamento:
        alvo = next((a for a in lista if a["codigo"] == lancamento.strip().upper()), None)
    else:
        alvo = next((a for a in lista if a["dia"] == hoje), None)

    snap = None
    if alvo and alvo["dia"] <= hoje and not erro:
        try:
            snap = await run_in_threadpool(mbv.obter, alvo)
        except Exception:  # noqa: BLE001
            logger.exception("/boas-vindas: cálculo falhou para %s", alvo["codigo"])
            erro = "Não deu para ler o Active Campaign ou as vendas agora. A página tenta de novo sozinha em 5 minutos."

    proxima = next((a for a in lista if a["dia"] > hoje), None)
    recentes = [a for a in reversed(lista) if a["dia"] <= hoje][:6]
    launches = await run_in_threadpool(get_launches)
    ctx = _base_ctx(
        request, "boas_vindas", "Boas-vindas", None, launches,
        alvo=alvo, snap=snap, erro=erro, hoje=hoje, proxima=proxima, recentes=recentes,
        pedido_lancamento=lancamento,
        ao_vivo=bool(alvo and alvo["dia"] == hoje),
    )
    return templates.TemplateResponse("boas_vindas.html", ctx)
