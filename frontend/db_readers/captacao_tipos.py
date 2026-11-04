"""Captação por plataforma e tipo de campanha (Principal, Potencial, Imagem, Carrossel, Reels/Shorts).

O tipo vem da tag entre colchetes do nome da campanha (`[principal]`, `[reels]`, `[shorts]`...). Não usa a
coluna `bucket`/`segmento` do banco: ela não conhece `carrossel` fora da Black, e mexer no mapa de lá mudaria
outras páginas. Campanha sem tag de tipo (ou com um tipo fora da lista, como o pós-edital) cai em linhas extras
que só aparecem quando têm gasto, para o total da tabela fechar com o da Captação.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import text

from frontend.db import _get_engine

TIPOS = ("Principal", "Potencial", "Imagem", "Carrossel", "Reels/Shorts")
EXTRAS = ("Pós-edital", "Outros")

_TAG_TIPO = {
    "principal": "Principal", "potencial": "Potencial", "imagem": "Imagem", "carrossel": "Carrossel",
    "reels": "Reels/Shorts", "shorts": "Reels/Shorts", "pos-edital": "Pós-edital",
}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def tipo_da_campanha(nome: str) -> str:
    """Tipo pela primeira tag conhecida do nome; `Outros` se não houver."""
    for tag in re.findall(r"\[([^\]]*)\]", _sem_acento(str(nome))):
        tipo = _TAG_TIPO.get(tag.strip())
        if tipo:
            return tipo
    return "Outros"


def _linha(tipo: str, campanhas: int, gasto: float, leads: float, base_gasto: float, base_leads: float) -> dict:
    return {
        "tipo": tipo, "campanhas": campanhas, "gasto": gasto, "leads": int(round(leads)),
        "cpl": gasto / leads if leads > 0 else 0.0,
        "pct_gasto": gasto / base_gasto * 100 if base_gasto > 0 else 0.0,
        "pct_leads": leads / base_leads * 100 if base_leads > 0 else 0.0,
    }


def montar_blocos(linhas_por_plataforma: dict[str, list[tuple[str, float, float]]]) -> list[dict]:
    """`{plataforma: [(nome_campanha, gasto, leads), ...]}` -> um bloco por plataforma, com as linhas de tipo,
    o total da plataforma e os percentuais dentro dela. As cinco linhas pedidas aparecem sempre (zeradas);
    as extras só com gasto."""
    blocos = []
    for plataforma, campanhas in linhas_por_plataforma.items():
        acc: dict[str, list[float]] = {}
        for nome, gasto, leads in campanhas:
            a = acc.setdefault(tipo_da_campanha(nome), [0, 0.0, 0.0])
            a[0] += 1
            a[1] += float(gasto or 0)
            a[2] += float(leads or 0)
        total_gasto = sum(a[1] for a in acc.values())
        total_leads = sum(a[2] for a in acc.values())
        linhas = []
        for tipo in TIPOS + EXTRAS:
            n, g, l = acc.get(tipo, [0, 0.0, 0.0])
            if tipo in TIPOS or g > 0:
                linhas.append(_linha(tipo, int(n), g, l, total_gasto, total_leads))
        blocos.append({
            "plataforma": plataforma, "linhas": linhas,
            "total": _linha("Total", sum(int(a[0]) for a in acc.values()), total_gasto, total_leads,
                            total_gasto, total_leads),
        })
    return blocos


def read_captacao_por_tipo(launch_code: str) -> list[dict]:
    """Blocos Facebook e YouTube da Captação do lançamento; lista vazia se nenhuma das duas tem gasto."""
    with _get_engine().connect() as conn:
        meta = conn.execute(text(
            "SELECT campaign_name, SUM(spend), SUM(leads) FROM meta_ads_daily "
            "WHERE lancamento_codigo = :c AND etapa = 'Captação' GROUP BY campaign_name"), {"c": launch_code}).fetchall()
        google = conn.execute(text(
            "SELECT campaign_name, SUM(cost), SUM(conversions) FROM google_ads_daily "
            "WHERE lancamento_codigo = :c AND etapa = 'Captação' GROUP BY campaign_name"), {"c": launch_code}).fetchall()
    dados = {"Facebook": [tuple(r) for r in meta], "YouTube": [tuple(r) for r in google]}
    blocos = montar_blocos({k: v for k, v in dados.items() if v})
    return [b for b in blocos if b["total"]["gasto"] > 0]
