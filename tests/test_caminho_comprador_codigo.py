import pandas as pd

from frontend.db_readers.caminho_comprador import _codigo_anuncio


def test_codigo_do_anuncio_vem_do_term_e_cai_para_o_content():
    term = pd.Series(["ad110 - banco", None, "xyz"])
    content = pd.Series([None, "AD7-foo", "AD9"])
    assert list(_codigo_anuncio(term, content)) == ["AD110", "AD7", "AD9"]


def test_nenhum_comprador_com_codigo_nao_estoura_o_accessor_str():
    # coluna toda sem ADxxx: no pandas 2.x isso virava object/float e quebrava o debriefing inteiro
    vazio = pd.Series([None, None], dtype=object)
    r = _codigo_anuncio(vazio, vazio)
    assert r.isna().all() and len(r) == 2
