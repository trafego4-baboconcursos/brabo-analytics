"""Menu Visão Geral: vocabulário da Black só na Black (11/10/26)."""
from frontend.core import _build_funis_nav_groups


def _labels(code):
    grupos = _build_funis_nav_groups(None, code, "index", None, None)
    return {l["page"]: l for l in grupos[0]["links"]}


def test_black_renomeia_e_divide_a_captacao():
    m = _labels("BV-26")
    assert m["pre_qualificacao"]["label"] == "Aquecimento"
    assert m["captacao"]["label"] == "Captação BV"
    assert "trilha=vitalicia" in m["captacao"]["href"]
    assert m["captacao_base_forte"]["label"] == "Captação Base Forte"
    assert "trilha=base-forte" in m["captacao_base_forte"]["href"]


def test_lancamento_normal_nao_muda():
    m = _labels("PI-AGO-26")
    assert m["pre_qualificacao"]["label"] == "Pré-Qualificação"
    assert m["captacao"]["label"] == "Captação"
    assert "captacao_base_forte" not in m


def test_perpetuo_selo_do_menu_usa_nome_curto():
    from frontend.core import _build_perpetuo_nav_items

    itens = {i["slug"]: i for i in _build_perpetuo_nav_items("/perpetuo/pmq-tjsp", None)}
    assert itens["pmq-tjsp"]["curto"] == "PMQ - TJ-SP"
    assert itens["pmq-pbb"]["curto"] == "PMQ - BB"
    assert itens["pmq-tjsp"]["label"] == "Mestre em Questões — TJ-SP"   # a lista mantém o nome completo
    assert all(i["curto"] for i in itens.values())                       # sem nome curto, cai no completo
