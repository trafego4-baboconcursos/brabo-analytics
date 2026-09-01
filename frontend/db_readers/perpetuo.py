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
from frontend.db import _get_engine
from frontend.services.attribution import _extract_ad_code

logger = get_logger("db")

VERTICALS: dict[str, dict] = {
    "pmq-tjsp": {"codigo": "PERPETUO-PMQ-TJSP", "nome": "Mestre em Questões — TJ-SP"},
    "pmq-inss": {"codigo": "PERPETUO-PMQ-INSS", "nome": "Mestre em Questões — INSS"},
    "pmq-pbb":  {"codigo": "PERPETUO-PMQ-PBB",  "nome": "Mestre em Questões — Banco do Brasil"},
    "planner":  {"codigo": "PERPETUO-PLANNER",  "nome": "Planner"},
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
        "criativos_meta": _meta_criativos(meta_rows),
        "criativos_google": _google_criativos(google_rows),
        "publico_meta": _meta_publico(meta_rows),
        "publico_google": _google_publico(google_aud_rows),
    }

    if compare:
        prev_meta_totals = _meta_totals(prev_meta_rows)
        prev_google_totals = _google_totals(prev_google_rows)
        prev_investimento_total = prev_meta_totals["spend"] + prev_google_totals["cost"]
        prev_leads_total = prev_meta_totals["leads"] + prev_google_totals["conversions"]
        result["prev_range_start"] = prev_start.isoformat()
        result["prev_range_end"] = prev_end.isoformat()
        result["deltas"] = {
            "investimento_total": _pct_delta(investimento_total, prev_investimento_total),
            "leads_total": _pct_delta(leads_total, prev_leads_total),
        }

    return result
