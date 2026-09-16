"""
frontend/db_readers/tmb.py — Detalhe do TMB e forma de pagamento da entrada.

``read_forma_pagamento_entrada`` mora aqui porque a entrada parcelada é um
produto do TMB, ainda que o resumo que ela devolve some as duas plataformas.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import _bucket_metodo_pagamento
from frontend.models import TmbDetails
from frontend.utils import (
    _extract_launch_code,
    _norm_text,
    _normalize_product_ids,
    _safe_date,
)
from logger import get_logger

logger = get_logger("db")


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


def read_forma_pagamento_entrada(launch_folder_or_code: Any, start_date=None, end_date=None) -> dict | None:
    """Forma de pagamento da ENTRADA de quem comprou "boleto parcelado"
    (produto rastreado 100% no TMB — checado que praticamente nenhum desses
    compradores tem transação correspondente no Hotmart, então a entrada
    não é rastreável por lá). O próprio TMB grava a forma da entrada no
    campo forma_pagamento ("BOLETO" = entrada em boleto, "PIX Parcelado +
    Boleto" = entrada em Pix e parcelas seguintes em boleto). Pauta
    debriefing (apresentação legada "Forma de Pagamento da Entrada")."""
    code = _extract_launch_code(launch_folder_or_code)

    with _get_engine().connect() as conn:
        l_row = conn.execute(text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
        if not l_row:
            return None
        project, dim_start, dim_end = l_row

    effective_start = _safe_date(start_date) or _safe_date(dim_start)
    effective_end   = _safe_date(end_date)   or _safe_date(dim_end)

    ops_engine = _get_users_engine()
    df = pd.read_sql(
        text(r"""
            SELECT forma_pagamento, status FROM tmb_clean_oficial
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
    if df.empty:
        return None

    df["status_norm"] = df["status"].fillna("").astype(str).apply(_norm_text)
    df_paid = df[df["status_norm"].isin({"vigente", "efetivado", "pago", "em dia", "integralizado", "aprovado", "concluido", "active"})]
    if df_paid.empty:
        return None

    df_paid = df_paid.copy()
    df_paid["bucket"] = df_paid["forma_pagamento"].apply(_bucket_metodo_pagamento)
    total = len(df_paid)
    vc = df_paid["bucket"].value_counts()
    rows = [
        {"metodo": m, "qtd": int(n), "pct": float(n / total * 100)}
        for m, n in vc.items()
    ]
    rows.sort(key=lambda r: r["qtd"], reverse=True)
    return {"rows": rows, "total": total}
