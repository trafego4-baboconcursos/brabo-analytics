"""split_hotmart_ids: `hotmart_produto_ids` aceita ids de produto e `oferta:<codigo>`."""
from frontend.utils import split_hotmart_ids


def test_so_produtos():
    assert split_hotmart_ids(["6857003", "8829061"]) == (["6857003", "8829061"], [])


def test_oferta_avulsa_vai_para_a_lista_de_ofertas():
    assert split_hotmart_ids(["6857003", "oferta:izfne8k1"]) == (["6857003"], ["izfne8k1"])


def test_oferta_normaliza_caixa_e_espacos():
    assert split_hotmart_ids([" OFERTA: IZFNE8K1 "]) == ([], ["izfne8k1"])


def test_vazio_e_valores_invalidos():
    assert split_hotmart_ids(None) == ([], [])
    assert split_hotmart_ids([]) == ([], [])
    assert split_hotmart_ids(["oferta:"]) == ([], [])


def test_string_unica():
    assert split_hotmart_ids("oferta:abc123") == ([], ["abc123"])
