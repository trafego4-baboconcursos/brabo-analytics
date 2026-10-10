"""Todo CASE produto→projeto precisa reconhecer a Black Vitalícia.

Sem o ramo 'BLACK' o produto caía em 'OUTRO' e nenhuma venda da Black aparecia no
dashboard (achado 10/10/26, antes da abertura do carrinho do BV-26).
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "frontend" / "db_readers"


def test_todo_case_de_projeto_tem_ramo_black():
    for arq in ("sales.py", "hotmart.py", "tmb.py", "afiliados.py", "launches.py"):
        linhas = (RAIZ / arq).read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(linhas):
            if "ILIKE '%inss%' THEN 'INSS'" in ln:
                bloco = " ".join(linhas[max(0, i - 1): i + 1])
                assert "THEN 'BLACK'" in bloco, f"{arq}:{i + 1} sem ramo BLACK"
