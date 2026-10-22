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


# ── Faturamento mensal (aproximado) ─────────────────────────────────────────
from datetime import date  # noqa: E402

from frontend.routes.analytics import _fracao_por_mes, _faturamento_mensal, _rotulo_curto  # noqa: E402


def test_carrinho_que_atravessa_o_mes_e_dividido_pelos_dias():
    # 19/01 a 02/02 = 15 dias: 13 em janeiro e 2 em fevereiro
    f = _fracao_por_mes(date(2026, 1, 19), date(2026, 2, 2), 2026)
    assert round(f[1], 4) == round(13 / 15, 4) and round(f[2], 4) == round(2 / 15, 4)
    assert round(sum(f.values()), 6) == 1.0


def test_dia_fora_do_ano_vai_para_o_mes_mais_proximo():
    f = _fracao_por_mes(date(2025, 12, 30), date(2026, 1, 2), 2026)
    assert set(f) == {1} and f[1] == 1.0


def test_faturamento_mensal_preserva_o_total_e_separa_investimento_de_2025():
    lancs = [L(code="PES-JAN-26", data_fim=date(2026, 2, 2), data_inicio=date(2026, 1, 1)),
             L(code="PI-ABR-26", data_fim=date(2026, 4, 19), data_inicio=date(2026, 3, 9)),
             L(code="PI-NOV-26", data_fim=date(2026, 11, 30), data_inicio=date(2026, 10, 12))]
    resumo = {"PES-JAN-26": {"receita": 1500.0, "vendas": 15}, "PI-ABR-26": {"receita": 400.0, "vendas": 4},
              "PI-NOV-26": {"receita": 0.0, "vendas": 0}}
    carrinhos = {"PES-JAN-26": (date(2026, 1, 19), date(2026, 2, 2)), "PI-ABR-26": (date(2026, 4, 6), date(2026, 4, 19))}
    invest = {(2025, 12): 50.0, (2026, 1): 100.0, (2026, 3): 200.0}
    m = _faturamento_mensal(lancs, resumo, 2026, carrinhos, invest)
    assert len(m["meses"]) == 12
    assert round(sum(x["receita"] for x in m["meses"]), 6) == 1900.0
    assert sum(x["vendas"] for x in m["meses"]) == 19
    assert round(m["meses"][0]["receita"], 2) == round(1500 * 13 / 15, 2)   # janeiro
    assert m["meses"][3]["receita"] == 400.0                                # abril
    assert m["invest_antes"] == 50.0 and m["meses"][0]["invest"] == 100.0 and m["meses"][2]["invest"] == 200.0
    assert m["melhor_mes"] == "Jan"


def test_rotulo_curto():
    assert _rotulo_curto(2_450_000) == "2,5 mi" and _rotulo_curto(850_000) == "850 mil" and _rotulo_curto(0) == ""


# ── Empresa inteira (perpétuo, setor de vendas, distribuição) ───────────────
from frontend.routes.analytics import _empresa_do_ano, _meta_do_ano  # noqa: E402


def _base():
    resumo = {"n_lancamentos": 3, "ranking": [{}], "total": {"receita": 900.0, "vendas": 90, "invest": 100.0}}
    empresa = {"hotmart": {"receita": 700.0, "vendas": 60}, "tmb": {"receita": 400.0, "vendas": 45},
               "invest": {"distribuicao": 30.0, "perpetuo": 5.0, "sem_codigo": 1.0}, "completo": True}
    perp = {"total": {"receita": 10.0, "vendas": 4}}
    return resumo, empresa, perp


def test_setor_de_vendas_e_o_que_sobra_do_total_vendido():
    r = _empresa_do_ano(*_base())
    por = {x["chave"]: x for x in r["linhas"]}
    assert por["lancamentos"]["receita"] == 900.0 and por["perpetuo"]["receita"] == 10.0
    assert por["vendas"]["receita"] == 190.0 and por["vendas"]["vendas"] == 11   # 1100 - 900 - 10 ; 105 - 90 - 4
    assert r["receita"] == 1100.0 and r["vendas"] == 105
    assert round(sum(x["pct"] for x in r["linhas"]), 6) == 100.0


def test_distribuicao_so_tem_investimento_e_o_total_soma_tudo():
    r = _empresa_do_ano(*_base())
    por = {x["chave"]: x for x in r["linhas"]}
    assert por["distribuicao"]["receita"] == 0.0 and por["distribuicao"]["invest"] == 31.0   # 30 + 1 sem código
    assert r["invest"] == 100.0 + 5.0 + 31.0 and r["resultado"] == 1100.0 - 136.0
    assert round(r["roas"], 4) == round(1100.0 / 136.0, 4)


def test_setor_de_vendas_nunca_fica_negativo():
    resumo, empresa, perp = _base()
    empresa["hotmart"]["receita"] = 100.0      # total vendido menor que os lançamentos: dado incompleto
    r = _empresa_do_ano(resumo, empresa, perp)
    assert {x["chave"]: x for x in r["linhas"]}["vendas"]["receita"] == 0.0


def test_meta_usa_o_total_da_empresa_mas_a_media_e_so_dos_lancamentos(monkeypatch):
    monkeypatch.delenv("META_FATURAMENTO_ANUAL_2026", raising=False)
    total = {"receita": 30_000_000.0}
    m = _meta_do_ano(2026, total, [{}, {}, {}], 5, atingido=33_000_000.0)
    assert m["atingido"] == 33_000_000.0 and m["falta"] == 5_000_000.0
    assert m["media_lancamento"] == 10_000_000.0      # 30 mi / 3 lançamentos com venda
    assert m["restantes"] == 2 and m["necessario_por_restante"] == 2_500_000.0


# ── Perpétuo nunca conta dentro de um lançamento ────────────────────────────
def test_ids_do_perpetuo_vem_de_um_lugar_so():
    from frontend.db_readers._vendas_comum import HOTMART_IDS_PERPETUO, HOTMART_IDS_PERPETUO_POR_VERTICAL
    from frontend.db_readers.perpetuo import VERTICALS

    das_verticais = sorted({i for v in VERTICALS.values() for i in v["hotmart"]})
    assert das_verticais == HOTMART_IDS_PERPETUO
    assert {s: v["hotmart"] for s, v in VERTICALS.items()} == HOTMART_IDS_PERPETUO_POR_VERTICAL
    assert "6859776" in HOTMART_IDS_PERPETUO and "8643509" not in HOTMART_IDS_PERPETUO   # Black 2026 não é perpétuo


def test_leitores_de_lancamento_excluem_os_produtos_do_perpetuo():
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "frontend" / "db_readers"
    for arq in ("sales.py", "hotmart.py", "afiliados.py"):
        assert "NOT (codigo_do_produto" in (base / arq).read_text(encoding="utf-8"), arq


# ── Paleta por produto (faixa dos cartões) ──────────────────────────────────
def test_paleta_dos_produtos_e_do_perpetuo():
    import re

    from src.constants import PALETA_PRODUTO, paleta_do_produto

    assert paleta_do_produto("PI")[:3] == ["#009A44", "#F2B83A", "#005EB8"]          # INSS: verde, amarelo, azul 300 C
    assert paleta_do_produto("pes") == ["#FFFFFF", "#C8102E", "#00A859"]            # TJ-SP: branco, vermelho, verde
    assert paleta_do_produto("PBB") == ["#FCFC30", "#465EFF"]                       # BB: RGB 252 252 48 e 70 94 255
    assert len(paleta_do_produto("PERPETUO")) == 3 and paleta_do_produto("XX") == []
    for chave, p in PALETA_PRODUTO.items():
        assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in p["cores"]), chave


def test_paleta_tem_cor_de_destaque_e_pesos_do_tamanho_das_cores():
    import re

    from src.constants import PALETA_PRODUTO

    for chave, p in PALETA_PRODUTO.items():
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", p["destaque"]), chave
        assert len(p["pesos"]) == len(p["cores"]), chave
        assert p["destaque"] in p["cores"], chave


# ── Faixa de resumo por produto, perpétuo e distribuição ───────────────────
def test_sparkline_normaliza_para_a_caixa_do_svg():
    from frontend.db_readers.distribuicao import _sparkline

    pts = [tuple(map(float, p.split(","))) for p in _sparkline([100.0, 150.0, 200.0]).split()]
    assert pts[0][0] == 0.0 and pts[-1][0] == 120.0
    assert pts[0][1] > pts[-1][1]                       # a série sobe -> y diminui (SVG)
    assert all(0 <= y <= 34 for _, y in pts)
    assert _sparkline([5.0]) == "" and _sparkline([]) == ""


def test_totais_das_secoes_perpetuo_e_distribuicao():
    from frontend.routes.analytics import _totais_secoes

    perp = [{"receita": 100.0, "vendas": 10, "invest": 50.0, "receita_30d": 20.0},
            {"receita": 50.0, "vendas": 5, "invest": 0.0, "receita_30d": 5.0}]
    dist = [{"invest": 200.0, "invest_30d": 60.0, "seguidores": 1000, "novos_30d": 30},
            {"invest": 100.0, "invest_30d": 0.0, "seguidores": None, "novos_30d": None}]
    p, d = _totais_secoes(perp, dist)
    assert p["receita"] == 150.0 and p["vendas"] == 15 and p["invest"] == 50.0 and p["roas"] == 3.0
    assert d["invest"] == 300.0 and d["seguidores"] == 1000 and d["novos_30d"] == 30 and d["custo_por_seguidor"] == 2.0
    assert _totais_secoes([], [])[0]["roas"] == 0.0


def test_paleta_da_distribuicao_existe():
    from src.constants import PALETA_PRODUTO

    assert len(PALETA_PRODUTO["DISTRIBUICAO"]["cores"]) == len(PALETA_PRODUTO["DISTRIBUICAO"]["pesos"])
