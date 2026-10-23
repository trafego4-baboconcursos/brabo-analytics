"""O aquecimento é sequencial e o servidor reinicia a cada deploy: quem tem o carrinho aberto tem que ir primeiro,
senão fica atrás dos outros e nunca é aquecido (BV-26, 23/10/26: 3 dias com número velho)."""
from datetime import date, timedelta
from types import SimpleNamespace as L

import frontend.services.prewarm as pw


def _l(code, product, dias_fim=10):
    return L(code=code, product=product, data_fim=date.today() + timedelta(days=dias_fim))


def test_carrinho_aberto_vai_primeiro_e_o_resto_mantem_a_ordem(monkeypatch):
    lancs = [_l("PI-NOV-26", "INSS"), _l("PES-NOV-26", "TJ-SP"), _l("BV-26", "Black Vitalícia")]
    monkeypatch.setattr(pw, "find_previous_launch", lambda l, todos: None)
    monkeypatch.setattr(pw, "carrinho_aberto", lambda code: code == "BV-26")
    assert [l.code for l in pw.select_launches_to_warm(lancs)] == ["BV-26", "PI-NOV-26", "PES-NOV-26"]


def test_sem_carrinho_aberto_nada_muda(monkeypatch):
    lancs = [_l("PI-NOV-26", "INSS"), _l("PES-NOV-26", "TJ-SP")]
    monkeypatch.setattr(pw, "find_previous_launch", lambda l, todos: None)
    monkeypatch.setattr(pw, "carrinho_aberto", lambda code: False)
    assert [l.code for l in pw.select_launches_to_warm(lancs)] == ["PI-NOV-26", "PES-NOV-26"]


def test_erro_ao_ler_o_carrinho_nao_derruba_o_aquecimento(monkeypatch):
    def quebra(code):
        raise RuntimeError("banco fora")

    lancs = [_l("PI-NOV-26", "INSS"), _l("BV-26", "Black Vitalícia")]
    monkeypatch.setattr(pw, "find_previous_launch", lambda l, todos: None)
    monkeypatch.setattr(pw, "carrinho_aberto", quebra)
    assert {l.code for l in pw.select_launches_to_warm(lancs)} == {"PI-NOV-26", "BV-26"}
