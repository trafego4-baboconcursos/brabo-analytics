from datetime import date
from decimal import Decimal

from frontend.services.comercial.tabelas import (
    BASE_TMB_POR_CATEGORIA,
    Participacao,
    RegraPercentual,
    ValorBase,
    buscar_valor_base,
    escolher_percentual,
    participacoes_vigentes,
)

D = Decimal


def rp(i, pl, mod, tipo, pct, vend=None, de=date(2026, 1, 1), ate=None):
    return RegraPercentual(i, pl, mod, tipo, D(pct), vend, de, ate)


def test_regra_de_vendedor_vence_regra_geral():
    regras = [rp(1, "hotmart", "cartao_pix", "Ativa", "0.04"), rp(2, "hotmart", "cartao_pix", "Ativa", "0.02", vend="AT12")]
    assert escolher_percentual(regras, "hotmart", "cartao_pix", "Ativa", "AT12", date(2026, 10, 5)).pct == D("0.02")
    assert escolher_percentual(regras, "hotmart", "cartao_pix", "Ativa", "AT4", date(2026, 10, 5)).pct == D("0.04")


def test_vigencia():
    regras = [rp(1, "hotmart", "parcelado", "Ativa", "0.10", de=date(2026, 1, 1), ate=date(2026, 6, 30)),
              rp(2, "hotmart", "parcelado", "Ativa", "0.02", de=date(2026, 7, 1))]
    assert escolher_percentual(regras, "hotmart", "parcelado", "Ativa", "AT4", date(2026, 6, 30)).id == 1
    assert escolher_percentual(regras, "hotmart", "parcelado", "Ativa", "AT4", date(2026, 7, 1)).id == 2
    assert escolher_percentual([], "hotmart", "parcelado", "Ativa", "AT4", date(2026, 7, 1)) is None


def test_empate_gerais_vence_vigente_de_mais_recente():
    regras = [rp(1, "hotmart", "parcelado", "Ativa", "0.10", de=date(2026, 1, 1)),
              rp(2, "hotmart", "parcelado", "Ativa", "0.02", de=date(2026, 7, 1))]
    assert escolher_percentual(regras, "hotmart", "parcelado", "Ativa", None, date(2026, 10, 1)).id == 2


def test_valor_base_por_valor_cobrado():
    t = [ValorBase(1, "hotmart", D("89.90"), D("1477"), "LEAD", date(2026, 1, 1), None)]
    assert buscar_valor_base(t, "hotmart", D("89.9"), date(2026, 10, 1)).valor_base == D("1477")
    assert buscar_valor_base(t, "hotmart", D("89.91"), date(2026, 10, 1)) is None
    assert buscar_valor_base(t, "tmb", D("89.90"), date(2026, 10, 1)) is None


def test_base_tmb_por_categoria():
    assert BASE_TMB_POR_CATEGORIA == {"LEAD": D("1879.34"), "UP SELL": D("495.68"), "CROSS SELL": D("939.67")}


def test_participacoes_vigentes():
    lista = [Participacao(1, "Rafael Batista", D("0.003"), D("0.001"), date(2026, 1, 1), None),
             Participacao(2, "Antigo", D("0.01"), D("0.01"), date(2025, 1, 1), date(2025, 12, 31))]
    r = participacoes_vigentes(lista, date(2026, 10, 1))
    assert [p.id for p in r] == [1]
