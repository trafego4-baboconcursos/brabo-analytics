from datetime import datetime
from decimal import Decimal

from frontend.db_readers.comercial import Venda, normalizar_hotmart, normalizar_tmb, _data_local

BASE = dict(nome_deste_preco="COM. LEAD - AT9", tipo_de_cobranca="Recuperador Inteligente",
            metodo_de_pagamento="Cartão de Crédito", codigo_do_produto="6857003", produto="Mentoria",
            codigo_do_preco="P1", valor_de_compra_sem_impostos=89.9,
            data_da_transacao="2026-10-05T10:00:00", ultimo_evento_em=None)


def test_hotmart_dedupe_e_primeira_cobranca():
    linhas = [dict(BASE, codigo_da_transacao="HP1", status_da_transacao="APPROVED", quantidade_de_cobrancas=1),
              dict(BASE, codigo_da_transacao="HP1", status_da_transacao="COMPLETED", quantidade_de_cobrancas=1),
              dict(BASE, codigo_da_transacao="HP2", status_da_transacao="Completo", quantidade_de_cobrancas=2)]
    v = normalizar_hotmart(linhas)
    assert [x.transacao for x in v] == ["HP1"]
    assert v[0].codigo_at == "AT9" and v[0].pago and v[0].modalidade == "cartao_pix"
    assert v[0].valor_cobrado == Decimal("89.9") and v[0].plataforma == "hotmart"
    assert isinstance(v[0], Venda)


def test_hotmart_nome_nulo_usa_ofertas():
    l = dict(BASE, nome_deste_preco=None, codigo_da_transacao="HP3", status_da_transacao="Completo",
             quantidade_de_cobrancas=None)
    v = normalizar_hotmart([l], ofertas={"P1": "R$ 997 preço base - at12."})
    assert v[0].codigo_at == "AT12" and v[0].oferta == "R$ 997 preço base - at12."
    assert normalizar_hotmart([l])[0].codigo_at is None


def test_hotmart_cancelamento_e_pago():
    ev = datetime(2026, 10, 9, 12, 0)
    l1 = dict(BASE, codigo_da_transacao="A", status_da_transacao="Completo", quantidade_de_cobrancas=1)
    l2 = dict(BASE, codigo_da_transacao="A", status_da_transacao="Reembolsado", quantidade_de_cobrancas=1,
              ultimo_evento_em=ev)
    l3 = dict(BASE, codigo_da_transacao="B", status_da_transacao="CANCELED", quantidade_de_cobrancas=1)
    l4 = dict(BASE, codigo_da_transacao="C", status_da_transacao="Aguardando pagamento", quantidade_de_cobrancas=1)
    a, b, c = normalizar_hotmart([l1, l2, l3, l4])
    assert a.pago and a.cancelada_em == ev
    assert not b.pago and b.cancelada_em == b.data == datetime(2026, 10, 5, 10, 0)
    assert not c.pago and c.cancelada_em is None


def test_data_local_tres_formatos():
    assert _data_local("05/10/2026 10:30:15") == datetime(2026, 10, 5, 10, 30, 15)
    assert _data_local("1790125220000") == datetime(2026, 9, 22, 22, 0, 20)
    assert _data_local("1790125220") == datetime(2026, 9, 22, 22, 0, 20)
    assert _data_local("2026-10-05T13:00:00Z") == datetime(2026, 10, 5, 10, 0)
    assert _data_local("2026-10-05T13:00:00-03:00") == datetime(2026, 10, 5, 13, 0)
    assert _data_local("2026-10-05T10:00:00") == datetime(2026, 10, 5, 10, 0)
    assert _data_local("lixo") is None and _data_local(None) is None


def test_tmb_codigo_fallback_e_conflito():
    b = dict(status="Efetivado", data_efetivado="2026-10-05T08:00:00", data_cancelamento=None,
             produto="Mentoria", oferta="Oferta", utm_campaign="MENTORIABBLEAD", ticket="1879.34", lancamento_id=29395)
    v = normalizar_tmb([dict(b, pedido="1", utm_content="", utm_last_content="AT11"),
                        dict(b, pedido="2", utm_content="AT4", utm_last_content="AT9"),
                        dict(b, pedido="TESTE", utm_content="AT4", utm_last_content=None),
                        dict(b, pedido="3", utm_content=None, utm_last_content=None, ticket="abc"),
                        dict(b, pedido="4", utm_content=None, utm_last_content=None, lancamento_id=None,
                             status="Cancelado", data_cancelamento=datetime(2026, 10, 7))])
    assert [x.transacao for x in v] == ["1", "2", "4"]
    assert v[0].codigo_at == "AT11" and not v[0].conflito_codigo and v[0].pago
    assert v[0].produto_id == "29395" and v[0].categoria == "LEAD" and v[0].modalidade == "parcelado"
    assert v[0].valor_cobrado == Decimal("1879.34")
    assert v[1].codigo_at is None and v[1].conflito_codigo
    assert v[2].produto_id == "" and not v[2].pago and v[2].cancelada_em == datetime(2026, 10, 7)


def test_tmb_data_dd_mm_yyyy_e_nao_legivel_ignorada():
    b = dict(status="Efetivado", data_cancelamento=None, produto="M", oferta="O", utm_campaign="",
             utm_content="AT1", utm_last_content=None, ticket="10", lancamento_id=1)
    v = normalizar_tmb([dict(b, pedido="1", data_efetivado="15/04/2026 10:20:00"),
                        dict(b, pedido="2", data_efetivado="lixo")])
    assert [x.transacao for x in v] == ["1"] and v[0].data == datetime(2026, 4, 15, 10, 20)


def test_data_calendario_invalido_e_descartada_sem_excecao():
    b = dict(status="Efetivado", data_cancelamento=None, produto="M", oferta="O", utm_campaign="",
             utm_content="AT1", utm_last_content=None, ticket="10", lancamento_id=1)
    assert normalizar_tmb([dict(b, pedido="1", data_efetivado="31/02/2026 10:00:00")]) == []
    assert normalizar_tmb([dict(b, pedido="2", data_efetivado="2026-02-31T10:00:00")]) == []
    l = dict(BASE, codigo_da_transacao="X", status_da_transacao="Completo", quantidade_de_cobrancas=1,
             data_da_transacao="31/02/2026")
    assert normalizar_hotmart([l]) == []


def test_hotmart_valor_api_soma_taxa_de_processamento():
    """Linha do webhook/API (sem faturamento_liquido): o `sem_impostos` do banco já é líquido
    da taxa de processamento; o "Valor de compra sem impostos" do export (= VLR ENTRADA da
    planilha, chave da tabela de valores-base) é sem_impostos + taxa_de_processamento."""
    l = dict(BASE, codigo_da_transacao="HP9", status_da_transacao="COMPLETED", quantidade_de_cobrancas=1,
             valor_de_compra_sem_impostos=1558.01, taxa_de_processamento=65.96, faturamento_liquido=None)
    assert normalizar_hotmart([l])[0].valor_cobrado == Decimal("1623.97")
    texto = dict(l, valor_de_compra_sem_impostos="190.04", taxa_de_processamento="8.96")
    assert normalizar_hotmart([texto])[0].valor_cobrado == Decimal("199.00")


def test_hotmart_valor_linha_de_export_fica_como_esta():
    """Linha antiga (export CSV, com faturamento_liquido): sem_impostos já é o do export."""
    l = dict(BASE, codigo_da_transacao="HP8", status_da_transacao="Completo", quantidade_de_cobrancas=1,
             valor_de_compra_sem_impostos=497.0, taxa_de_processamento="24.86", faturamento_liquido=472.14)
    assert normalizar_hotmart([l])[0].valor_cobrado == Decimal("497.0")
