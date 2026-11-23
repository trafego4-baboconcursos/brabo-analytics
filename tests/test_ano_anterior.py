"""Comparação com o ano anterior no resumo de /lancamentos (PLANO_BACKFILL_2025, etapa 6)."""
from datetime import date
from types import SimpleNamespace as L

from frontend.services.ano_anterior import (
    anexar_serie_anterior,
    cartao_vs,
    codigo_par,
    comparar_meses,
    fontes_faltando,
    pares_do_ano,
    ultimo_mes_fechado,
)


def _mensal(receitas, invests=None, vendas=None):
    invests = invests or [0.0] * 12
    vendas = vendas or [0] * 12
    return {"meses": [{"mes": i + 1, "nome": f"M{i + 1}", "receita": float(receitas[i]),
                       "invest": float(invests[i]), "vendas": vendas[i],
                       "h_receita": 0.0, "h_invest": 0.0} for i in range(12)],
            "invest_antes": 0.0, "melhor_mes": None}


def test_par_e_o_mesmo_produto_e_mes_do_ano_anterior():
    assert codigo_par("PI-JAN-26") == "PI-JAN-25"
    assert codigo_par("pbb-fev-26") == "PBB-FEV-25"
    # Black (código de 2 partes) e código fora do padrão não têm par: aparecem sozinhos
    assert codigo_par("BV-26") is None
    assert codigo_par("PI-NOV") is None


def test_pares_so_com_lancamento_que_existe_no_ano_anterior():
    p = pares_do_ano(["PI-JAN-26", "PES-SET-26", "PBB-FEV-26", "BV-26"], ["PI-JAN-25", "PBB-FEV-25", "PES-AGO-25", "BV-25"])
    assert p == {"PI-JAN-26": "PI-JAN-25", "PBB-FEV-26": "PBB-FEV-25"}


def test_ultimo_mes_fechado():
    assert ultimo_mes_fechado(2026, date(2026, 11, 23)) == 10
    assert ultimo_mes_fechado(2026, date(2026, 1, 15)) == 0
    assert ultimo_mes_fechado(2025, date(2026, 11, 23)) == 12
    assert ultimo_mes_fechado(2027, date(2026, 11, 23)) == 0


def test_comparacao_usa_os_mesmos_meses_fechados_nos_dois_anos():
    atual = _mensal([100] * 12, [50] * 12, [10] * 12)
    ant = _mensal([80] * 12, [40] * 12, [8] * 12)
    atual["meses"][10]["receita"] = 9999   # novembro (em andamento) não entra
    c = comparar_meses(atual, ant, ate_mes=10)
    assert c["atual"]["receita"] == 1000 and c["anterior"]["receita"] == 800
    assert c["atual"]["invest"] == 500 and c["anterior"]["vendas"] == 80
    assert round(c["var"]["receita"], 1) == 25.0
    assert round(c["var"]["invest"], 1) == 25.0
    assert c["var"]["roas"] == 0.0                     # 2,0x nos dois
    assert c["atual"]["cac"] == 5.0 and c["var"]["cac"] == 0.0
    assert c["periodo"] == "Jan–Out"


def test_comparacao_sem_mes_fechado_ou_sem_ano_anterior_nao_aparece():
    assert comparar_meses(_mensal([100] * 12), _mensal([80] * 12), ate_mes=0) is None
    assert comparar_meses(_mensal([100] * 12), _mensal([0] * 12), ate_mes=10) is None


def test_ano_inteiro_e_variacao_sem_base():
    atual = _mensal([10] * 12, [5] * 12, [1] * 12)
    ant = _mensal([10] * 12, [0] * 12, [0] * 12)   # 2025 sem investimento nem matrícula
    c = comparar_meses(atual, ant, ate_mes=12)
    assert c["periodo"] == "o ano todo"
    assert c["var"]["invest"] is None and c["var"]["roas"] is None and c["var"]["cac"] is None


def test_serie_anterior_divide_a_mesma_escala_do_grafico():
    atual = _mensal([100] + [0] * 11, [50] + [0] * 11)
    ant = _mensal([200] + [0] * 11)
    anexar_serie_anterior(atual, ant, 2025)
    m = atual["meses"][0]
    assert atual["ano_anterior"] == 2025
    assert m["receita_ant"] == 200 and m["h_ant"] == 100.0
    assert m["h_receita"] == 50.0 and m["h_invest"] == 25.0   # o teto passou a ser o ano anterior
    assert m["receita_ant_rot"] == "200"


def test_cartao_mostra_variacao_so_com_lancamento_fechado():
    v = cartao_vs({"receita": 1200.0}, {"receita": 1000.0, "roas": 2.5}, "PI-JAN-25", fechado=True)
    assert v["code"] == "PI-JAN-25" and round(v["var_receita"], 1) == 20.0 and v["roas_ant"] == 2.5
    aberto = cartao_vs({"receita": 300.0}, {"receita": 1000.0, "roas": 2.5}, "PI-NOV-25", fechado=False)
    assert aberto["var_receita"] is None and aberto["receita_ant"] == 1000.0
    assert cartao_vs({"receita": 1.0}, {"receita": 0.0}, "X-25", fechado=True) is None


def test_fontes_faltando_ignora_leads():
    assert fontes_faltando(L(has_meta=True, has_google=False, has_vendas=False, has_ac=False)) == ["Google/YouTube", "Vendas"]
    assert fontes_faltando(L(has_meta=True, has_google=True, has_vendas=True, has_ac=False)) == []
