from datetime import date, datetime

from frontend.services.comercial.regras import (
    categoria_tmb,
    extrair_codigo_at,
    janela_reativa,
    modalidade_hotmart,
    projeto_do_produto,
    situacao,
    tipo_venda,
)


def test_extrair_codigo_at():
    assert extrair_codigo_at("COM. LEAD - AT9") == "AT9"
    assert extrair_codigo_at("R$ 997,00 preço base (APOSTILA) - at12. - Recorrência") == "AT12"
    assert extrair_codigo_at("COM. R$1197 PARCELAMENTO INTELIGENTE APOSTILA AT 4") == "AT4"
    assert extrair_codigo_at("Organico - Organico") is None
    assert extrair_codigo_at("Black Vitalícia 2026 - BLP") is None
    assert extrair_codigo_at(None) is None


def test_modalidade_hotmart():
    assert modalidade_hotmart("Recuperador Inteligente", "Cartão de Crédito") == "cartao_pix"
    assert modalidade_hotmart(None, "HOTMART_INSTALLMENTS") == "parcelado"
    assert modalidade_hotmart("Parcelado Hotmart - Link exclusivo", "Boleto Bancário") == "parcelado"
    assert modalidade_hotmart("Apenas à vista", "Pix") == "cartao_pix"
    assert modalidade_hotmart("Assinatura", "Cartão de Crédito") == "cartao_pix"


def test_categoria_tmb():
    assert categoria_tmb("MENTORIABBLEAD", None) == "LEAD"
    assert categoria_tmb("MENTORIABBCROSS", None) == "CROSS SELL"
    assert categoria_tmb("MENTORIABBUP", None) == "UP SELL"
    assert categoria_tmb("Organico", "Mentoria Vitalícia - BBSA - Crossell8995") == "CROSS SELL"
    assert categoria_tmb(None, None) is None


def test_projeto_do_produto():
    assert projeto_do_produto("Black Vitalícia 2026 - INSS") == "BLACK"
    assert projeto_do_produto("Mentoria INSS") == "INSS"
    assert projeto_do_produto("Mentoria Vitalícia - TJSP") == "TJ"
    assert projeto_do_produto("Escrevente") == "TJ"
    assert projeto_do_produto("Mentoria BBSA") == "BB"
    assert projeto_do_produto("Banco do Brasil") == "BB"
    assert projeto_do_produto("Outro curso") == "OUTRO"
    assert projeto_do_produto(None) == "OUTRO"


def test_janela_reativa_pes_nov_26():
    j = janela_reativa("PES-NOV-26", date(2026, 11, 9), {"6857003"}, {"29395"})
    assert j.inicio == datetime(2026, 11, 9, 0, 0, 0)
    assert j.fim == datetime(2026, 11, 16, 23, 59, 59)
    assert j.projeto == "TJ"
    j2 = janela_reativa("X", date(2026, 11, 12), set(), set())
    assert j2.inicio == datetime(2026, 11, 9, 0, 0, 0)
    assert j2.projeto == "OUTRO"
    assert janela_reativa("PI-AGO-26", date(2026, 8, 3), set(), set()).projeto == "INSS"
    assert janela_reativa("PBB-AGO-26", date(2026, 8, 3), set(), set()).projeto == "BB"


def test_tipo_venda():
    j = janela_reativa("PES-NOV-26", date(2026, 11, 9), {"6857003"}, {"29395"})
    assert tipo_venda("hotmart", "6857003", None, datetime(2026, 11, 16, 23, 59, 59), [j]) == "Reativa"
    assert tipo_venda("hotmart", "6857003", None, datetime(2026, 11, 17, 0, 0, 0), [j]) == "Ativa"
    assert tipo_venda("hotmart", "6856971", None, datetime(2026, 11, 10, 12, 0), [j]) == "Ativa"
    assert tipo_venda("tmb", "29395", None, datetime(2026, 11, 10, 12, 0), [j]) == "Reativa"
    assert tipo_venda("tmb", "29395", None, datetime(2026, 11, 10, 12, 0), []) == "Ativa"
    assert tipo_venda("tmb", None, "Mentoria Vitalícia - TJSP", datetime(2026, 11, 10, 12, 0), [j]) == "Reativa"
    assert tipo_venda("tmb", None, "Mentoria Vitalícia - INSS", datetime(2026, 11, 10, 12, 0), [j]) == "Ativa"


def test_situacao():
    d = datetime(2026, 10, 28, 10, 0)
    assert situacao(True, d, None, datetime(2026, 11, 4, 10, 1)) == "elegivel"
    assert situacao(True, d, None, datetime(2026, 11, 3, 10, 0)) == "prevista"
    assert situacao(True, d, datetime(2026, 11, 2), datetime(2026, 11, 20)) == "cancelada"
    assert situacao(True, d, datetime(2026, 11, 10), datetime(2026, 11, 20)) == "elegivel"
    assert situacao(False, d, None, datetime(2026, 11, 20)) == "nao_paga"
