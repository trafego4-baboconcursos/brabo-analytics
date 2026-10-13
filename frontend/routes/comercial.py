from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.concurrency import run_in_threadpool

from frontend.auth import _get_current_user
from frontend.core import templates, get_launches, _base_ctx
from frontend.db_readers import (
    PERIODOS, RECARREGAR_HORAS, SITUACOES, read_atendimento, read_conversas_abertas, espera_texto,
)

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
        atendimento=atendimento, dias=atendimento.dias, periodos=PERIODOS, recarregar_horas=RECARREGAR_HORAS,
        conexao=atendimento.conexao, conexoes=atendimento.conexoes, situacoes=SITUACOES,
    )
    return templates.TemplateResponse("atendimento.html", ctx)


@router.get("/atendimento/conversas.csv")
async def atendimento_conversas_csv(conexao: str | None = None, atendente: str | None = None,
                                    situacao: str | None = None):
    """Relatório completo das conversas abertas em CSV (Excel-friendly: ';' e
    BOM). A página mostra no máximo 200; aqui vêm todas, com os mesmos filtros
    (conta, atendente, situação) da tabela."""
    import csv
    import io
    from datetime import datetime

    conversas = await run_in_threadpool(read_conversas_abertas, conexao, atendente or None, situacao or None)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Contato", "Telefone", "Atendente", "Conexão", "Última mensagem de",
                "Última mensagem em", "Esperando há", "Esperando (min)", "Situação"])
    for c in conversas:
        w.writerow([
            c["contato"], c["telefone"] or "", c["atendente"], c["conexao"],
            {"cliente": "Cliente", "atendente": "Atendente"}.get(c["ultima_msg_de"], ""),
            c["ultima_msg_em"].strftime("%d/%m/%Y %H:%M") if c["ultima_msg_em"] else "",
            espera_texto(c["espera_min"]),
            c["espera_min"] if c["espera_min"] is not None else "",
            SITUACOES[c["situacao"]],
        ])
    nome = "conversas-abertas_" + datetime.now().strftime("%Y-%m-%d_%H%M") + ".csv"
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
