"""Os dois blocos da /whatsapp na Black: Vitalícia (principal) e Base Forte (segundo).

Nasceu de 10/10/26: a `BV_26` estava vazia e a página só tinha a Base Forte; quando a
automação passou a gravar a Vitalícia nela (09/10, 25 grupos), a página seguiu mostrando só
a Base Forte e o Michel não achava a Vitalícia. Sem banco: só as regras de escolha de tabela,
de rótulo e de ordenação.
"""
from __future__ import annotations

import pandas as pd

from frontend.db_readers import whatsapp_alunos as wa
from frontend.db_readers.whatsapp_groups import _candidatos_tabelas
from frontend.db_readers.whatsapp_sheets import _alias_base_forte
from src.constants import rotulos_blocos_whatsapp


def test_black_bloco_principal_e_a_vitalicia_e_o_segundo_e_a_base_forte():
    normal, vip = _candidatos_tabelas("BV-26", "BV_26")
    assert normal == ["BV_26_API", "BV_26"]
    assert "base_forte" in vip and "BV_26_VIP" not in vip


def test_lancamento_normal_nao_muda():
    normal, vip = _candidatos_tabelas("PES-SET-26", "PES_SET_26")
    assert normal == ["PES_SET_26_API", "PES_SET_26"]
    assert vip[0] == "PES_SET_26_VIP_API" and "base_forte" not in vip


def test_rotulos_da_pagina():
    assert rotulos_blocos_whatsapp("BV-26") == {"normal": "Black Vitalícia", "vip": "Base Forte"}
    assert rotulos_blocos_whatsapp("PES-SET-26") == {"normal": "Grupos Normais", "vip": "Grupos VIP"}


def test_sheets_so_separa_a_base_forte_na_black():
    assert _alias_base_forte("BV-26") == "base-forte"
    assert _alias_base_forte("PES-SET-26") == ""      # vazio nunca casa com um launch_code


def test_grupos_da_vitalicia_ordenam_pelo_numero_depois_do_jogo_da_velha():
    """"Desconto Black Vitalícia #7" e "Black Vitalícia 2026 #16": o número não está no começo do nome."""
    linhas = [(f"t{i}", g, "2026-10-09", True, wa.ATIVO_COMPRA, "INSS", "telefone")
              for i, g in enumerate(["Black Vitalícia 2026 #16", "Desconto Black Vitalícia #7",
                                     "Black Vitalícia 2026 #25", "Desconto Black Vitalícia #10"])]
    membros = pd.DataFrame(linhas, columns=["tel", "grupo", "entrada", "no_grupo", "classificacao", "ativo_de", "via"])
    r = wa.resumir(membros, pd.Timestamp("2026-10-10"))
    assert [g["grupo"].split("#")[1] for g in r["por_grupo"]] == ["7", "10", "16", "25"]


def test_candidatos_do_aluno_por_bloco():
    assert wa._candidatos_tabela("BV-26", "vitalicia") == ["BV_26_API", "BV_26"]
    assert "base_forte" in wa._candidatos_tabela("BV-26", "base_forte")
