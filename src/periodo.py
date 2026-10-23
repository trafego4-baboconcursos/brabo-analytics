"""
src/periodo.py — período de análise das páginas que filtram por data (Perpétuo, Distribuição, Redes Sociais).

Dois jeitos de escolher, na mesma URL:
    ?days=30                       → os últimos N dias, terminando hoje (atalhos 7/30/90);
    ?inicio=2026-09-01&fim=2026-09-30  → um intervalo livre. Vale quando os dois vêm preenchidos e válidos.
"""
from __future__ import annotations

from datetime import date, timedelta

MAX_DIAS = 366   # teto do intervalo livre: o Meta/Google do banco não precisa de mais que um ano por consulta


def _data(txt) -> date | None:
    try:
        return date.fromisoformat(str(txt)[:10])
    except (TypeError, ValueError):
        return None


def resolver_periodo(days: int = 30, inicio=None, fim=None, hoje: date | None = None) -> tuple[date, date, int, bool]:
    """(início, fim, nº de dias, personalizado?). Datas invertidas são trocadas; o fim nunca passa de
    hoje (não existe dado do futuro) e o intervalo é limitado a MAX_DIAS terminando no fim."""
    hoje = hoje or date.today()
    i, f = _data(inicio), _data(fim)
    if i and f:
        if i > f:
            i, f = f, i
        f = min(f, hoje)
        i = max(min(i, f), f - timedelta(days=MAX_DIAS - 1))
        return i, f, (f - i).days + 1, True
    n = days if isinstance(days, int) and 1 <= days <= MAX_DIAS else 30
    return hoje - timedelta(days=n - 1), hoje, n, False
