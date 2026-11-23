"""Vendas atribuídas por conjunto (Facebook/Meta) e por grupo (Google) — base do CPA da página /publicos.

Não é uma atribuição nova: usa a UTM que o motor de sempre (`_sales_attribution_calc`, só e-mail/telefone, com a
UTM congelada) escolheu para cada comprador e só descobre a QUE conjunto/grupo ela aponta.

O padrão de UTM grava `utm_campaign` = nome da campanha e `utm_content` = nome do conjunto (Meta) ou o slug do nome
do grupo (Google). O `vk_ad_id` seria a chave exata, mas vem vazio nos leads (conferido em 23/11/26). Como o banco
guarda só o NOME ATUAL do conjunto, um conjunto renomeado depois do clique não casa pelo nome; por isso a ligação
tenta, nesta ordem, e só aceita quando a resposta é única:
  1. campanha + nome do conjunto/grupo (comparados sem acento, caixa e pontuação);
  2. campanha + número do grupo ("04 - ...") — cobre o conjunto renomeado que manteve o número da cascata;
  3. só o nome do conjunto/grupo, quando ele existe uma vez só no lançamento.
O que sobra aparece como "sem conjunto identificado" (cobertura na tela).
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from frontend.services.classificadores import _classify_campaign
from logger import get_logger

logger = get_logger("db")

_CANAL = {"Meta Ads": "meta", "Google Ads": "google"}
_NUMERO = re.compile(r"^\s*(\d{1,2})\s*[-–—.]")


def slug(texto: Any) -> str:
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def numero_do_grupo(nome: Any) -> str | None:
    m = _NUMERO.match(str(nome or ""))
    return m.group(1).zfill(2) if m else None


@dataclass
class VendasPorGrupo:
    por_grupo: dict[tuple[str, str], tuple[int, float]] = field(default_factory=dict)   # (plataforma, id) → (vendas, receita)
    ligadas: dict[str, int] = field(default_factory=dict)       # vendas ligadas a um conjunto/grupo, por plataforma
    sem_grupo: dict[str, int] = field(default_factory=dict)     # vendas atribuídas à plataforma sem conjunto identificado

    def cobertura(self, plataforma: str) -> float | None:
        total = self.ligadas.get(plataforma, 0) + self.sem_grupo.get(plataforma, 0)
        return self.ligadas.get(plataforma, 0) / total * 100 if total else None


def ligar_vendas(buyer_utms: dict[str, dict], vendas_por_email: dict, receita_por_email: dict,
                 grupos: list[tuple[str, str, str, str]]) -> VendasPorGrupo:
    """`grupos`: [(plataforma, nome da campanha, nome do conjunto/grupo, id)] do lançamento. Pura."""
    por_par, por_numero, por_nome = defaultdict(set), defaultdict(set), defaultdict(set)
    for plat, camp, nome, gid in grupos:
        gid = str(gid)
        por_par[(plat, slug(camp), slug(nome))].add(gid)
        if (n := numero_do_grupo(nome)):
            por_numero[(plat, slug(camp), n)].add(gid)
        por_nome[(plat, slug(nome))].add(gid)

    def _unico(ids):
        return next(iter(ids)) if len(ids) == 1 else None

    out = VendasPorGrupo()
    acum: dict[tuple[str, str], list] = {}
    for email, u in buyer_utms.items():
        canal = _CANAL.get(_classify_campaign(u.get("campaign") or "", u.get("source") or "", u.get("medium") or "")["channel"])
        if not canal:
            continue
        camp, conteudo = slug(u.get("campaign")), u.get("content") or ""
        gid = _unico(por_par.get((canal, camp, slug(conteudo)), ()))
        if gid is None and camp and (n := numero_do_grupo(conteudo)):
            gid = _unico(por_numero.get((canal, camp, n), ()))
        if gid is None:
            gid = _unico(por_nome.get((canal, slug(conteudo)), ()))
        vendas = int(vendas_por_email.get(email, 1) or 1)
        if gid is None:
            out.sem_grupo[canal] = out.sem_grupo.get(canal, 0) + vendas
            continue
        a = acum.setdefault((canal, gid), [0, 0.0])
        a[0] += vendas
        a[1] += float(receita_por_email.get(email, 0.0) or 0.0)
        out.ligadas[canal] = out.ligadas.get(canal, 0) + vendas
    out.por_grupo = {k: (v[0], v[1]) for k, v in acum.items()}
    return out


def _grupos_do_lancamento(code: str) -> list[tuple[str, str, str, str]]:
    from sqlalchemy import text  # noqa: PLC0415

    from frontend.db import _get_engine  # noqa: PLC0415

    with _get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT 'meta', campaign_name, adset_name, adset_id FROM meta_ads_daily WHERE lancamento_codigo = :l
            UNION
            SELECT DISTINCT 'google', campaign_name, ad_group_name, ad_group_id FROM google_ads_daily WHERE lancamento_codigo = :l
        """), {"l": code}).fetchall()
    return [(r[0], r[1] or "", r[2] or "", str(r[3])) for r in rows if r[3] is not None]


_TTL_ATIVO = 3 * 3600


def read_vendas_por_grupo(launch: Any) -> VendasPorGrupo | None:
    """None se não houver venda. A conta refaz a atribuição (40–70 s num lançamento ativo, 23/11/26) e não usa o
    cache da atribuição das outras páginas; por isso o cache é de 3 h no lançamento ativo (CPA por público não
    precisa de minuto) e de 6 h no encerrado (o mesmo da atribuição). Recalcular de hora em hora já saturou o banco
    (27/10/26). Com o cache vencido a página mostra o valor anterior e recalcula em segundo plano."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415
    from frontend.services.attribution import _sales_attribution_calc, _ttl_atribuicao  # noqa: PLC0415
    from frontend.services.fetch import _vendas  # noqa: PLC0415

    def _calc():
        vendas = _vendas(launch) if getattr(launch, "has_vendas", True) else None
        if not vendas:
            return None
        # caminho que devolve a UTM escolhida por comprador (não lê nem grava o cache da atribuição)
        bu = _sales_attribution_calc(launch, vendas, devolver_utms=True).get("_buyer_utms") or {}
        return ligar_vendas(bu, getattr(vendas, "vendas_por_email", {}) or {}, vendas.receita_por_email or {},
                            _grupos_do_lancamento(launch.code))

    return _get_or_compute(launch.code, "vendas_por_grupo", _calc, ttl=_ttl_atribuicao(launch) or _TTL_ATIVO)
