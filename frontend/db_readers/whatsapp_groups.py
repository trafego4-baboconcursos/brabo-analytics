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

import re
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


def _tem_coluna(conn, tabela: str, coluna: str) -> bool:
    r = conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name = :t AND column_name = :c"),
        {"t": tabela, "c": coluna},
    ).fetchone()
    return r is not None


def _escolhe_tabela(conn, candidatos: list[str]) -> str | None:
    """Primeira candidata existente COM linhas; senão a primeira existente (vazia)."""
    existentes = [t for t in candidatos if _tabela_existe(conn, t)]
    for t in existentes:
        n = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).fetchone()[0]
        if n:
            return t
    return existentes[0] if existentes else None


_DATA_EXPR = "to_date(\"DATA1\", 'DD/MM/YYYY')"


def _norm_phone(v: Any) -> str | None:
    """Normaliza pra DDD + últimos 8 dígitos (ignora DDI 55 e o nono dígito),
    permitindo casar números dos grupos (com 55, às vezes sem o 9) com os
    telefones das vendas (11 dígitos)."""
    s = re.sub(r"\D", "", str(v or ""))
    if s.startswith("55") and len(s) > 11:
        s = s[2:]
    if len(s) < 10 or len(s) > 11:
        return None
    return s[:2] + s[-8:]


def _telefones_tabela(conn, tabela: str) -> set[str]:
    rows = conn.execute(text(f'SELECT DISTINCT "NÚMERO" FROM "{tabela}"')).fetchall()
    out: set[str] = set()
    for r in rows:
        p = _norm_phone(r[0])
        if p:
            out.add(p)
    return out


def _compradores_grupos(conn, t_normal: str | None, t_vip: str | None, code: str) -> dict | None:
    """Cruza compradores (Hotmart+TMB, por telefone) com presença nos grupos."""
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415 — evita import circular

    vendas = read_vendas(code)
    if not vendas:
        return None
    buyers = vendas.emails_hotmart | vendas.emails_tmb
    if not buyers:
        return None

    phone_por_email = vendas.phone_por_email or {}
    receita_por_email = vendas.receita_por_email or {}

    fones_normal = _telefones_tabela(conn, t_normal) if t_normal else set()
    fones_vip = _telefones_tabela(conn, t_vip) if t_vip else set()
    fones_grupos = fones_normal | fones_vip

    dentro = dentro_vip = dentro_normal = fora = sem_tel = 0
    receita_dentro = receita_fora = 0.0
    for email in buyers:
        p = _norm_phone(phone_por_email.get(email))
        receita = float(receita_por_email.get(email) or 0)
        if p is None:
            sem_tel += 1
            continue
        if p in fones_grupos:
            dentro += 1
            receita_dentro += receita
            if p in fones_vip:
                dentro_vip += 1
            if p in fones_normal:
                dentro_normal += 1
        else:
            fora += 1
            receita_fora += receita

    com_tel = dentro + fora
    return {
        "total": len(buyers),
        "com_telefone": com_tel,
        "sem_telefone": sem_tel,
        "dentro": dentro,
        "dentro_normal": dentro_normal,
        "dentro_vip": dentro_vip,
        "fora": fora,
        "pct_dentro": (dentro / com_tel * 100) if com_tel else 0.0,
        "receita_dentro": receita_dentro,
        "receita_fora": receita_fora,
    }


def _resumo_tabela(conn, tabela: str, start, end, tem_lead_numero: bool) -> dict:
    """Agrega tudo em SQL — as tabelas têm centenas de milhares de linhas.

    SEMPRE deduplicado por telefone: as tabelas novas (_API) já têm uma linha
    por pessoa, mas várias antigas guardam uma linha por (pessoa, grupo) —
    ex: PBB_ABR_26 tem 20k linhas repetidas. Pessoa em N grupos conta 1 vez;
    "ativa" se estiver ativa em pelo menos um grupo; a data considerada é a
    da PRIMEIRA entrada.
    """
    params = {"start": start, "end": end}
    # uma linha por pessoa: primeira entrada, ativa em algum grupo, nº de grupos.
    # Sem filtro de formato de número — mantém a mesma contagem que a
    # planilha (inclui LID do WhatsApp), por decisão de manter os dois
    # números iguais em vez de divergir.
    dedup = f'''
        SELECT "NÚMERO"::text                        AS fone,
               MIN({_DATA_EXPR})                     AS dia,
               MAX("LEAD ÚNICO")                     AS ativo,
               COUNT(DISTINCT "GRUPO DA CAMPANHA")   AS n_grupos
        FROM "{tabela}"
        GROUP BY 1
    '''
    where = "WHERE dia BETWEEN :start AND :end"

    tot = conn.execute(text(f'''
        SELECT COUNT(*)                          AS entradas,
               COALESCE(SUM(ativo), 0)           AS ativos,
               COUNT(*) - COALESCE(SUM(ativo),0) AS saidas,
               COUNT(*) FILTER (WHERE n_grupos >= 2) AS multi
        FROM ({dedup}) d {where}
    '''), params).fetchone()

    # Totais histórico completo (não escopado pelo período selecionado) —
    # alimenta os cards Total / Total Limpo / Saída do topo da página.
    tot_geral = conn.execute(text(f'''
        SELECT COUNT(*)                          AS total,
               COALESCE(SUM(ativo), 0)           AS total_limpo,
               COUNT(*) - COALESCE(SUM(ativo),0) AS saida_total
        FROM ({dedup}) d
    ''')).fetchone()

    n_grupos_total = conn.execute(text(f'''
        SELECT COUNT(DISTINCT "GRUPO DA CAMPANHA") FROM "{tabela}"
        WHERE {_DATA_EXPR} BETWEEN :start AND :end
    '''), params).fetchone()[0]

    # "em 2+ grupos": nas tabelas antigas sai das linhas repetidas (n_grupos);
    # nas novas (1 linha/pessoa) só o campo LEAD NÚMERO carrega essa informação
    multi_grupo = int(tot[3] or 0)
    if tem_lead_numero:
        via_campo = conn.execute(text(f'''
            SELECT COUNT(*) FROM "{tabela}"
            WHERE {_DATA_EXPR} BETWEEN :start AND :end AND "LEAD NÚMERO" >= 2
        '''), params).fetchone()[0]
        multi_grupo = max(multi_grupo, int(via_campo or 0))

    timeline = conn.execute(text(f'''
        SELECT dia,
               COUNT(*) AS entradas,
               COUNT(*) - COALESCE(SUM(ativo),0) AS saidas
        FROM ({dedup}) d {where}
        GROUP BY 1 ORDER BY 1
    '''), params).fetchall()

    # por grupo: deduplicado por (grupo, pessoa) — pessoa em 2 grupos conta
    # 1x em cada grupo (a soma dos grupos pode exceder o total geral)
    grupos = conn.execute(text(f'''
        SELECT grupo,
               COUNT(*) AS entradas,
               COALESCE(SUM(ativo),0) AS ativos,
               COUNT(*) - COALESCE(SUM(ativo),0) AS saidas
        FROM (
            SELECT "GRUPO DA CAMPANHA" AS grupo, "NÚMERO"::text AS fone,
                   MIN({_DATA_EXPR}) AS dia, MAX("LEAD ÚNICO") AS ativo
            FROM "{tabela}"
            GROUP BY 1, 2
        ) g {where}
        GROUP BY 1 ORDER BY 2 DESC
    '''), params).fetchall()

    entradas = int(tot[0] or 0)
    ativos = int(tot[1] or 0)
    saidas = int(tot[2] or 0)
    total_limpo = int(tot_geral[1] or 0)
    saida_total = int(tot_geral[2] or 0)
    return {
        "entradas": entradas,
        "ativos": ativos,
        "saidas": saidas,
        "total": int(tot_geral[0] or 0),
        "total_limpo": total_limpo,
        "saida_total": saida_total,
        "churn_pct": (saidas / entradas * 100) if entradas else 0.0,
        "grupos": int(n_grupos_total or 0),
        "media_por_grupo": (ativos / int(n_grupos_total)) if n_grupos_total else 0.0,
        "multi_grupo": multi_grupo,
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


def _snapshot(conn, tabela: str | None) -> dict | None:
    """Números finais (TOTAL LEADS/TOTAL LIMPO) já calculados pelo poller
    que alimenta o Sheets, gravados em whatsapp_snapshot — usados pra bater
    exatamente com a planilha, em vez de recalcular da tabela de leads
    acumulada (que cresce ao longo do tempo por causa do LID do WhatsApp).
    Retorna None se a tabela de snapshot ainda não existe ou não tem linha
    pra esse lançamento (lançamentos sem poller ativo, ou antigos)."""
    if not tabela:
        return None
    try:
        if not _tabela_existe(conn, "whatsapp_snapshot"):
            return None
        r = conn.execute(
            text('SELECT total_leads, total_limpo FROM "whatsapp_snapshot" WHERE tabela = :t'),
            {"t": tabela},
        ).fetchone()
        return {"total": int(r[0]), "total_limpo": int(r[1])} if r else None
    except Exception:
        logger.exception("_snapshot: falha ao ler whatsapp_snapshot para %s", tabela)
        return None


def _read_whatsapp_uncached(code: str, start_date=None, end_date=None) -> dict | None:
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    base = code.replace("-", "_")
    # Padrões por geração da automação: novos "_API", antigos sem sufixo/_VIPS;
    # o "_VIP" solto cobre exceções tipo PES_SET_VIP (base sem o ano).
    candidatos_normal = [f"{base}_API", base]
    candidatos_vip = [f"{base}_VIP_API", f"{base}_VIPS", f"{base}_VIP",
                      base.rsplit("_", 1)[0] + "_VIP"]

    cfg = read_launch_config(code)
    start = _safe_date(start_date) or _safe_date(cfg.get("pre_quali_start_date"))
    end = _safe_date(end_date) or _safe_date(cfg.get("carrinho_end_date"))

    engine = _get_engine()
    with engine.connect() as conn:
        t_normal = _escolhe_tabela(conn, candidatos_normal)
        t_vip = _escolhe_tabela(conn, candidatos_vip)
        tem_normal = t_normal is not None
        tem_vip = t_vip is not None
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

        # "LEAD NÚMERO" não existe em algumas tabelas da geração _API — detecta
        normal = _resumo_tabela(
            conn, t_normal, start, end,
            tem_lead_numero=_tem_coluna(conn, t_normal, "LEAD NÚMERO"),
        ) if tem_normal else None
        vip = _resumo_tabela(
            conn, t_vip, start, end,
            tem_lead_numero=_tem_coluna(conn, t_vip, "LEAD NÚMERO"),
        ) if tem_vip else None

        snap_normal = _snapshot(conn, t_normal)
        if normal and snap_normal:
            normal.update(snap_normal)
        snap_vip = _snapshot(conn, t_vip)
        if vip and snap_vip:
            vip.update(snap_vip)

        overlap = 0
        if tem_normal and tem_vip:
            overlap = conn.execute(text(f'''
                SELECT COUNT(DISTINCT a."NÚMERO")
                FROM "{t_normal}" a
                JOIN "{t_vip}" b ON a."NÚMERO"::text = b."NÚMERO"::text
            ''')).fetchone()[0]

        try:
            compradores = _compradores_grupos(conn, t_normal, t_vip, code)
        except Exception:
            logger.exception("compradores_grupos: falha para %s", code)
            compradores = None

    return {
        "start": str(start),
        "end": str(end),
        "normal": normal,
        "vip": vip,
        "overlap_vip": int(overlap or 0),
        "compradores": compradores,
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
