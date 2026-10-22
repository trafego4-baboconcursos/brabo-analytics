from datetime import date
from types import SimpleNamespace as L

from src.anos import ano_do_codigo, anos_disponiveis, do_ano, resolver_ano


def test_ano_vem_do_sufixo_do_codigo():
    assert ano_do_codigo("PI-JAN-26") == 2026
    assert ano_do_codigo("BV-25") == 2025
    assert ano_do_codigo("PBB-ABR-27") == 2027
    assert ano_do_codigo("PERPETUO") is None
    assert ano_do_codigo(None) is None


def test_do_ano_filtra_objetos_e_codigos():
    ls = [L(code="PI-JAN-26"), L(code="BV-25"), L(code="PES-NOV-26")]
    assert [l.code for l in do_ano(ls, 2026)] == ["PI-JAN-26", "PES-NOV-26"]
    assert do_ano(["BV-25", "PI-JAN-26"], 2025) == ["BV-25"]


def test_anos_disponiveis_inclui_ano_corrente_e_2027_aparece_sozinho():
    hoje = date(2026, 10, 22)
    assert anos_disponiveis(["BV-25", "PI-JAN-26"], hoje) == [2026, 2025]
    assert anos_disponiveis(["BV-25", "PI-JAN-26", "PI-JAN-27"], hoje) == [2027, 2026, 2025]
    assert anos_disponiveis([], hoje) == [2026]   # virada: sem lançamento, ainda oferece o ano corrente


def test_resolver_ano_ordem_url_cookie_corrente():
    disp = [2027, 2026, 2025]
    hoje = date(2026, 10, 22)
    assert resolver_ano(disp, "2025", "2027", hoje) == 2025
    assert resolver_ano(disp, None, "2027", hoje) == 2027
    assert resolver_ano(disp, "lixo", "1999", hoje) == 2026          # inválidos caem no ano corrente
    assert resolver_ano([2025], None, None, hoje) == 2025            # corrente ausente: mais novo disponível
    assert resolver_ano(disp, None, None, date(2027, 1, 3)) == 2027  # virada de ano
