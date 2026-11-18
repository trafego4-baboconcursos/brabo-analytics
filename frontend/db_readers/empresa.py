"""
frontend/db_readers/empresa.py — Faturamento e investimento da EMPRESA inteira num ano civil.

Serve ao Resumo Executivo de /lancamentos. Os cartões dos lançamentos só contam a venda
que cai dentro do carrinho; aqui entra tudo o que a Hotmart e a TMB venderam no ano, para
fechar a conta com o número da empresa:

    total vendido no ano = lançamentos (dentro do carrinho)
                         + perpétuo (produtos das verticais)
                         + setor de vendas (o resto: fora do carrinho, apostilas, cursos...)

A regra de valor é a de `read_vendas`: líquido (`faturamento_liquido`, senão o valor sem
impostos — que nas vendas de 2026 já é o líquido do produtor), venda por parcela projetada
pelas parcelas (`_parcela_unica_info`), cobrança repetida e e-mail de teste fora.

A distribuição NÃO tem venda ligada (só anúncio); entra aqui apenas pelo investimento.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from src.constants import TMB_FATOR_LIQUIDO
from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import (
    parse_ts_brt,
    _HOTMART_STATUS_APROVADO,
    _hm_data_sql,
    _parcela_unica_info,
)

logger = get_logger("db")

# Total da TMB no ano = mesmo critério do relatório "contas a receber por data de efetivação" do financeiro:
# `tmb_oficial` com status 'Efetivado', soma do `ticket` pela `data_efetivado` (DD/MM/AAAA, ISO ou epoch),
# × TMB_FATOR_LIQUIDO. (Antes: `tmb_clean_oficial.valor_liquido` pela data de criação do pedido — ficava com 22
# pedidos efetivados a menos em 2026 e ~R$ 36 mil abaixo do financeiro.)
_TMB_ANO_SQL = "SELECT pedido, ticket, data_efetivado FROM tmb_oficial WHERE status = 'Efetivado'"

# Hotmart Editora (conta "Brabo Editora Ltda": apostilas físicas, Planner, combos). Fica fora de `hotmart_clean_oficial`.
# As tabelas `ht_editora_*` já existem, mas ainda estão vazias (falta ligar o webhook da conta). NÃO usar
# `hotmart_editora_oficial` / `hotmart_editora_clean_oficial`: o produtor delas é a Aprovasim (Vitalícia, Black, MEQ) e
# a venda entraria em dobro. Até o webhook alimentar `ht_editora_clean_oficial`, vale o relatório da Hotmart Editora
# até a data abaixo; depois dela, somam-se as linhas da tabela (as de antes dessa data são ignoradas, sem dobrar).
_EDITORA_TABELA = "ht_editora_clean_oficial"
_EDITORA_RELATORIO = {2026: {"ate": date(2026, 11, 18), "vendas": None, "receita": 78572.31 + 8452.21}}


def _num(v) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _hotmart_ano(ano: int, tabela: str = "hotmart_clean_oficial", depois_de: date | None = None) -> dict:
    sql = (
        "SELECT codigo_do_produto, codigo_do_preco, faturamento_liquido, valor_de_compra_sem_impostos, "
        "tipo_de_cobranca, quantidade_de_cobrancas, quantidade_total_de_parcelas "
        "FROM " + tabela + " WHERE status_da_transacao = ANY(:ok) AND COALESCE("
        + _hm_data_sql("data_da_transacao") + ", " + _hm_data_sql("confirmacao_do_pagamento")
        + ") BETWEEN :start AND :end AND (email_do_a_comprador_a IS NULL OR ("
        "email_do_a_comprador_a NOT ILIKE '%+teste%' AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'))"
    )
    df = pd.read_sql(
        text(sql), _get_users_engine(),
        params={"ok": list(_HOTMART_STATUS_APROVADO),
                "start": (depois_de + timedelta(days=1)) if depois_de else date(ano, 1, 1), "end": date(ano, 12, 31)},
    )
    vendas, receita = 0, 0.0
    for _, row in df.iterrows():
        por_parcela, repeticao, _cob, parcelas = _parcela_unica_info(row)
        if repeticao:
            continue
        valor = _num(row.get("faturamento_liquido")) or _num(row.get("valor_de_compra_sem_impostos"))
        if por_parcela:
            valor *= max(1, parcelas)
        vendas += 1
        receita += valor
    return {"vendas": vendas, "receita": receita}


def _tmb_ano(ano: int) -> dict:
    df = pd.read_sql(text(_TMB_ANO_SQL), _get_users_engine())
    vendas, ticket = 0, 0.0
    for _, row in df.iterrows():
        ts = parse_ts_brt(row.get("data_efetivado"))
        if ts is None or ts.year != ano:
            continue
        txt = str(row.get("ticket") or "").replace("R$", "").strip()
        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
        valor = _num(txt)
        if valor <= 0:
            continue
        vendas += 1
        ticket += valor
    return {"vendas": vendas, "receita": ticket * TMB_FATOR_LIQUIDO}


def _editora_ano(ano: int) -> dict:
    """Hotmart Editora no ano: relatório manual até `ate` + linhas da tabela depois dessa data (ver topo do arquivo)."""
    rel = _EDITORA_RELATORIO.get(ano)
    if not rel:
        return _hotmart_ano(ano, _EDITORA_TABELA)
    novo = _hotmart_ano(ano, _EDITORA_TABELA, depois_de=rel["ate"])
    return {"vendas": novo["vendas"] + (rel["vendas"] or 0), "receita": rel["receita"] + novo["receita"],
            "vendas_sem_contagem": rel["vendas"] is None}


def _investimento_fora_de_lancamento(ano: int) -> dict:
    """Gasto Meta + Google do ano em campanhas que NÃO são de lançamento."""
    with _get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT CASE WHEN lancamento_codigo ILIKE 'DISTRIBUICAO%'
                          OR (lancamento_codigo IS NULL AND campaign_name ILIKE '%distribui%') THEN 'distribuicao'
                        WHEN lancamento_codigo ILIKE 'PERPETUO%' THEN 'perpetuo'
                        WHEN lancamento_codigo IS NULL THEN 'sem_codigo' END AS grupo,
                   SUM(v)
            FROM (SELECT lancamento_codigo, campaign_name, spend AS v FROM meta_ads_daily
                  WHERE date BETWEEN :start AND :end
                  UNION ALL
                  SELECT lancamento_codigo, campaign_name, cost FROM google_ads_daily
                  WHERE date BETWEEN :start AND :end) t
            GROUP BY 1
        """), {"start": date(ano, 1, 1), "end": date(ano, 12, 31)}).fetchall()
    saida = {"distribuicao": 0.0, "perpetuo": 0.0, "sem_codigo": 0.0}
    for grupo, v in rows:
        if grupo in saida:
            saida[grupo] = float(v or 0.0)
    return saida


def read_empresa_ano(ano: int) -> dict:
    """Tudo que a Hotmart e a TMB venderam no ano + investimento fora de lançamento.
    Cada parte falha sozinha (o resumo aparece sem ela) em vez de derrubar a página."""
    saida = {"hotmart": {"vendas": 0, "receita": 0.0}, "tmb": {"vendas": 0, "receita": 0.0}, "editora": {"vendas": 0, "receita": 0.0},
             "invest": {"distribuicao": 0.0, "perpetuo": 0.0, "sem_codigo": 0.0}, "completo": True}
    for chave, fn in (("hotmart", _hotmart_ano), ("tmb", _tmb_ano), ("editora", _editora_ano), ("invest", _investimento_fora_de_lancamento)):
        try:
            saida[chave] = fn(ano)
        except Exception:
            logger.exception("read_empresa_ano: falha em %s", chave)
            saida["completo"] = False
    return saida
