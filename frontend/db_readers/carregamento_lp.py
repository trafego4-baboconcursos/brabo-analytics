"""
frontend/db_readers/carregamento_lp.py — Carregamento da página no Meta: cliques no link que viraram
página aberta (landing_page_view), por LP e por campanha.

Junta `meta_ads_daily` (landing_page_views, link_clicks) com `ad_landing_pages` (ad_id → URL do
criativo, gravada pelo etl_meta_ads). Duas ressalvas que a página mostra junto:
- a métrica só existe desde LPV_DESDE (antes disso a coluna ficou 0 — não é "0% carregou");
- as LPs atuais adiam o pixel até a 1ª interação, então LPV/clique subconta quem abre e sai sem
  tocar. Não é medida pura de velocidade (MUDANCAS_BV-26 item 264).
"""
from __future__ import annotations

from sqlalchemy import text

from frontend.db import _get_engine
from frontend.utils import _extract_launch_code
from logger import get_logger

logger = get_logger("db")

# Primeiro dia com landing_page_views gravado (backfill de 10/10/26).
LPV_DESDE = "2026-09-23"
# Linha com menos cliques que isso não entra na tabela por campanha: taxa de 3 cliques é ruído.
MIN_CLIQUES_CAMPANHA = 50


def _linha(r) -> dict:
    cliques, lpv, leads, gasto = int(r.cliques or 0), int(r.lpv or 0), int(r.leads or 0), float(r.gasto or 0)
    return {
        "cliques": cliques, "lpv": lpv, "leads": leads, "gasto": gasto,
        "taxa": lpv / cliques * 100 if cliques else 0.0,
        "lead_por_lpv": leads / lpv * 100 if lpv else 0.0,
        "cpl": gasto / leads if leads else 0.0,
    }


def read_carregamento_lp(launch_folder_or_code, start_date=None, end_date=None) -> dict | None:
    """{'desde', 'total', 'por_lp': [...], 'por_campanha': [...]} ou None sem clique no período."""
    code = _extract_launch_code(launch_folder_or_code)
    inicio = max(str(start_date), LPV_DESDE) if start_date else LPV_DESDE
    params = {"code": code, "ini": inicio, "fim": str(end_date) if end_date else "2999-12-31"}
    base = """
        FROM meta_ads_daily d
        LEFT JOIN ad_landing_pages lp ON lp.platform = 'meta' AND lp.ad_id = d.ad_id
        WHERE d.lancamento_codigo = :code AND d.date BETWEEN :ini AND :fim
    """
    soma = ("SUM(d.link_clicks) AS cliques, SUM(d.landing_page_views) AS lpv, "
            "SUM(d.leads) AS leads, SUM(d.spend) AS gasto")
    try:
        with _get_engine().connect() as conn:
            total = conn.execute(text(f"SELECT {soma} {base}"), params).one()
            if not total.cliques:
                return None
            por_lp = conn.execute(text(f"""
                SELECT COALESCE(lp.url, '(sem link lido)') AS url, COUNT(DISTINCT d.ad_id) AS anuncios, {soma}
                {base} GROUP BY 1 HAVING SUM(d.link_clicks) > 0 ORDER BY cliques DESC"""), params).all()
            por_campanha = conn.execute(text(f"""
                SELECT d.campaign_name AS campanha, MIN(lp.url) AS url, COUNT(DISTINCT lp.url) AS n_urls, {soma}
                {base} GROUP BY 1 HAVING SUM(d.link_clicks) >= :minimo ORDER BY cliques DESC"""),
                params | {"minimo": MIN_CLIQUES_CAMPANHA}).all()
    except Exception:
        logger.exception("carregamento_lp: falha ao ler %s", code)
        return None
    return {
        "desde": inicio,
        "total": _linha(total),
        "por_lp": [{"url": r.url, "anuncios": int(r.anuncios)} | _linha(r) for r in por_lp],
        "por_campanha": [{"campanha": r.campanha,
                          "url": r.url if r.n_urls == 1 else (f"{r.n_urls} LPs" if r.n_urls else None)}
                         | _linha(r) for r in por_campanha],
    }
