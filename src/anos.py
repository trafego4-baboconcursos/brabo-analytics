"""
src/anos.py — o ANO como conceito único do sistema.

O ano de um lançamento é o sufixo do código (PBB-ABR-26 → 2026), não a data de início:
PI-JAN-26 começa em nov/2025 e é de 2026; BV-25 é de 2025. Tudo que filtra, agrupa ou soma
"por ano" passa por aqui, para a regra não se repetir (e não quebrar na virada para 2027).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

ANO_COOKIE = "brabo_ano"
_SUFIXO = re.compile(r"-(\d{2})$")


def ano_do_codigo(codigo: str | None) -> int | None:
    """2000 + o sufixo de dois dígitos do código; None se o código não tem ano (PERPETUO...)."""
    m = _SUFIXO.search((codigo or "").strip())
    return 2000 + int(m.group(1)) if m else None


def sufixo_do_ano(ano: int) -> str:
    return f"-{str(ano)[-2:]}"


def do_ano(codigos: Iterable, ano: int) -> list:
    """Filtra itens (códigos ou objetos com `.code`) cujo código é do ano."""
    return [c for c in codigos if ano_do_codigo(getattr(c, "code", c)) == ano]


def _data(v) -> date | None:
    if not v or isinstance(v, date):
        return v or None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def roda_no_ano(itens: Iterable, ano: int) -> list:
    """Lançamentos que pertencem ao ano OU que rodam dentro dele (janela `data_inicio`–`data_fim`).
    É o filtro do menu e do Calendário: o PI-JAN-27 começa em 14/12/26 e precisa aparecer em 2026
    enquanto roda. Somas "por ano" (faturamento, metas) continuam no `do_ano`, que é pelo código."""
    saida = []
    for c in itens:
        if ano_do_codigo(getattr(c, "code", c)) == ano:
            saida.append(c)
            continue
        ini = _data(getattr(c, "data_inicio", None))
        fim = _data(getattr(c, "data_fim", None)) or ini
        if ini and fim and ini.year <= ano <= fim.year:
            saida.append(c)
    return saida


def anos_disponiveis(codigos: Iterable, hoje: date | None = None) -> list[int]:
    """Anos com lançamento, do mais novo ao mais antigo. O ano corrente entra sempre
    (mesmo sem lançamento ainda), para o padrão nunca apontar para um ano ausente."""
    anos = {a for a in (ano_do_codigo(getattr(c, "code", c)) for c in codigos) if a}
    anos.add((hoje or date.today()).year)
    return sorted(anos, reverse=True)


def resolver_ano(disponiveis: list[int], query=None, cookie=None, hoje: date | None = None) -> int:
    """Ordem: ?ano= da URL → cookie → ano corrente → o mais novo disponível."""
    for bruto in (query, cookie):
        try:
            a = int(bruto)
        except (TypeError, ValueError):
            continue
        if a in disponiveis:
            return a
    corrente = (hoje or date.today()).year
    if corrente in disponiveis:
        return corrente
    return disponiveis[0] if disponiveis else corrente
