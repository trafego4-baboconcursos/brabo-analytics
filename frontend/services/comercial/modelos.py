"""Modelos compartilhados do comercial (puro, sem banco/rede)."""
from __future__ import annotations

from dataclasses import dataclass, field

from frontend.services.comercial.tabelas import Participacao, RegraPercentual, ValorBase


@dataclass
class Cadastros:
    """Cadastros do comercial. `atribuicoes` = só as aprovadas: transação -> código AT."""
    vendedores: dict[str, str] = field(default_factory=dict)
    regras: list[RegraPercentual] = field(default_factory=list)
    valores_base: list[ValorBase] = field(default_factory=list)
    participacoes: list[Participacao] = field(default_factory=list)
    atribuicoes: dict[str, str] = field(default_factory=dict)
