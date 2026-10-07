from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool

from frontend.auth import _get_current_user
from frontend.core import templates, get_launches, _base_ctx
from frontend.db_readers import CONEXAO_LABELS, PERIODOS, conexoes_do_usuario, read_atendimento

router = APIRouter()


@router.get("/atendimento", response_class=HTMLResponse)
async def atendimento_page(request: Request, dias: int = 7, conexao: str | None = None):
    """Mensagens, templates e conversas abertas por atendente do Unnichat.

    Não é página de lançamento: o atendimento comercial é contínuo. O filtro de
    conexão respeita os produtos liberados pro usuário (INSS = PI, TJ = PES…),
    então um gestor só do INSS nunca vê a conexão do TJ, nem pela URL.
    """
    user = _get_current_user(request)
    permitidas = conexoes_do_usuario(user.get("products"))
    dias = dias if dias in PERIODOS else PERIODOS[0]
    if conexao not in permitidas:
        conexao = None
    launches = await run_in_threadpool(get_launches)
    atendimento = await run_in_threadpool(read_atendimento, dias, [conexao] if conexao else permitidas)
    ctx = _base_ctx(
        request, "atendimento", "Atendimento", None, launches,
        atendimento=atendimento, dias=dias, periodos=PERIODOS,
        conexao=conexao, conexoes=[(c, CONEXAO_LABELS[c]) for c in permitidas],
    )
    return templates.TemplateResponse("atendimento.html", ctx)
