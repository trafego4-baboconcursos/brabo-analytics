"""
frontend/formatters.py — Filtros de formatação Jinja2 (BRL, número, percentual).
"""
from __future__ import annotations


def fmt_brl(value: float | int, decimals: int = 2) -> str:
    try:
        v = float(value)
        formatted = f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except (TypeError, ValueError):
        return "R$ 0,00"


def fmt_num(value: float | int, decimals: int = 0) -> str:
    try:
        v = float(value)
        if decimals == 0:
            return f"{int(v):,}".replace(",", ".")
        return f"{v:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0"


def fmt_pct(value: float, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return "0%"
