import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from baixar_drive_para_analises import lancamento_da_pasta, nome_seguro


def test_pasta_por_produto_e_mes():
    assert lancamento_da_pasta("INSS - Janeiro ") == "PI-JAN-25"
    assert lancamento_da_pasta("TJSP - Março") == "PES-MAR-25"
    assert lancamento_da_pasta("BB - Fevereiro") == "PBB-FEV-25"
    assert lancamento_da_pasta("INSS - Julho") == "PI-JUL-25"
    assert lancamento_da_pasta("TJSP - Junho ") == "PES-JUN-25"


def test_pasta_pelo_codigo_no_nome():
    assert lancamento_da_pasta("PES-AGO-25 (pós-edital)") == "PES-AGO-25"
    assert lancamento_da_pasta("INSS - Reabertura | PI-JUL-25") == "PI-JUL-25"
    assert lancamento_da_pasta("pbb-ago-25") == "PBB-AGO-25"


def test_pasta_sem_lancamento_e_nome_seguro():
    assert lancamento_da_pasta("Templates - Referências") is None
    assert lancamento_da_pasta("") is None
    assert nome_seguro("Lista: a/b?*.csv") == "Lista_ a_b__.csv"
