from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool

from frontend.auth import _get_current_user
from frontend.core import templates, get_launches, _base_ctx
from frontend.db_readers import PERIODOS, read_atendimento

router = APIRouter()


@router.get("/atendimento", response_class=HTMLResponse)
async def atendimento_page(request: Request, dias: int = 7, conexao: str | None = None):
    """Mensagens, templates e conversas abertas por atendente do Unnichat.

    Não é página de lançamento: o atendimento comercial é contínuo. O filtro é
    por conta (número de WhatsApp do Unnichat, cadastro unnichat_conexoes), não
    por produto: o que importa é em qual conta o atendimento aconteceu.
    """
    launches = await run_in_threadpool(get_launches)
    atendimento = await run_in_threadpool(read_atendimento, dias, conexao)
    ctx = _base_ctx(
        request, "atendimento", "Atendimento", None, launches,
        atendimento=atendimento, dias=atendimento.dias, periodos=PERIODOS,
        conexao=atendimento.conexao, conexoes=atendimento.conexoes,
    )
    return templates.TemplateResponse("atendimento.html", ctx)
