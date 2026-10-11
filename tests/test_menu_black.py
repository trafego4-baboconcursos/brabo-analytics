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
