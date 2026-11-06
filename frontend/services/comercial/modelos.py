"""Modelos compartilhados do comercial (puro, sem banco/rede)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from frontend.services.comercial.tabelas import Participacao, RegraPercentual, ValorBase


@dataclass
class Cadastros:
    """Cadastros do comercial. `atribuicoes` = só as aprovadas: transação -> código AT."""
    vendedores: dict[str, str] = field(default_factory=dict)
    regras: list[RegraPercentual] = field(default_factory=list)
    valores_base: list[ValorBase] = field(default_factory=list)
    participacoes: list[Participacao] = field(default_factory=list)
    atribuicoes: dict[str, str] = field(default_factory=dict)
    ofertas: dict[str, str] = field(default_factory=dict)  # codigo_do_preco -> nome_deste_preco


@dataclass(frozen=True)
class Venda:
    """Venda normalizada (Hotmart ou TMB). Datas naive em America/Sao_Paulo."""
    plataforma: str
    transacao: str
    data: datetime
    produto_id: str
    produto: str
    oferta: str
    codigo_at: str | None
    conflito_codigo: bool
    modalidade: str
    categoria: str | None
    valor_cobrado: Decimal
    pago: bool
    cancelada_em: datetime | None
