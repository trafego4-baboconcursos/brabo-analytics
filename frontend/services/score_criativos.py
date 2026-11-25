"""
frontend/services/score_criativos.py — Nota 0–100 por criativo (ADxxx) a partir do custo por lead A.

Conta pura, sem banco. Plano: .superpowers/sdd/PLANO_SCORE_CRIATIVOS.
Lead A = `faixa_pesquisa == "A"` do `lead_score.calcular_leads` (respondeu a pesquisa e ficou na metade de
cima da probabilidade dos respondentes do lançamento). Gasto = o `gasto` do Ranking Geral (só captação).

Régua: nota = round(50 − 50 · ln(custo_a / mediana) / ln(FATOR²)), limitada a 0–100.
50 na mediana, 25 em 1,5× a mediana, 75 em mediana ÷ 1,5. A mediana vem só dos ADs com
`leads_a >= MIN_LEADS_A` e `gasto > 0`; sem nenhum, não há mediana e nenhum AD recebe nota.
"""
from __future__ import annotations

import math
import statistics

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
