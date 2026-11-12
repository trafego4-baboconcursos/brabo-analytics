"""
frontend/db_readers/resumo.py — dados extras da página /resumo.

``read_perfil_compradores`` separa os compradores do lançamento em "Aluno do mesmo projeto",
"Aluno de outro projeto" e "Novo aluno" olhando as compras ANTERIORES ao início do carrinho
(Hotmart + TMB, por e-mail). Não existe um cadastro de alunos no banco — é a melhor aproximação
com o histórico de vendas: quem já pagou algo nosso antes deste carrinho "já era aluno".
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import _hm_data_sql, parse_ts_brt
from logger import get_logger

logger = get_logger("db")

_STATUS_HOTMART_PAGO = (
    "Completa", "Aprovada", "Paga", "Completo", "Aprovado", "Pago",
    "approved", "complete", "APPROVED", "COMPLETED",
)
_STATUS_TMB_PAGO = {"vigente", "efetivado", "pago", "em dia", "integralizado", "aprovado", "concluido", "active"}

_CASE_PROJETO = """CASE
    WHEN produto ILIKE '%black vital%' THEN 'BLACK'
    WHEN produto ILIKE '%inss%' THEN 'INSS'
    WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%' OR produto ILIKE '%escrevente%') THEN 'TJ'
    WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
    ELSE 'OUTRO'
  END"""

ROTULOS = ("Aluno (mesmo projeto)", "Aluno (outro projeto)", "Novo aluno")


def _projeto_de(produto: Any) -> str:
    p = str(produto or "").lower()
    if "black vital" in p:
        return "BLACK"
    if "inss" in p:
        return "INSS"
    if "tj" in p or "escrevente" in p:
        return "TJ"
    if "bb" in p or "banco do brasil" in p:
        return "BB"
    return "OUTRO"


def read_perfil_compradores(code: str, emails: set[str], inicio_carrinho: date | None) -> dict:
    """{"total", "linhas": [{"rotulo","qtd","pct"}]} — compradores x histórico de compras.

    `emails` = compradores do lançamento (read_vendas). Compra anterior = qualquer venda paga
    de produto nosso com data ANTES de `inicio_carrinho`.
    """
    emails = {e.strip().lower() for e in (emails or set()) if e and str(e).strip()}
    vazio = {"total": 0, "linhas": [{"rotulo": r, "qtd": 0, "pct": 0.0} for r in ROTULOS]}
    if not emails or inicio_carrinho is None:
        return vazio

    with _get_engine().connect() as conn:
        row = conn.execute(text("SELECT projeto FROM dim_lancamentos WHERE codigo = :c"), {"c": code}).fetchone()
    projeto = row[0] if row else None

    lista = sorted(emails)
    anteriores: dict[str, set[str]] = {}
    ops = _get_users_engine()

    # Hotmart — por SQL (a data usa o mesmo fragmento do resto do painel).
    sql_hm = text(
        "SELECT lower(email_do_a_comprador_a) AS email, " + _CASE_PROJETO + " AS proj "
        "FROM hotmart_clean_oficial "
        "WHERE lower(email_do_a_comprador_a) = ANY(:emails) "
        "  AND status_da_transacao = ANY(:status) "
        "  AND COALESCE(" + _hm_data_sql("data_da_transacao") + ", " + _hm_data_sql("confirmacao_do_pagamento") + ") < :inicio "
        "GROUP BY 1, 2"
    )
    try:
        with ops.connect() as conn_hm:
            for r in conn_hm.execute(sql_hm, {"emails": lista, "status": list(_STATUS_HOTMART_PAGO), "inicio": inicio_carrinho}):
                anteriores.setdefault(r[0], set()).add(r[1])
    except Exception:  # noqa: BLE001
        logger.exception("read_perfil_compradores: falha no histórico Hotmart (%s)", code)

    # TMB — em Python (data_efetivado mistura formatos).
    try:
        df = pd.read_sql(
            text("SELECT lower(email_cliente) AS email, produto, status, data_efetivado FROM tmb_clean_oficial "
                 "WHERE lower(email_cliente) = ANY(:emails) AND valor_liquido > 0"),
            ops, params={"emails": lista},
        )
        corte = pd.Timestamp(inicio_carrinho).to_pydatetime()
        for _, r in df.iterrows():
            if str(r["status"] or "").strip().lower() not in _STATUS_TMB_PAGO:
                continue
            ts = parse_ts_brt(r["data_efetivado"])
            if ts is not None and ts < corte:
                anteriores.setdefault(r["email"], set()).add(_projeto_de(r["produto"]))
    except Exception:  # noqa: BLE001
        logger.exception("read_perfil_compradores: falha no histórico TMB (%s)", code)

    qtd = {r: 0 for r in ROTULOS}
    for e in emails:
        projs = anteriores.get(e)
        if not projs:
            qtd["Novo aluno"] += 1
        elif projeto and projeto in projs:
            qtd["Aluno (mesmo projeto)"] += 1
        else:
            qtd["Aluno (outro projeto)"] += 1
    total = sum(qtd.values())
    return {
        "total": total,
        "linhas": [{"rotulo": r, "qtd": qtd[r], "pct": (qtd[r] / total * 100) if total else 0.0} for r in ROTULOS],
    }
