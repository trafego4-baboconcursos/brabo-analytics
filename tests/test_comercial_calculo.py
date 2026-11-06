from datetime import date, datetime
from decimal import Decimal

from frontend.services.comercial.calculo import calcular, resumo_por_beneficiario
from frontend.services.comercial.modelos import Cadastros, Venda
from frontend.services.comercial.regras import Janela
from frontend.services.comercial.tabelas import Participacao, RegraPercentual, ValorBase

D = Decimal
HOJE = datetime(2026, 11, 30)


def venda(tx="HP1", cod="AT4", valor="1726", plat="hotmart", mod="cartao_pix", prod="6856971",
          data=datetime(2026, 10, 5, 10), pago=True, cancelada_em=None, conflito=False):
    return Venda(plat, tx, data, prod, "Mentoria", "COM. LEAD", cod, conflito, mod, None,
                 D(valor), pago, cancelada_em)


def cad(atrib=None, part=()):
    regras = [RegraPercentual(1, "hotmart", "cartao_pix", "Ativa", D("0.04"), None, date(2026, 1, 1), None),
              RegraPercentual(2, "hotmart", "cartao_pix", "Reativa", D("0.015"), None, date(2026, 1, 1), None)]
    base = [ValorBase(1, "hotmart", D("1726"), D("1726"), "LEAD", date(2026, 1, 1), None),
            ValorBase(2, "hotmart", D("89.90"), D("1477"), "LEAD", date(2026, 1, 1), None)]
    return Cadastros({"AT4": "Ediléia", "AT12": "Rafael Batista"}, regras, base, list(part), atrib or {})


RAFA = Participacao(1, "Rafael Batista", D("0.003"), D("0.001"), date(2026, 1, 1), None)


def test_exemplo_do_doc_lead_hotmart_ativa():
    [l] = calcular([venda()], cad(), [], HOJE)
    assert (l.valor_base, l.pct, l.valor, l.tipo, l.situacao) == (D("1726"), D("0.04"), D("69.04"), "Ativa", "elegivel")


def test_exemplo_do_doc_reativa():
    j = Janela("PI-OUT-26", "INSS", datetime(2026, 10, 5), datetime(2026, 10, 12, 23, 59, 59), frozenset({"6856971"}), frozenset())
    [l] = calcular([venda()], cad(), [j], HOJE)
    assert (l.tipo, l.valor) == ("Reativa", D("25.89"))


def test_participacao_rafael_sobre_venda_do_time():
    ls = calcular([venda(valor="89.90")], cad(part=[RAFA]), [], HOJE)
    p = [l for l in ls if l.papel == "participacao"][0]
    assert (p.beneficiario, p.valor_base, p.pct, p.valor) == ("Rafael Batista", D("1477"), D("0.003"), D("4.431"))


def test_venda_do_proprio_beneficiario_nao_gera_participacao():
    ls = calcular([venda(cod="AT12")], cad(part=[RAFA]), [], HOJE)
    assert [l.papel for l in ls] == ["venda"]


def test_sem_base_vira_inconsistente():
    [l] = calcular([venda(valor="12.34")], cad(), [], HOJE)
    assert (l.situacao, l.motivo, l.valor) == ("inconsistente", "sem_valor_base", D("0"))


def test_atribuicao_manual_cobre_venda_sem_codigo():
    [l] = calcular([venda(cod=None)], cad(atrib={"HP1": "AT4"}), [], HOJE)
    assert (l.beneficiario, l.atribuicao_manual, l.valor) == ("Ediléia", True, D("69.04"))
    [l2] = calcular([venda(cod=None)], cad(), [], HOJE)
    assert (l2.situacao, l2.motivo) == ("inconsistente", "sem_codigo")


def test_resumo_soma_sem_arredondar_por_linha():
    ls = calcular([venda("HP1", valor="89.90"), venda("HP2", valor="89.90")], cad(part=[RAFA]), [], HOJE)
    r = resumo_por_beneficiario(ls)
    assert r["Rafael Batista"]["total"] == D("8.862")      # 2 x 4,431, sem arredondar cada uma
    assert r["Ediléia"]["Ativa"] == D("118.16")


def test_cancelada_tem_valor_zero_e_sem_participacao():
    v = venda(cancelada_em=datetime(2026, 10, 8))
    ls = calcular([v], cad(part=[RAFA]), [], HOJE)
    assert [(l.papel, l.situacao, l.valor) for l in ls] == [("venda", "cancelada", D("0"))]
    assert ls[0].valor_base == D("1726")


def test_nao_paga_nao_gera_linha():
    assert calcular([venda(pago=False)], cad(), [], HOJE) == []


def test_codigo_fora_do_cadastro_vira_vendedor_n():
    [l] = calcular([venda(cod="AT6")], cad(), [], HOJE)
    assert l.beneficiario == "Vendedor 6"
    assert l.vendedor_codigo == "AT6"


def test_conflito_de_codigo_e_inconsistente():
    [l] = calcular([venda(conflito=True)], cad(), [], HOJE)
    assert (l.situacao, l.motivo, l.valor) == ("inconsistente", "conflito_codigo", D("0"))
    [m] = calcular([venda(conflito=True)], cad(atrib={"HP1": "AT4"}), [], HOJE)
    assert (m.situacao, m.atribuicao_manual) == ("elegivel", True)


def test_sem_regra_e_inconsistente():
    [l] = calcular([venda(mod="parcelado")], cad(), [], HOJE)
    assert (l.situacao, l.motivo) == ("inconsistente", "sem_regra")


def test_tmb_usa_base_por_categoria_quando_tabela_nao_acha():
    c = cad()
    c.regras.append(RegraPercentual(3, "tmb", "parcelado", "Ativa", D("0.02"), None, date(2026, 1, 1), None))
    v = Venda("tmb", "T1", datetime(2026, 10, 5), "x", "INSS", "o", "AT4", False, "parcelado", "LEAD", D("99"), True, None)
    [l] = calcular([v], c, [], HOJE)
    assert (l.valor_base, l.valor) == (D("1879.34"), D("37.5868"))
