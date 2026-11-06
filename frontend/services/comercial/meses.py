"""Aritmética de meses da área Comercial (pura): um lugar só para o piso e as contas de mês.

PRIMEIRO_MES: o comercial existe de 2026-01 em diante (mês aceito nas telas, mês que pode
fechar, início mínimo de regra/vigência).
"""
from __future__ import annotations

import calendar
from datetime import date

PRIMEIRO_MES = date(2026, 1, 1)


def soma_meses(m: date, n: int) -> date:
    """1º dia do mês `n` meses depois (negativo = antes) do mês de `m`."""
    t = m.year * 12 + m.month - 1 + n
    return date(t // 12, t % 12 + 1, 1)


def ultimo_dia(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])
