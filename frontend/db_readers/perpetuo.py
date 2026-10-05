"""
frontend/db_readers/perpetuo.py — Perpétuo (tráfego pago contínuo).

4 verticais: Mestre em Questões (TJ-SP / INSS / Banco do Brasil) + Planner.
Campanhas always-on, sem janela de datas fixa — identificadas pela tag
[perpétuo] no nome (ver etl/launch_resolver.py) e classificadas num
pseudo-lançamento (ex: PERPETUO-PMQ-TJSP). De propósito NÃO tem linha em
dim_lancamentos: não é um lançamento de verdade, não deve aparecer no
seletor de lançamentos — só é usado como chave de agrupamento aqui.

Suporta seletor de período (7/30/90 dias) e comparação com o período
anterior de mesma duração, no mesmo padrão de instagram_detail.py.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine, _get_users_engine
from frontend.services.attribution import _extract_ad_code
from frontend.db_readers._vendas_comum import _hm_data_sql

logger = get_logger("db")

VERTICALS: dict[str, dict] = {
    "pmq-tjsp": {"codigo": "PERPETUO-PMQ-TJSP", "nome": "Mestre em Questões — TJ-SP",
                 "hotmart": ["6857217", "6024397", "6030870"]},
    "pmq-inss": {"codigo": "PERPETUO-PMQ-INSS", "nome": "Mestre em Questões — INSS",
                 "hotmart": ["6859776"]},
    "pmq-pbb":  {"codigo": "PERPETUO-PMQ-PBB",  "nome": "Mestre em Questões — Banco do Brasil",
                 "hotmart": ["6859789"]},
    "planner":  {"codigo": "PERPETUO-PLANNER",  "nome": "Planner",
                 "hotmart": ["5334881", "4924116", "7040689", "5004680"]},
}


def _pct_delta(curr: float, prev: float) -> float | None:
    if not prev:
        return None
    return round((curr - prev) / prev * 100, 1)


def _meta_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT date, ad_name, adset_name, spend, impressions, clicks, leads, "
            "video_views_3s, video_views_25, video_views_50, video_views_75, video_views_100, video_thruplays "
            "FROM meta_ads_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _google_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT date, ad_name, cost, impressions, clicks, conversions, "
            "video_views, video_views_25, video_views_50, video_views_75, video_views_100 "
            "FROM google_ads_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _google_audience_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT audience_name, ad_group_name, impressions, clicks, cost, conversions "
            "FROM google_ads_audiences_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _vendas(produtos: list[str], start: date, end: date) -> dict:
    """Vendas Hotmart dos produtos da vertical no período.

    **Não é venda atribuída ao anúncio** — é toda venda do produto na janela.
    O perpétuo vende direto, sem captura de lead: o comprador não tem UTM desta
    campanha (o que existe em `leads` é o cadastro antigo dele, de um
    lançamento, e creditar aquilo seria pior que não creditar), e o `src` da
    Hotmart chega vazio porque os anúncios não o passam no link de checkout.
    Enquanto o `src` não for configurado, o número aqui é **teto**: inclui
    orgânico, e-mail e régua. A página diz isso na tela.

    Vive no banco OPERACIONAL (`hotmart_clean_oficial`), não no analytics.
    """
    if not produtos:
        return {"vendas": 0, "receita": 0.0}
    data_sql = _hm_data_sql("data_da_transacao")
    valor = "COALESCE(NULLIF(replace(valor_de_compra_com_impostos,',','.'),'')::numeric,0)"
    try:
        with _get_users_engine().connect() as conn:
            r = conn.execute(
                text(
                    f"SELECT COUNT(*) AS vendas, COALESCE(SUM({valor}),0) AS receita "
                    f"FROM hotmart_clean_oficial "
                    f"WHERE codigo_do_produto = ANY(:ids) AND {data_sql} BETWEEN :start AND :end"
                ),
                {"ids": produtos, "start": start, "end": end},
            ).fetchone()
    except Exception:
        logger.exception("read_perpetuo: falha ao ler vendas dos produtos %s", produtos)
        return {"vendas": 0, "receita": 0.0}
    return {"vendas": int(r[0] or 0), "receita": float(r[1] or 0.0)}


def _meta_totals(rows) -> dict:
    return {
        "spend": sum(float(r.spend or 0) for r in rows),
        "impressions": sum(r.impressions or 0 for r in rows),
        "clicks": sum(r.clicks or 0 for r in rows),
        "leads": sum(r.leads or 0 for r in rows),
    }


def _google_totals(rows) -> dict:
    return {
        "cost": sum(float(r.cost or 0) for r in rows),
        "impressions": sum(r.impressions or 0 for r in rows),
        "clicks": sum(r.clicks or 0 for r in rows),
        "conversions": sum(float(r.conversions or 0) for r in rows),
    }


def _meta_criativos(rows) -> list[dict]:
    by_ad: dict[str, dict] = {}
    for r in rows:
        code = _extract_ad_code(r.ad_name) or (r.ad_name or "")
        d = by_ad.setdefault(code, {
            "ad_code": code, "ad_name": r.ad_name, "spend": 0.0, "impressions": 0,
            "views_3s": 0, "thruplays": 0, "views_50": 0, "views_100": 0,
        })
        d["spend"] += float(r.spend or 0)
        d["impressions"] += r.impressions or 0
        d["views_3s"] += r.video_views_3s or 0
        d["thruplays"] += r.video_thruplays or 0
        d["views_50"] += r.video_views_50 or 0
        d["views_100"] += r.video_views_100 or 0
    out = []
    for d in by_ad.values():
        d["hook_rate"] = round(d["views_3s"] / d["impressions"] * 100, 2) if d["impressions"] else 0
        d["hold_rate"] = round(d["thruplays"] / d["views_3s"] * 100, 2) if d["views_3s"] else 0
        d["custo_por_thruplay"] = round(d["spend"] / d["thruplays"], 4) if d["thruplays"] else None
        out.append(d)
    return sorted(out, key=lambda d: -d["spend"])


def _google_criativos(rows) -> list[dict]:
    by_ad: dict[str, dict] = {}
    for r in rows:
        code = _extract_ad_code(r.ad_name) or (r.ad_name or "")
        d = by_ad.setdefault(code, {
            "ad_code": code, "ad_name": r.ad_name, "cost": 0.0, "impressions": 0,
            "views": 0, "views_50": 0, "views_100": 0,
        })
        d["cost"] += float(r.cost or 0)
        d["impressions"] += r.impressions or 0
        d["views"] += r.video_views or 0
        d["views_50"] += r.video_views_50 or 0
        d["views_100"] += r.video_views_100 or 0
    out = []
    for d in by_ad.values():
        d["cpv"] = round(d["cost"] / d["views"], 4) if d["views"] else None
        d["completion_rate"] = round(d["views_100"] / d["views"] * 100, 2) if d["views"] else 0
        out.append(d)
    return sorted(out, key=lambda d: -d["cost"])


def _meta_publico(rows) -> list[dict]:
    """Meta não tem tabela de interesse/público por ad set — agrupa pelo
    nome do ad set, que já carrega a segmentação (mesma leitura manual já
    feita no levantamento da Distribuição Felipe Graton, só automatizada)."""
    by_adset: dict[str, dict] = {}
    for r in rows:
        name = r.adset_name or "(sem ad set)"
        d = by_adset.setdefault(name, {"adset_name": name, "spend": 0.0, "impressions": 0, "leads": 0})
        d["spend"] += float(r.spend or 0)
        d["impressions"] += r.impressions or 0
        d["leads"] += r.leads or 0
    return sorted(by_adset.values(), key=lambda d: -d["spend"])


def _google_publico(rows) -> list[dict]:
    by_audience: dict[str, dict] = {}
    for r in rows:
        name = r.audience_name or "(sem público)"
        d = by_audience.setdefault(name, {"audience_name": name, "spend": 0.0, "impressions": 0, "conversions": 0.0})
        d["spend"] += float(r.cost or 0)
        d["impressions"] += r.impressions or 0
        d["conversions"] += float(r.conversions or 0)
    return sorted(by_audience.values(), key=lambda d: -d["spend"])


def read_perpetuo(vertical: str, days: int = 30, compare: bool = False) -> dict | None:
    info = VERTICALS.get(vertical)
    if not info:
        return None
    codigo = info["codigo"]

    end = date.today()
    start = end - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    try:
        with _get_engine().connect() as conn:
            meta_rows = _meta_rows(conn, codigo, start, end)
            google_rows = _google_rows(conn, codigo, start, end)
            google_aud_rows = _google_audience_rows(conn, codigo, start, end)
            prev_meta_rows = _meta_rows(conn, codigo, prev_start, prev_end) if compare else []
            prev_google_rows = _google_rows(conn, codigo, prev_start, prev_end) if compare else []
    except Exception:
        logger.exception("read_perpetuo: falha para %s", vertical)
        return None

    meta_totals = _meta_totals(meta_rows)
    google_totals = _google_totals(google_rows)
    vendas = _vendas(info.get("hotmart") or [], start, end)
    investimento_total = meta_totals["spend"] + google_totals["cost"]
    leads_total = meta_totals["leads"] + google_totals["conversions"]

    result = {
        "vertical": vertical,
        "nome": info["nome"],
        "no_data": not meta_rows and not google_rows,
        "days": days,
        "compare": compare,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "investimento_meta": meta_totals["spend"],
        "investimento_google": google_totals["cost"],
        "investimento_total": investimento_total,
        "leads_meta": meta_totals["leads"],
        "conversoes_google": google_totals["conversions"],
        "leads_total": leads_total,
        "cpl": round(investimento_total / leads_total, 2) if leads_total else None,
        # Venda do PRODUTO no período, não venda atribuída ao anúncio — ver _vendas().
        "vendas": vendas["vendas"],
        "receita": round(vendas["receita"], 2),
        "cpa": round(investimento_total / vendas["vendas"], 2) if vendas["vendas"] else None,
        "roas": round(vendas["receita"] / investimento_total, 2) if investimento_total else None,
        "vendas_atribuidas": False,
        "criativos_meta": _meta_criativos(meta_rows),
        "criativos_google": _google_criativos(google_rows),
        "publico_meta": _meta_publico(meta_rows),
        "publico_google": _google_publico(google_aud_rows),
    }

    if compare:
        prev_meta_totals = _meta_totals(prev_meta_rows)
        prev_google_totals = _google_totals(prev_google_rows)
        prev_investimento_total = prev_meta_totals["spend"] + prev_google_totals["cost"]
        prev_vendas = _vendas(info.get("hotmart") or [], prev_start, prev_end)
        prev_leads_total = prev_meta_totals["leads"] + prev_google_totals["conversions"]
        result["prev_range_start"] = prev_start.isoformat()
        result["prev_range_end"] = prev_end.isoformat()
        prev_cpa = (prev_investimento_total / prev_vendas["vendas"]) if prev_vendas["vendas"] else 0.0
        result["deltas"] = {
            "investimento_total": _pct_delta(investimento_total, prev_investimento_total),
            "leads_total": _pct_delta(leads_total, prev_leads_total),
            "vendas": _pct_delta(vendas["vendas"], prev_vendas["vendas"]),
            "receita": _pct_delta(vendas["receita"], prev_vendas["receita"]),
            "cpa": _pct_delta(result["cpa"] or 0.0, prev_cpa),
        }

    return result
