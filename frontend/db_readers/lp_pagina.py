"""
frontend/db_readers/lp_pagina.py — Página /landing-pages: tudo de cada LP do lançamento num lugar só.

Fontes (uma linha por URL, normalizada sem query e com barra no fim):
- lista oficial      → lp_oficiais (banco operacional; editável na própria página)
- saúde e velocidade → lp_auditoria (gravada por `python -m scripts.ads.auditar_lps <LANC>`)
- Meta               → meta_ads_daily (link_clicks, landing_page_views, leads, spend) × ad_landing_pages
- Google             → google_ads_daily (clicks, cost, conversions) × ad_landing_pages (gravado pela auditoria)
- GA4                → ga4_daily por caminho da LP: sessões, engajadas, eventos-chave e duração. Eventos-chave
                       não é taxa de conversão: um cadastro dispara mais de um (lead + lead qualificado).
                       A página de obrigado não serve de contagem: no ga4_daily ela só aparece quando a
                       sessão começa nela.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from sqlalchemy import text

from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers.carregamento_lp import LPV_DESDE, read_carregamento_lp
from frontend.utils import _extract_launch_code
from logger import get_logger

logger = get_logger("db")


def _caminho(url: str | None) -> str:
    """'https://lp.x.com.br/black-vitalicia-26-v1a/' → '/black-vitalicia-26-v1a' (formato do GA4)."""
    if not url:
        return ""
    p = urlsplit(url).path.rstrip("/").lower()
    return p or "/"


def _json(v):
    return v if isinstance(v, (dict, list)) else json.loads(v or "null")


def read_oficiais(code: str) -> list[dict]:
    try:
        with _get_users_engine().connect() as c:
            return [dict(r._mapping) for r in c.execute(text("""
                SELECT url, tag_esperada, funcao, observacao, atualizado_por, updated_at
                FROM lp_oficiais WHERE lancamento_codigo = :c ORDER BY funcao NULLS LAST, url"""), {"c": code})]
    except Exception:
        logger.exception("landing_pages: falha ao ler lp_oficiais de %s", code)
        return []


def _auditoria(conn, code: str) -> dict[str, dict]:
    out = {}
    for r in conn.execute(text("SELECT url, auditado_em, ok, alertas, dados FROM lp_auditoria "
                               "WHERE lancamento_codigo = :c"), {"c": code}):
        out[r.url] = {"auditado_em": r.auditado_em, "ok": r.ok, "alertas": _json(r.alertas) or [],
                      "dados": _json(r.dados) or {}}
    return out


def _google(conn, code: str) -> dict[str, dict]:
    out = {}
    for r in conn.execute(text("""
            SELECT lp.url, COUNT(DISTINCT g.ad_id) AS anuncios, SUM(g.clicks) AS cliques,
                   SUM(g.cost) AS gasto, SUM(g.conversions) AS conversoes
            FROM google_ads_daily g
            JOIN ad_landing_pages lp ON lp.platform = 'google' AND lp.ad_id = g.ad_id::text
            WHERE g.lancamento_codigo = :c GROUP BY lp.url"""), {"c": code}):
        gasto, conv = float(r.gasto or 0), float(r.conversoes or 0)
        out[r.url] = {"anuncios": int(r.anuncios), "cliques": int(r.cliques or 0), "gasto": gasto,
                      "conversoes": conv, "cpl": gasto / conv if conv else 0.0}
    return out


def _ga4(conn, caminhos: set[str]) -> dict[str, dict]:
    if not caminhos:
        return {}
    out = {}
    for r in conn.execute(text("""
            SELECT LOWER(RTRIM(landing_page, '/')) AS caminho, SUM(sessions) AS sessoes,
                   SUM(engaged_sessions) AS engajadas, SUM(key_events) AS eventos,
                   SUM(avg_session_duration * sessions) AS duracao_x_sessoes
            FROM ga4_daily
            WHERE LOWER(RTRIM(landing_page, '/')) = ANY(:caminhos) AND date >= :desde
            GROUP BY 1"""), {"caminhos": sorted(caminhos), "desde": LPV_DESDE}):
        s = int(r.sessoes or 0)
        out[r.caminho] = {"sessoes": s, "engajadas": int(r.engajadas or 0), "eventos": float(r.eventos or 0),
                          "taxa_engajamento": (r.engajadas or 0) / s * 100 if s else 0.0,
                          "eventos_por_sessao": float(r.eventos or 0) / s if s else 0.0,
                          "duracao_media_s": float(r.duracao_x_sessoes or 0) / s if s else 0.0}
    return out


def read_landing_pages(launch_folder_or_code) -> dict:
    code = _extract_launch_code(launch_folder_or_code)
    oficiais = read_oficiais(code)
    carregamento = read_carregamento_lp(code) or {}
    meta = {r["url"]: r for r in carregamento.get("por_lp", [])}
    try:
        with _get_engine().connect() as conn:
            auditoria = _auditoria(conn, code)
            google = _google(conn, code)
            urls = {o["url"] for o in oficiais} | set(auditoria) | set(meta) | set(google)
            urls.discard("(sem link lido)")
            ga4 = _ga4(conn, {_caminho(u) for u in urls})
    except Exception:
        logger.exception("landing_pages: falha ao ler %s", code)
        return {"code": code, "lps": [], "oficiais": oficiais, "por_campanha": [], "erro": True}

    por_oficial = {o["url"]: o for o in oficiais}
    lps = []
    for u in urls:
        aud = auditoria.get(u)
        d = (aud or {}).get("dados", {})
        g4 = ga4.get(_caminho(u))
        forms = d.get("forms") or []
        lps.append({
            "url": u, "rotulo": urlsplit(u).path.strip("/") or u,
            "oficial": por_oficial.get(u), "auditoria": aud, "dados": d, "forms": forms,
            "meta": meta.get(u), "google": google.get(u), "ga4": g4,
            "envios_ac": sum(int(f.get("envios") or 0) for f in forms) if forms else None,
            "cliques_total": ((meta.get(u) or {}).get("cliques", 0) + (google.get(u) or {}).get("cliques", 0)),
        })
    # Com tráfego primeiro; depois as oficiais ainda sem anúncio; por último o resto.
    lps.sort(key=lambda x: (-x["cliques_total"], x["oficial"] is None, x["url"]))
    auditadas = [x["auditoria"] for x in lps if x["auditoria"]]
    return {
        "code": code, "lps": lps, "oficiais": oficiais, "desde": LPV_DESDE,
        "por_campanha": carregamento.get("por_campanha", []), "total_meta": carregamento.get("total"),
        "n_alerta": sum(1 for a in auditadas if not a["ok"]),
        "auditado_em": min((a["auditado_em"] for a in auditadas), default=None),
        "sem_auditoria": [x["url"] for x in lps if not x["auditoria"]],
    }


# ── edição da lista oficial ────────────────────────────────────────────────────

def salvar_oficial(code: str, url: str, tag: str | None, funcao: str | None, observacao: str | None,
                   usuario: str) -> str:
    """Upsert de uma LP na lista oficial. Devolve a URL normalizada gravada."""
    from src.landing_pages import normalizar_url
    u = normalizar_url(url)
    if not u.startswith("https://") or "." not in urlsplit(u).netloc:
        raise ValueError("URL inválida — use o endereço completo, com https://")
    with _get_users_engine().begin() as c:
        c.execute(text("""
            INSERT INTO lp_oficiais (lancamento_codigo, url, tag_esperada, funcao, observacao, atualizado_por, updated_at)
            VALUES (:c, :u, :t, :f, :o, :p, NOW())
            ON CONFLICT (lancamento_codigo, url) DO UPDATE
               SET tag_esperada = EXCLUDED.tag_esperada, funcao = EXCLUDED.funcao,
                   observacao = EXCLUDED.observacao, atualizado_por = EXCLUDED.atualizado_por, updated_at = NOW()
        """), {"c": code, "u": u, "t": (tag or "").strip() or None, "f": (funcao or "").strip() or None,
               "o": (observacao or "").strip() or None, "p": usuario})
    return u


def remover_oficial(code: str, url: str) -> bool:
    with _get_users_engine().begin() as c:
        r = c.execute(text("DELETE FROM lp_oficiais WHERE lancamento_codigo = :c AND url = :u"), {"c": code, "u": url})
    return r.rowcount > 0
