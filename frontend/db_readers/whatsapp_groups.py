"""
frontend/db_readers/whatsapp_groups.py — Leitor dos grupos de WhatsApp (banco analytics).

Cada lançamento pode ter duas tabelas no banco analytics, alimentadas pela
automação de grupos:
    [CODE]_API      → grupos normais  (ex: PI_AGO_26_API)
    [CODE]_VIP_API  → grupos VIP      (ex: PI_AGO_26_VIP_API)

Formato: uma linha por telefone (sem repetição). Colunas relevantes:
    DATA1              → data de ENTRADA no grupo (DD/MM/YYYY)
    GRUPO DA CAMPANHA  → nome do grupo
    LEAD ÚNICO         → 1 = está no grupo, 0 = saiu
    LEAD NÚMERO        → em quantos grupos a pessoa entrou (só na tabela normal)

Não há data de saída — "saíram" é o total de LEAD ÚNICO = 0 entre quem entrou
no período, sem timeline de saída.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code, _safe_date
from frontend.db import _get_engine

logger = get_logger("db")


def _tabela_existe(conn, nome: str) -> bool:
    r = conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name = :t"),
        {"t": nome},
    ).fetchone()
    return r is not None


_DATA_EXPR = "to_date(\"DATA1\", 'DD/MM/YYYY')"


def _resumo_tabela(conn, tabela: str, start, end, tem_lead_numero: bool) -> dict:
    """Agrega tudo em SQL — as tabelas têm centenas de milhares de linhas."""
    where = f"WHERE {_DATA_EXPR} BETWEEN :start AND :end"
    params = {"start": start, "end": end}

    tot = conn.execute(text(f'''
        SELECT COUNT(*)                                 AS entradas,
               COALESCE(SUM("LEAD ÚNICO"), 0)           AS ativos,
               COUNT(*) - COALESCE(SUM("LEAD ÚNICO"),0) AS saidas,
               COUNT(DISTINCT "GRUPO DA CAMPANHA")      AS grupos
        FROM "{tabela}" {where}
    '''), params).fetchone()

    multi_grupo = 0
    if tem_lead_numero:
        multi_grupo = conn.execute(text(f'''
            SELECT COUNT(*) FROM "{tabela}" {where} AND "LEAD NÚMERO" >= 2
        '''), params).fetchone()[0]

    timeline = conn.execute(text(f'''
        SELECT {_DATA_EXPR} AS dia,
               COUNT(*) AS entradas,
               COUNT(*) - COALESCE(SUM("LEAD ÚNICO"),0) AS saidas
        FROM "{tabela}" {where}
        GROUP BY 1 ORDER BY 1
    '''), params).fetchall()

    grupos = conn.execute(text(f'''
        SELECT "GRUPO DA CAMPANHA" AS grupo,
               COUNT(*) AS entradas,
               COALESCE(SUM("LEAD ÚNICO"),0) AS ativos,
               COUNT(*) - COALESCE(SUM("LEAD ÚNICO"),0) AS saidas
        FROM "{tabela}" {where}
        GROUP BY 1 ORDER BY 2 DESC
    '''), params).fetchall()

    entradas = int(tot[0] or 0)
    ativos = int(tot[1] or 0)
    saidas = int(tot[2] or 0)
    return {
        "entradas": entradas,
        "ativos": ativos,
        "saidas": saidas,
        "churn_pct": (saidas / entradas * 100) if entradas else 0.0,
        "grupos": int(tot[3] or 0),
        "media_por_grupo": (ativos / int(tot[3])) if tot[3] else 0.0,
        "multi_grupo": int(multi_grupo or 0),
        "timeline": [
            {"data": r[0].strftime("%Y-%m-%d"), "data_str": r[0].strftime("%d/%m"),
             "entradas": int(r[1]), "saidas": int(r[2])}
            for r in timeline
        ],
        "por_grupo": [
            {"grupo": r[0], "entradas": int(r[1]), "ativos": int(r[2]), "saidas": int(r[3]),
             "churn_pct": (int(r[3]) / int(r[1]) * 100) if r[1] else 0.0}
            for r in grupos
        ],
    }


def _read_whatsapp_uncached(code: str, start_date=None, end_date=None) -> dict | None:
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    base = code.replace("-", "_")
    t_normal = f"{base}_API"
    t_vip = f"{base}_VIP_API"

    cfg = read_launch_config(code)
    start = _safe_date(start_date) or _safe_date(cfg.get("pre_quali_start_date"))
    end = _safe_date(end_date) or _safe_date(cfg.get("carrinho_end_date"))

    engine = _get_engine()
    with engine.connect() as conn:
        tem_normal = _tabela_existe(conn, t_normal)
        tem_vip = _tabela_existe(conn, t_vip)
        if not tem_normal and not tem_vip:
            return None

        # Sem janela configurada, usa o range real dos dados
        if start is None or end is None:
            t_ref = t_normal if tem_normal else t_vip
            r = conn.execute(text(f'SELECT MIN({_DATA_EXPR}), MAX({_DATA_EXPR}) FROM "{t_ref}"')).fetchone()
            start = start or r[0]
            end = end or r[1]
        if start is None or end is None:
            return None

        normal = _resumo_tabela(conn, t_normal, start, end, tem_lead_numero=True) if tem_normal else None
        vip = _resumo_tabela(conn, t_vip, start, end, tem_lead_numero=False) if tem_vip else None

        overlap = 0
        if tem_normal and tem_vip:
            overlap = conn.execute(text(f'''
                SELECT COUNT(DISTINCT a."NÚMERO")
                FROM "{t_normal}" a
                JOIN "{t_vip}" b ON a."NÚMERO" = b."NÚMERO"
            ''')).fetchone()[0]

    return {
        "start": str(start),
        "end": str(end),
        "normal": normal,
        "vip": vip,
        "overlap_vip": int(overlap or 0),
    }


def read_whatsapp_groups(launch_folder_or_code: Any, start_date=None, end_date=None) -> dict | None:
    """Resumo dos grupos de WhatsApp do lançamento (cacheado por janela)."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415 — evita import circular

    code = _extract_launch_code(launch_folder_or_code)
    try:
        return _get_or_compute(
            code,
            f"whatsapp::{start_date}::{end_date}",
            lambda: _read_whatsapp_uncached(code, start_date, end_date),
        )
    except Exception:
        logger.exception("read_whatsapp_groups: falha para %s", code)
        return None
