"""Resumo executivo do ano em /lancamentos: soma dos lançamentos do ano (21/10/26)."""
from types import SimpleNamespace as L

from frontend.routes.analytics import _resumo_do_ano


def _l(code, produto="INSS"):
    return L(code=code, product_name=produto, product=produto, accent="#123456")


def test_soma_so_lancamentos_do_ano_e_calcula_derivados():
    lancs = [_l("PI-JAN-26"), _l("PI-ABR-26"), _l("PES-MAR-26", "TJ-SP"), _l("PI-AGO-25")]
    resumo = {
        "PI-JAN-26": {"leads": 1000, "invest": 100.0, "receita": 500.0, "vendas": 10},
        "PI-ABR-26": {"leads": 500, "invest": 100.0, "receita": 300.0, "vendas": 5},
        "PES-MAR-26": {"leads": 500, "invest": 50.0, "receita": 200.0, "vendas": 5},
        "PI-AGO-25": {"leads": 9999, "invest": 9999.0, "receita": 9999.0, "vendas": 99},  # outro ano
    }
    r = _resumo_do_ano(lancs, resumo, ano=2026)
    t = r["total"]
    assert r["n_lancamentos"] == 3
    assert t["receita"] == 1000.0 and t["invest"] == 250.0 and t["vendas"] == 20 and t["leads"] == 2000
    assert t["resultado"] == 750.0 and round(t["roas"], 2) == 4.0
    assert t["ticket"] == 50.0 and t["cac"] == 12.5 and t["cpl"] == 0.125


def test_por_produto_ordenado_e_percentual_fecha_100():
    lancs = [_l("PI-JAN-26"), _l("PES-MAR-26", "TJ-SP")]
    resumo = {"PI-JAN-26": {"receita": 750.0, "invest": 1.0}, "PES-MAR-26": {"receita": 250.0, "invest": 1.0}}
    r = _resumo_do_ano(lancs, resumo, ano=2026)
    assert [p["nome"] for p in r["produtos"]] == ["INSS", "TJ-SP"]
    assert round(sum(p["pct_receita"] for p in r["produtos"]), 6) == 100.0


def test_ranking_ignora_lancamento_sem_venda_e_sem_ano_devolve_none():
    lancs = [_l("PI-JAN-26"), _l("PI-NOV-26")]
    resumo = {"PI-JAN-26": {"receita": 10.0, "invest": 1.0}, "PI-NOV-26": {"receita": 0.0, "invest": 5.0}}
    assert [x["code"] for x in _resumo_do_ano(lancs, resumo, ano=2026)["ranking"]] == ["PI-JAN-26"]
    assert _resumo_do_ano(lancs, resumo, ano=2024) is None
