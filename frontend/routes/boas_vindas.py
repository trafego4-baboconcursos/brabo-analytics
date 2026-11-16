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
from fastapi.responses import HTMLResponse, Response

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
        alvo=alvo, snap=snap, erro=erro, hoje=hoje, situacoes=mbv.SITUACOES,
        ao_vivo=bool(alvo and alvo["dia"] == hoje),
    )
    return templates.TemplateResponse("boas_vindas.html", ctx)


@router.get("/boas-vindas/compradores.csv")
async def boas_vindas_compradores_csv(request: Request, launch_code: str | None = None,
                                      situacao: str | None = None):
    """Todos os compradores do dia de abertura com a situação na automação, em CSV
    (Excel: ';' e BOM). `situacao` filtra (fora, a_caminho, entrou, ja_aluno), como
    os botões da página."""
    import csv
    import io

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    codigo = launch.code if launch else (launch_code or "").upper()
    alvo = await run_in_threadpool(mbv.abertura_de, codigo) if mbv.tem_monitor(codigo) else None
    hoje = datetime.now(mbv.BR).date()
    if not alvo or alvo["dia"] > hoje:
        return Response("Este lançamento ainda não teve dia de abertura com monitor de boas-vindas.",
                        status_code=404, media_type="text/plain; charset=utf-8")
    snap = await run_in_threadpool(mbv.obter, alvo)

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    cab = ["Comprou em", "E-mail", "Produto", "Situação", "Entrou na automação às", "Na fila agora"]
    if snap.get("aberturas_ok"):
        cab += ["Abriu o e-mail de boas-vindas", "Última abertura"]
    w.writerow(cab)
    for p in snap["pessoas"]:
        if situacao == "nao_abriu":
            if p["situacao"] != "entrou" or p.get("abriu"):
                continue
        elif situacao and p["situacao"] != situacao:
            continue
        linha = [
            p["quando"].strftime("%d/%m/%Y %H:%M"), p["email"], p["produto"],
            mbv.SITUACOES[p["situacao"]],
            p["entrou_hora"] or ("antes do dia" if p["situacao"] == "entrou" else ""),
            "sim" if p["na_fila"] else "não",
        ]
        if snap.get("aberturas_ok"):
            linha += ["sim" if p.get("abriu") else ("não" if p["situacao"] == "entrou" else ""),
                      p["abriu"].strftime("%d/%m/%Y %H:%M") if p.get("abriu") else ""]
        w.writerow(linha)
    nome = f"boas-vindas_{snap['codigo']}_{snap['atualizado_em'].strftime('%Y-%m-%d_%H%M')}"
    nome += f"_{situacao}.csv" if situacao else ".csv"
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
