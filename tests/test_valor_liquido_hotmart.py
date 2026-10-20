"""Receita líquida da Hotmart: sem faturamento_liquido, desconta a taxa (20/10/26)."""
from frontend.db_readers._vendas_comum import valor_sem_impostos_liquido


def num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def test_desconta_a_taxa_de_processamento():
    row = {"valor_de_compra_sem_impostos": "1165.68", "taxa_de_processamento": "56.95"}
    assert round(valor_sem_impostos_liquido(row, num), 2) == 1108.73


def test_sem_taxa_devolve_o_valor_sem_impostos():
    assert valor_sem_impostos_liquido({"valor_de_compra_sem_impostos": "150"}, num) == 150.0


def test_taxa_invalida_nao_zera_a_venda():
    assert valor_sem_impostos_liquido({"valor_de_compra_sem_impostos": "100", "taxa_de_processamento": "100"}, num) == 100.0
    assert valor_sem_impostos_liquido({"valor_de_compra_sem_impostos": "100", "taxa_de_processamento": "-5"}, num) == 100.0


def test_sem_valor_devolve_vazio():
    assert not valor_sem_impostos_liquido({}, num)
