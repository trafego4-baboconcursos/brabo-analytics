"""
frontend/db_readers/distribuicao.py — Distribuição de Conteúdo (mídia paga).

Mídia paga que impulsiona o conteúdo ORGÂNICO do Instagram/YouTube de um
expert (na maioria das vezes) — não é sobre produto, é sobre o perfil, o
mesmo já cadastrado em config/instagram_accounts.yaml e lido organicamente
em /instagram/{username}. Aqui é o lado pago do mesmo perfil: quanto se
gastou promovendo os posts/vídeos, quantas views, quantos "viu 50%".

Campanhas identificadas pela tag [distribuição] + nome do expert (ver
etl/launch_resolver.py), classificadas num pseudo-lançamento
(ex: DISTRIBUICAO-FELIPE-GRATON). De propósito NÃO tem linha em
dim_lancamentos — não é lançamento de verdade.

Mesmo padrão de seletor de período (7/30/90 dias + comparação) de
instagram_detail.py/perpetuo.py.
"""
from __future__ import annotations

import unicodedata
from datetime import date, timedelta

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.services.attribution import _extract_ad_code
from frontend.services.instagram import _load_experts

logger = get_logger("db")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _codigo_from_name(name: str) -> str:
    slug = _strip_accents(name).upper().replace(" ", "-")
    return f"DISTRIBUICAO-{slug}"


def _find_expert(username: str) -> dict | None:
    for account in _load_experts():
        if account.get("username") == username:
            return account
    return None


def _pct_delta(curr: float, prev: float) -> float | None:
    if not prev:
        return None
    return round((curr - prev) / prev * 100, 1)


def _meta_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT date, ad_name, spend, impressions, clicks, "
            "video_views_3s, video_views_25, video_views_50, video_views_75, video_views_100, video_thruplays "
            "FROM meta_ads_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _google_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT date, ad_name, cost, impressions, clicks, avg_cpv, "
            "video_views, video_views_25, video_views_50, video_views_75, video_views_100 "
            "FROM google_ads_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _meta_totals(rows) -> dict:
    return {
        "spend": sum(float(r.spend or 0) for r in rows),
        "impressions": sum(r.impressions or 0 for r in rows),
        "thruplays": sum(r.video_thruplays or 0 for r in rows),
        "views_50": sum(r.video_views_50 or 0 for r in rows),
        "views_100": sum(r.video_views_100 or 0 for r in rows),
    }


def _google_totals(rows) -> dict:
    return {
        "cost": sum(float(r.cost or 0) for r in rows),
        "impressions": sum(r.impressions or 0 for r in rows),
        "views": sum(r.video_views or 0 for r in rows),
        "views_50": sum(r.video_views_50 or 0 for r in rows),
        "views_100": sum(r.video_views_100 or 0 for r in rows),
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


def read_distribuicao(username: str, days: int = 30, compare: bool = False) -> dict | None:
    account = _find_expert(username)
    if not account:
        return None
    codigo = _codigo_from_name(account["name"])

    end = date.today()
    start = end - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    try:
        with _get_engine().connect() as conn:
            meta_rows = _meta_rows(conn, codigo, start, end)
            google_rows = _google_rows(conn, codigo, start, end)
            prev_meta_rows = _meta_rows(conn, codigo, prev_start, prev_end) if compare else []
            prev_google_rows = _google_rows(conn, codigo, prev_start, prev_end) if compare else []
    except Exception:
        logger.exception("read_distribuicao: falha para %s", username)
        return None

    meta_totals = _meta_totals(meta_rows)
    google_totals = _google_totals(google_rows)
    investimento_total = meta_totals["spend"] + google_totals["cost"]
    views_50_total = meta_totals["views_50"] + google_totals["views_50"]

    result = {
        "username": username,
        "name": account.get("name"),
        "profile_url": f"https://instagram.com/{username}",
        "no_data": not meta_rows and not google_rows,
        "days": days,
        "compare": compare,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "investimento_meta": meta_totals["spend"],
        "investimento_google": google_totals["cost"],
        "investimento_total": investimento_total,
        "thruplays_meta": meta_totals["thruplays"],
        "views_google": google_totals["views"],
        "views_50_total": views_50_total,
        "views_100_total": meta_totals["views_100"] + google_totals["views_100"],
        "criativos_meta": _meta_criativos(meta_rows),
        "criativos_google": _google_criativos(google_rows),
    }

    if compare:
        prev_meta_totals = _meta_totals(prev_meta_rows)
        prev_google_totals = _google_totals(prev_google_rows)
        prev_investimento_total = prev_meta_totals["spend"] + prev_google_totals["cost"]
        prev_views_50_total = prev_meta_totals["views_50"] + prev_google_totals["views_50"]
        result["prev_range_start"] = prev_start.isoformat()
        result["prev_range_end"] = prev_end.isoformat()
        result["deltas"] = {
            "investimento_total": _pct_delta(investimento_total, prev_investimento_total),
            "views_50_total": _pct_delta(views_50_total, prev_views_50_total),
        }

    return result
