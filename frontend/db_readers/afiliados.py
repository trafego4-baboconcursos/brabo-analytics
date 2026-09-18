"""
frontend/db_readers/afiliados.py — Programa de afiliados da Hotmart.

Responde "quem vendeu pra gente como afiliado neste lançamento, quanto vendeu e
quanto levou de comissão".

Fonte: ``hotmart_clean_oficial``, no banco **operacional** — nunca a cópia no
analytics, que está desatualizada (mesma regra de ``sales.py``/``hotmart.py``).
``tmb_clean_oficial`` não tem nenhuma coluna de afiliado, então não entra aqui.

Colunas de afiliado que a Hotmart entrega, todas usadas nesta página:
``nome_do_a_afiliado_a``, ``comissao_do_a_afiliado_a``, ``venda_feita_como``
(papel da conta na venda), ``codigo_src``/``codigo_sck`` (como o afiliado marca
o tráfego), ``canal_usado_para_venda`` e ``ferramenta_de_venda``.

A CASA FICA DE FORA. ``nome_do_a_afiliado_a`` traz "Aprovasim - Cursos,
Treinamentos e Coaching Eireli" em 105.955 das 108.227 linhas da base: toda
venda do próprio produtor passa sob a indicação dela. Incluí-la aqui faria a
tela repetir o faturamento total e enterrar os parceiros de verdade — que em
toda a história da conta são 43 vendas (2022-2026). Ver ``_SQL_SO_TERCEIROS``.

O recorte de janela é opcional de propósito: o perpétuo vai precisar do mesmo
cálculo sem janela de carrinho, quando a tabela de vendas dele subir.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import _hm_data_sql, _parcela_unica_info
from frontend.models import AfiliadosSummary
from frontend.utils import (
    _extract_launch_code,
    _norm_text,
    _normalize_product_ids,
    _safe_date,
)
from logger import get_logger

logger = get_logger("db")

# Status que contam como venda paga — mesma lista de sales.py, para o número
# daqui bater com o de /vendas e /hotmart.
_STATUS_PAGOS = (
    "'Completa', 'Aprovada', 'Paga', 'Completo', 'Aprovado', 'Pago', "
    "'approved', 'complete', 'APPROVED', 'COMPLETED'"
)

# Recorte de "afiliado parceiro": tem nome preenchido e não é a casa.
_SQL_SO_TERCEIROS = (
    "nome_do_a_afiliado_a IS NOT NULL "
    "AND btrim(nome_do_a_afiliado_a) <> '' "
    "AND nome_do_a_afiliado_a NOT ILIKE '%Aprovasim%'"
)


def _num(v) -> float:
    """Converte um valor monetário da Hotmart (texto) em float.

    A tabela é toda TEXT e mistura '1798.8' com '1.798,80', então tenta o
    formato americano primeiro e cai no brasileiro quando há vírgula decimal.
    """
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0
    s = str(v).strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        x = float(s)
    except (ValueError, TypeError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def _valor_da_linha(row) -> float:
    """Faturamento líquido de uma linha, já com a correção de parcela.

    Mesmo critério de ``read_hotmart_details``: quando a linha guarda o valor
    da PARCELA em vez do total, multiplica pelo número de parcelas. Retorna
    ``None`` para retentativa de cobrança, que nunca é venda nova.
    """
    eh_por_parcela, eh_repeticao, _cobrancas, parcelas = _parcela_unica_info(row)
    if eh_repeticao:
        return None
    valor = _num(row.get("faturamento_liquido"))
    if not valor:
        valor = _num(row.get("valor_de_compra_sem_impostos"))
    if eh_por_parcela:
        valor *= max(1, parcelas)
    return valor


def read_afiliados(launch_folder_or_code: Any, start_date=None, end_date=None) -> AfiliadosSummary:
    code = _extract_launch_code(launch_folder_or_code)
    resumo = AfiliadosSummary()

    with _get_engine().connect() as conn:
        l_row = conn.execute(
            text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"),
            {"code": code},
        ).fetchone()
    if not l_row:
        logger.warning("read_afiliados: dim_lancamentos sem registro para code=%s", code)
        return resumo
    project, dim_start, dim_end = l_row

    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415
    cfg = read_launch_config(code)
    # Mesma precedência de sales.py: a janela do carrinho manda, dim_lancamentos
    # é o fallback. Sem isso a página contaria venda de fora do lançamento.
    inicio = (_safe_date(start_date) or _safe_date(cfg.get("carrinho_start_date"))
              or _safe_date(dim_start))
    fim = (_safe_date(end_date) or _safe_date(cfg.get("carrinho_end_date"))
           or _safe_date(dim_end))
    if inicio is None or fim is None:
        logger.warning("read_afiliados: janela invalida code=%s", code)
        return resumo
    resumo.janela_inicio, resumo.janela_fim = inicio, fim

    produto_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))
    data_sql = (
        "COALESCE(" + _hm_data_sql("data_da_transacao") + ", "
        + _hm_data_sql("confirmacao_do_pagamento") + ")"
    )

    # Escopo do produto: id cadastrado no wizard quando houver, senão o mesmo
    # CASE de projeto que sales.py usa (PES-MAI-26, por exemplo, está sem id).
    if produto_ids:
        escopo_sql = "codigo_do_produto = ANY(:product_ids)"
        params: dict = {"product_ids": produto_ids}
    else:
        escopo_sql = """CASE
              WHEN produto ILIKE '%inss%' THEN 'INSS'
              WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
              WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
              ELSE 'OUTRO'
          END = :project"""
        params = {"project": project}

    sql = f"""
        SELECT nome_do_a_afiliado_a, comissao_do_a_afiliado_a, venda_feita_como,
               codigo_src, codigo_sck, canal_usado_para_venda, ferramenta_de_venda,
               produto, codigo_do_produto, metodo_de_pagamento, faturamento_liquido,
               valor_de_compra_sem_impostos, valor_de_compra_com_impostos,
               tipo_de_cobranca, quantidade_de_cobrancas, quantidade_total_de_parcelas,
               {data_sql} AS data_venda
        FROM hotmart_clean_oficial
        WHERE status_da_transacao IN ({_STATUS_PAGOS})
          AND {escopo_sql}
          AND {_SQL_SO_TERCEIROS}
          AND (email_do_a_comprador_a IS NULL OR (
              email_do_a_comprador_a NOT ILIKE '%+teste%'
              AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'
          ))
    """
    df = pd.read_sql(text(sql), _get_users_engine(), params=params)
    # has_data marca "a consulta rodou", não "achou afiliado" — o template
    # precisa distinguir lançamento sem programa de afiliados de erro de leitura.
    resumo.has_data = True
    if df.empty:
        return resumo

    df["data_venda"] = pd.to_datetime(df["data_venda"], errors="coerce").dt.date
    dentro = df[(df["data_venda"] >= inicio) & (df["data_venda"] <= fim)].copy()
    fora = df[~df.index.isin(dentro.index)]

    # Venda do mesmo produto por afiliado que caiu fora do carrinho. Quase toda
    # venda por afiliado da base é assim, então sem esse aviso a página parece
    # vazia quando o que não pega é o recorte.
    fora_valores = [_valor_da_linha(r) for _, r in fora.iterrows()]
    fora_valores = [v for v in fora_valores if v is not None]
    resumo.fora_da_janela_qtd = len(fora_valores)
    resumo.fora_da_janela_faturamento = float(sum(fora_valores))

    if dentro.empty:
        return resumo

    vendas: list[dict] = []
    for _, row in dentro.iterrows():
        valor = _valor_da_linha(row)
        if valor is None:  # retentativa de cobrança, não é venda nova
            continue
        vendas.append({
            "afiliado": str(row.get("nome_do_a_afiliado_a") or "").strip(),
            "data": row.get("data_venda"),
            "produto": str(row.get("produto") or "").strip(),
            "valor": valor,
            "comissao": _num(row.get("comissao_do_a_afiliado_a")),
            "metodo": str(row.get("metodo_de_pagamento") or "").strip(),
            "papel": str(row.get("venda_feita_como") or "").strip(),
            "src": _limpa_codigo(row.get("codigo_src")),
            "sck": _limpa_codigo(row.get("codigo_sck")),
            "canal": _limpa_codigo(row.get("canal_usado_para_venda")),
            "ferramenta": str(row.get("ferramenta_de_venda") or "").strip(),
        })
    if not vendas:
        return resumo

    resumo.total_vendas = len(vendas)
    resumo.faturamento = float(sum(v["valor"] for v in vendas))
    resumo.comissao_total = float(sum(v["comissao"] for v in vendas))
    resumo.ticket_medio = resumo.faturamento / resumo.total_vendas if resumo.total_vendas else 0.0
    resumo.vendas = sorted(vendas, key=lambda v: (v["data"] is None, v["data"]), reverse=True)

    resumo.afiliados = _agrupa_por_afiliado(vendas)
    resumo.total_afiliados = len(resumo.afiliados)
    resumo.pct_faturamento = _pct_do_faturamento(code, resumo.faturamento, inicio, fim)
    return resumo


def _limpa_codigo(v) -> str:
    """Normaliza SRC/SCK/canal: a Hotmart grava a ausência como '(none)'."""
    s = str(v or "").strip()
    return "" if _norm_text(s) in {"none", "(none)", "nan", ""} else s


def _agrupa_por_afiliado(vendas: list[dict]) -> list[dict]:
    """Uma linha por afiliado, ordenada por faturamento."""
    por_nome: dict[str, dict] = {}
    for v in vendas:
        nome = v["afiliado"]
        item = por_nome.setdefault(nome, {
            "nome": nome, "vendas": 0, "faturamento": 0.0, "comissao": 0.0,
            "produtos": set(), "origens": set(),
            "primeira_venda": None, "ultima_venda": None,
        })
        item["vendas"] += 1
        item["faturamento"] += v["valor"]
        item["comissao"] += v["comissao"]
        if v["produto"]:
            item["produtos"].add(v["produto"])
        for origem in (v["src"], v["sck"], v["canal"]):
            if origem:
                item["origens"].add(origem)
        data = v["data"]
        if data:
            if item["primeira_venda"] is None or data < item["primeira_venda"]:
                item["primeira_venda"] = data
            if item["ultima_venda"] is None or data > item["ultima_venda"]:
                item["ultima_venda"] = data

    linhas = []
    for item in por_nome.values():
        item["produtos"] = sorted(item["produtos"])
        item["origens"] = sorted(item["origens"])
        item["ticket_medio"] = item["faturamento"] / item["vendas"] if item["vendas"] else 0.0
        # Comissão sobre o que ele mesmo vendeu — a Hotmart deixa a coluna em
        # 0.0 em parte das linhas, então isso pode ser 0 com faturamento > 0.
        item["comissao_pct"] = (item["comissao"] / item["faturamento"] * 100) if item["faturamento"] else 0.0
        linhas.append(item)
    return sorted(linhas, key=lambda i: i["faturamento"], reverse=True)


def _pct_do_faturamento(code: str, faturamento_afiliados: float, inicio, fim) -> float:
    """Quanto os afiliados representam do faturamento Hotmart do lançamento.

    Reusa ``read_vendas`` em vez de refazer a conta: é a mesma janela e o mesmo
    cache, e garante que o denominador aqui seja o número que /vendas mostra.
    """
    if not faturamento_afiliados:
        return 0.0
    try:
        from frontend.db_readers.sales import read_vendas  # noqa: PLC0415
        v = read_vendas(code, start_date=inicio, end_date=fim)
    except Exception:
        logger.exception("read_afiliados: falha ao ler faturamento total para %%")
        return 0.0
    total = getattr(v, "hotmart_receita", 0.0) if v else 0.0
    return (faturamento_afiliados / total * 100) if total else 0.0
