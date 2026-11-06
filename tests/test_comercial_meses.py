"""Aritmética de meses da área Comercial (módulo único: meses.py)."""
from datetime import date

import pytest

from frontend.services.comercial import fechamento, meses, regras_tela, telas


@pytest.mark.parametrize("m,n,esperado", [
    (date(2026, 11, 1), 1, date(2026, 12, 1)),
    (date(2026, 12, 1), 1, date(2027, 1, 1)),
    (date(2026, 1, 1), -1, date(2025, 12, 1)),
    (date(2026, 3, 1), -14, date(2025, 1, 1)),
    (date(2026, 5, 1), 0, date(2026, 5, 1)),
    (date(2026, 5, 31), 1, date(2026, 6, 1)),  # devolve sempre o 1º dia
])
def test_soma_meses(m, n, esperado):
    assert meses.soma_meses(m, n) == esperado


@pytest.mark.parametrize("m,esperado", [
    (date(2026, 2, 10), date(2026, 2, 28)), (date(2028, 2, 1), date(2028, 2, 29)),
    (date(2026, 12, 1), date(2026, 12, 31)), (date(2026, 11, 30), date(2026, 11, 30)),
])
def test_ultimo_dia(m, esperado):
    assert meses.ultimo_dia(m) == esperado


def test_piso_unico():
    assert meses.PRIMEIRO_MES == date(2026, 1, 1)
    assert telas.PRIMEIRO_MES is fechamento.PRIMEIRO_MES is regras_tela.INICIO_MINIMO is meses.PRIMEIRO_MES


def test_sem_copias_da_aritmetica():
    assert fechamento.soma_meses is meses.soma_meses and fechamento.ultimo_dia is meses.ultimo_dia
    for mod, nome in ((telas, "_soma_meses"), (regras_tela, "_soma_mes")):
        assert not hasattr(mod, nome), f"{mod.__name__}.{nome} ainda existe"
