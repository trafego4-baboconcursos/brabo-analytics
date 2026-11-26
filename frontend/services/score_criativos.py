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


def _utms_dos_respondentes(code: str, emails: list[str]) -> pd.DataFrame:
    """Uma linha por respondente que está na base de leads do lançamento: UTM e ADxxx do primeiro UTM visto que traz
    código de anúncio (None se nenhum traz). E-mail fora da base não aparece.
    Colunas: email, source, medium, campaign, content, ad."""
    from frontend.services.lead_score import _AD_SQL  # noqa: PLC0415

    colunas = ["email", "source", "medium", "campaign", "content", "ad"]
    if not emails:
        return pd.DataFrame(columns=colunas)
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        rows = conn.execute(text(
            "SELECT DISTINCT ON (email) email, utm_source, utm_medium, utm_campaign, utm_content, " + _AD_SQL +
            " FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email = ANY(:e) "
            "ORDER BY email, (" + _AD_SQL + " IS NULL), primeiro_visto_em"), {"c": code, "e": emails}).fetchall()
    return pd.DataFrame([tuple(r) for r in rows], columns=colunas)


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


def contar_por_unidade(utms: pd.DataFrame, emails_a: set[str], casar) -> dict:
    """Conta os leads A por anúncio, por conjunto/grupo e por par conjunto × anúncio. Pura.

    `casar(source, medium, campaign, content) -> (plataforma, grupo_id) | None` (`vendas_por_grupo.casador_de_grupos`).
    `total_canal` = leads A cuja campanha é Meta ou Google (denominador da cobertura do score por conjunto)."""
    from frontend.services.classificadores import _classify_campaign  # noqa: PLC0415

    por_ad: dict[str, int] = {}
    por_grupo: dict[str, int] = {}
    por_par: dict[str, int] = {}
    total_canal = 0
    for email, source, medium, campaign, content, ad in utms.itertuples(index=False, name=None):
        if email not in emails_a:
            continue
        if ad:
            por_ad[ad] = por_ad.get(ad, 0) + 1
        if _classify_campaign(campaign or "", source or "", medium or "")["channel"] in ("Meta Ads", "Google Ads"):
            total_canal += 1
        achou = casar(source or "", medium or "", campaign or "", content or "")
        if not achou:
            continue
        chave = f"{achou[0]}:{achou[1]}"
        por_grupo[chave] = por_grupo.get(chave, 0) + 1
        if ad:
            par = f"{chave}|{ad}"
            por_par[par] = por_par.get(par, 0) + 1
    return {"por_ad": por_ad, "por_grupo": por_grupo, "por_par": por_par, "total_canal": total_canal}


def _contagem_leads_a_sem_cache(code: str) -> dict | None:
    """`contar_por_unidade` do lançamento. None sem modelo, sem pesquisa pontuável ou sem respondente na base."""
    from frontend.services import lead_score, vendas_por_grupo  # noqa: PLC0415

    m = lead_score._carregar_modelo()
    if not m:
        return None
    resp = lead_score._respostas_df(code, m)
    if resp is None or resp.empty:
        return None
    utms = _utms_dos_respondentes(code, [e for e in resp["email"].tolist() if e])
    if utms.empty:
        return None
    emails_a = leads_a_dos_respondentes(resp, set(utms["email"]), m)
    casar = vendas_por_grupo.casador_de_grupos(vendas_por_grupo._grupos_do_lancamento(code))
    return contar_por_unidade(utms, emails_a, casar)


TTL_PADRAO = 1800


def contagem_leads_a(code: str, ttl: int = TTL_PADRAO) -> dict | None:
    """Uma leitura dos respondentes por lançamento, compartilhada pela coluna Score do Ranking Geral
    (`/criativos/score`) e pelo score por conjunto (`/criativos/score-conjuntos`): as duas rotas abrem juntas na
    `/criativos` e cada uma lia a pesquisa e a `lead_utm_lancamento` por conta própria. O cache guarda só as
    contagens (dicionários pequenos), nunca a base de leads."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "score_leads_a_contagem", lambda: _contagem_leads_a_sem_cache(code), ttl=ttl)


def leads_a_por_anuncio(code: str, ttl: int = TTL_PADRAO) -> dict[str, int] | None:
    """{ADxxx: nº de leads A}, da contagem compartilhada. None sem pesquisa pontuável."""
    c = contagem_leads_a(code, ttl)
    return None if c is None else c["por_ad"]


def ttl_do_lancamento(launch) -> int:
    """30 min no lançamento ativo; o TTL da atribuição (6 h) quando ele já encerrou, porque o dado não muda mais."""
    from frontend.services.attribution import _ttl_atribuicao  # noqa: PLC0415

    return _ttl_atribuicao(launch) or TTL_PADRAO
