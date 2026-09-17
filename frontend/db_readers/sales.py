"""
frontend/db_readers/sales.py — Vendas do lançamento: total, consolidado e dia 1.

``read_vendas`` é a entrada principal: soma Hotmart e TMB dentro da janela do
carrinho e devolve, além dos totais, os índices por e-mail (receita, estado,
telefone, canal) que a atribuição e o Caminho do Comprador consomem depois.

O detalhamento de cada plataforma vive em ``hotmart.py`` e ``tmb.py``; o que os
três compartilham, em ``_vendas_comum.py``. Os três seguem reexportados daqui,
porque `frontend.db_readers` e vários serviços importam por este caminho.
"""
from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import (  # noqa: F401 — reexport
    _DIA1_CHECKPOINTS,
    _HOTMART_STATUS_APROVADO,
    _UF_POR_NOME,
    _UFS_VALIDAS,
    _bucket_metodo_pagamento,
    _canal_venda,
    _hm_data_sql,
    _hm_metodo_label,
    _hm_parse_date,
    _norm_uf,
    _parcela_unica_info,
)
from frontend.db_readers.hotmart import (  # noqa: F401 — reexport
    read_hotmart_details,
    read_hotmart_recompra,
)
from frontend.db_readers.nomenclatura import categorizar_campanha_meta
from frontend.db_readers.tmb import (  # noqa: F401 — reexport
    read_forma_pagamento_entrada,
    read_tmb_details,
)
from frontend.models import (
    ConsolidadoVendasSummary,
    HotmartDetails,
    TmbDetails,
    VendasSummary,
)
from frontend.utils import _extract_launch_code, _norm_text, _normalize_product_ids, _safe_date
from logger import get_logger

logger = get_logger("db")


def read_vendas(launch_folder_or_code: Any, start_date=None, end_date=None) -> VendasSummary | None:
    """Cache + single-flight: read_meta/read_google/typeform chamam read_vendas
    internamente e em paralelo; sem isso a mesma consulta rodava 3-4x por página."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415 — evita import circular

    code = _extract_launch_code(launch_folder_or_code)
    return _get_or_compute(
        code,
        f"vendas::{start_date}::{end_date}",
        lambda: _read_vendas_uncached(code, start_date, end_date),
    )


def _read_vendas_uncached(code: str, start_date=None, end_date=None) -> VendasSummary | None:
    logger.info("read_vendas: inicio code=%s start=%s end=%s", code, start_date, end_date)

    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    with _get_engine().connect() as conn:
        l_row = conn.execute(
            text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"),
            {"code": code},
        ).fetchone()
        if not l_row:
            logger.warning("read_vendas: dim_lancamentos sem registro para code=%s", code)
            return None
        project, dim_start, dim_end = l_row

    effective_start = _safe_date(start_date) or _safe_date(dim_start)
    effective_end = _safe_date(end_date) or _safe_date(dim_end)
    if effective_start is None or effective_end is None:
        logger.warning("read_vendas: janela invalida code=%s dim_start=%s dim_end=%s", code, dim_start, dim_end)
        return None

    cfg = read_launch_config(code)
    carrinho_start = _safe_date(cfg.get("carrinho_start_date"))
    carrinho_end = _safe_date(cfg.get("carrinho_end_date"))
    launch_start = carrinho_start or effective_start
    launch_end = carrinho_end or effective_end
    hotmart_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))
    tmb_ids = _normalize_product_ids(cfg.get("tmb_produto_ids"))
    logger.info(
        "read_vendas: config code=%s has_cfg=%s carrinho=%s..%s hotmart_ids=%s tmb_ids=%s",
        code, bool(cfg), launch_start, launch_end, hotmart_ids, tmb_ids,
    )

    ops_engine = _get_users_engine()

    def _query_hotmart(use_ids: bool) -> pd.DataFrame:
        sql = (
            r"""
            SELECT * FROM hotmart_clean_oficial
            WHERE status_da_transacao IN ('Completa', 'Aprovada', 'Paga', 'Completo', 'Aprovado', 'Pago', 'approved', 'complete', 'APPROVED', 'COMPLETED')
              AND CASE
                  WHEN produto ILIKE '%inss%' THEN 'INSS'
                  WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
                  WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
                  ELSE 'OUTRO'
              END = :project
              AND COALESCE(
                """ + _hm_data_sql("data_da_transacao") + """,
                """ + _hm_data_sql("confirmacao_do_pagamento") + r"""
              ) BETWEEN :start AND :end
              AND (email_do_a_comprador_a IS NULL OR (
                  email_do_a_comprador_a NOT ILIKE '%+teste%'
                  AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'
              ))
        """
        )
        params: dict = {"project": project, "start": launch_start, "end": launch_end}
        if use_ids:
            sql += " AND codigo_do_produto = ANY(:product_ids)"
            params["product_ids"] = hotmart_ids
        return pd.read_sql(text(sql), ops_engine, params=params)

    def _query_tmb(use_ids: bool) -> pd.DataFrame:
        # Data efetiva = data de CRIAÇÃO do pedido (tmb_oficial.criado_em) quando
        # ela está PERTO da data de compensação (até 20 dias) — cobre um boleto
        # gerado no fim do carrinho que demora a compensar, mesmo critério já usado
        # pro Hotmart (data_da_transacao antes de confirmacao_do_pagamento).
        # Gaps maiores que 20 dias entre criado_em e data_efetivado são parcela/
        # renovação de um contrato antigo (ex.: Mentoria Vitalícia parcelada) —
        # nesses casos criado_em aponta pra assinatura original, não pra ESTA
        # cobrança, então usa data_efetivado (data real do evento de pagamento).
        sql = r"""
            SELECT * FROM (
                SELECT c.*, o.criado_em AS tmb_oficial_criado_em,
                    CASE WHEN NULLIF(TRIM(o.criado_em),'') ~ '^\d{2}/\d{2}/\d{4}' THEN to_timestamp(TRIM(o.criado_em),'DD/MM/YYYY HH24:MI:SS')::date
                         WHEN NULLIF(TRIM(o.criado_em),'') ~ '^\d{4}-\d{2}-\d{2}' THEN TRIM(o.criado_em)::timestamp::date
                         ELSE NULL END AS _criado_date,
                    CASE
                        WHEN NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(TRIM(c.data_efetivado::text),'DD/MM/YYYY')
                        WHEN NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""') ~ '^\d{10,13}$' THEN to_timestamp(
                            CASE WHEN length(NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""')) = 13
                                 THEN TRIM(c.data_efetivado::text)::bigint / 1000
                                 ELSE TRIM(c.data_efetivado::text)::bigint END)::date
                        WHEN NULLIF(NULLIF(TRIM(c.data_efetivado::text),''),'""') IS NOT NULL THEN TRIM(c.data_efetivado::text)::timestamptz::date
                        END AS _efetivado_date
                FROM tmb_clean_oficial c
                LEFT JOIN tmb_oficial o ON o.pedido = c.pedido
                WHERE c.valor_liquido > 0
                  AND CASE
                      WHEN c.produto ILIKE '%inss%' THEN 'INSS'
                      WHEN (c.produto ILIKE '%tj%' OR c.produto ILIKE '%tjsp%') THEN 'TJ'
                      WHEN (c.produto ILIKE '%bb%' OR c.produto ILIKE '%banco do brasil%' OR c.produto ILIKE '%bbsa%') THEN 'BB'
                      ELSE 'OUTRO'
                  END = :project
            ) sub
            WHERE COALESCE(
                CASE WHEN _criado_date IS NOT NULL AND _efetivado_date IS NOT NULL
                          AND (_efetivado_date - _criado_date) BETWEEN 0 AND 20
                     THEN _criado_date END,
                _efetivado_date
            ) BETWEEN :start AND :end
        """
        params: dict = {"project": project, "start": launch_start, "end": launch_end}
        if use_ids:
            ids_literal = ", ".join(str(int(i)) for i in tmb_ids)
            sql += f" AND lancamento_id = ANY(ARRAY[{ids_literal}]::int[])"
        return pd.read_sql(text(sql), ops_engine, params=params)

    hm_df = _query_hotmart(bool(hotmart_ids))
    if hm_df.empty and not hotmart_ids:
        hm_df = _query_hotmart(False)
    logger.info("read_vendas: hotmart code=%s rows=%s", code, len(hm_df))

    tmb_df = _query_tmb(bool(tmb_ids))
    if tmb_df.empty:
        tmb_df = _query_tmb(False)
    logger.info("read_vendas: tmb code=%s rows=%s", code, len(tmb_df))

    summary = VendasSummary()

    if not hm_df.empty:
        for _, row in hm_df.iterrows():
            def _hm_val(v):
                try:
                    if v is None or pd.isna(v):
                        return None
                    val = float(v)
                    return val if math.isfinite(val) else None
                except (ValueError, TypeError):
                    return None

            valor = _hm_val(row.get("faturamento_liquido"))
            if valor is None:
                valor = _hm_val(row.get("valor_de_compra_sem_impostos"))
            if valor is None:
                valor = 0.0
            valor_bruto = _hm_val(row.get("valor_de_compra_com_impostos"))
            if valor_bruto is None:
                valor_bruto = valor
            eh_por_parcela, eh_repeticao, cobrancas, parcelas = _parcela_unica_info(row)
            if eh_repeticao:
                continue
            if eh_por_parcela:
                valor *= max(1, parcelas)
                valor_bruto *= max(1, parcelas)

            email = str(row["email_do_a_comprador_a"]).strip().lower()
            pagto = _norm_text(row.get("metodo_de_pagamento", ""))

            if not math.isfinite(valor):
                logger.warning("read_vendas: hotmart valor invalido code=%s row=%s valor=%r", code, row.get("codigo_da_transacao"), valor)
                continue

            summary.hotmart_vendas += 1
            summary.hotmart_receita += valor
            summary.hotmart_receita_bruta += valor_bruto
            summary.hotmart_receita_liquida += valor
            if email:
                summary.emails_hotmart.add(email)
                summary.receita_por_email[email] = summary.receita_por_email.get(email, 0.0) + valor
                summary.vendas_por_email[email] = summary.vendas_por_email.get(email, 0) + 1
                if email not in summary.phone_por_email:
                    phone_digits = re.sub(r"\D", "", str(row.get("telefone") or ""))
                    if len(phone_digits) >= 10:
                        summary.phone_por_email[email] = phone_digits[-11:]
                if email not in summary.nome_por_email:
                    nome = str(row.get("comprador_a") or "").strip()
                    if nome:
                        summary.nome_por_email[email] = nome
                if email not in summary.estado_por_email:
                    uf = _norm_uf(row.get("estado_provincia"))
                    if uf:
                        summary.estado_por_email[email] = uf

            if "cartao" in pagto or "card" in pagto or "credit" in pagto:
                summary.pagamento_cartao += 1
            elif "boleto" in pagto:
                summary.pagamento_boleto += 1
            elif "pix" in pagto:
                summary.pagamento_pix += 1
            else:
                summary.pagamento_outros += 1

            canal = _canal_venda(row.get("codigo_sck"), None)
            d = summary.por_canal.setdefault(canal, {"vendas": 0, "receita": 0.0})
            d["vendas"] += 1
            d["receita"] += valor
            if email and canal != "Orgânico":
                summary.canal_por_email[email] = canal

    if not tmb_df.empty:
        for _, row in tmb_df.iterrows():
            try:
                valor = float(row["valor_liquido"])
            except (TypeError, ValueError):
                valor = 0.0
            if not math.isfinite(valor) or valor <= 0:
                logger.warning("read_vendas: tmb valor invalido code=%s row=%s valor=%r", code, row.get("pedido"), row.get("valor_liquido"))
                continue
            email = str(row["email_cliente"]).strip().lower()
            pagto = _norm_text(row.get("forma_pagamento", ""))

            summary.tmb_vendas += 1
            summary.tmb_receita += valor
            summary.tmb_receita_bruta += valor  # TMB não expõe valor pré-comissão
            if email:
                summary.emails_tmb.add(email)
                summary.receita_por_email[email] = summary.receita_por_email.get(email, 0.0) + valor
                summary.vendas_por_email[email] = summary.vendas_por_email.get(email, 0) + 1
                if email not in summary.phone_por_email:
                    phone_digits = re.sub(r"\D", "", str(row.get("telefone") or ""))
                    if len(phone_digits) >= 10:
                        summary.phone_por_email[email] = phone_digits[-11:]
                if email not in summary.nome_por_email:
                    nome = str(row.get("nome_cliente") or "").strip()
                    if nome:
                        summary.nome_por_email[email] = nome
                if email not in summary.estado_por_email:
                    uf = _norm_uf(row.get("estado"))
                    if uf:
                        summary.estado_por_email[email] = uf

            if "cartao" in pagto or "card" in pagto or "credito" in pagto:
                summary.pagamento_cartao += 1
            elif "boleto" in pagto:
                summary.pagamento_boleto += 1
            elif "pix" in pagto:
                summary.pagamento_pix += 1
            else:
                summary.pagamento_outros += 1

            canal = _canal_venda(None, row.get("utm_source"))
            d = summary.por_canal.setdefault(canal, {"vendas": 0, "receita": 0.0})
            d["vendas"] += 1
            d["receita"] += valor
            if email and canal != "Orgânico":
                summary.canal_por_email[email] = canal

    summary.total_vendas = summary.hotmart_vendas + summary.tmb_vendas
    summary.total_receita = summary.hotmart_receita + summary.tmb_receita
    summary.total_receita_bruta = summary.hotmart_receita_bruta + summary.tmb_receita_bruta
    summary.total_receita_liquida = summary.hotmart_receita_liquida + summary.tmb_receita
    if not math.isfinite(summary.hotmart_receita):
        summary.hotmart_receita = 0.0
    if not math.isfinite(summary.tmb_receita):
        summary.tmb_receita = 0.0
    if not math.isfinite(summary.total_receita):
        summary.total_receita = summary.hotmart_receita + summary.tmb_receita
    if not math.isfinite(summary.hotmart_receita_bruta):
        summary.hotmart_receita_bruta = 0.0
    if not math.isfinite(summary.tmb_receita_bruta):
        summary.tmb_receita_bruta = 0.0
    if not math.isfinite(summary.total_receita_bruta):
        summary.total_receita_bruta = summary.hotmart_receita_bruta + summary.tmb_receita_bruta
    if not math.isfinite(summary.hotmart_receita_liquida):
        summary.hotmart_receita_liquida = 0.0
    if not math.isfinite(summary.total_receita_liquida):
        summary.total_receita_liquida = summary.hotmart_receita_liquida + summary.tmb_receita
    summary.hotmart_ticket_medio = (summary.hotmart_receita / summary.hotmart_vendas) if summary.hotmart_vendas > 0 else 0.0
    summary.tmb_ticket_medio = (summary.tmb_receita / summary.tmb_vendas) if summary.tmb_vendas > 0 else 0.0
    summary.total_ticket_medio = (summary.total_receita / summary.total_vendas) if summary.total_vendas > 0 else 0.0

    if summary.total_vendas == 0:
        logger.warning(
            "read_vendas: sem vendas code=%s project=%s period=%s..%s hotmart_rows=%s tmb_rows=%s",
            code, project, launch_start, launch_end, len(hm_df), len(tmb_df),
        )
        return None

    logger.info(
        "read_vendas: sucesso code=%s total_vendas=%s total_receita=%s hotmart=%s tmb=%s",
        code, summary.total_vendas, summary.total_receita, summary.hotmart_receita, summary.tmb_receita,
    )
    return summary


def read_vendas_consolidado(launch_folder_or_code: Any, start_date=None, end_date=None) -> ConsolidadoVendasSummary:
    code = _extract_launch_code(launch_folder_or_code)

    v_sum = read_vendas(code, start_date=start_date, end_date=end_date)
    summary = ConsolidadoVendasSummary()
    if not v_sum:
        return summary

    summary.has_data = True
    summary.total_receita = v_sum.total_receita
    summary.total_transacoes = v_sum.total_vendas
    summary.compradores_unicos = v_sum.total_vendas
    summary.ticket_medio = v_sum.total_ticket_medio

    if v_sum.hotmart_vendas > 0:
        summary.fechamento.append({
            "plataforma": "Hotmart",
            "compradores": v_sum.hotmart_vendas,
            "transacoes": v_sum.hotmart_vendas,
            "faturamento": v_sum.hotmart_receita,
            "ticket": v_sum.hotmart_ticket_medio
        })
    if v_sum.tmb_vendas > 0:
        summary.fechamento.append({
            "plataforma": "TMB",
            "compradores": v_sum.tmb_vendas,
            "transacoes": v_sum.tmb_vendas,
            "faturamento": v_sum.tmb_receita,
            "ticket": v_sum.tmb_ticket_medio
        })

    engine = _get_engine()
    buyers = v_sum.emails_hotmart | v_sum.emails_tmb
    # Total de leads sai por COUNT no servidor; as linhas em si só interessam
    # pros compradores (o resto é descartado logo abaixo). Antes isso baixava a
    # lista inteira do lançamento — 269 mil linhas no PI-AGO-26 — a cada
    # chamada (ver ARQUITETURA.md, 14/09/26 — egress).
    with engine.connect() as conn:
        total_leads_crm = conn.execute(
            text("SELECT COUNT(*) FROM leads WHERE lancamento_codigo = :code"),
            {"code": code},
        ).scalar() or 0
    leads_df = pd.read_sql(
        text("SELECT email, utm_source, utm_medium FROM leads "
             "WHERE lancamento_codigo = :code AND LOWER(TRIM(email)) = ANY(:buyers)"),
        engine,
        params={"code": code, "buyers": list(buyers)}
    ) if buyers else pd.DataFrame(columns=["email", "utm_source", "utm_medium"])

    if total_leads_crm:
        summary.leads_crm = total_leads_crm
        leads_emails = set(leads_df["email"].str.strip().str.lower()) if not leads_df.empty else set()
        crm_buyers = leads_emails & buyers

        summary.compradores_crm = len(crm_buyers)
        summary.compradores_sem_crm = max(0, summary.compradores_unicos - summary.compradores_crm)
        summary.tx_compradores_crm_pct = summary.compradores_crm / summary.compradores_unicos * 100 if summary.compradores_unicos > 0 else 0.0

        leads_df["email_norm"] = leads_df["email"].str.strip().str.lower()
        crm_buyers_df = leads_df[leads_df["email_norm"].isin(buyers)].copy()

        if not crm_buyers_df.empty:
            crm_buyers_df["utm_source_norm"] = crm_buyers_df["utm_source"].fillna("Sem rastreio").str.strip()
            utm_vc = crm_buyers_df["utm_source_norm"].value_counts().head(10)
            for src, cnt in utm_vc.items():
                plat = "Outros"
                src_lower = src.lower()
                if "youtube" in src_lower or src_lower.startswith("yt"):
                    plat = "YouTube"
                elif "facebook" in src_lower or "instagram" in src_lower or "meta" in src_lower or src_lower.startswith("fb"):
                    plat = "Meta / FB"
                faturamento = sum(v_sum.receita_por_email.get(em, 0.0) for em in set(crm_buyers_df[crm_buyers_df["utm_source_norm"] == src]["email_norm"]))
                compradores = int(cnt)
                summary.canais.append({
                    "origem": src,
                    "label": src,
                    "canal": plat,
                    "compradores": compradores,
                    "faturamento": faturamento,
                    "ticket": faturamento / compradores if compradores > 0 else 0.0,
                })

    summary.conversao_lead_venda = summary.total_transacoes / summary.leads_crm * 100 if summary.leads_crm > 0 else 0.0
    summary.top_canais = summary.canais
    summary.top_estados = summary.propensao_uf
    summary.propensao = summary.propensao_uf

    if summary.top_canais:
        top_origem = max(summary.top_canais, key=lambda item: item.get("compradores", 0))
        summary.top_origem_nome = str(top_origem.get("origem") or top_origem.get("canal") or "")
        summary.top_origem_compradores = int(top_origem.get("compradores") or 0)
        summary.top_origem_faturamento = float(top_origem.get("faturamento") or 0.0)
        summary.top_origem_ticket = summary.top_origem_faturamento / summary.top_origem_compradores if summary.top_origem_compradores > 0 else 0.0

    if summary.top_estados:
        top_estado = max(summary.top_estados, key=lambda item: item.get("compradores", item.get("qtd", 0)))
        summary.top_estado_nome = str(top_estado.get("estado") or top_estado.get("uf") or "")
        summary.top_estado_compradores = int(top_estado.get("compradores") or top_estado.get("qtd") or 0)
        summary.top_estado_faturamento = float(top_estado.get("faturamento") or top_estado.get("receita") or 0.0)

    return summary


def read_qualidade_regiao(launch_folder_or_code: Any, vendas: Any = None) -> dict | None:
    """Qualidade por região (pauta debriefing, item 3): investimento do Meta
    por estado (Captação) cruzado com compradores/receita por estado.

    Duas limitações reais da API, confirmadas testando ao vivo:
    - Google Ads não expõe breakdown de estado/cidade em nenhuma view de
      relatório (geographic_view e user_location_view só devolvem o
      country_criterion_id, sempre Brasil) — por isso não há coluna Google.
    - O Meta só oferece "region" (estado, sem cidade) E, quando o insights é
      quebrado por region, a API NÃO devolve o action_type "lead" no array de
      actions (só ações de engajamento) — confirmado em ~2.400 linhas reais
      de Captação sem nenhum "lead". Por isso não há leads/CPL/conversão por
      estado do Meta aqui, só investimento (spend segue correto) cruzado com
      o ROAS calculado a partir da receita das vendas.
    """

    code = _extract_launch_code(launch_folder_or_code)
    if vendas is None:
        vendas = read_vendas(code)
    if not vendas:
        return None

    receita = vendas.receita_por_email or {}
    estado_email = vendas.estado_por_email or {}
    buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()

    compradores_uf: dict[str, dict] = {}
    for email in buyers:
        uf = estado_email.get(email)
        if not uf:
            continue
        d = compradores_uf.setdefault(uf, {"compradores": 0, "receita": 0.0})
        d["compradores"] += 1
        d["receita"] += float(receita.get(email) or 0)

    engine = _get_engine()
    df = pd.read_sql(
        text("SELECT region, campaign_name, cost FROM meta_ads_region_daily WHERE lancamento_codigo = :code"),
        engine, params={"code": code},
    )
    invest_uf: dict[str, float] = {}
    if not df.empty:
        df["uf"] = df["region"].map(_norm_uf)
        df["etapa"] = df["campaign_name"].map(lambda c: categorizar_campanha_meta(c)[0])
        df_cap = df[(df["etapa"] == "Captação") & df["uf"].notna()]
        g = df_cap.groupby("uf").agg(cost=("cost", "sum"))
        for uf, r in g.iterrows():
            invest_uf[uf] = float(r["cost"])

    ufs = set(compradores_uf) | set(invest_uf)
    if not ufs:
        return None

    rows = []
    for uf in ufs:
        c = compradores_uf.get(uf, {"compradores": 0, "receita": 0.0})
        invest = invest_uf.get(uf, 0.0)
        rows.append({
            "estado": uf,
            "invest": invest,
            "compradores": c["compradores"],
            "receita": c["receita"],
            "roas": (c["receita"] / invest) if invest > 0 else 0.0,
        })
    rows.sort(key=lambda r: r["receita"], reverse=True)
    return {"rows": rows, "tem_invest_meta": bool(invest_uf)}


def read_dia1_sales(launch: Any) -> dict:
    """Vendas cumulativas hora a hora no primeiro dia do carrinho (abertura),
    pra comparar o ritmo de vendas do dia de lançamento entre ciclos.

    `carrinho_start_date` é a segunda-feira (1º dia de aula) — início da
    janela usada pra contar vendas do lançamento. A abertura oficial real do
    carrinho (normalmente quinta-feira, mas o intervalo já variou +2/+3 dias
    entre lançamentos — não é um offset fixo) vem do campo explícito
    `abertura_oficial_carrinho`. Fallback pra carrinho_start_date + 3 dias
    só em lançamentos antigos que ainda não tiveram esse campo preenchido.
    """
    from datetime import timedelta  # noqa: PLC0415

    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    code = _extract_launch_code(launch)
    cfg = read_launch_config(code)
    day = _safe_date(cfg.get("abertura_oficial_carrinho"))
    if not day:
        carrinho_start = _safe_date(cfg.get("carrinho_start_date"))
        day = carrinho_start + timedelta(days=3) if carrinho_start else None
    if not day:
        return {"data_abertura": None, "checkpoints": []}

    hotmart_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))
    tmb_ids = _normalize_product_ids(cfg.get("tmb_produto_ids"))

    # Filtrar por product_id falha em dois casos reais, os dois já tratados no
    # read_vendas — aqui o dia 1 é só o par que faltava (achado 17/09/26):
    #   1. launch_config sem product_ids (PES-MAI-26) — nunca acha nada;
    #   2. venda nova do TMB entra com lancamento_id NULL e só é classificada
    #      depois, então no dia da abertura o filtro por ID devolve vazio.
    # Nos dois, cai pro projeto (via dim_lancamentos), igual ao read_vendas.
    with _get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT projeto FROM dim_lancamentos WHERE codigo = :code"),
            {"code": code},
        ).fetchone()
    project = row[0] if row else None

    project_case = """CASE
              WHEN produto ILIKE '%inss%' THEN 'INSS'
              WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
              WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
              ELSE 'OUTRO'
          END"""

    ops_engine = _get_users_engine()
    day_start = f"{day} 00:00:00"
    day_end = f"{day} 23:59:59"

    hm_df = pd.DataFrame()
    if hotmart_ids or project:
        id_clause = (
            "AND codigo_do_produto = ANY(:product_ids)" if hotmart_ids
            else "AND " + project_case + " = :project"
        )
        hm_sql = r"""
            SELECT
              COALESCE(
                CASE WHEN NULLIF(data_da_transacao,'') ~ '^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$'
                       THEN to_date(split_part(data_da_transacao, ' ', 1), 'DD/MM/YYYY')
                            + split_part(data_da_transacao, ' ', 2)::interval
                     WHEN NULLIF(data_da_transacao,'') ~ '^\d{2}/\d{2}/\d{4}$'
                       THEN to_date(data_da_transacao, 'DD/MM/YYYY')::timestamp
                     WHEN NULLIF(data_da_transacao,'') ~ '^\d{10,13}$'
                       THEN (to_timestamp(CASE WHEN length(data_da_transacao) = 13
                                 THEN data_da_transacao::bigint / 1000 ELSE data_da_transacao::bigint END)
                             AT TIME ZONE 'America/Sao_Paulo')
                     WHEN NULLIF(data_da_transacao,'') IS NOT NULL
                       THEN (data_da_transacao::timestamptz AT TIME ZONE 'America/Sao_Paulo')
                END
              ) AS ts,
              faturamento_liquido, valor_de_compra_sem_impostos, valor_de_compra_com_impostos,
              tipo_de_cobranca, venda_feita_como,
              quantidade_de_cobrancas, quantidade_total_de_parcelas
            FROM hotmart_clean_oficial
            WHERE status_da_transacao = ANY(:status)
              """ + id_clause + r"""
              AND (email_do_a_comprador_a IS NULL OR (
                  email_do_a_comprador_a NOT ILIKE '%+teste%'
                  AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'
              ))
        """
        params: dict = {"status": list(_HOTMART_STATUS_APROVADO)}
        if hotmart_ids:
            params["product_ids"] = hotmart_ids
        else:
            params["project"] = project
        raw = pd.read_sql(text(hm_sql), ops_engine, params=params)
        raw = raw[raw["ts"].notna()]
        raw["ts"] = pd.to_datetime(raw["ts"])
        if raw["ts"].dt.tz is not None:
            raw["ts"] = raw["ts"].dt.tz_localize(None)
        hm_df = raw[(raw["ts"] >= day_start) & (raw["ts"] <= day_end)].copy()

    def _query_tmb(usar_ids: bool) -> pd.DataFrame:
        if usar_ids:
            ids_literal = ", ".join(str(int(i)) for i in tmb_ids)
            filtro = f"lancamento_id = ANY(ARRAY[{ids_literal}]::int[])"
            params_tmb: dict = {"start": day_start, "end": day_end}
        else:
            filtro = project_case + " = :project"
            params_tmb = {"start": day_start, "end": day_end, "project": project}
        tmb_sql = f"""
            SELECT data_efetivado AS ts, valor_liquido
            FROM tmb_clean_oficial
            WHERE valor_liquido > 0
              AND {filtro}
              AND data_efetivado BETWEEN :start AND :end
        """
        return pd.read_sql(text(tmb_sql), ops_engine, params=params_tmb)

    tmb_df = pd.DataFrame()
    if tmb_ids:
        tmb_df = _query_tmb(True)
    # Vazio com os IDs cadastrados = venda de hoje ainda sem lancamento_id;
    # o read_vendas faz esse mesmo retry por projeto (por isso o total da
    # página mostrava a venda e o dia 1 não).
    if tmb_df.empty and project:
        tmb_df = _query_tmb(False)
    if not tmb_df.empty:
        tmb_df["ts"] = pd.to_datetime(tmb_df["ts"])

    def _hm_valor(row) -> float | None:
        def _v(x):
            try:
                if x is None or (isinstance(x, float) and math.isnan(x)):
                    return None
                v = float(str(x).replace(",", "."))
                return v if math.isfinite(v) else None
            except (ValueError, TypeError):
                return None
        valor = _v(row.get("faturamento_liquido"))
        if valor is None:
            valor = _v(row.get("valor_de_compra_sem_impostos"))
        if valor is None:
            valor = 0.0
        eh_por_parcela, eh_repeticao, cobrancas, parcelas = _parcela_unica_info(row)
        if eh_repeticao:
            return None  # ignorado, igual ao read_vendas (evita contar recorrencia)
        if eh_por_parcela:
            valor *= max(1, parcelas)
        return valor

    if not hm_df.empty:
        hm_df["valor"] = hm_df.apply(_hm_valor, axis=1)
        hm_df = hm_df[hm_df["valor"].notna()]

    if not tmb_df.empty:
        # TMB não expõe valor pré-comissão — usa o líquido mesmo (ver read_vendas)
        tmb_df["valor"] = pd.to_numeric(tmb_df["valor_liquido"], errors="coerce").fillna(0.0)

    # "day"/"ts" acima são naive mas já em horário de Brasília (a query SQL
    # converte explicitamente AT TIME ZONE 'America/Sao_Paulo'). pd.Timestamp.now()
    # sem tz pega o horário local do processo — em produção isso costuma ser UTC
    # (containers geralmente rodam em UTC), adiantando "agora" em ~3h e fazendo
    # checkpoints que ainda não aconteceram aparecerem como se já tivessem passado.
    agora = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None)

    checkpoints = []
    for label, minutes in _DIA1_CHECKPOINTS:
        cutoff = pd.Timestamp(day) + pd.Timedelta(minutes=minutes)
        if cutoff > agora:
            # checkpoint ainda não aconteceu (dia 1 em andamento) — não repete o
            # último valor real como se já tivesse passado
            checkpoints.append({"hora": label, "ht": None, "tmb": None, "total": None, "faturamento": None, "pendente": True})
            continue
        ht_slice = hm_df[hm_df["ts"] <= cutoff] if not hm_df.empty else hm_df
        tmb_slice = tmb_df[tmb_df["ts"] <= cutoff] if not tmb_df.empty else tmb_df
        ht_count = len(ht_slice)
        tmb_count = len(tmb_slice)
        ht_fat = float(ht_slice["valor"].sum()) if not ht_slice.empty else 0.0
        tmb_fat = float(tmb_slice["valor"].sum()) if not tmb_slice.empty else 0.0
        checkpoints.append({
            "hora": label,
            "ht": ht_count, "tmb": tmb_count,
            "total": ht_count + tmb_count,
            "faturamento": ht_fat + tmb_fat,
            "pendente": False,
        })

    return {"data_abertura": str(day), "checkpoints": checkpoints}
