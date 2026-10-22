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


def _load_distribuicao_extra() -> list[dict]:
    """Experts com distribuicao paga mas sem Instagram proprio (postam pelo
    perfil de outro) — ver config/instagram_accounts.yaml."""
    try:
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[2] / "config" / "instagram_accounts.yaml"
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return [dict(e, sem_instagram=True) for e in cfg.get("distribuicao_extra", [])]
    except Exception:
        logger.exception("_load_distribuicao_extra: falha ao ler config")
        return []


def _find_expert(username: str) -> dict | None:
    for account in list(_load_experts()) + _load_distribuicao_extra():
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
        "profile_url": (None if account.get("sem_instagram")
                        else f"https://instagram.com/{username}"),
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


def _sparkline(valores: list[float], largura: int = 120, altura: int = 34) -> str:
    """Pontos de um <polyline> SVG (já normalizados) para uma linha de evolução."""
    if len(valores) < 2:
        return ""
    lo, hi = min(valores), max(valores)
    faixa = (hi - lo) or 1.0
    passo = largura / (len(valores) - 1)
    return " ".join(f"{i * passo:.1f},{altura - 3 - (v - lo) / faixa * (altura - 6):.1f}" for i, v in enumerate(valores))


def read_distribuicao_cards(ano: int) -> list[dict]:
    """Resumo de cada perfil da distribuição para /lancamentos: gasto (ano e 30 dias), seguidores,
    novos seguidores e custo por novo seguidor. Ivan Neto não tem Instagram próprio (posta pelo
    @braboconcursos): entra só com o gasto."""
    hoje = date.today()
    ini30 = hoje - timedelta(days=29)
    gasto: dict[str, dict] = {}
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT lancamento_codigo, SUM(v), SUM(v) FILTER (WHERE d >= :ini30), SUM(imp) FILTER (WHERE d >= :ini30)
                FROM (SELECT lancamento_codigo, date AS d, spend AS v, impressions AS imp FROM meta_ads_daily
                      WHERE lancamento_codigo ILIKE 'DISTRIBUICAO%' AND date BETWEEN :ini AND :fim
                      UNION ALL
                      SELECT lancamento_codigo, date, cost, impressions FROM google_ads_daily
                      WHERE lancamento_codigo ILIKE 'DISTRIBUICAO%' AND date BETWEEN :ini AND :fim) t
                GROUP BY 1
            """), {"ini": date(ano, 1, 1), "fim": date(ano, 12, 31), "ini30": ini30}).fetchall()
        gasto = {str(c): {"ano": float(a or 0), "d30": float(b or 0), "imp30": float(i or 0)} for c, a, b, i in rows}
    except Exception:
        logger.exception("read_distribuicao_cards: falha ao somar o gasto")

    cartoes = []
    for conta in list(_load_experts()) + _load_distribuicao_extra():
        codigo = _codigo_from_name(conta["name"])
        g = gasto.get(codigo, {"ano": 0.0, "d30": 0.0, "imp30": 0.0})
        cartao = {
            "nome": conta["name"], "username": conta["username"], "codigo": codigo,
            "sem_instagram": bool(conta.get("sem_instagram")),
            "invest": g["ano"], "invest_30d": g["d30"], "impressoes_30d": g["imp30"],
            "seguidores": None, "delta_30d": None, "novos_30d": None, "custo_por_seguidor": None, "spark": "",
        }
        ig_id = conta.get("ig_id")
        if ig_id:
            try:
                with _get_engine().connect() as conn:
                    perfil = conn.execute(text(
                        "SELECT date, followers_count FROM instagram_profile_daily "
                        "WHERE ig_id = :i AND date >= :d ORDER BY date"), {"i": ig_id, "d": hoje - timedelta(days=89)}).fetchall()
                    novos = conn.execute(text(
                        "SELECT COALESCE(SUM(new_followers), 0) FROM instagram_follower_growth_daily "
                        "WHERE ig_id = :i AND date >= :d"), {"i": ig_id, "d": ini30}).scalar()
                if perfil:
                    serie = [float(r[1] or 0) for r in perfil]
                    cartao["seguidores"] = int(serie[-1])
                    antes = [float(r[1] or 0) for r in perfil if r[0] <= ini30]
                    cartao["delta_30d"] = int(serie[-1] - (antes[-1] if antes else serie[0]))
                    cartao["spark"] = _sparkline(serie[-60:])
                cartao["novos_30d"] = int(novos or 0)
                if cartao["novos_30d"] > 0 and g["d30"] > 0:
                    cartao["custo_por_seguidor"] = g["d30"] / cartao["novos_30d"]
            except Exception:
                logger.exception("read_distribuicao_cards: falha ao ler os seguidores de %s", conta["name"])
        cartoes.append(cartao)
    cartoes.sort(key=lambda c: c["invest"], reverse=True)
    return cartoes
