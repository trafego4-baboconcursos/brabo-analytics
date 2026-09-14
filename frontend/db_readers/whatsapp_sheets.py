"""
frontend/db_readers/whatsapp_sheets.py — Leitor de whatsapp_sheets_resumo /
whatsapp_sheets_diario (banco analytics), alimentadas por
etl/etl_sheets_contagem.py a partir do Sheets do sendflow-analytics-poller.

Puramente banco — nenhuma chamada à SendFlow nem ao Google Sheets acontece
aqui. Total/Total Limpo/Grupos Cheios/Entrada/Saída exibidos no Brabo
Analytics são cópia literal do que está na planilha, sem recálculo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

from frontend.db import _get_engine
from frontend.utils import _extract_launch_code


def _resumo_por_bloco(code: str) -> dict[str, dict]:
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT bloco, total_grupos_cheios, total_leads, total_limpo
                FROM whatsapp_sheets_resumo
                WHERE launch_code = :code
            """),
            {"code": code},
        ).fetchall()
    return {
        bloco: {"grupos_cheios": gc, "total_leads": tl, "total_limpo": tlimp}
        for bloco, gc, tl, tlimp in rows
    }


def _diario_por_bloco(code: str) -> dict[str, list[dict]]:
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT bloco, date::text, entradas, saidas, leads_no_dia
                FROM whatsapp_sheets_diario
                WHERE launch_code = :code
                ORDER BY date
            """),
            {"code": code},
        ).fetchall()

    out: dict[str, list[dict]] = {"normal": [], "vip": []}
    for bloco, data_iso, entradas, saidas, leads_no_dia in rows:
        if bloco not in out:
            continue
        dia = datetime.strptime(data_iso, "%Y-%m-%d").date()
        entradas = entradas or 0
        saidas = saidas or 0
        out[bloco].append({
            "data": data_iso,
            "data_str": dia.strftime("%d/%m/%Y"),
            "entradas": entradas,
            "saidas": saidas,
            "relacao": entradas - saidas,
            "leads_no_dia": leads_no_dia,
        })
    return out


def pico_por_bloco(code: str) -> dict[str, dict]:
    """Pico histórico por bloco (normal/vip), com a data em que ocorreu:
        {"normal": {"leads_no_dia": {"valor":.., "data":"YYYY-MM-DD"},
                     "saidas":      {"valor":.., "data":"YYYY-MM-DD"}},
         "vip": {...}}

    "leads_no_dia" = pico de pessoas ativas no grupo num dia (não o total
    atual, que só cai depois que o carrinho fecha e não reflete mais o
    alcance real do lançamento). "saidas" = pico de saída NUM ÚNICO DIA
    (não confundir com o total acumulado de saídas do lançamento inteiro)."""
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT bloco, date::text, entradas, saidas, leads_no_dia
                FROM whatsapp_sheets_diario
                WHERE launch_code = :code
                ORDER BY bloco, date
            """),
            {"code": code},
        ).fetchall()

    out: dict[str, dict] = {}
    for bloco, data, _entradas, saidas, leads_no_dia in rows:
        bucket = out.setdefault(bloco, {"leads_no_dia": None, "saidas": None})
        if leads_no_dia is not None:
            atual = bucket["leads_no_dia"]
            if atual is None or leads_no_dia > atual["valor"]:
                bucket["leads_no_dia"] = {"valor": int(leads_no_dia), "data": data}
        if saidas is not None:
            atual = bucket["saidas"]
            if atual is None or saidas > atual["valor"]:
                bucket["saidas"] = {"valor": int(saidas), "data": data}
    return out


def contar_lancamento(launch_folder_or_code: Any) -> dict[str, dict]:
    """Retorna {"normal": {"total":.., "total_limpo":.., "grupos":..,
    "entradas_hoje":.., "saidas_hoje":..}, "vip": {...}} — os mesmos campos
    que os cards Total/Total Limpo/Grupos/Entrada/Saída da página esperam.
    "hoje" é o dia mais recente que já tem linha em whatsapp_sheets_diario
    (normalmente hoje mesmo, assim que o poller atualiza o Sheets)."""
    code = _extract_launch_code(launch_folder_or_code)
    resumo = _resumo_por_bloco(code)
    diario = _diario_por_bloco(code)

    out: dict[str, dict] = {}
    for bloco, r in resumo.items():
        ultimo = diario.get(bloco, [])[-1] if diario.get(bloco) else None
        out[bloco] = {
            "total": r["total_leads"],
            "total_limpo": r["total_limpo"],
            "grupos": r["grupos_cheios"],
            "entradas_hoje": ultimo["entradas"] if ultimo else 0,
            "saidas_hoje": ultimo["saidas"] if ultimo else 0,
        }
    return out


def historico_diario(launch_folder_or_code: Any) -> dict[str, list[dict]]:
    """Tabela diária (Data/Entradas/Saídas/Relação/Leads no dia) por bloco,
    idêntica à aba do Sheets — cópia direta de whatsapp_sheets_diario."""
    code = _extract_launch_code(launch_folder_or_code)
    diario = _diario_por_bloco(code)
    return {bloco: linhas for bloco, linhas in diario.items() if linhas}
