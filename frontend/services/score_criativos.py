"""
frontend/services/score_criativos.py — Nota 0–100 por criativo (ADxxx) a partir do custo por lead A.

Régua pura (`nota_custo_lead_a`, `notas_por_anuncio`); a leitura dos leads A por anúncio vem do banco. Plano: .superpowers/sdd/PLANO_SCORE_CRIATIVOS.
Lead A = `faixa_pesquisa == "A"` do `lead_score.calcular_leads` (respondeu a pesquisa e ficou na metade de
cima da probabilidade dos respondentes do lançamento). Gasto = o `gasto` do Ranking Geral (só captação).

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


def _ad_por_email(code: str) -> dict[str, str]:
    """ADxxx de cada e-mail do lançamento: o do primeiro UTM visto que traz um código de anúncio."""
    from frontend.services.lead_score import _AD_SQL  # noqa: PLC0415

    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        rows = conn.execute(text(
            "SELECT DISTINCT ON (email) email, " + _AD_SQL + " FROM lead_utm_lancamento "
            "WHERE lancamento_codigo = :c AND email <> '' AND " + _AD_SQL + " IS NOT NULL "
            "ORDER BY email, primeiro_visto_em"), {"c": code}).fetchall()
    return {email: ad for email, ad in rows}


def _leads_a_por_anuncio_sem_cache(code: str) -> dict[str, int] | None:
    """{ADxxx: nº de leads A}. None sem leads/modelo ou quando ninguém respondeu a pesquisa (não há faixa A)."""
    from frontend.services import lead_score  # noqa: PLC0415

    leads = lead_score.obter_leads_do_lancamento(code)
    if leads is None or leads.empty or int(leads["respondeu"].sum()) == 0:
        return None
    return contar_leads_a(leads, _ad_por_email(code))


def leads_a_por_anuncio(code: str) -> dict[str, int] | None:
    """`_leads_a_por_anuncio_sem_cache` com o mesmo cache de 30 min do score por lead."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "score_criativos_leads_a", lambda: _leads_a_por_anuncio_sem_cache(code), ttl=1800)
