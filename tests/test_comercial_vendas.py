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
    # Ruling 6: cancelado depois de efetivar conta como paga e cancelada na data_cancelamento
    assert v[2].produto_id == "" and v[2].pago and v[2].cancelada_em == datetime(2026, 10, 7)


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


def test_filtro_de_periodo_descarta_extra_fora_por_padrao():
    from datetime import date
    from frontend.db_readers.comercial import _filtrar_periodo
    dentro = Venda("hotmart", "A", datetime(2026, 10, 5), "", "", "", None, False, "cartao_pix", None, Decimal("1"), True, None)
    fora = Venda("hotmart", "B", datetime(2026, 9, 5), "", "", "", None, False, "cartao_pix", None, Decimal("1"), True, None)
    ini, fim = date(2026, 10, 1), date(2026, 10, 31)
    ex = frozenset({"B"})
    assert [v.transacao for v in _filtrar_periodo([dentro, fora], ini, fim, ex, False)] == ["A"]
    assert [v.transacao for v in _filtrar_periodo([dentro, fora], ini, fim, ex, True)] == ["A", "B"]


# ---------------------------------------------------------------- Ruling 6: TMB cancelado depois de efetivar
_TMB = dict(data_efetivado="2026-10-05T08:00:00", data_cancelamento=None, produto="Mentoria",
            oferta="Oferta", utm_campaign="MENTORIABBLEAD", utm_content="AT11", utm_last_content=None,
            ticket="1879.34", lancamento_id=29395)
_HOJE = datetime(2026, 11, 30)


def _uma_tmb(**kw):
    [v] = normalizar_tmb([dict(_TMB, pedido="P", **kw)])
    return v


def _sit(v):
    from frontend.services.comercial.regras import situacao
    return situacao(v.pago, v.data, v.cancelada_em, _HOJE)


def test_tmb_efetivado_pago_sem_cancelamento():
    v = _uma_tmb(status="Efetivado")
    assert v.pago and v.cancelada_em is None and _sit(v) == "elegivel"


def test_tmb_efetivado_com_data_cancelamento_solta_nao_cancela():
    v = _uma_tmb(status="Efetivado", data_cancelamento=datetime(2026, 10, 7))
    assert v.pago and v.cancelada_em is None


def test_tmb_cancelado_em_3_dias_e_cancelada():
    v = _uma_tmb(status="Cancelado", data_cancelamento=datetime(2026, 10, 8, 8, 0))
    assert v.pago and v.cancelada_em == datetime(2026, 10, 8, 8, 0) and _sit(v) == "cancelada"


def test_tmb_cancelado_em_10_dias_vai_para_reembolso_a_verificar():
    v = _uma_tmb(status="Cancelado", data_cancelamento=datetime(2026, 10, 15, 8, 0))
    assert v.pago and _sit(v) == "reembolso_a_verificar"


def test_tmb_cancelado_sem_data_cancela_na_data_da_venda():
    v = _uma_tmb(status="Cancelado", data_cancelamento=None)
    assert v.pago and v.cancelada_em == v.data == datetime(2026, 10, 5, 8, 0)
    assert _sit(v) == "cancelada"


def test_tmb_cancelamento_solicitado_conta_como_cancelado():
    v = _uma_tmb(status="Cancelamento Solicitado", data_cancelamento=None)
    assert v.pago and v.cancelada_em == v.data


def test_tmb_boleto_gerado_e_aguardando_nao_pagos():
    for st in ("Boleto Gerado", "Aguardando Assinatura", "Aguardando Validação"):
        v = _uma_tmb(status=st)
        assert not v.pago and v.cancelada_em is None and _sit(v) == "nao_paga"


def test_hotmart_valores_alternativos_para_buscar_a_base():
    """Fallback da busca do valor-base (09/11/26, HP1930038622 e HP1190909150): quando o valor de
    hoje não acha base, tenta o valor COM impostos; no Parcelamento Inteligente (1ª de N cobranças),
    a parcela × N — a parcela sozinha casaria com a base de recorrência, errada."""
    api = dict(BASE, status_da_transacao="APPROVED", faturamento_liquido=None, taxa_de_processamento=32.5)
    cartao10x = dict(api, codigo_da_transacao="HPA", valor_de_compra_sem_impostos=641.81,
                     valor_de_compra_com_impostos=899.4, quantidade_total_de_parcelas=10,
                     quantidade_de_cobrancas=None)
    assert normalizar_hotmart([cartao10x])[0].valores_alternativos == (Decimal("899.40"),)
    inteligente = dict(api, codigo_da_transacao="HPB", valor_de_compra_sem_impostos=121.46,
                       taxa_de_processamento=7.0, valor_de_compra_com_impostos=149.9,
                       quantidade_total_de_parcelas=12, quantidade_de_cobrancas=1)
    assert normalizar_hotmart([inteligente])[0].valores_alternativos == (Decimal("1798.80"), Decimal("149.90"))
    sem_com_impostos = dict(api, codigo_da_transacao="HPC", quantidade_de_cobrancas=1)
    assert normalizar_hotmart([sem_com_impostos])[0].valores_alternativos == ()
