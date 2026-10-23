"""Produto 8743334 (Black Vitalícia 2026 - AC): regras próprias de parcelas (20/10/26)."""
from frontend.db_readers._vendas_comum import _parcela_unica_info


def _row(**kw):
    base = {"codigo_do_produto": "8743334", "codigo_do_preco": "", "tipo_de_cobranca": None,
            "quantidade_de_cobrancas": "1", "quantidade_total_de_parcelas": "1"}
    base.update(kw)
    return base


def test_drp_vira_24_parcelas():
    por_parcela, repeticao, _cob, parcelas = _parcela_unica_info(_row(codigo_do_preco="ppt48w0vDRP"))
    assert por_parcela is True and repeticao is False and parcelas == 24


def test_cartao_12x_do_total_nao_e_por_parcela():
    por_parcela, repeticao, _cob, parcelas = _parcela_unica_info(
        _row(codigo_do_preco="1kqrcfre", quantidade_total_de_parcelas="12"))
    assert por_parcela is False and repeticao is False and parcelas == 12


def test_drp_na_segunda_cobranca_continua_sendo_repeticao():
    _pp, repeticao, _cob, _par = _parcela_unica_info(_row(codigo_do_preco="ppt48w0vDRP", quantidade_de_cobrancas="2"))
    assert repeticao is True


def test_outro_produto_segue_a_regra_geral():
    por_parcela, _r, _c, parcelas = _parcela_unica_info(
        _row(codigo_do_produto="8643509", codigo_do_preco="abcDRP", quantidade_total_de_parcelas="12"))
    assert por_parcela is True and parcelas == 12


def test_todo_classificador_de_produto_reconhece_escrevente_como_tj():
    """Em 2025 o produto do TJ-SP se chamava "Escrevente 360" (sem "TJ" no nome). Um classificador sem esse ramo
    zerava as vendas de PES-JAN/MAR/JUN/AGO-25 sem erro nenhum (23/10/26)."""
    import re
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "frontend" / "db_readers"
    achados = 0
    for arq in ("afiliados.py", "hotmart.py", "launches.py", "sales.py", "tmb.py"):
        for linha in (base / arq).read_text(encoding="utf-8").splitlines():
            if re.search(r"produto ILIKE '%tj%'", linha):
                achados += 1
                assert "escrevente" in linha, f"{arq}: {linha.strip()}"
    assert achados >= 10
