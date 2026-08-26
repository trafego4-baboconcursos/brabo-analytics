"""Resolve o lançamento correto pra uma linha de dado (campanha + data),
protegendo contra reatribuição retroativa quando uma campanha é renomeada.

Motivação: campanhas Meta/Google às vezes são renomeadas pra reaproveitar
estrutura/aprendizado do próximo lançamento (ex.: campanha criada durante o
PBB-JUN-26, depois renomeada pra "[old][PBB-AGO-26]"). Classificar só pelo
nome ATUAL faria todo o histórico de gasto — inclusive os dias em que a
campanha ainda rodava pelo lançamento anterior — migrar retroativamente pro
lançamento novo. Aqui, o lançamento é resolvido pela DATA do gasto: qual
lançamento do mesmo produto (prefixo PBB/PES/PI) tinha a janela
[data_inicio, data_fim] ativa naquele dia — não o nome que a campanha carrega
hoje.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from functools import lru_cache

from sqlalchemy import text

CODE_RE = re.compile(r"\b(PBB|PES|PI)-\w{3}-\d{2}\b", re.IGNORECASE)
PREFIX_RE = re.compile(r"\b(PBB|PES|PI)-", re.IGNORECASE)


def extract_code_from_text(campaign_name: str | None) -> str | None:
    if not campaign_name:
        return None
    match = CODE_RE.search(str(campaign_name))
    return match.group(0).upper() if match else None


def extract_prefix(campaign_name: str | None) -> str | None:
    if not campaign_name:
        return None
    match = PREFIX_RE.search(str(campaign_name))
    return match.group(1).upper() if match else None


@lru_cache(maxsize=1)
def _load_launch_windows() -> dict[str, list[tuple]]:
    from db import get_engine  # etl/db.py; import local pra evitar ciclo de import

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT codigo, data_inicio, data_fim FROM dim_lancamentos ORDER BY data_inicio")
        ).fetchall()
    by_prefix: dict[str, list[tuple]] = {}
    for codigo, inicio, fim in rows:
        prefix = codigo.split("-")[0].upper()
        by_prefix.setdefault(prefix, []).append((inicio, fim, codigo))
    return by_prefix


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resolve_launch_code(campaign_name: str | None, row_date) -> str | None:
    """Código do lançamento pra uma linha de dado (campanha + data).

    Prioridade: janela [data_inicio, data_fim] do mesmo produto que contém
    row_date. Sem match (spend fora de qualquer janela cadastrada — ex.:
    lançamento futuro ainda sem linha em dim_lancamentos, ou campanha
    always-on fora de qualquer período), cai pro código extraído do nome
    (comportamento anterior).
    """
    prefix = extract_prefix(campaign_name)
    if not prefix:
        return None
    parsed_date = _to_date(row_date)
    if parsed_date is not None:
        for inicio, fim, codigo in _load_launch_windows().get(prefix, []):
            if inicio <= parsed_date <= fim:
                return codigo
    return extract_code_from_text(campaign_name)
