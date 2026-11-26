"""
frontend/services/score_criativos.py — Nota 0–100 por criativo (ADxxx) a partir do custo por lead A.

Régua pura (`nota_custo_lead_a`, `notas_por_anuncio`); a leitura dos leads A por anúncio vem do banco. Plano: docs/projetos/PLANO_SCORE_CRIATIVOS.md; arquitetura: docs/sistema/ARQUITETURA.md, seção «Score por criativo».
Lead A = respondeu a pesquisa, está na base de leads do lançamento e ficou acima da mediana da probabilidade
(modelo só da pesquisa) entre esses respondentes — a mesma faixa A de `lead_score.calcular_leads`, mas calculada
só sobre quem respondeu (~20% dos leads), sem montar a base inteira. Gasto = o `gasto` do Ranking Geral (só captação).

Régua: nota = round(50 − 50 · ln(custo_a / mediana) / ln(FATOR²)), limitada a 0–100.
50 na mediana, 25 em 1,5× a mediana, 75 em mediana ÷ 1,5. A mediana vem só dos ADs com
`leads_a >= MIN_LEADS_A` e `gasto > 0`; sem nenhum, não há mediana e nenhum AD recebe nota.
"""
from __future__ import annotations

import math
import statistics

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine

MIN_LEADS_A: int = 30
FATOR: float = 1.5


def nota_custo_lead_a(custo_a: float, mediana: float) -> int:
    """Nota 0–100 do custo por lead A frente à mediana do lançamento (menor custo, maior nota)."""
    nota = 50 - 50 * math.log(custo_a / mediana) / math.log(FATOR ** 2)
    return max(0, min(100, round(nota)))


def notas_por_anuncio(gasto_por_ad: dict[str, float], leads_a_por_ad: dict[str, int]) -> dict:
    """Nota de cada AD do ranking. As chaves de saída são os ADs de `gasto_por_ad`.

    `motivo` (quando não há nota): "sem_gasto", "sem_leads" (AD ausente de `leads_a_por_ad`) ou
    "poucos_leads_a" (menos de MIN_LEADS_A, ou sem mediana). `custo_a` é None sem lead A ou sem gasto.
    """
    custos: dict[str, float | None] = {}
    for ad, gasto in gasto_por_ad.items():
        leads_a = leads_a_por_ad.get(ad, 0)
        custos[ad] = gasto / leads_a if leads_a > 0 and gasto > 0 else None

    base = [custos[ad] for ad, gasto in gasto_por_ad.items()
            if gasto > 0 and leads_a_por_ad.get(ad, 0) >= MIN_LEADS_A]
    mediana = statistics.median(base) if base else None

    anuncios: dict[str, dict] = {}
    for ad, gasto in gasto_por_ad.items():
        leads_a = leads_a_por_ad.get(ad, 0)
        custo_a = custos[ad]
        nota = None
        if gasto <= 0:
            motivo = "sem_gasto"
        elif ad not in leads_a_por_ad or leads_a <= 0:
            motivo = "sem_leads"
        elif leads_a < MIN_LEADS_A or mediana is None:
            motivo = "poucos_leads_a"
        else:
            motivo = None
            nota = nota_custo_lead_a(custo_a, mediana)
        anuncios[ad] = {"nota": nota, "leads_a": leads_a, "custo_a": custo_a, "motivo": motivo}
    return {"mediana": mediana, "anuncios": anuncios}


def contar_leads_a(leads: pd.DataFrame, ad_por_email: dict[str, str]) -> dict[str, int]:
    """Leads A (`faixa_pesquisa == "A"`) por ADxxx do e-mail. E-mail sem AD fica de fora."""
    contagem: dict[str, int] = {}
    for email in leads.loc[leads["faixa_pesquisa"] == "A", "email"]:
        ad = ad_por_email.get(email)
        if ad:
            contagem[ad] = contagem.get(ad, 0) + 1
    return contagem


def _ad_dos_respondentes(code: str, emails: list[str]) -> dict[str, str | None]:
    """Respondentes que estão na base de leads do lançamento → ADxxx do primeiro UTM visto que traz código de
    anúncio (None se nenhum UTM do e-mail traz). E-mail fora da base não aparece."""
    from frontend.services.lead_score import _AD_SQL  # noqa: PLC0415

    if not emails:
        return {}
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        rows = conn.execute(text(
            "SELECT DISTINCT ON (email) email, " + _AD_SQL + " FROM lead_utm_lancamento "
            "WHERE lancamento_codigo = :c AND email = ANY(:e) "
            "ORDER BY email, (" + _AD_SQL + " IS NULL), primeiro_visto_em"), {"c": code, "e": emails}).fetchall()
    return {email: ad for email, ad in rows}


def leads_a_dos_respondentes(resp: pd.DataFrame, na_base: set[str], m: dict) -> set[str]:
    """E-mails na faixa A: entre os respondentes que estão na base, probabilidade acima da mediana deles."""
    from frontend.services import lead_score  # noqa: PLC0415

    df = resp[resp["email"].isin(na_base)].reset_index(drop=True)
    if df.empty:
        return set()
    df = df.assign(respondeu=1)
    p = lead_score._logit_vetorial(m, df)
    corte = float(pd.Series(p).median())
    return set(df.loc[p > corte, "email"])


def _leads_a_por_anuncio_sem_cache(code: str) -> dict[str, int] | None:
    """{ADxxx: nº de leads A}. None sem modelo, sem pesquisa pontuável ou sem respondente na base de leads."""
    from frontend.services import lead_score  # noqa: PLC0415

    m = lead_score._carregar_modelo()
    if not m:
        return None
    resp = lead_score._respostas_df(code, m)
    if resp is None or resp.empty:
        return None
    ad_de = _ad_dos_respondentes(code, [e for e in resp["email"].tolist() if e])
    if not ad_de:
        return None
    emails_a = leads_a_dos_respondentes(resp, set(ad_de), m)
    leads = pd.DataFrame({"email": sorted(emails_a), "faixa_pesquisa": "A"})
    return contar_leads_a(leads, {e: ad for e, ad in ad_de.items() if ad})


def leads_a_por_anuncio(code: str) -> dict[str, int] | None:
    """`_leads_a_por_anuncio_sem_cache` com cache de 30 min (só o dicionário pequeno fica em memória)."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "score_criativos_leads_a", lambda: _leads_a_por_anuncio_sem_cache(code), ttl=1800)
