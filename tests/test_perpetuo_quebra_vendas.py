"""Quebra das vendas do perpétuo: sem vendedor × comercial e preço cheio × com desconto (perpetuo.classificar_vendas)."""
from frontend.db_readers.perpetuo import classificar_vendas


def _venda(transacao, pago, preco_id="P1", produto_id="100", nome="Oferta", liquido=None, **extra):
    d = {"transacao": transacao, "produto_id": produto_id, "codigo_do_produto": produto_id, "produto": "Apostila",
         "preco_id": preco_id, "codigo_do_preco": preco_id, "preco_nome": nome, "pago": str(pago),
         "liquido": liquido if liquido is not None else pago, "tipo_de_cobranca": "", "quantidade_de_cobrancas": None,
         "quantidade_total_de_parcelas": 1}
    d.update(extra)
    return d


def test_canais_somam_o_total_e_a_oferta_com_codigo_at_e_comercial():
    linhas = [_venda(f"T{i}", 397) for i in range(6)] + [_venda("C1", 190, preco_id="CS"), _venda("C2", 190, preco_id="CS")]
    q = classificar_vendas(linhas, {"CS": "AT13"}, {})
    assert q["canais"]["sem_vendedor"]["vendas"] == 6
    assert q["canais"]["comercial"]["vendas"] == 2
    assert q["total"]["vendas"] == 8
    assert q["vendedores"][0]["at"] == "AT13" and q["vendedores"][0]["vendas"] == 2


def test_atribuicao_aprovada_da_transacao_vence_a_oferta():
    linhas = [_venda("T1", 397)] * 1 + [_venda(f"X{i}", 397) for i in range(5)]
    q = classificar_vendas(linhas, {}, {"T1": "AT4"})
    assert q["canais"]["comercial"]["vendas"] == 1
    assert q["vendedores"][0]["at"] == "AT4"


def test_preco_menor_do_mesmo_produto_e_desconto_e_o_maior_relevante_e_a_referencia():
    linhas = [_venda(f"A{i}", 397) for i in range(10)] + [_venda(f"B{i}", 380, preco_id="P2", nome="Atualizada") for i in range(4)]
    q = classificar_vendas(linhas, {}, {})
    prod = q["produtos"][0]
    assert prod["referencia"] == 397.0
    assert (prod["cheio"], prod["desconto"]) == (10, 4)
    assert q["descontos"][0]["oferta"] == "Atualizada" and q["descontos"][0]["vendas"] == 4
    assert q["perda_desconto"] == 4 * 17


def test_diferenca_pequena_nao_e_desconto():
    # 390 é 98,2% de 397: dentro dos 97%, o centavo e a taxa não viram desconto
    linhas = [_venda(f"A{i}", 397) for i in range(8)] + [_venda(f"B{i}", 390) for i in range(2)]
    q = classificar_vendas(linhas, {}, {})
    assert q["total"]["desconto"] == 0


def test_preco_raro_nao_vira_referencia():
    # um R$ 1.000 isolado (1 em 11) não pode virar o "preço cheio" e transformar todas as outras em desconto
    linhas = [_venda(f"A{i}", 397) for i in range(10)] + [_venda("Z", 1000)]
    q = classificar_vendas(linhas, {}, {})
    assert q["produtos"][0]["referencia"] == 397.0
    assert q["total"]["desconto"] == 0


def test_produto_com_poucas_vendas_nao_tem_referencia_e_conta_como_cheio():
    q = classificar_vendas([_venda("A", 100), _venda("B", 50)], {}, {})
    assert q["produtos"][0]["referencia"] is None
    assert (q["total"]["cheio"], q["total"]["desconto"]) == (2, 0)


def test_cobranca_repetida_conta_no_canal_mas_fica_fora_do_preco():
    linhas = [_venda(f"A{i}", 397) for i in range(6)] + [_venda("R", 33, quantidade_de_cobrancas=3, quantidade_total_de_parcelas=12)]
    q = classificar_vendas(linhas, {}, {})
    assert q["total"]["vendas"] == 7
    assert q["total"]["desconto"] == 0  # a parcela de R$ 33 não é "desconto"


def test_sem_vendas_devolve_zeros():
    q = classificar_vendas([], {}, {})
    assert q["total"]["vendas"] == 0 and q["vendedores"] == [] and q["descontos"] == []
