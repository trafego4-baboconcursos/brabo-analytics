"""
frontend/database_reader.py — Brabo Analytics
Leitor que busca dados diretamente do banco de dados no Supabase (SQLAlchemy)
e retorna as mesmas estruturas e dataclasses que os readers CSV antigos,
garantindo compatibilidade 100% com os templates HTML do Frontend.
"""
from __future__ import annotations

import re
import json
import time as _time_module
import unicodedata
import math
import numpy as np
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Optional
import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv
from logger import get_logger
from frontend.utils import (
    _norm_text, _extract_launch_code,
    _safe_div, _delta,
    _safe_date, _normalize_product_ids,
)
from src.constants import (
    ETAPAS_ORDEM, PRODUCT_BY_PREFIX,
    LAUNCH_ACCENT, LAUNCH_SHORT, LAUNCH_NAMES,
)
from frontend.db import _get_engine, _get_users_engine
from frontend.models import (
    Launch, MetaCriativo, MetaSummary,
    GoogleCampanha, GooglePublico, GoogleSummary,
    VendasSummary, LeadsSummary,
    HotmartDetails, TmbDetails, YoutubeAulaStat,
    ConsolidadoVendasSummary, TypeformSummary,
    AcCampaign, AcCampaignSummary,
    ComparativoAd, ComparativoData,
)


# ─ Re-exportações dos módulos de domínio extraídos ─────────────────────────
from frontend.db_readers.users import (  # noqa: E402
    PRODUCT_LABELS, ROLE_LABELS, _users_table_exists,
    get_user_by_email, get_user_by_id, list_users, create_user,
    update_user, update_last_login, bootstrap_admin_if_needed,
    create_invite, get_invite, use_invite, list_invites, delete_invite,
)
from frontend.db_readers.typeform import (  # noqa: E402
    _get_typeform_forms, _get_typeform_fields, _resolve_typeform_ids,
    _reconstruct_tabular_df, _build_typeform_comparison,
    read_typeform, _generate_ia_insights,
)
from frontend.db_readers.ads_meta import get_historico_ad_codes, read_meta  # noqa: E402
from frontend.db_readers.ads_google import (  # noqa: E402
    _classify_google_type, read_google, read_daily_breakdown,
)
from frontend.db_readers.launches import (  # noqa: E402
    discover_launches, get_launch,
    autodetect_launch_data, read_launch_config, save_launch_config,
    get_drive_thumbnails, count_campaigns_for_filter,
    get_etl_status, _ETL_SOURCES,
)

from frontend.db_readers.sales import (  # noqa: E402
    read_vendas, read_hotmart_details, read_tmb_details, read_vendas_consolidado,
)
from frontend.db_readers.leads import (  # noqa: E402
    read_ac_leads_for_attribution, read_leads, read_ac_campaigns,
)

load_dotenv()

logger = get_logger("db")


def read_comparativo(launch_b: "Launch", launch_a: "Launch") -> ComparativoData:
    """
    Compara launch_b (atual) com launch_a (anterior do mesmo produto).
    Retorna ComparativoData com todos os indicadores e deltas calculados.
    """
    engine = _get_engine()
    data = ComparativoData(
        has_data=True,
        code_a=launch_a.code,
        code_b=launch_b.code,
        accent_a=launch_a.accent,
        accent_b=launch_b.accent,
    )

    def _query_launch(launch: "Launch") -> dict:
        result = {"top_ads": [], "top_google": []}
        cfg = read_launch_config(launch.code)
        cs = cfg.get("captacao_start_date")
        ce = cfg.get("captacao_end_date")
        rs = cfg.get("carrinho_start_date")
        re_ = cfg.get("carrinho_end_date")

        vendas_sum = read_vendas(launch.code, start_date=rs, end_date=re_)

        def _date_clause(col: str) -> str:
            return f" AND {col} BETWEEN :cs AND :ce" if cs and ce else ""

        p_base   = {"code": launch.code}
        p_dates  = {"code": launch.code, "cs": cs, "ce": ce}

        with engine.connect() as conn:
            # â€” Investimento Meta â€”
            r = conn.execute(text(f"""
                SELECT COALESCE(SUM(spend), 0)
                FROM meta_ads_daily
                WHERE lancamento_codigo = :code{_date_clause('date')}
            """), p_dates if cs and ce else p_base).fetchone()
            result["meta_inv"] = float(r[0] or 0)

            # â€” Meta leads e ads Ãºnicos â€”
            r = conn.execute(text(f"""
                SELECT COALESCE(SUM(leads), 0),
                       COUNT(DISTINCT ad_name)
                FROM meta_ads_daily
                WHERE lancamento_codigo = :code{_date_clause('date')}
            """), p_dates if cs and ce else p_base).fetchone()
            result["meta_leads"] = int(r[0] or 0)
            result["meta_ads"]   = int(r[1] or 0)

            # â€” Investimento Google â€”
            r = conn.execute(text(f"""
                SELECT COALESCE(SUM(cost), 0),
                       COALESCE(SUM(conversions), 0),
                       COUNT(DISTINCT campaign_name),
                       CASE WHEN SUM(clicks)>0 THEN SUM(cost)/SUM(clicks) ELSE 0 END,
                       CASE WHEN SUM(impressions)>0 THEN SUM(clicks)*100.0/SUM(impressions) ELSE 0 END
                FROM google_ads_daily
                WHERE lancamento_codigo = :code{_date_clause('date')}
            """), p_dates if cs and ce else p_base).fetchone()
            result["google_inv"]   = float(r[0] or 0)
            result["google_conv"]  = int(r[1] or 0)
            result["google_camps"] = int(r[2] or 0)
            result["google_cpc"]   = float(r[3] or 0)
            result["google_ctr"]   = float(r[4] or 0)

            # â€” Leads CRM â€”
            r = conn.execute(text(f"""
                SELECT COUNT(*) FROM leads
                WHERE lancamento_codigo = :code{_date_clause('created_at::date')}
            """), p_dates if cs and ce else p_base).fetchone()
            result["leads"] = int(r[0] or 0)

            # â€” Top 5 anÃºncios Meta â€”
            r2 = conn.execute(text(f"""
                SELECT
                    ad_name as nome,
                    SUM(spend) as inv,
                    SUM(leads) as leads,
                    0 as vendas,
                    CASE WHEN SUM(leads)>0 THEN SUM(spend)/SUM(leads) ELSE 0 END as cpl
                FROM meta_ads_daily
                WHERE lancamento_codigo = :code
                  AND spend > 0{_date_clause('date')}
                GROUP BY ad_name
                ORDER BY inv DESC
                LIMIT 5
            """), p_dates if cs and ce else p_base).fetchall()
            result["top_ads"] = [
                ComparativoAd(
                    nome=row[0] or "â€”",
                    inv=float(row[1] or 0),
                    leads=int(row[2] or 0),
                    cpl=float(row[4] or 0),
                )
                for row in r2
            ]

            # â€” Top 5 anÃºncios Google â€”
            r3 = conn.execute(text(f"""
                SELECT
                    ad_name as nome,
                    SUM(cost) as inv,
                    SUM(conversions) as conv,
                    CASE WHEN SUM(conversions)>0 THEN SUM(cost)/SUM(conversions) ELSE 0 END as cpa
                FROM google_ads_daily
                WHERE lancamento_codigo = :code
                  AND cost > 0{_date_clause('date')}
                GROUP BY ad_name
                ORDER BY inv DESC
                LIMIT 5
            """), p_dates if cs and ce else p_base).fetchall()
            result["top_google"] = [
                ComparativoAd(
                    nome=row[0] or "â€”",
                    inv=float(row[1] or 0),
                    leads=int(row[2] or 0),
                    cpl=float(row[3] or 0),
                )
                for row in r3
            ]

        result["hotmart_count"]   = int(vendas_sum.hotmart_vendas   if vendas_sum else 0)
        result["hotmart_receita"] = float(vendas_sum.hotmart_receita if vendas_sum else 0.0)
        result["tmb_count"]       = int(vendas_sum.tmb_vendas       if vendas_sum else 0)
        result["tmb_receita"]     = float(vendas_sum.tmb_receita     if vendas_sum else 0.0)

        return result

    ra = _query_launch(launch_a)
    rb = _query_launch(launch_b)

    # â€” Investimentos â€”
    inv_capt_a = ra["meta_inv"] + ra["google_inv"]
    inv_capt_b = rb["meta_inv"] + rb["google_inv"]
    data.inv_a = inv_capt_a
    data.inv_b = inv_capt_b
    data.inv_meta_a = ra["meta_inv"]
    data.inv_meta_b = rb["meta_inv"]
    data.inv_google_a = ra["google_inv"]
    data.inv_google_b = rb["google_inv"]

    # â€” Meta â€”
    data.meta_leads_a = ra["meta_leads"]
    data.meta_leads_b = rb["meta_leads"]
    data.meta_cpl_a   = _safe_div(ra["meta_inv"], ra["meta_leads"])
    data.meta_cpl_b   = _safe_div(rb["meta_inv"], rb["meta_leads"])
    data.meta_ads_a   = ra["meta_ads"]
    data.meta_ads_b   = rb["meta_ads"]

    # â€” Google â€”
    data.google_conv_a  = ra["google_conv"]
    data.google_conv_b  = rb["google_conv"]
    data.google_camps_a = ra["google_camps"]
    data.google_camps_b = rb["google_camps"]
    data.google_cpc_a   = ra["google_cpc"]
    data.google_cpc_b   = rb["google_cpc"]
    data.google_ctr_a   = ra["google_ctr"]
    data.google_ctr_b   = rb["google_ctr"]
    data.google_cpa_a   = _safe_div(ra["google_inv"], ra["google_conv"])
    data.google_cpa_b   = _safe_div(rb["google_inv"], rb["google_conv"])

    # â€” Leads CRM â€”
    data.leads_a = ra["leads"]
    data.leads_b = rb["leads"]
    data.cpl_a   = _safe_div(inv_capt_a, ra["leads"])
    data.cpl_b   = _safe_div(inv_capt_b, rb["leads"])

    # â€” Vendas â€”
    vendas_a = ra["hotmart_count"] + ra["tmb_count"]
    vendas_b = rb["hotmart_count"] + rb["tmb_count"]
    receita_a = ra["hotmart_receita"] + ra["tmb_receita"]
    receita_b = rb["hotmart_receita"] + rb["tmb_receita"]
    data.vendas_a   = vendas_a
    data.vendas_b   = vendas_b
    data.hotmart_a  = ra["hotmart_count"]
    data.hotmart_b  = rb["hotmart_count"]
    data.tmb_a      = ra["tmb_count"]
    data.tmb_b      = rb["tmb_count"]
    data.receita_a  = receita_a
    data.receita_b  = receita_b
    data.ticket_a   = _safe_div(receita_a, vendas_a)
    data.ticket_b   = _safe_div(receita_b, vendas_b)
    data.roas_a     = _safe_div(receita_a, inv_capt_a)
    data.roas_b     = _safe_div(receita_b, inv_capt_b)
    data.tx_conv_a  = _safe_div(vendas_a, ra["leads"]) * 100 if ra["leads"] else 0.0
    data.tx_conv_b  = _safe_div(vendas_b, rb["leads"]) * 100 if rb["leads"] else 0.0
    data.cpa_a      = _safe_div(inv_capt_a, vendas_a)
    data.cpa_b      = _safe_div(inv_capt_b, vendas_b)

    # â€” Top ads â€”
    data.top_ads_a = ra["top_ads"]
    data.top_ads_b = rb["top_ads"]
    data.top_google_a = ra.get("top_google", [])
    data.top_google_b = rb.get("top_google", [])

    # â€” Funil â€”
    data.funil_a = {
        "leads":   ra["leads"],
        "meta":    ra["meta_leads"],
        "google":  ra["google_conv"],
        "vendas":  vendas_a,
        "tx_crm":  data.tx_conv_a,
    }
    data.funil_b = {
        "leads":   rb["leads"],
        "meta":    rb["meta_leads"],
        "google":  rb["google_conv"],
        "vendas":  vendas_b,
        "tx_crm":  data.tx_conv_b,
    }

    return data




def read_youtube_aulas(launch_code: str) -> list["YoutubeAulaStat"]:
    """Lê métricas das aulas YouTube do banco de dados."""
    from frontend.db import _get_engine
    from sqlalchemy import text as _text
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                _text("""
                    SELECT aula_num, video_id, titulo, duration_sec,
                           views_total, views_live, views_replay,
                           likes, comments, watch_time_min,
                           avg_view_dur_sec, avg_view_pct, peak_concurrent
                    FROM youtube_aulas_stats
                    WHERE launch_code = :code
                    ORDER BY aula_num NULLS LAST, video_id
                """),
                {"code": launch_code},
            ).fetchall()
    except Exception:
        return []
    return [
        YoutubeAulaStat(
            aula_num        = r.aula_num or 0,
            video_id        = r.video_id or "",
            titulo          = r.titulo or "",
            duration_sec    = r.duration_sec or 0,
            views_total     = r.views_total or 0,
            views_live      = r.views_live or 0,
            views_replay    = r.views_replay or 0,
            likes           = r.likes or 0,
            comments        = r.comments or 0,
            watch_time_min  = float(r.watch_time_min or 0),
            avg_view_dur_sec= float(r.avg_view_dur_sec or 0),
            avg_view_pct    = float(r.avg_view_pct or 0),
            peak_concurrent = r.peak_concurrent or 0,
        )
        for r in rows
    ]

KNOWN_META_ACCOUNTS = [
    {"id": "act_438212624024216",  "name": "CA - Anunciante Felipe Graton", "project": "PBB"},
    {"id": "act_1175937361058463", "name": "CA - Criadora de PÃºblicos 2",   "project": "PBB"},
    {"id": "act_1407542209639031", "name": "CA2 - Anunciante (TJSP/INSS)",  "project": "PES/PI"},
]

KNOWN_GOOGLE_ACCOUNTS = [
    {"id": "1450466453", "name": "Felipe Graton - Brabo Concursos", "project": "PBB"},
    {"id": "6482320788", "name": "LanÃ§amentos - Brabo Concursos",   "project": "PES/PI"},
]




