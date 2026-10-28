import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("corrigir_utm_gclid", Path(__file__).resolve().parents[1] / "scripts" / "corrigir_utm_gclid.py")
cug = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cug)


def test_norm_decodifica_url_e_normaliza():
    assert cug._norm("[GA][capta%C3%A7%C3%A3o][Quente]") == "[ga][captação][quente]"
    assert cug._norm(None) == ""


def test_sem_data_tira_so_o_colchete_de_data():
    assert cug._sem_data("[ga][captação][quente][principal][pi-ago-26][27.07.26]") == "[ga][captação][quente][principal][pi-ago-26]"
    assert cug._sem_data("[ga][x][pi-ago-26]") == "[ga][x][pi-ago-26]"


def test_classificacao_dos_casos_que_apareceram_no_pi_ago_26_e_pbb_ago_26():
    real_esp = "[ga][captação][específico][principal][pi-ago-26][27.07.26]"
    assert cug._classificar(real_esp, real_esp) == "igual"
    # a data de OUTRA campanha (24.03.26) no lugar da certa: o resto do nome é o mesmo
    assert cug._classificar("[ga][captação][específico][principal][pi-ago-26][24.03.26]", real_esp) == "so_a_data"
    # o UTM dizia "principal" e o clique foi numa campanha "potencial"
    assert cug._classificar("[ga][captação][quente][principal][pi-ago-26][27.07.26]",
                            "[ga][captação][quente][potencial][pi-ago-26][27.07.26]") == "outra_campanha"
    # variantes do PBB
    assert cug._classificar("[ga][captação][quente][principal][pbb-ago-26][03.08.26]",
                            "[ga][captação][quente][principal][new-ads][pbb-ago-26][03.08.26]") == "outra_campanha"
    assert cug._classificar("", real_esp) == "sem_campanha_no_utm"


def test_corrigir_congelada_ignora_chamada_vazia():
    from frontend.db_readers.atribuicao_congelada import corrigir_congelada

    assert corrigir_congelada("", {"a@b.c": {}}, origem="x") == 0
    assert corrigir_congelada("PI-AGO-26", {}, origem="x") == 0
    assert corrigir_congelada("PI-AGO-26", {"a@b.c": {}}, origem="") == 0     # sem origem declarada não grava
