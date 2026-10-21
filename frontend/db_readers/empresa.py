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
from datetime import date

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import (
    _HOTMART_STATUS_APROVADO,
    _hm_data_sql,
    _parcela_unica_info,
)

logger = get_logger("db")

_TMB_ANO_SQL = r"""
SELECT COUNT(*), COALESCE(SUM(valor_liquido), 0) FROM (
    SELECT c.valor_liquido,
        CASE WHEN NULLIF(TRIM(o.criado_em),'') ~ '^\d{2}/\d{2}/\d{4}'
                  THEN to_timestamp(TRIM(o.criado_em),'DD/MM/YYYY HH24:MI:SS')::date
             WHEN NULLIF(TRIM(o.criado_em),'') ~ '^\d{4}-\d{2}-\d{2}' THEN TRIM(o.criado_em)::timestamp::date
             ELSE NULL END AS _criado_date,
        CASE
            WHEN NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""') ~ '^\d{2}/\d{2}/\d{4}'
                 THEN to_date(TRIM(c.data_efetivado::text),'DD/MM/YYYY')
            WHEN NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""') ~ '^\d{10,13}$' THEN to_timestamp(
                 CASE WHEN length(NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""')) = 13
                      THEN TRIM(c.data_efetivado::text)::bigint / 1000
                      ELSE TRIM(c.data_efetivado::text)::bigint END)::date
            WHEN NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""') IS NOT NULL
                 THEN TRIM(c.data_efetivado::text)::timestamptz::date
            END AS _efetivado_date
    FROM tmb_clean_oficial c
    LEFT JOIN tmb_oficial o ON o.pedido = c.pedido
    WHERE c.valor_liquido > 0
) sub
WHERE COALESCE(
    CASE WHEN _criado_date IS NOT NULL AND _efetivado_date IS NOT NULL
              AND (_efetivado_date - _criado_date) BETWEEN 0 AND 20 THEN _criado_date END,
    _efetivado_date
) BETWEEN :start AND :end
"""


def _num(v) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _hotmart_ano(ano: int) -> dict:
    sql = (
        "SELECT codigo_do_produto, codigo_do_preco, faturamento_liquido, valor_de_compra_sem_impostos, "
        "tipo_de_cobranca, quantidade_de_cobrancas, quantidade_total_de_parcelas "
        "FROM hotmart_clean_oficial WHERE status_da_transacao = ANY(:ok) AND COALESCE("
        + _hm_data_sql("data_da_transacao") + ", " + _hm_data_sql("confirmacao_do_pagamento")
        + ") BETWEEN :start AND :end AND (email_do_a_comprador_a IS NULL OR ("
        "email_do_a_comprador_a NOT ILIKE '%+teste%' AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'))"
    )
    df = pd.read_sql(
        text(sql), _get_users_engine(),
        params={"ok": list(_HOTMART_STATUS_APROVADO), "start": date(ano, 1, 1), "end": date(ano, 12, 31)},
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
    with _get_users_engine().connect() as conn:
        n, r = conn.execute(text(_TMB_ANO_SQL), {"start": date(ano, 1, 1), "end": date(ano, 12, 31)}).fetchone()
    return {"vendas": int(n or 0), "receita": float(r or 0.0)}


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
    saida = {"hotmart": {"vendas": 0, "receita": 0.0}, "tmb": {"vendas": 0, "receita": 0.0},
             "invest": {"distribuicao": 0.0, "perpetuo": 0.0, "sem_codigo": 0.0}, "completo": True}
    for chave, fn in (("hotmart", _hotmart_ano), ("tmb", _tmb_ano), ("invest", _investimento_fora_de_lancamento)):
        try:
            saida[chave] = fn(ano)
        except Exception:
            logger.exception("read_empresa_ano: falha em %s", chave)
            saida["completo"] = False
    return saida
