"""
frontend/db_readers/publicos.py — Atribuição de vendas por público (conjunto de
anúncios), lida da mv_atribuicao_publicos (refresh horário via etl/refresh_views.py).

Na UTM padrão nova o utm_content carrega o nome do conjunto/público; a MV cruza
leads → vendas por e-mail distinto com trava de projeto (mesma lógica da
view_atribuicao). `fonte` separa 'meta' / 'google' / 'outro'.
"""
from __future__ import annotations

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine

logger = get_logger("db")


def read_sales_by_publico(code: str, fonte: str) -> dict | None:
    """{publico: {"sales": int, "receita": float}} para o lançamento/fonte.

    Retorna None se a MV não existir (deixa o chamador cair no fallback).
    """
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT publico, vendas, faturamento_total
                    FROM mv_atribuicao_publicos
                    WHERE lancamento_codigo = :code AND fonte = :fonte
                """),
                {"code": code, "fonte": fonte},
            ).fetchall()
    except Exception:
        logger.warning("mv_atribuicao_publicos indisponível; usando fallback em pandas")
        return None
    return {
        r.publico: {"sales": int(r.vendas or 0), "receita": float(r.faturamento_total or 0)}
        for r in rows
    }
