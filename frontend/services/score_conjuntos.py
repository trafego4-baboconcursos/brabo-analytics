"""
frontend/services/score_conjuntos.py — Nota 0–100 por conjunto/grupo, par anúncio×conjunto, público e segmento.

Conta pura, sem banco. Reusa a régua de `score_criativos.notas_por_anuncio` (uma chamada por nível, cada nível com a
própria mediana). Plano: docs/projetos/PLANO_SCORE_CONJUNTOS.md.
Chaves: conjunto/grupo "meta:<id>" / "google:<id>"; par "<chave do conjunto>|<ADxxx>".
"""
from __future__ import annotations

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
