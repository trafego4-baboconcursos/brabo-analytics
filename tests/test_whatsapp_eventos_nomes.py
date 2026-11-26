"""Filtro por nome de campanha em `leads_grupos_eventos` (26/11/26).

O `ILIKE '%[COD]%'` lia a tabela inteira a cada chamada. Agora o código escolhe, entre os nomes distintos
(~30), os que contêm "[COD]" — a mesma regra do ILIKE — e o banco filtra por igualdade, com índice.
"""
from frontend.db_readers import whatsapp_eventos as we

NOMES = [
    "Projeto INSS [PI-NOV-26]",
    "Grupo VIP [PI-NOV-26]",
    "Projeto INSS [PI-AGO-26]",
    "Grupo VIP [PES-SET-26] ",                 # espaço no fim, como no banco
    "Projeto TJ-SP [PES-SET-26]",
    "Projeto TJ-SP Pós-Edital [PES-PPE-26]",
    "Grupo VIP Pós Edital [PES-PPE-26]",
    "Vitalícia TJ-SP [PES-JAN-26] ",
    "Projeto TJ-SP [PES-JAN-26]",
    "Base Forte 2026",
    "REAB - PBB-NOV-26",                       # sem colchete: o ILIKE também não pegava
]


def test_pega_normal_e_vip_do_lancamento():
    assert we._nomes_do_lancamento("PI-NOV-26", NOMES) == ["Projeto INSS [PI-NOV-26]", "Grupo VIP [PI-NOV-26]"]


def test_mantem_nome_com_espaco_no_fim():
    assert we._nomes_do_lancamento("PES-SET-26", NOMES) == ["Grupo VIP [PES-SET-26] ", "Projeto TJ-SP [PES-SET-26]"]


def test_usa_os_codigos_alternativos():
    assert we._nomes_do_lancamento("PES-NOV-26", NOMES) == [
        "Projeto TJ-SP Pós-Edital [PES-PPE-26]", "Grupo VIP Pós Edital [PES-PPE-26]",
    ]


def test_ignora_maiusculas_como_o_ilike():
    assert we._nomes_do_lancamento("pi-nov-26", NOMES) == ["Projeto INSS [PI-NOV-26]", "Grupo VIP [PI-NOV-26]"]


def test_qualquer_nome_com_o_codigo_entra_como_no_ilike():
    assert we._nomes_do_lancamento("PES-JAN-26", NOMES) == ["Vitalícia TJ-SP [PES-JAN-26] ", "Projeto TJ-SP [PES-JAN-26]"]


def test_sem_colchete_nao_casa():
    assert we._nomes_do_lancamento("PBB-NOV-26", NOMES) == []
