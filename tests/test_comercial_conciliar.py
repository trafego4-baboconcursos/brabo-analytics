"""Conciliação sistema x planilha (pura, sem banco/planilha real)."""
from datetime import datetime
from decimal import Decimal

import pandas as pd

from frontend.services.comercial.calculo import LinhaComissao
from scripts.comercial_conciliar import COLUNAS, conciliar

D = Decimal


def linha(tx, base="1477", pct="0.04", tipo="Ativa", quem="Ediléia", sit="elegivel",
          motivo=None, papel="venda"):
    b, p = (D(base) if base else None), (D(pct) if pct else None)
    valor = b * p if b is not None and p is not None and sit == "elegivel" else D("0")
    return LinhaComissao(tx, "hotmart", papel, quem, "AT4", datetime(2026, 10, 5), tipo,
                         "cartao_pix", "LEAD", b, p, valor, sit, motivo, 1, False)


def planilha(*linhas):
    return pd.DataFrame([dict(transacao=t, vendedor=v, tipo=ti, pct=D(p), base=D(b),
                              valor=D(b) * D(p)) for t, v, ti, p, b in linhas])


def test_quatro_casos():
    sis = [linha("HP1"), linha("HP3"), linha("HP4", pct="0.02"),
           linha("HP1", papel="participacao", quem="Rafael Batista", pct="0.003")]
    pla = planilha(("HP1", "Edileia", "Ativa", "0.04", "1477"),
                   ("HP2", "Ediléia", "Ativa", "0.04", "1477"),
                   ("HP4", "Ediléia", "Ativa", "0.04", "1477"))
    df = conciliar(sis, pla)
    assert list(df.columns) == COLUNAS
    causas = dict(zip(df["transacao"], df["causa"]))
    assert causas == {"HP1": "ok", "HP2": "so_planilha", "HP3": "so_sistema", "HP4": "pct"}
    hp4 = df[df["transacao"] == "HP4"].iloc[0]
    assert hp4["valor_sistema"] == D("29.54") and hp4["valor_planilha"] == D("59.08")


def test_vendedor_vem_antes_e_inconsistente_vira_base():
    sis = [linha("A", quem="Izabela"), linha("B", base=None, pct=None, sit="inconsistente",
                                             motivo="sem_valor_base"),
           linha("C", sit="cancelada"), linha("D", sit="inconsistente", motivo="sem_regra")]
    pla = planilha(("A", "Ediléia", "Ativa", "0.04", "1477"), ("B", "Ediléia", "Ativa", "0.04", "1477"),
                   ("C", "Ediléia", "Ativa", "0.04", "1477"))
    df = conciliar(sis, pla).set_index("transacao")
    assert df.loc["A", "causa"] == "vendedor"
    assert df.loc["B", "causa"] == "base" and df.loc["B", "detalhe"] == "inconsistente:sem_valor_base"
    assert df.loc["C", "causa"] == "so_planilha" and df.loc["C", "detalhe"] == "cancelada"
    assert df.loc["D", "causa"] == "so_sistema" and df.loc["D", "detalhe"] == "inconsistente:sem_regra"


def test_pct_pequeno_nao_cai_na_tolerancia_de_dinheiro():
    """2% x 1,5% diferem 0,005: precisa sair como pct, não como so_planilha."""
    sis = [linha("E", base="1558.02", pct="0.015", tipo="Reativa")]
    pla = planilha(("E", "Ediléia", "Reativa", "0.02", "1558.02"))
    assert conciliar(sis, pla)["causa"].tolist() == ["pct"]


def test_atribuicao_completada_marca_detalhe():
    sis = [linha("T1"), linha("T2")]
    pla = planilha(("T1", "Ediléia", "Ativa", "0.04", "1477"), ("T2", "Ediléia", "Ativa", "0.04", "1477"))
    df = conciliar(sis, pla, completadas=frozenset({"T2"})).set_index("transacao")
    assert df.loc["T1", "detalhe"] == "elegivel"
    assert df.loc["T2", "detalhe"] == "elegivel atribuicao_completada" and df.loc["T2", "causa"] == "ok"
