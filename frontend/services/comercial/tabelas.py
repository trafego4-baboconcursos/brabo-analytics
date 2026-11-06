"""Escolha de percentual, valor-base e participação (puro, sem banco/rede)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_CENTAVO = Decimal("0.01")

BASE_TMB_POR_CATEGORIA: dict[str, Decimal] = {
    "LEAD": Decimal("1879.34"),
    "UP SELL": Decimal("495.68"),
    "CROSS SELL": Decimal("939.67"),
}


@dataclass(frozen=True)
class RegraPercentual:
    id: int
    plataforma: str
    modalidade: str
    tipo: str
    pct: Decimal
    vendedor_codigo: str | None
    vigente_de: date
    vigente_ate: date | None
    categorias: frozenset[str] | None = None  # só vale para vendas dessas categorias
    forca_tipo: str | None = None  # "Ativa": a venda que casa ignora a janela Reativa


@dataclass(frozen=True)
class ValorBase:
    id: int
    plataforma: str
    valor_cobrado: Decimal
    valor_base: Decimal
    categoria: str
    vigente_de: date
    vigente_ate: date | None


@dataclass(frozen=True)
class Participacao:
    id: int
    beneficiario: str
    pct_ativa: Decimal
    pct_reativa: Decimal
    vigente_de: date
    vigente_ate: date | None
    beneficiario_codigo: str | None = None  # código AT do beneficiário, quando é vendedor


def _vigente(item, dia: date) -> bool:
    return item.vigente_de <= dia and (item.vigente_ate is None or dia <= item.vigente_ate)


def _casa(r: RegraPercentual, plataforma: str, modalidade: str, vendedor_codigo: str | None,
          dia: date, categoria: str | None) -> bool:
    return (r.plataforma == plataforma and r.modalidade == modalidade and _vigente(r, dia)
            and (r.vendedor_codigo is None
                 or (vendedor_codigo is not None and r.vendedor_codigo == vendedor_codigo))
            and (r.categorias is None or (categoria is not None and categoria in r.categorias)))


def _especificidade(r: RegraPercentual):
    """Categoria vence geral, depois vendedor vence geral, depois vigente_de mais recente."""
    return (r.categorias is not None, r.vendedor_codigo is not None, r.vigente_de)


def escolher_percentual(regras: list[RegraPercentual], plataforma: str, modalidade: str,
                        tipo: str, vendedor_codigo: str | None, dia: date,
                        categoria: str | None = None) -> RegraPercentual | None:
    """Regra de categoria vence; depois regra do vendedor vence a geral; empate -> vigente_de
    mais recente. Regra com `categorias` só casa se `categoria` estiver nelas."""
    candidatas = [r for r in regras if r.tipo == tipo
                  and _casa(r, plataforma, modalidade, vendedor_codigo, dia, categoria)]
    if not candidatas:
        return None
    return max(candidatas, key=_especificidade)


def tipo_forcado(regras: list[RegraPercentual], plataforma: str, modalidade: str,
                 vendedor_codigo: str | None, dia: date, categoria: str | None) -> str | None:
    """`forca_tipo` da regra mais específica que casa com a venda (qualquer tipo), ou None."""
    candidatas = [r for r in regras if r.forca_tipo
                  and _casa(r, plataforma, modalidade, vendedor_codigo, dia, categoria)]
    if not candidatas:
        return None
    return max(candidatas, key=_especificidade).forca_tipo


def buscar_valor_base(tabela: list[ValorBase], plataforma: str, valor_cobrado: Decimal,
                      dia: date) -> ValorBase | None:
    alvo = Decimal(valor_cobrado).quantize(_CENTAVO)
    candidatos = [
        v for v in tabela
        if v.plataforma == plataforma and _vigente(v, dia)
        and Decimal(v.valor_cobrado).quantize(_CENTAVO) == alvo
    ]
    return max(candidatos, key=lambda v: v.vigente_de) if candidatos else None


def participacoes_vigentes(lista: list[Participacao], dia: date) -> list[Participacao]:
    return [p for p in lista if _vigente(p, dia)]
