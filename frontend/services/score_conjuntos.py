"""
frontend/services/score_conjuntos.py — Nota 0–100 por conjunto/grupo, par anúncio×conjunto, público e segmento.

Conta pura, sem banco. Reusa a régua de `score_criativos.notas_por_anuncio` (uma chamada por nível, cada nível com a
própria mediana). Plano: docs/projetos/PLANO_SCORE_CONJUNTOS.md.
Chaves: conjunto/grupo "meta:<id>" / "google:<id>"; par "<chave do conjunto>|<ADxxx>".
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine
from frontend.services.score_criativos import notas_por_anuncio


def somar_unidades(membros: dict[str, set[str]], gasto: dict[str, float],
                   leads_a: dict[str, int]) -> tuple[dict[str, float], dict[str, int]]:
    """Gasto e leads A de cada unidade (público, segmento, nome): soma dos conjuntos membros, cada um uma vez.
    Membro ausente vale 0; unidade sem membro conhecido fica com gasto 0."""
    gasto_u: dict[str, float] = {}
    leads_u: dict[str, int] = {}
    for unidade, conjuntos in membros.items():
        gasto_u[unidade] = sum(gasto.get(c, 0) for c in conjuntos)
        leads_u[unidade] = sum(leads_a.get(c, 0) for c in conjuntos)
    return gasto_u, leads_u


def _nivel(gasto: dict[str, float], leads: dict[str, int]) -> tuple[float | None, dict[str, dict]]:
    """Notas de um nível, com o `gasto` de cada unidade junto."""
    r = notas_por_anuncio(gasto, leads)
    return r["mediana"], {k: {**v, "gasto": gasto[k]} for k, v in r["anuncios"].items()}


def _nivel_somado(membros: dict[str, set[str]], gasto_grupo: dict[str, float],
                  leads_grupo: dict[str, int]) -> tuple[float | None, dict[str, dict]]:
    gasto, leads = somar_unidades(membros, gasto_grupo, leads_grupo)
    return _nivel(gasto, leads)


def montar_score(gasto_grupo: dict[str, float], leads_grupo: dict[str, int],
                 gasto_par: dict[str, float], leads_par: dict[str, int],
                 info_grupo: dict[str, dict], publicos: dict[str, set[str]],
                 segmentos: dict[str, set[str]], nomes_meta: dict[str, set[str]],
                 cobertura_leads_a: float | None) -> dict:
    """Notas de todos os níveis. Cada nível tem a própria mediana (ver `notas_por_anuncio`)."""
    mediana_conjunto, conjuntos = _nivel(gasto_grupo, leads_grupo)
    for chave, dados in conjuntos.items():
        info = info_grupo.get(chave) or {}
        dados.update(plataforma=info.get("plataforma", ""), campanha=info.get("campanha", ""),
                     nome=info.get("nome", ""), anuncios={})

    mediana_par, pares = _nivel(gasto_par, leads_par)
    for chave, dados in pares.items():
        grupo, _, ad = chave.partition("|")
        if grupo in conjuntos:
            conjuntos[grupo]["anuncios"][ad] = dados

    mediana_publico, pub = _nivel_somado(publicos, gasto_grupo, leads_grupo)
    mediana_segmento, seg = _nivel_somado(segmentos, gasto_grupo, leads_grupo)
    mediana_nome_meta, nomes = _nivel_somado(nomes_meta, gasto_grupo, leads_grupo)

    return {
        "mediana_conjunto": mediana_conjunto, "mediana_par": mediana_par,
        "mediana_publico": mediana_publico, "mediana_segmento": mediana_segmento,
        "mediana_nome_meta": mediana_nome_meta, "cobertura_leads_a": cobertura_leads_a,
        "conjuntos": conjuntos, "publicos": pub, "segmentos_google": seg, "conjuntos_meta_por_nome": nomes,
    }


def _gasto_captacao(code: str) -> pd.DataFrame:
    """Gasto de captação por campanha × conjunto/grupo × `ad_name` (ADxxx vazio quando o nome não traz código).
    Colunas: chave, plataforma, campanha, nome, ad, gasto."""
    from frontend.db_readers.publicos import etapa_da_campanha  # noqa: PLC0415
    from frontend.services.classificadores import _extract_ad_code  # noqa: PLC0415

    linhas: list[dict] = []
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        meta = conn.execute(text(
            "SELECT campaign_name, adset_id, adset_name, ad_name, SUM(spend) FROM meta_ads_daily "
            "WHERE lancamento_codigo = :c AND adset_id IS NOT NULL GROUP BY 1, 2, 3, 4"), {"c": code}).fetchall()
        google = conn.execute(text(
            "SELECT campaign_name, ad_group_id, ad_group_name, ad_name, SUM(cost) FROM google_ads_daily "
            "WHERE lancamento_codigo = :c AND ad_group_id IS NOT NULL GROUP BY 1, 2, 3, 4"), {"c": code}).fetchall()
    for plat, rows in (("meta", meta), ("google", google)):
        for camp, gid, nome, ad_name, gasto in rows:
            if etapa_da_campanha(camp or "") != "captacao":
                continue
            linhas.append({"chave": f"{plat}:{gid}", "plataforma": plat, "campanha": camp or "", "nome": nome or "",
                           "ad": _extract_ad_code(ad_name or ""), "gasto": float(gasto or 0)})
    df = pd.DataFrame(linhas, columns=["chave", "plataforma", "campanha", "nome", "ad", "gasto"])
    return df.groupby(["chave", "plataforma", "campanha", "nome", "ad"], as_index=False)["gasto"].sum()


def _publicos_dos_grupos(code: str) -> dict[str, set[str]]:
    """{"<plataforma>:<publico_id>": {"<plataforma>:<grupo_id>"}} só dos públicos incluídos (`papel = 'inclui'`).
    Vazio quando o lançamento não teve coleta de públicos."""
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        rows = conn.execute(text(
            "SELECT DISTINCT plataforma, grupo_id, publico_id FROM publicos_uso "
            "WHERE lancamento_codigo = :c AND papel = 'inclui'"), {"c": code}).fetchall()
    out: dict[str, set[str]] = {}
    for plat, grupo, publico in rows:
        out.setdefault(f"{plat}:{publico}", set()).add(f"{plat}:{grupo}")
    return out


def _segmentos_google(code: str, casar) -> dict[str, set[str]]:
    """{audience_name: {"google:<ad_group_id>"}}: liga cada linha ao grupo pelo mesmo casador das UTMs."""
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        rows = conn.execute(text(
            "SELECT DISTINCT audience_name, campaign_name, ad_group_name FROM google_ads_audiences_daily "
            "WHERE lancamento_codigo = :c"), {"c": code}).fetchall()
    out: dict[str, set[str]] = {}
    for segmento, campanha, grupo in rows:
        achou = casar("google", "cpc", campanha or "", grupo or "")
        if achou:
            out.setdefault(segmento, set()).add(f"{achou[0]}:{achou[1]}")
    return out


def _score_conjuntos_sem_cache(code: str, ttl: int = 1800) -> dict | None:
    """Notas de todos os níveis. None sem modelo, sem pesquisa pontuável ou sem respondente na base de leads.
    Os leads A vêm da contagem compartilhada com a coluna Score do Ranking Geral (`score_criativos.contagem_leads_a`):
    a pesquisa e a `lead_utm_lancamento` são lidas uma vez só por lançamento."""
    from frontend.services import score_criativos, vendas_por_grupo  # noqa: PLC0415

    contagem = score_criativos.contagem_leads_a(code, ttl)
    if contagem is None:
        return None

    gasto = _gasto_captacao(code)
    gasto_grupo = {k: float(v) for k, v in gasto.groupby("chave")["gasto"].sum().items()}
    com_ad = gasto[gasto["ad"] != ""]
    gasto_par = {f"{c}|{a}": float(v) for (c, a), v in com_ad.groupby(["chave", "ad"])["gasto"].sum().items()}
    info_grupo = {r.chave: {"plataforma": r.plataforma, "campanha": r.campanha, "nome": r.nome}
                  for r in gasto.drop_duplicates("chave").itertuples()}
    nomes_meta: dict[str, set[str]] = {}
    for r in gasto[gasto["plataforma"] == "meta"].drop_duplicates("chave").itertuples():
        nomes_meta.setdefault(r.nome, set()).add(r.chave)

    # Só conta lead A de conjunto de captação: o gasto só cobre captação, e público/segmento somam conjuntos.
    leads_grupo = {k: v for k, v in contagem["por_grupo"].items() if k in gasto_grupo}
    leads_par = {k: v for k, v in contagem["por_par"].items() if k in gasto_par}
    total_a = contagem["total_canal"]
    cobertura = 100 * sum(leads_grupo.values()) / total_a if total_a else None
    casar = vendas_por_grupo.casador_de_grupos(vendas_por_grupo._grupos_do_lancamento(code))
    return montar_score(gasto_grupo, leads_grupo, gasto_par, leads_par, info_grupo,
                        _publicos_dos_grupos(code), _segmentos_google(code, casar), nomes_meta, cobertura)


def score_conjuntos(code: str, ttl: int = 1800) -> dict | None:
    """`_score_conjuntos_sem_cache` com cache (30 min no lançamento ativo; `ttl` maior quando já encerrou)."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "score_conjuntos", lambda: _score_conjuntos_sem_cache(code, ttl), ttl=ttl)
