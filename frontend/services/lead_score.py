"""
frontend/services/lead_score.py — Qualidade dos leads pelo score da pesquisa (bloco do debriefing).

O modelo (regressão logística treinada em lançamentos fechados) vem pronto de `config/lead_score_modelo.json`,
gerado por `scripts/lead_score_treino.py --exportar`. Aqui só se aplica: quem respondeu a pesquisa recebe uma
probabilidade de compra pelas respostas; quem não respondeu é a faixa C. Faixas:
  A — respondeu e a probabilidade fica na metade de cima dos respondentes DO LANÇAMENTO;
  B — respondeu, metade de baixo;
  C — não respondeu a pesquisa.
Só lê. Cobre lançamentos cuja pesquisa está no sistema novo (perguntas com título); o Typeform antigo (ids de
campo) devolve None e o bloco some.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine
from logger import get_logger

logger = get_logger("lead_score")

_MODELO_JSON = Path(__file__).resolve().parent.parent.parent / "config" / "lead_score_modelo.json"
_modelo: dict | None = None

# Mesmos padrões de `scripts/lead_score_dataset.py` (texto da pergunta normalizado, sem acento).
_PADROES = {
    "idade": r"\bidade\b",
    "genero": r"\bgenero\b",
    "estado": r"qual estado|de qual estado",
    "filhos": r"quantos filhos",
    "mora": r"com quem voce mora",
    "escolaridade": r"escolaridade",
    "situacao": r"situacao profissional",
    "nivel": r"voce se considera",
}


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def _limpa(v: Any) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().lower()[:60]


def _carregar_modelo() -> dict | None:
    global _modelo
    if _modelo is None:
        try:
            _modelo = json.loads(_MODELO_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("lead_score: modelo ausente em %s", _MODELO_JSON)
            return None
    return _modelo


def _probabilidades(m: dict, resp: pd.DataFrame) -> list[float]:
    """Mesma codificação do treino: `respondeu`=1 + uma coluna por (pergunta, resposta conhecida)."""
    nomes_cols: list[tuple[str, str]] = [(q, v) for q in m["perguntas"] for v in m["vocab"][q]]
    coef = m["coef"]
    peso = {nc: coef[i + 1] for i, nc in enumerate(nomes_cols)}
    base = m["intercepto"] + coef[0]
    out = []
    for _, r in resp.iterrows():
        z = base
        for q in m["perguntas"]:
            z += peso.get((q, r[q]), 0.0)
        out.append(1.0 / (1.0 + math.exp(-z)))
    return out


_AD_SQL = (
    "COALESCE(substring(UPPER(COALESCE(utm_term, '')) FROM '^(AD[0-9]+)'), "
    "substring(UPPER(COALESCE(utm_content, '')) FROM '^(AD[0-9]+)'))"
)
_MIN_LEADS_ANUNCIO = 200
_TOP_ANUNCIOS = 15


def gasto_por_anuncio(meta: Any, google: Any) -> dict[str, dict]:
    """{ADxxx: {nome, gasto}} somando Meta + Google (mesmas listas do perfil por anúncio do debriefing)."""
    info: dict[str, dict] = {}
    for a in [
        *(getattr(meta, "preq_por_ad", None) or []), *(getattr(meta, "captacao_por_ad", None) or []),
        *(getattr(google, "preq_por_ad", None) or []), *(getattr(google, "anuncios_por_ad", None) or []),
    ]:
        cod = str(a.get("ad_code") or "").upper()
        if cod:
            d = info.setdefault(cod, {"nome": a.get("nome") or cod, "gasto": 0.0})
            d["gasto"] += float(a.get("gasto") or 0)
    return info


def calcular(code: str, emails_compradores: set[str], anuncios: dict[str, dict] | None = None) -> dict | None:
    """{faixas:[{faixa,leads,pct_leads,compradores,taxa,pct_compradores}], total_leads, respondentes, ...} ou None."""
    from frontend.db_readers.typeform import _novo_sistema_respostas_cached  # noqa: PLC0415

    m = _carregar_modelo()
    if not m:
        return None
    tf = _novo_sistema_respostas_cached(code)
    if tf is None or tf.empty:
        return None
    cols = {}
    for q, pad in _PADROES.items():
        col = next((c for c in tf.columns if c != "email_norm" and re.search(pad, _norm(c))), None)
        if col:
            cols[q] = col
    if len(cols) < 4:                       # pesquisa sem as perguntas-padrão: não dá para pontuar
        return None
    tf = tf.drop_duplicates("email_norm", keep="last")
    resp = pd.DataFrame({"email": tf["email_norm"].values})
    for q in m["perguntas"]:
        resp[q] = tf[cols[q]].map(_limpa).values if q in cols else ""

    emails = [e for e in resp["email"].tolist() if e]
    compradores = sorted(emails_compradores or [])
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        no_lead = {r[0] for r in conn.execute(
            text("SELECT DISTINCT email FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email = ANY(:e)"),
            {"c": code, "e": emails})}
        total_leads = int(conn.execute(
            text("SELECT COUNT(DISTINCT email) FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email <> ''"),
            {"c": code}).scalar() or 0)
        compradores_nos_leads = {r[0] for r in conn.execute(
            text("SELECT DISTINCT email FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email = ANY(:e)"),
            {"c": code, "e": compradores})} if compradores else set()
    resp = resp[resp["email"].isin(no_lead)].reset_index(drop=True)
    if resp.empty or total_leads <= 0:
        return None

    resp["p"] = _probabilidades(m, resp)
    # Corte relativo ao lançamento: o modelo não separa por produto (a taxa de compra do PES é o dobro da do PI),
    # então um limiar fixo põe quase todos os respondentes de um produto na mesma faixa.
    limiar = float(resp["p"].median())
    resp["faixa"] = ["A" if p > limiar else "B" for p in resp["p"]]
    resp["comprou"] = resp["email"].isin(compradores_nos_leads)

    # Anúncio de origem (ADxxx do utm_term/utm_content) do lead: total por anúncio, dos respondentes e dos compradores.
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        leads_por_ad = {r[0]: int(r[1]) for r in conn.execute(text(
            "SELECT " + _AD_SQL + " AS ad, COUNT(DISTINCT email) FROM lead_utm_lancamento "
            "WHERE lancamento_codigo = :c AND " + _AD_SQL + " IS NOT NULL GROUP BY 1"), {"c": code})}
        ad_de: dict[str, str] = {}
        for lote in (resp["email"].tolist(), sorted(compradores_nos_leads)):
            if not lote:
                continue
            for e, ad in conn.execute(text(
                    "SELECT email, " + _AD_SQL + " FROM lead_utm_lancamento "
                    "WHERE lancamento_codigo = :c AND email = ANY(:e) AND " + _AD_SQL + " IS NOT NULL"),
                    {"c": code, "e": lote}):
                ad_de.setdefault(e, ad)
    resp["ad"] = resp["email"].map(ad_de)
    por_ad: dict[str, dict] = {
        ad: {"ad": ad, "leads": n, "resp": 0, "a": 0, "b": 0, "compradores": 0} for ad, n in leads_por_ad.items()}
    for ad, faixa in zip(resp["ad"], resp["faixa"]):
        if ad in por_ad:
            por_ad[ad]["resp"] += 1
            por_ad[ad]["a" if faixa == "A" else "b"] += 1
    for e in compradores_nos_leads:
        ad = ad_de.get(e)
        if ad in por_ad:
            por_ad[ad]["compradores"] += 1
    anuncios = anuncios or {}
    linhas_ad = []
    for ad, d in por_ad.items():
        if d["leads"] < _MIN_LEADS_ANUNCIO:
            continue
        gasto = float((anuncios.get(ad) or {}).get("gasto") or 0)
        d.update({
            "nome": (anuncios.get(ad) or {}).get("nome") or ad, "gasto": gasto,
            "pct_resp": d["resp"] / d["leads"] * 100,
            "pct_a_resp": d["a"] / d["resp"] * 100 if d["resp"] else 0.0,
            "cpl": gasto / d["leads"] if gasto else 0.0,
            "custo_a": gasto / d["a"] if gasto and d["a"] else 0.0,
            "cpa": gasto / d["compradores"] if gasto and d["compradores"] else 0.0,
        })
        linhas_ad.append(d)
    linhas_ad.sort(key=lambda d: d["gasto"], reverse=True)

    n_resp = len(resp)
    compr_total = len(compradores_nos_leads)
    linhas = []
    for faixa in ("A", "B"):
        sub = resp[resp["faixa"] == faixa]
        linhas.append({"faixa": faixa, "leads": len(sub), "compradores": int(sub["comprou"].sum())})
    linhas.append({"faixa": "C", "leads": total_leads - n_resp,
                   "compradores": compr_total - int(resp["comprou"].sum())})
    for l in linhas:
        l["pct_leads"] = l["leads"] / total_leads * 100 if total_leads else 0.0
        l["taxa"] = l["compradores"] / l["leads"] * 100 if l["leads"] else 0.0
        l["pct_compradores"] = l["compradores"] / compr_total * 100 if compr_total else 0.0
    return {
        "faixas": linhas, "total_leads": total_leads, "respondentes": n_resp,
        "pct_respondentes": n_resp / total_leads * 100, "compradores": compr_total,
        "taxa_geral": compr_total / total_leads * 100 if total_leads else 0.0,
        "anuncios": linhas_ad[:_TOP_ANUNCIOS],
        "auc_resp": m.get("auc_medio_entre_respondentes"), "lancamentos_treino": len(m.get("lancamentos") or []),
    }


def obter(code: str, emails_compradores: set[str], anuncios: dict[str, dict] | None = None) -> dict | None:
    """`calcular` com cache de 30 min por lançamento (leva ~15 s: Typeform novo + consultas na base de leads)."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "lead_score", lambda: calcular(code, emails_compradores, anuncios), ttl=1800)
