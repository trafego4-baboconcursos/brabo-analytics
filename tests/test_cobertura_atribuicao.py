"""Faixa de cobertura da atribuição: quanto do lançamento o ranking explica.

Nasceu do achado de 08/10/26: a `leads` perdia compradores (18% dos de um
lançamento fechado, contra 1,9% dos leads), e o ranking de criativos mostrava
ROAS e custo por venda sem dizer quanto da venda ele realmente cobria.
"""
from __future__ import annotations

from types import SimpleNamespace

from frontend.services.criativos import _cobertura_atribuicao


def _resumo(**kw):
    base = {"total_compradores": 2499, "compradores_com_utm": 2003,
            "total_vendas_ads": 1836, "total_faturamento_ads": 3_000_000.0}
    base.update(kw)
    return base


def _vendas(total=2500, receita=4_100_000.0):
    return SimpleNamespace(total_vendas=total, total_receita=receita)


def test_dois_numeros_distintos_compradores_e_vendas_ligadas_a_criativo():
    cb = _cobertura_atribuicao(_resumo(), _vendas())
    assert round(cb["compradores_pct"]) == 80      # tem UTM
    assert round(cb["vendas_pct"]) == 73           # chega a um criativo
    assert cb["vendas_sem_criativo"] == 664
    assert round(cb["receita_sem_criativo"]) == 1_100_000


def test_sem_venda_nao_ha_faixa():
    """Lançamento que ainda não abriu o carrinho (BV-26): nada a cobrir."""
    assert _cobertura_atribuicao(_resumo(total_compradores=0), _vendas(0, 0.0)) is None


def test_atribuido_nunca_passa_do_total():
    """Venda de comprador com mais de uma compra pode somar além do total de
    transações; a cobertura não pode passar de 100%."""
    cb = _cobertura_atribuicao(_resumo(total_vendas_ads=3000), _vendas(total=2500))
    assert cb["vendas_ads"] == 2500 and cb["vendas_pct"] == 100.0
    assert cb["vendas_sem_criativo"] == 0
