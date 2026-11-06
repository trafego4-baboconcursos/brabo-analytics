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


def escolher_percentual(regras: list[RegraPercentual], plataforma: str, modalidade: str,
                        tipo: str, vendedor_codigo: str | None, dia: date) -> RegraPercentual | None:
    """Regra do vendedor vence a geral; empate -> vigente_de mais recente."""
    candidatas = [
        r for r in regras
        if r.plataforma == plataforma and r.modalidade == modalidade and r.tipo == tipo
        and _vigente(r, dia)
        and (r.vendedor_codigo is None
             or (vendedor_codigo is not None and r.vendedor_codigo == vendedor_codigo))
    ]
    if not candidatas:
        return None
    return max(candidatas, key=lambda r: (r.vendedor_codigo is not None, r.vigente_de))


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
