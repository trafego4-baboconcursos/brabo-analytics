"""Partes puras da carga inicial do comercial (sem banco, sem planilhas)."""
from decimal import Decimal

import pandas as pd
import pytest

from scripts.comercial_carga_inicial import (
    _dec, ler_valores_a_preencher, montar_atribuicoes, montar_ofertas,
)


def test_ler_valores_a_preencher_mapeia_plataformas():
    df = pd.DataFrame({
        "Plataforma": ["Hotmart Aprovasim", "Hotmart Brabo Editora", "TMB"],
        "Valor_Plataforma": ["89.90", "89,90", "1879.34"],
        "Valor_Base_Comissao": ["1477", "1477", "1879.34"],
        "Categoria": ["LEAD", "UP SELL", "LEAD"],
    })
    r = ler_valores_a_preencher(df)
    assert [x["plataforma"] for x in r] == ["hotmart", "hotmart", "tmb"]
    assert r[0]["valor_cobrado"] == Decimal("89.90")
    assert r[1]["valor_cobrado"] == Decimal("89.90")
    assert r[0]["valor_base"] == Decimal("1477")
    assert r[1]["categoria"] == "UP SELL"


def test_ler_valores_a_preencher_plataforma_desconhecida():
    df = pd.DataFrame({"Plataforma": ["Kiwify"], "Valor_Plataforma": ["1"],
                       "Valor_Base_Comissao": ["1"], "Categoria": ["LEAD"]})
    with pytest.raises(ValueError):
        ler_valores_a_preencher(df)


def test_montar_atribuicoes():
    vendas = pd.DataFrame({
        "transacao": ["T1", "T2", "T3"],
        "nome": ["Priscila", "Ediléia", "Izabela"],
    })
    codigo_da_venda = {"T1": "AT11", "T2": None, "T3": "AT4"}
    nomes = {"Priscila": "AT11", "Ediléia": "AT4", "Izabela": "AT13"}
    r = montar_atribuicoes(vendas, codigo_da_venda, nomes)
    assert r == {"T2": "AT4", "T3": "AT13"}


def test_ler_valores_a_preencher_celulas_sujas():
    df = pd.DataFrame({
        "Plataforma": ["Hotmart Aprovasim"] * 3,
        "Valor_Plataforma": ["116.57", "372.28", "2998.8"],
        "Valor_Base_Comissao": ["(ATENÇÃO) 1197", "NÃO TEM", "(ATENÇÃO) 2.998,80"],
        "Categoria": ["LEAD", "BLACK VITALÍCIA", "LEAD"],
    })
    r = ler_valores_a_preencher(df)
    assert [x["valor_base"] for x in r] == [Decimal("1197"), Decimal("2998.80")]


def test_montar_ofertas():
    df = pd.DataFrame({
        "Código do preço": ["P1", "P2", "P3", "P3", "P4", "P4", "P4", None],
        "Nome deste preço": ["COM. LEAD - AT9", "Sem codigo", "X AT4", "X AT11",
                             "CS Mestre AT13", "Mestre AT13", "Mestre AT13", "Y AT4"],
    })
    assert montar_ofertas(df) == {"P1": "COM. LEAD - AT9", "P4": "Mestre AT13"}


@pytest.mark.parametrize("bruto,esperado", [
    ("1.477", "1477"), ("(ATENÇÃO) 1.477", "1477"), ("2.998,80", "2998.80"),
    ("(ATENÇÃO) 2.998,80", "2998.80"), ("89.9", "89.9"), ("89.90", "89.90"),
    ("1477", "1477"), ("89,90", "89.90"), ("0.477", "0.477"),
])
def test_dec_formatos(bruto, esperado):
    assert _dec(bruto) == Decimal(esperado)


@pytest.mark.parametrize("bruto", ["nan", "", None, float("nan"), "  "])
def test_dec_vazio_rejeitado(bruto):
    with pytest.raises(ValueError):
        _dec(bruto)


def test_linha_em_branco_e_pulada():
    df = pd.DataFrame({
        "Plataforma": ["TMB", "TMB", "TMB"],
        "Valor_Plataforma": ["10", None, "30"],
        "Valor_Base_Comissao": ["100", "200", None],
        "Categoria": ["LEAD", "LEAD", "LEAD"],
    })
    assert [x["valor_cobrado"] for x in ler_valores_a_preencher(df)] == [Decimal("10")]


def test_codigo_tmb_conflito_vira_none_para_gerar_atribuicao():
    from scripts.comercial_carga_inicial import codigo_tmb
    assert codigo_tmb("AT13", "AT4") is None          # conflito: o motor marca inconsistente
    assert codigo_tmb("AT13", "AT13") == "AT13"
    assert codigo_tmb(None, "at 9") == "AT9"
    assert codigo_tmb(float("nan"), None) is None
    vendas = pd.DataFrame({"transacao": ["2281968"], "nome": ["Izabela"]})
    assert montar_atribuicoes(vendas, {"2281968": codigo_tmb("AT13", "AT4")},
                              {"Izabela": "AT13"}) == {"2281968": "AT13"}


def test_regras_historicas_da_carga():
    from datetime import date

    from scripts.comercial_carga_inicial import _regras, categorias_apostila
    from frontend.services.comercial.tabelas import ValorBase, escolher_percentual, tipo_forcado

    D = Decimal
    vb = [ValorBase(1, "hotmart", D("397"), D("397"), "APOSTILA MEQ|ESQ", date(2026, 1, 1), None),
          ValorBase(2, "hotmart", D("97"), D("97"), "APOSTILA MEQ B.E.", date(2026, 1, 1), None),
          ValorBase(3, "hotmart", D("863"), D("863"), "CROSS SELL", date(2026, 1, 1), None),
          ValorBase(4, "tmb", D("97"), D("97"), "APOSTILA X", date(2026, 1, 1), None)]
    apost = categorias_apostila(vb)
    assert apost == frozenset({"APOSTILA MEQ|ESQ", "APOSTILA MEQ B.E."})
    regras = _regras(apost)
    assert len({r.id for r in regras}) == len(regras)

    def pct(pl, mod, tipo, cod, dia, cat=None):
        return escolher_percentual(regras, pl, mod, tipo, cod, dia, cat).pct

    # time: parcelado Hotmart muda em 01/10/26
    assert pct("hotmart", "parcelado", "Ativa", "AT4", date(2026, 9, 30)) == D("0.04")
    assert pct("hotmart", "parcelado", "Reativa", "AT4", date(2026, 9, 30)) == D("0.015")
    assert pct("hotmart", "parcelado", "Ativa", "AT4", date(2026, 10, 1)) == D("0.02")
    assert pct("hotmart", "parcelado", "Reativa", "AT4", date(2026, 10, 1)) == D("0.0075")
    # Izabela CS até 31/10/26
    set_ = date(2026, 9, 10)
    assert pct("hotmart", "cartao_pix", "Ativa", "AT13", set_, "APOSTILA MEQ B.E.") == D("0.05")
    assert pct("tmb", "parcelado", "Ativa", "AT13", set_, "UP SELL") == D("0.04")
    assert pct("hotmart", "cartao_pix", "Ativa", "AT13", set_, "CROSS SELL") == D("0.04")
    assert pct("hotmart", "parcelado", "Ativa", "AT13", set_, "CROSS SELL") == D("0.04")
    assert pct("hotmart", "parcelado", "Ativa", "AT13", date(2026, 10, 5), "CROSS SELL") == D("0.02")
    assert pct("tmb", "parcelado", "Ativa", "AT13", date(2026, 11, 2), "UP SELL") == D("0.02")
    assert pct("tmb", "parcelado", "Ativa", "AT13", set_, "LEAD") == D("0.02")
    assert tipo_forcado(regras, "hotmart", "cartao_pix", "AT13", set_, "UP SELL") == "Ativa"
    assert tipo_forcado(regras, "hotmart", "cartao_pix", "AT13", set_, "LEAD") is None
    assert tipo_forcado(regras, "hotmart", "cartao_pix", "AT13", date(2026, 11, 1), "UP SELL") is None
    assert tipo_forcado(regras, "hotmart", "cartao_pix", "AT9", set_, "UP SELL") is None
