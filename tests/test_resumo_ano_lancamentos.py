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


def test_meta_anual_progresso_e_necessario_por_lancamento_restante(monkeypatch):
    monkeypatch.delenv("META_FATURAMENTO_ANUAL_2026", raising=False)
    lancs = [_l("PI-JAN-26"), _l("PI-ABR-26"), _l("PI-NOV-26"), _l("PES-NOV-26", "TJ-SP")]
    resumo = {"PI-JAN-26": {"receita": 20_000_000.0, "invest": 1.0},
              "PI-ABR-26": {"receita": 4_000_000.0, "invest": 1.0},
              "PI-NOV-26": {"receita": 0.0, "invest": 5.0},
              "PES-NOV-26": {"receita": 0.0, "invest": 5.0}}
    m = _resumo_do_ano(lancs, resumo, ano=2026)["meta"]
    assert m["valor"] == 38_000_000.0 and m["atingido"] == 24_000_000.0
    assert round(m["pct"], 1) == 63.2 and m["falta"] == 14_000_000.0
    assert m["restantes"] == 2 and m["necessario_por_restante"] == 7_000_000.0
    assert m["media_lancamento"] == 12_000_000.0 and m["batida"] is False


def test_meta_batida_e_ano_sem_meta(monkeypatch):
    monkeypatch.delenv("META_FATURAMENTO_ANUAL_2026", raising=False)
    r = _resumo_do_ano([_l("PI-JAN-26")], {"PI-JAN-26": {"receita": 50_000_000.0, "invest": 1.0}}, ano=2026)
    assert r["meta"]["batida"] is True and r["meta"]["falta"] == 0.0 and r["meta"]["pct_barra"] == 100.0
    assert _resumo_do_ano([_l("PI-JAN-25")], {"PI-JAN-25": {"receita": 1.0, "invest": 1.0}}, ano=2025)["meta"] is None


def test_meta_pode_ser_trocada_por_variavel_de_ambiente(monkeypatch):
    from src.constants import meta_faturamento_anual
    monkeypatch.setenv("META_FATURAMENTO_ANUAL_2026", "50.000.000,00")
    assert meta_faturamento_anual(2026) == 50_000_000.0
    monkeypatch.setenv("META_FATURAMENTO_ANUAL_2026", "texto invalido")
    assert meta_faturamento_anual(2026) == 38_000_000.0
