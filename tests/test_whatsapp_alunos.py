"""Aluno × não aluno dos membros dos grupos — a agregação da página /whatsapp.

A regra de casamento (plataforma decide quem é aluno; lista de ex-aluno do
Active só marca ex-aluno de quem não é ativo) roda em SQL e foi conferida contra
a análise manual de 05/10/26 (11 diferenças em 16.614 números). Aqui fica a
parte em Python: o resumo que a página mostra.
"""
from __future__ import annotations

import pandas as pd

from frontend.db_readers import whatsapp_alunos as wa

HOJE = pd.Timestamp("2026-10-08")


def _membros(linhas):
    return pd.DataFrame(linhas, columns=["tel", "grupo", "entrada", "no_grupo",
                                         "classificacao", "ativo_de", "via"])


BASE = [
    ("1", "#1 Desafio Base Forte", "2026-09-28", True,  wa.ATIVO_COMPRA, "INSS", "telefone"),
    ("2", "#1 Desafio Base Forte", "2026-09-28", True,  wa.ATIVO_PRORROGADO, "INSS+TJSP", "telefone"),
    ("3", "#2 Desafio Base Forte", "2026-10-07", False, wa.NAO_ALUNO, None, None),
    ("4", "#10 Desafio Base Forte", "2026-10-08", True, wa.EX_ALUNO, None, "e-mail do CRM"),
]


def test_classes_somam_o_total_e_ativo_e_a_soma_das_duas_linhas():
    r = wa.resumir(_membros(BASE), HOJE)
    linhas = {c["rotulo"]: c["n"] for c in r["classes"]}
    assert r["total"] == 4
    assert linhas["Aluno ativo"] == 2
    assert linhas["comprou em 2025–26"] + linhas["turma antiga com acesso prorrogado"] == 2
    assert linhas["Aluno ativo"] + linhas["Ex-aluno"] + linhas["Não aluno"] == 4
    assert r["pct_ativo"] == 50.0 and r["pct_nao"] == 25.0


def test_aluno_de_mais_de_um_expert_conta_nos_dois():
    r = wa.resumir(_membros(BASE), HOJE)
    assert r["por_expert"] == {"Mateus (INSS)": 2, "Ivan (TJ-SP)": 1}


def test_grupos_em_ordem_numerica_nao_alfabetica():
    """#10 vem depois do #2 — em ordem de texto viria antes."""
    r = wa.resumir(_membros(BASE), HOJE)
    assert [g["grupo"].split()[0] for g in r["por_grupo"]] == ["#1", "#2", "#10"]


def test_recentes_sao_os_ultimos_dias():
    r = wa.resumir(_membros(BASE), HOJE)
    assert r["recentes"]["n"] == 2          # 07/10 e 08/10
    assert r["recentes"]["nao_pct"] == 50.0


def test_quem_ainda_esta_no_grupo():
    assert wa.resumir(_membros(BASE), HOJE)["no_grupo"] == 3


def test_fora_da_black_nao_le_nada():
    """Num lançamento normal a régua de hoje responderia outra pergunta."""
    assert wa.read_whatsapp_alunos("PES-SET-26") is None
