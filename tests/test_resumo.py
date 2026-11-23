"""/resumo: título do lançamento, nome de produto sem sufixo de oferta e parser de horário."""
from datetime import datetime

from frontend.db_readers._vendas_comum import parse_ts_brt
from frontend.services.resumo import _SUFIXO_OFERTA, titulo_do_lancamento


def test_titulo_do_lancamento():
    assert titulo_do_lancamento("PES-SET-26") == "Projeto Escrevente de Setembro de 2026 [PES-SET-26]"
    assert titulo_do_lancamento("PI-NOV-26") == "Projeto INSS de Novembro de 2026 [PI-NOV-26]"
    assert titulo_do_lancamento("PBB-ABR-26") == "Projeto Banco do Brasil de Abril de 2026 [PBB-ABR-26]"
    assert titulo_do_lancamento("XYZ") == "Projeto [XYZ]"


def test_sufixo_de_oferta_do_tmb_sai_do_nome_do_produto():
    limpar = lambda s: _SUFIXO_OFERTA.sub("", s).strip()  # noqa: E731
    assert limpar("Mentoria Vitalícia - TJSP - Lead17990") == "Mentoria Vitalícia - TJSP"
    assert limpar("Mentoria Vitalícia - TJSP - Crossell8995") == "Mentoria Vitalícia - TJSP"
    assert limpar("Mentoria Vitalícia - TJSP - UpSell8909") == "Mentoria Vitalícia - TJSP"
    assert limpar("Mentoria Vitalícia - TJSP") == "Mentoria Vitalícia - TJSP"
    assert limpar("TJSP Vitalicio 24x") == "TJSP Vitalicio 24x"


def test_parse_ts_brt_formatos():
    assert parse_ts_brt("1794449416000") == datetime(2026, 11, 11, 23, 10, 16)   # epoch ms (UTC -> Brasília)
    assert parse_ts_brt("1794449416") == datetime(2026, 11, 11, 23, 10, 16)      # epoch s
    assert parse_ts_brt("12/11/2026 08:21:38") == datetime(2026, 11, 12, 8, 21, 38)
    assert parse_ts_brt("2026-11-12T11:21:38+00:00") == datetime(2026, 11, 12, 8, 21, 38)
    assert parse_ts_brt("") is None and parse_ts_brt(None) is None
