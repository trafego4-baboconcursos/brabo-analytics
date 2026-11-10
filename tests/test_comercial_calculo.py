from dataclasses import replace
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


RAFA_AT12 = Participacao(1, "Rafael Batista", D("0.003"), D("0.001"), date(2026, 1, 1), None, "AT12")


def test_participacao_casa_por_codigo_mesmo_com_vendedor_renomeado():
    c = cad(part=[RAFA_AT12])
    c.vendedores["AT12"] = "Rafael B."
    ls = calcular([venda(cod="AT12")], c, [], HOJE)
    assert [l.papel for l in ls] == ["venda"]


def test_participacao_sem_codigo_gera_linha_em_venda_de_outro():
    rl = Participacao(2, "Rafael Lago", D("0.003"), D("0.001"), date(2026, 1, 1), None)
    ls = calcular([venda(cod="AT4")], cad(part=[rl]), [], HOJE)
    assert [l.papel for l in ls] == ["venda", "participacao"]


def test_resumo_separa_elegivel_de_prevista():
    ant = venda("HP1", data=datetime(2026, 10, 5, 10))
    rec = venda("HP2", data=datetime(2026, 11, 28, 10))
    ls = calcular([ant, rec], cad(), [], HOJE)
    r = resumo_por_beneficiario(ls)["Ediléia"]
    assert r["total"] == r["elegivel"] + r["prevista"]
    assert r["elegivel"] + r["prevista"] == D("138.08") and r["prevista"] > 0


# ---------------------------------------------------------------- Fase 2: regras históricas

CS = frozenset({"CROSS SELL", "UP SELL"})
JANELA_SET = Janela("PI-SET-26", "INSS", datetime(2026, 9, 7), datetime(2026, 9, 14, 23, 59, 59),
                    frozenset({"6856971"}), frozenset())


def _com_part(c):
    c.participacoes.append(RAFA_AT12)
    return c


def cad_izabela():
    c = cad()
    c.vendedores["AT13"] = "Izabela"
    c.valores_base.append(ValorBase(3, "hotmart", D("863"), D("863"), "CROSS SELL", date(2026, 1, 1), None))
    c.regras.append(RegraPercentual(9, "hotmart", "cartao_pix", "Ativa", D("0.04"), "AT13",
                                    date(2026, 1, 1), date(2026, 10, 31), CS, "Ativa"))
    return c


def test_parcelado_hotmart_por_data_da_venda():
    c = cad()
    c.regras += [RegraPercentual(3, "hotmart", "parcelado", "Ativa", D("0.04"), None, date(2026, 1, 1), date(2026, 9, 30)),
                 RegraPercentual(4, "hotmart", "parcelado", "Ativa", D("0.02"), None, date(2026, 10, 1), None)]
    [a] = calcular([venda(mod="parcelado", data=datetime(2026, 9, 15, 10))], c, [], HOJE)
    [b] = calcular([venda(mod="parcelado", data=datetime(2026, 10, 1, 10))], c, [], HOJE)
    assert (a.pct, b.pct) == (D("0.04"), D("0.02"))


def test_izabela_cross_sell_na_janela_vira_ativa():
    v = venda(cod="AT13", valor="863", data=datetime(2026, 9, 9, 10))
    [l] = calcular([v], cad_izabela(), [JANELA_SET], HOJE)
    assert (l.tipo, l.pct, l.regra_id, l.valor, l.categoria) == ("Ativa", D("0.04"), 9, D("34.52"), "CROSS SELL")


def test_izabela_lead_na_janela_continua_reativa():
    v = venda(cod="AT13", valor="1726", data=datetime(2026, 9, 9, 10))
    [l] = calcular([v], cad_izabela(), [JANELA_SET], HOJE)
    assert (l.tipo, l.pct, l.regra_id) == ("Reativa", D("0.015"), 2)


def test_outra_vendedora_cross_sell_na_janela_e_ativa():
    # regra do Rafael Batista (10/11/26): Up/Cross Sell não tem Reativa, para qualquer vendedora
    v = venda(cod="AT4", valor="863", data=datetime(2026, 9, 9, 10))
    [l] = calcular([v], cad_izabela(), [JANELA_SET], HOJE)
    assert (l.tipo, l.pct) == ("Ativa", D("0.04"))


def test_izabela_cross_sell_depois_do_fim_da_condicao_e_ativa_com_pct_do_time():
    # fim da condição da Izabela (31/10) volta o % do time, mas Cross Sell segue Ativa (10/11/26)
    j = Janela("PI-NOV-26", "INSS", datetime(2026, 11, 2), datetime(2026, 11, 9, 23, 59, 59),
               frozenset({"6856971"}), frozenset())
    v = venda(cod="AT13", valor="863", data=datetime(2026, 11, 3, 10))
    [l] = calcular([v], cad_izabela(), [j], HOJE)
    assert (l.tipo, l.pct) == ("Ativa", D("0.04"))


def test_participacao_segue_tipo_forcado():
    v = venda(cod="AT13", valor="863", data=datetime(2026, 9, 9, 10))
    ls = calcular([v], _com_part(cad_izabela()), [JANELA_SET], HOJE)
    p = [l for l in ls if l.papel == "participacao"][0]
    assert (p.tipo, p.pct) == ("Ativa", D("0.003"))


def test_cancelada_10_dias_depois_fica_a_verificar_e_conta_como_prevista():
    v = venda(data=datetime(2026, 10, 5, 10), cancelada_em=datetime(2026, 10, 15, 10))
    ls = calcular([v], _com_part(cad()), [], HOJE)
    assert [(l.papel, l.situacao) for l in ls] == [("venda", "reembolso_a_verificar"),
                                                    ("participacao", "reembolso_a_verificar")]
    assert ls[0].valor == D("69.04")
    r = resumo_por_beneficiario(ls)["Ediléia"]
    assert (r["prevista"], r["elegivel"], r["total"], r["Ativa"]) == (D("69.04"), D("0"), D("69.04"), D("69.04"))


def test_decisao_de_reembolso():
    v = venda(data=datetime(2026, 10, 5, 10), cancelada_em=datetime(2026, 10, 15, 10))
    c = _com_part(cad())
    c.decisoes_reembolso["HP1"] = "tira"
    assert [(l.situacao, l.valor) for l in calcular([v], c, [], HOJE)] == [("cancelada", D("0"))]
    c.decisoes_reembolso["HP1"] = "mantem"
    ls = calcular([v], c, [], HOJE)
    assert [(l.papel, l.situacao) for l in ls] == [("venda", "elegivel"), ("participacao", "elegivel")]
    assert ls[0].valor == D("69.04")


def test_cancelada_ate_7_dias_continua_cancelada_mesmo_com_decisao():
    v = venda(data=datetime(2026, 10, 5, 10), cancelada_em=datetime(2026, 10, 9, 10))
    c = cad()
    c.decisoes_reembolso["HP1"] = "mantem"
    assert [(l.situacao, l.valor) for l in calcular([v], c, [], HOJE)] == [("cancelada", D("0"))]


def test_cadastros_decisoes_reembolso_padrao_vazio():
    assert Cadastros().decisoes_reembolso == {}


def test_base_cai_no_valor_alternativo_so_quando_o_principal_nao_acha():
    from dataclasses import replace
    c = cad()
    c.valores_base.append(ValorBase(3, "hotmart", D("899.40"), D("863"), "CROSS SELL", date(2026, 1, 1), None))
    [l] = calcular([replace(venda(valor="674.31"), valores_alternativos=(D("899.40"),))], c, [], HOJE)
    assert (l.valor_base, l.situacao) == (D("863"), "elegivel")
    [l2] = calcular([replace(venda(valor="1726"), valores_alternativos=(D("899.40"),))], c, [], HOJE)
    assert l2.valor_base == D("1726")  # principal achou: alternativo não é usado
    [l3] = calcular([replace(venda(valor="12.34"), valores_alternativos=(D("55.55"),))], c, [], HOJE)
    assert (l3.situacao, l3.motivo) == ("inconsistente", "sem_valor_base")


def test_linha_guarda_produto():
    [l] = calcular([venda()], cad(), [], HOJE)
    assert l.produto == "Mentoria"


def test_venda_da_camila_vira_papel_ia_sem_comissao():
    v = replace(venda(cod=None), oferta="COM. LEAD - Camila")
    ls = calcular([v], cad(part=[RAFA]), [], HOJE)
    assert [(l.papel, l.beneficiario, l.vendedor_codigo, l.valor, l.motivo, l.situacao) for l in ls] ==         [("ia", "Camila", None, D("0"), None, "elegivel")]
    assert ls[0].valor_base == D("1726")


def test_camila_cancelada_segue_regra_dos_7_dias():
    v = replace(venda(cod=None), oferta="COM. LEAD - Camila", cancelada_em=datetime(2026, 10, 7))
    [l] = calcular([v], cad(), [], HOJE)
    assert (l.papel, l.situacao) == ("ia", "cancelada")


def test_camila_com_atribuicao_manual_vira_venda():
    v = replace(venda(cod=None), oferta="COM. LEAD - Camila")
    [l] = calcular([v], cad(atrib={"HP1": "AT4"}), [], HOJE)
    assert (l.papel, l.vendedor_codigo) == ("venda", "AT4")


def test_camila_fora_do_resumo_e_dos_totais_congelados():
    from frontend.services.comercial.fechamento import totais
    v = replace(venda(cod=None), oferta="COM. LEAD - Camila")
    ls = calcular([v, venda(tx="HP2")], cad(), [], HOJE)
    assert "Camila" not in resumo_por_beneficiario(ls)
    t = totais(ls, {})
    assert "Camila" not in t["por_beneficiario"] and t["linhas"] == 1


def test_up_e_cross_sell_sao_sempre_ativa_mesmo_na_janela_reativa():
    """Rafael Batista, 10/11/26: Ativa × Reativa só vale para aluno novo; Up Sell e Cross Sell são
    sempre Ativa — pela categoria do valor-base ou pelo prefixo do nome do preço padronizado."""
    from dataclasses import replace
    j = Janela("PI-OUT-26", "INSS", datetime(2026, 10, 5), datetime(2026, 10, 12, 23, 59, 59), frozenset({"6856971"}), frozenset())
    c = cad()
    c.valores_base.append(ValorBase(3, "hotmart", D("899.40"), D("863"), "CROSS SELL", date(2026, 1, 1), None))
    c.valores_base.append(ValorBase(4, "hotmart", D("499.90"), D("479"), "UP SELL", date(2026, 1, 1), None))
    [cross] = calcular([venda(valor="899.40")], c, [j], HOJE)
    [up] = calcular([venda(tx="HP2", valor="499.90")], c, [j], HOJE)
    [lead] = calcular([venda(tx="HP3")], c, [j], HOJE)
    assert (cross.tipo, up.tipo, lead.tipo) == ("Ativa", "Ativa", "Reativa")
    assert cross.valor == D("863") * D("0.04")
    v = replace(venda(tx="HP4"), oferta="CrossSell Mentoria Vitalícia TJSP Cartão 12x - COM. LEAD - AT4")
    [pelo_nome] = calcular([v], c, [j], HOJE)
    assert pelo_nome.tipo == "Ativa"
    v2 = replace(venda(tx="HP5"), oferta="UpSell Mentoria Vitalícia TJSP Cartão 12x - COM. LEAD - AT4")
    assert calcular([v2], c, [j], HOJE)[0].tipo == "Ativa"
