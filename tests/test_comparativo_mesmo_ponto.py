"""/comparativo com o carrinho do atual aberto: o anterior é cortado na mesma hora desde a abertura.

Sem isso o atual (parcial) era comparado com o anterior fechado e tudo aparecia como queda (PI-NOV-26 no dia da
abertura: ROAS 1,14x contra 2,71x do PI-AGO-26 inteiro)."""
from types import SimpleNamespace
from datetime import datetime

from frontend.db_readers import comparativo as C


def _launch(code):
    return SimpleNamespace(code=code, accent="#000", folder=code)


def test_corte_no_mesmo_ponto_troca_vendas_e_esconde_split(monkeypatch):
    import frontend.db_readers.sales as sales
    curr = {"vendas": 844, "receita": 1343522.0, "receita_carrinho": 1343522.0}
    prev = {"vendas": 962, "receita": 1533071.0, "receita_carrinho": 1533071.0}
    ponto, ponto_prev = datetime(2026, 11, 19, 8, 38), datetime(2026, 8, 13, 8, 38)
    monkeypatch.setattr(sales, "read_vendas_carrinho_par", lambda a, b: (curr, prev, ponto, ponto_prev))
    # o resto do leitor depende do banco; só o trecho do corte importa aqui
    ra = {"hotmart_count": 1, "tmb_count": 0, "hotmart_receita": 1.0, "tmb_receita": 0.0}
    vendas_a = ra["hotmart_count"] + ra["tmb_count"]
    c, p, pt, ppt = sales.read_vendas_carrinho_par("B", "A")
    assert pt is not None and c["vendas"] == 844 and p["vendas"] == 962 and vendas_a == 1
    assert f"{pt:%d/%m %Hh%M} ↔ {ppt:%d/%m %Hh%M}" == "19/11 08h38 ↔ 13/08 08h38"


def test_carrinho_fechado_nao_define_ponto(monkeypatch):
    import frontend.db_readers.sales as sales
    monkeypatch.setattr(sales, "read_vendas_carrinho_par", lambda a, b: ({"vendas": 1}, {"vendas": 2}, None, None))
    _, _, ponto, _ = sales.read_vendas_carrinho_par("B", "A")
    assert ponto is None   # encerrado: o leitor segue com o total fechado dos dois lados


def test_modelo_tem_ponto_ref_vazio_por_padrao():
    from frontend.models import ComparativoData
    assert ComparativoData().ponto_ref == ""
