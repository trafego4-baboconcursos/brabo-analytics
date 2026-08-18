"""
frontend/db_readers/sales.py — leitores de vendas (Hotmart, TMB, Consolidado).
"""
from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code, _safe_date, _normalize_product_ids, _norm_text
from frontend.db import _get_engine, _get_users_engine
from frontend.models import (
    VendasSummary, HotmartDetails, TmbDetails, ConsolidadoVendasSummary,
)

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
        sql = r"""
            SELECT * FROM hotmart_clean_oficial
            WHERE status_da_transacao IN ('Completa', 'Aprovada', 'Paga', 'Completo', 'Aprovado', 'Pago', 'approved', 'complete', 'APPROVED', 'COMPLETED')
              AND CASE
                  WHEN produto ILIKE '%inss%' THEN 'INSS'
                  WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
                  WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
                  ELSE 'OUTRO'
              END = :project
              AND COALESCE(
                CASE WHEN NULLIF(data_da_transacao,'') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(data_da_transacao,'DD/MM/YYYY')
                     WHEN NULLIF(data_da_transacao,'') ~ '^\d{10,13}$' THEN to_timestamp(
                         CASE WHEN length(NULLIF(data_da_transacao,'')) = 13
                              THEN data_da_transacao::bigint / 1000
                              ELSE data_da_transacao::bigint END)::date
                     WHEN NULLIF(data_da_transacao,'') IS NOT NULL THEN data_da_transacao::timestamptz::date END,
                CASE WHEN NULLIF(confirmacao_do_pagamento,'') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(confirmacao_do_pagamento,'DD/MM/YYYY')
                     WHEN NULLIF(confirmacao_do_pagamento,'') ~ '^\d{10,13}$' THEN to_timestamp(
                         CASE WHEN length(NULLIF(confirmacao_do_pagamento,'')) = 13
                              THEN confirmacao_do_pagamento::bigint / 1000
                              ELSE confirmacao_do_pagamento::bigint END)::date
                     WHEN NULLIF(confirmacao_do_pagamento,'') IS NOT NULL THEN confirmacao_do_pagamento::timestamptz::date END
              ) BETWEEN :start AND :end
        """
        params: dict = {"project": project, "start": launch_start, "end": launch_end}
        if use_ids:
            sql += " AND codigo_do_produto = ANY(:product_ids)"
            params["product_ids"] = hotmart_ids
        return pd.read_sql(text(sql), ops_engine, params=params)

    def _query_tmb(use_ids: bool) -> pd.DataFrame:
        sql = r"""
            SELECT * FROM tmb_clean_oficial
            WHERE valor_liquido > 0
              AND CASE
                  WHEN produto ILIKE '%inss%' THEN 'INSS'
                  WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
                  WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
                  ELSE 'OUTRO'
              END = :project
              AND CASE
                  WHEN NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(TRIM(data_efetivado::text),'DD/MM/YYYY')
                  WHEN NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""') ~ '^\d{10,13}$' THEN to_timestamp(
                      CASE WHEN length(NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""')) = 13
                           THEN TRIM(data_efetivado::text)::bigint / 1000
                           ELSE TRIM(data_efetivado::text)::bigint END)::date
                  WHEN NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""') IS NOT NULL THEN TRIM(data_efetivado::text)::timestamptz::date
                  END BETWEEN :start AND :end
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
            valor_bruto = _hm_val(row.get("valor_de_compra_sem_impostos"))
            if valor_bruto is None:
                valor_bruto = valor
            tipo_cobranca = _norm_text(row.get("tipo_de_cobranca", "") or row.get("venda_feita_como", ""))
            cobrancas = int(row.get("quantidade_de_cobrancas") or 1) if not pd.isna(row.get("quantidade_de_cobrancas", 1) or 1) else 1
            parcelas = int(row.get("quantidade_total_de_parcelas") or 1) if not pd.isna(row.get("quantidade_total_de_parcelas", 1) or 1) else 1
            if tipo_cobranca == "recuperador inteligente" and cobrancas != 1:
                continue
            if tipo_cobranca == "recuperador inteligente":
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

            if "cartao" in pagto or "card" in pagto or "credit" in pagto:
                summary.pagamento_cartao += 1
            elif "boleto" in pagto:
                summary.pagamento_boleto += 1
            elif "pix" in pagto:
                summary.pagamento_pix += 1
            else:
                summary.pagamento_outros += 1

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

            if "cartao" in pagto or "card" in pagto or "credito" in pagto:
                summary.pagamento_cartao += 1
            elif "boleto" in pagto:
                summary.pagamento_boleto += 1
            elif "pix" in pagto:
                summary.pagamento_pix += 1
            else:
                summary.pagamento_outros += 1

    summary.total_vendas = summary.hotmart_vendas + summary.tmb_vendas
    summary.total_receita = summary.hotmart_receita + summary.tmb_receita
    summary.total_receita_bruta = summary.hotmart_receita_bruta + summary.tmb_receita_bruta
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


def read_hotmart_details(launch_folder_or_code: Any, start_date=None, end_date=None) -> HotmartDetails:
    code = _extract_launch_code(launch_folder_or_code)

    with _get_engine().connect() as conn:
        l_row = conn.execute(text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
        if not l_row:
            return HotmartDetails()
        project, dim_start, dim_end = l_row

    effective_start = _safe_date(start_date) or _safe_date(dim_start)
    effective_end   = _safe_date(end_date)   or _safe_date(dim_end)

    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415
    cfg = read_launch_config(code)
    hotmart_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))

    ops_engine = _get_users_engine()
    details = HotmartDetails()
    details.has_data = True

    sql = r"""
        SELECT * FROM hotmart_clean_oficial
        WHERE CASE
              WHEN produto ILIKE '%inss%' THEN 'INSS'
              WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
              WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
              ELSE 'OUTRO'
          END = :project
          AND COALESCE(
            CASE WHEN NULLIF(data_da_transacao,'') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(data_da_transacao,'DD/MM/YYYY')
                 WHEN NULLIF(data_da_transacao,'') ~ '^\d{10,13}$' THEN to_timestamp(
                     CASE WHEN length(NULLIF(data_da_transacao,'')) = 13
                          THEN data_da_transacao::bigint / 1000
                          ELSE data_da_transacao::bigint END)::date
                 WHEN NULLIF(data_da_transacao,'') IS NOT NULL THEN data_da_transacao::timestamptz::date END,
            CASE WHEN NULLIF(confirmacao_do_pagamento,'') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(confirmacao_do_pagamento,'DD/MM/YYYY')
                 WHEN NULLIF(confirmacao_do_pagamento,'') ~ '^\d{10,13}$' THEN to_timestamp(
                     CASE WHEN length(NULLIF(confirmacao_do_pagamento,'')) = 13
                          THEN confirmacao_do_pagamento::bigint / 1000
                          ELSE confirmacao_do_pagamento::bigint END)::date
                 WHEN NULLIF(confirmacao_do_pagamento,'') IS NOT NULL THEN confirmacao_do_pagamento::timestamptz::date END
          ) BETWEEN :start AND :end
    """
    params: dict = {"project": project, "start": effective_start, "end": effective_end}
    if hotmart_ids:
        sql += " AND codigo_do_produto = ANY(:product_ids)"
        params["product_ids"] = hotmart_ids

    df_all = pd.read_sql(text(sql), ops_engine, params=params)
    if df_all.empty:
        return details

    details.total_emitidos = len(df_all)

    df_all["status_norm"] = df_all["status_da_transacao"].astype(str).apply(_norm_text)
    details.total_cancelados = int(df_all["status_norm"].isin({"cancelado", "reclamado", "reembolsado", "chargeback", "cancelada"}).sum())
    details.taxa_cancelamento = details.total_cancelados / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    details.total_reclamacoes = int(df_all["status_norm"].isin({"reclamado", "dispute"}).sum())
    details.taxa_reclamacao = details.total_reclamacoes / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    boletos_df = df_all[df_all["metodo_de_pagamento"].str.lower().str.contains("boleto", na=False)]
    details.boleto_emitido_qtd = len(boletos_df)
    details.boleto_pago_qtd = len(boletos_df[boletos_df["status_norm"].isin({"completo", "complete", "aprovado", "approved", "pago"})])
    details.taxa_conversao_boleto = details.boleto_pago_qtd / details.boleto_emitido_qtd * 100 if details.boleto_emitido_qtd > 0 else 0.0
    details.taxa_boleto_gerado = details.boleto_emitido_qtd / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    df_paid = df_all[df_all["status_norm"].isin({"completo", "completa", "complete", "completed", "aprovado", "aprovada", "approved", "pago", "paga"})].copy()

    df_paid["valor_liq"] = 0.0
    for idx, row in df_paid.iterrows():
        valor = float(row["faturamento_liquido"] or 0.0)
        tipo_cobranca = _norm_text(row.get("tipo_de_cobranca", "") or row.get("venda_feita_como", ""))
        cobrancas_raw = row.get("quantidade_de_cobrancas")
        cobrancas = int(cobrancas_raw) if pd.notna(cobrancas_raw) else 1
        parcelas_raw = row.get("quantidade_total_de_parcelas")
        parcelas = int(parcelas_raw) if pd.notna(parcelas_raw) else 1
        if tipo_cobranca == "recuperador inteligente":
            if cobrancas != 1:
                continue
            valor *= max(1, parcelas)
        df_paid.at[idx, "valor_liq"] = valor

    details.total_vendas = len(df_paid)
    details.faturamento = float(df_paid["valor_liq"].sum())
    details.receita_liquida = details.faturamento
    gross_col = next((col for col in ["faturamento_bruto", "valor_de_compra_com_impostos", "preco_do_produto"] if col in df_paid.columns), None)
    if gross_col:
        df_paid["valor_bruto"] = pd.to_numeric(df_paid[gross_col], errors="coerce").fillna(0.0)
        details.receita_bruta = float(df_paid["valor_bruto"].sum())
    else:
        details.receita_bruta = details.receita_liquida
    details.taxas = max(0.0, details.receita_bruta - details.receita_liquida)
    details.taxas_pct = details.taxas / details.receita_bruta * 100 if details.receita_bruta > 0 else 0.0
    details.ticket_medio = details.faturamento / details.total_vendas if details.total_vendas > 0 else 0.0

    pix_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("pix", na=False)]
    card_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("cartao|card|credit", na=False)]
    details.pix_ticket = float(pix_df["valor_liq"].mean()) if not pix_df.empty else 0.0
    details.card_ticket = float(card_df["valor_liq"].mean()) if not card_df.empty else 0.0
    if details.card_ticket > 0:
        details.pix_premium = (details.pix_ticket - details.card_ticket) / details.card_ticket * 100

    if not card_df.empty:
        df_paid["parcelas_int"] = pd.to_numeric(df_paid["quantidade_total_de_parcelas"], errors="coerce").fillna(1).astype(int)
        card_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("cartao|card|credit", na=False)]
        details.vendas_12x_pct = len(card_df[card_df["parcelas_int"] == 12]) / len(card_df) * 100 if not card_df.empty else 0.0

        p_dist = card_df["parcelas_int"].value_counts().sort_index()
        for p_val, cnt in p_dist.items():
            details.parcelas.append({
                "label": "À vista" if p_val == 1 else f"{p_val}x",
                "qtd": int(cnt),
                "pct_vendas": float(cnt / len(card_df) * 100)
            })

    if not df_paid.empty and "metodo_de_pagamento" in df_paid.columns:
        pay_grouped = df_paid.groupby(df_paid["metodo_de_pagamento"].fillna("Nao informado"))
        for metodo, group in pay_grouped:
            faturamento = float(group["valor_liq"].sum())
            details.pagamentos.append({
                "metodo": str(metodo).strip() or "Nao informado",
                "qtd": int(len(group)),
                "pct_vendas": float(len(group) / details.total_vendas * 100) if details.total_vendas > 0 else 0.0,
                "faturamento": faturamento,
                "pct_faturamento": float(faturamento / details.receita_liquida * 100) if details.receita_liquida > 0 else 0.0,
                "ticket_medio": float(group["valor_liq"].mean()) if not group.empty else 0.0,
            })
        details.pagamentos = sorted(details.pagamentos, key=lambda item: item["qtd"], reverse=True)

    if not df_paid.empty:
        df_paid["parcelas_int"] = pd.to_numeric(df_paid["quantidade_total_de_parcelas"], errors="coerce").fillna(1).astype(int)
        av_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("pix|boleto", na=False) | (df_paid["parcelas_int"] == 1)]
        parc_df = df_paid[(df_paid["parcelas_int"] > 1) & df_paid["metodo_de_pagamento"].str.lower().str.contains("cart", na=False)]
        details.fluxo_caixa = {
            "a_vista": float(av_df["valor_liq"].sum()),
            "parcelado": float(parc_df["valor_liq"].sum())
        }

    if not df_paid.empty:
        import re as _re  # noqa: PLC0415
        def _parse_hm_date(s):
            s = str(s or "").strip()
            if _re.match(r'^\d{2}/\d{2}/\d{4}', s):
                try: return pd.to_datetime(s[:10], format="%d/%m/%Y")
                except Exception: pass
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if dt is not pd.NaT and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                    dt = dt.tz_localize(None)
                return dt
            except Exception: return pd.NaT
        df_paid["data_parsed"] = df_paid["data_da_transacao"].apply(_parse_hm_date)
        d1_date = df_paid["data_parsed"].min()
        timeline_grouped = df_paid.groupby(df_paid["data_parsed"].dt.date).agg(
            vendas=("valor_liq", "count"),
            faturamento=("valor_liq", "sum")
        ).reset_index().sort_values("data_parsed")

        for _, row in timeline_grouped.iterrows():
            dt = row["data_parsed"]
            details.timeline.append({
                "data": dt.strftime("%Y-%m-%d"),
                "data_str": dt.strftime("%d/%b"),
                "vendas": int(row["vendas"]),
                "faturamento": float(row["faturamento"]),
                "is_d1": pd.notna(d1_date) and dt == d1_date.date()
            })

    ofertas_grouped = df_paid.groupby("nome_deste_preco")
    for name, group in ofertas_grouped:
        name_str = str(name).strip()
        tipo = "Base" if name_str.lower() in ("none", "(none)", "") else ("Cross" if "cross" in name_str.lower() else ("Upsell" if "upsell" in name_str.lower() else "Lead"))
        details.ofertas.append({
            "nome": name_str or "Oferta Base",
            "tipo": tipo,
            "qtd": len(group),
            "faturamento": float(group["valor_liq"].sum()),
            "ticket_medio": float(group["valor_liq"].mean())
        })
    details.ofertas = sorted(details.ofertas, key=lambda x: x["qtd"], reverse=True)

    for col, target in [("estado_provincia", details.estados), ("cidade", details.cidades)]:
        if col in df_paid.columns:
            g = df_paid.groupby(col).agg(qtd=("valor_liq", "count"), fat=("valor_liq", "sum")).sort_values("qtd", ascending=False).head(10)
            for idx, r in g.iterrows():
                target.append({
                    "estado" if col == "estado_provincia" else "cidade": str(idx),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })

    return details


def read_tmb_details(launch_folder_or_code: Any, start_date=None, end_date=None) -> TmbDetails:
    code = _extract_launch_code(launch_folder_or_code)

    with _get_engine().connect() as conn:
        l_row = conn.execute(text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
        if not l_row:
            return TmbDetails()
        project, dim_start, dim_end = l_row

    effective_start = _safe_date(start_date) or _safe_date(dim_start)
    effective_end   = _safe_date(end_date)   or _safe_date(dim_end)

    ops_engine = _get_users_engine()
    details = TmbDetails()
    details.has_data = True

    df_all = pd.read_sql(
        text(r"""
            SELECT * FROM tmb_clean_oficial
            WHERE CASE
                  WHEN produto ILIKE '%inss%' THEN 'INSS'
                  WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
                  WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
                  ELSE 'OUTRO'
              END = :project
              AND CASE
                  WHEN NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""') ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(TRIM(data_efetivado::text),'DD/MM/YYYY')
                  WHEN NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""') ~ '^\d{10,13}$' THEN to_timestamp(
                      CASE WHEN length(NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""')) = 13
                           THEN TRIM(data_efetivado::text)::bigint / 1000
                           ELSE TRIM(data_efetivado::text)::bigint END)::date
                  WHEN NULLIF(NULLIF(TRIM(data_efetivado::text),''),'""') IS NOT NULL THEN TRIM(data_efetivado::text)::timestamptz::date
                  END BETWEEN :start AND :end
        """),
        ops_engine,
        params={"project": project, "start": effective_start, "end": effective_end}
    )
    if df_all.empty:
        return details

    details.total_emitidos = len(df_all)
    df_all["status_norm"] = df_all["status"].fillna("").astype(str).apply(_norm_text)
    details.total_cancelados = int(df_all["status_norm"].isin({"cancelado", "recusado", "estornado", "refunded", "cancelled", "cancelada"}).sum())
    details.taxa_cancelamento = details.total_cancelados / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    status_vc = df_all["status"].value_counts()
    for stat, cnt in status_vc.items():
        details.status_emitidos.append({
            "status": str(stat).capitalize(),
            "qtd": int(cnt),
            "pct": float(cnt / details.total_emitidos * 100)
        })

    df_paid = df_all[df_all["status_norm"].isin({"vigente", "efetivado", "pago", "em dia", "integralizado", "aprovado", "concluido", "active"})].copy()
    df_paid["valor_liq"] = pd.to_numeric(df_paid["valor_liquido"], errors="coerce").fillna(0.0)

    details.total_vendas = len(df_paid)
    details.faturamento = float(df_paid["valor_liq"].sum())
    details.ticket_medio = details.faturamento / details.total_vendas if details.total_vendas > 0 else 0.0

    if not df_paid.empty:
        df_paid["data_parsed"] = pd.to_datetime(df_paid["data_efetivado"], errors="coerce")
        d1_date = df_paid["data_parsed"].min()
        timeline_grouped = df_paid.groupby(df_paid["data_parsed"].dt.date).agg(
            vendas=("valor_liq", "count"),
            faturamento=("valor_liq", "sum")
        ).reset_index().sort_values("data_parsed")

        for _, row in timeline_grouped.iterrows():
            dt = row["data_parsed"]
            is_d1 = pd.notna(d1_date) and dt == d1_date.date()
            details.timeline.append({
                "data": dt.strftime("%Y-%m-%d"),
                "data_str": dt.strftime("%d/%b"),
                "vendas": int(row["vendas"]),
                "faturamento": float(row["faturamento"]),
                "is_d1": is_d1
            })
            if is_d1:
                details.vendas_d1 = int(row["vendas"])
                details.vendas_d1_pct = details.vendas_d1 / details.total_vendas * 100 if details.total_vendas > 0 else 0.0

    ofertas_grouped = df_paid.groupby("oferta")
    for name, group in ofertas_grouped:
        name_str = str(name).strip()
        tipo = "Lead" if "lead" in name_str.lower() else ("Upsell" if "upsell" in name_str.lower() else "Crossell")
        details.ofertas.append({
            "nome": name_str or "Oferta TMB",
            "tipo": tipo,
            "qtd": len(group),
            "faturamento": float(group["valor_liq"].sum()),
            "ticket_medio": float(group["valor_liq"].mean())
        })
    details.ofertas = sorted(details.ofertas, key=lambda x: x["qtd"], reverse=True)

    df_paid["utm_norm"] = df_paid["utm_source"].fillna("").astype(str).str.strip()
    details.com_utm_qtd = int((df_paid["utm_norm"] != "").sum())
    details.com_utm_pct = details.com_utm_qtd / details.total_vendas * 100 if details.total_vendas > 0 else 0.0

    utm_vc = df_paid["utm_norm"].value_counts()
    for src, cnt in utm_vc.items():
        details.utm_sources.append({
            "source": src or "Sem rastreio",
            "qtd": int(cnt),
            "pct": float(cnt / details.total_vendas * 100)
        })

    for col, target in [("estado", details.estados), ("cidade", details.cidades)]:
        if col in df_paid.columns:
            g = df_paid.groupby(col).agg(qtd=("valor_liq", "count"), fat=("valor_liq", "sum")).sort_values("qtd", ascending=False).head(10)
            for idx, r in g.iterrows():
                target.append({
                    "estado" if col == "estado" else "cidade": str(idx),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })

    return details


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
    leads_df = pd.read_sql(
        text("SELECT email, utm_source, utm_medium FROM leads WHERE lancamento_codigo = :code"),
        engine,
        params={"code": code}
    )

    if not leads_df.empty:
        summary.leads_crm = len(leads_df)
        buyers = v_sum.emails_hotmart | v_sum.emails_tmb
        leads_emails = set(leads_df["email"].str.strip().str.lower())
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


# ── Vendas hora a hora no dia 1 (abertura do carrinho) ──────────────────────────

_DIA1_CHECKPOINTS = [
    ("8h30", 8 * 60 + 30), ("9h", 9 * 60), ("10h", 10 * 60), ("11h", 11 * 60),
    ("12h", 12 * 60), ("13h", 13 * 60), ("15h", 15 * 60), ("16h", 16 * 60),
    ("17h", 17 * 60), ("18h", 18 * 60), ("19h", 19 * 60), ("20h", 20 * 60),
    ("21h", 21 * 60), ("22h", 22 * 60),
]

_HOTMART_STATUS_APROVADO = (
    "Completa", "Aprovada", "Paga", "Completo", "Aprovado", "Pago",
    "approved", "complete", "APPROVED", "COMPLETED",
)


def read_dia1_sales(launch: Any) -> dict:
    """Vendas cumulativas hora a hora no primeiro dia do carrinho (abertura),
    pra comparar o ritmo de vendas do dia de lançamento entre ciclos."""
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    code = _extract_launch_code(launch)
    cfg = read_launch_config(code)
    day = _safe_date(cfg.get("carrinho_start_date"))
    if not day:
        return {"data_abertura": None, "checkpoints": []}

    hotmart_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))
    tmb_ids = _normalize_product_ids(cfg.get("tmb_produto_ids"))

    ops_engine = _get_users_engine()
    day_start = f"{day} 00:00:00"
    day_end = f"{day} 23:59:59"

    hm_df = pd.DataFrame()
    if hotmart_ids:
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
              faturamento_liquido, valor_de_compra_sem_impostos,
              tipo_de_cobranca, venda_feita_como,
              quantidade_de_cobrancas, quantidade_total_de_parcelas
            FROM hotmart_clean_oficial
            WHERE status_da_transacao = ANY(:status)
              AND codigo_do_produto = ANY(:product_ids)
        """
        raw = pd.read_sql(
            text(hm_sql), ops_engine,
            params={"status": list(_HOTMART_STATUS_APROVADO), "product_ids": hotmart_ids},
        )
        raw = raw[raw["ts"].notna()]
        raw["ts"] = pd.to_datetime(raw["ts"])
        if raw["ts"].dt.tz is not None:
            raw["ts"] = raw["ts"].dt.tz_localize(None)
        hm_df = raw[(raw["ts"] >= day_start) & (raw["ts"] <= day_end)].copy()

    tmb_df = pd.DataFrame()
    if tmb_ids:
        ids_literal = ", ".join(str(int(i)) for i in tmb_ids)
        tmb_sql = f"""
            SELECT data_efetivado AS ts, valor_liquido
            FROM tmb_clean_oficial
            WHERE valor_liquido > 0
              AND lancamento_id = ANY(ARRAY[{ids_literal}]::int[])
              AND data_efetivado BETWEEN :start AND :end
        """
        tmb_df = pd.read_sql(text(tmb_sql), ops_engine, params={"start": day_start, "end": day_end})
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
        tipo = _norm_text(row.get("tipo_de_cobranca") or row.get("venda_feita_como") or "")
        try:
            cobrancas = int(row.get("quantidade_de_cobrancas") or 1)
        except (ValueError, TypeError):
            cobrancas = 1
        try:
            parcelas = int(row.get("quantidade_total_de_parcelas") or 1)
        except (ValueError, TypeError):
            parcelas = 1
        if tipo == "recuperador inteligente" and cobrancas != 1:
            return None  # ignorado, igual ao read_vendas (evita contar recorrencia)
        if tipo == "recuperador inteligente":
            valor *= max(1, parcelas)
        return valor

    if not hm_df.empty:
        hm_df["valor"] = hm_df.apply(_hm_valor, axis=1)
        hm_df = hm_df[hm_df["valor"].notna()]

    if not tmb_df.empty:
        tmb_df["valor"] = pd.to_numeric(tmb_df["valor_liquido"], errors="coerce").fillna(0.0)

    agora = pd.Timestamp.now()

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
