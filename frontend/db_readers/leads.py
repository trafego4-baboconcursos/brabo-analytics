"""
frontend/db_readers/leads.py — leitores de leads, Active Campaign e confronto de atribuição.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code
from frontend.db import _get_engine
from frontend.models import (
    LeadsSummary, VendasSummary,
    AcCampaign, AcCampaignSummary, Launch,
)

logger = get_logger("db")


def read_ac_leads_for_attribution(launch_code: str, start_date=None, end_date=None) -> pd.DataFrame:  # noqa: ARG001
    """Retorna DataFrame com email_norm e UTMs da tabela leads para o lançamento."""
    engine = _get_engine()
    df = pd.read_sql(
        text("""
            SELECT email, utm_source, utm_medium, utm_campaign, utm_content, utm_term
            FROM leads
            WHERE lancamento_codigo = :code
        """),
        engine,
        params={"code": launch_code},
    )
    if df.empty:
        return df
    df["email_norm"] = df["email"].astype(str).str.strip().str.lower()
    df = df[df["email_norm"].str.contains("@", na=False)].copy()
    for col in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def read_leads(launch_folder_or_code: Any, vendas: VendasSummary | None = None, start_date=None, end_date=None) -> LeadsSummary | None:  # noqa: ARG001
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    df = pd.read_sql(
        text("SELECT * FROM leads WHERE lancamento_codigo = :code"),
        engine,
        params={"code": code}
    )
    if df.empty:
        return None

    summary = LeadsSummary()
    summary.total_leads = len(df)

    buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()
    receita_por_email = vendas.receita_por_email if vendas else {}
    summary.total_compradores = len(buyers)

    df["email_norm"] = df["email"].str.strip().str.lower()
    rastreados_emails = set(df["email_norm"]) & buyers
    summary.compradores_rastreados = len(rastreados_emails)
    summary.compradores_sem_utm = max(0, summary.total_compradores - summary.compradores_rastreados)
    summary.emails_rastreados = rastreados_emails
    summary.tx_conversao = summary.compradores_rastreados / summary.total_leads * 100 if summary.total_leads > 0 else 0.0

    def _vendas_para_emails(email_set: set) -> tuple[int, float]:
        v = email_set & buyers
        fat = sum(receita_por_email.get(e, 0.0) for e in v)
        return len(v), fat

    SOURCE_LABEL = {
        "facebook": "Facebook Ads",
        "fb": "Facebook Ads",
        "instagram": "Instagram Ads",
        "ig": "Instagram Ads",
        "google": "Google Ads",
        "youtube": "YouTube",
        "tiktok": "TikTok Ads",
        "email": "E-mail",
        "organico": "Orgânico",
        "organic": "Orgânico",
        "direto": "Direto / Orgânico",
    }
    df["canal"] = df["utm_source"].fillna("").str.strip().str.lower().map(
        lambda s: SOURCE_LABEL.get(s, s.title() if s else "Direto / Orgânico")
    )
    canal_rows = []
    for canal, grp in df.groupby("canal"):
        emails = set(grp["email_norm"])
        v, fat = _vendas_para_emails(emails)
        canal_rows.append({
            "canal": canal,
            "leads": len(grp),
            "compradores": v,
            "faturamento": fat,
            "conversao": v / len(grp) * 100 if len(grp) > 0 else 0.0,
            "ticket": fat / v if v > 0 else 0.0,
        })
    summary.por_canal = sorted([r for r in canal_rows if r["leads"] >= 10], key=lambda x: x["leads"], reverse=True)

    WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    df["dia"] = pd.to_datetime(df["created_at"]).dt.date
    dia_rows = []
    for dia, grp in df.groupby("dia"):
        emails = set(grp["email_norm"])
        v, fat = _vendas_para_emails(emails)
        dt = pd.Timestamp(dia)
        dia_rows.append({
            "_dt": dt,
            "date": dt.strftime("%d/%m"),
            "weekday": WEEKDAYS_PT[dt.weekday()],
            "leads": len(grp),
            "compradores": v,
            "conversao": v / len(grp) * 100 if len(grp) > 0 else 0.0,
            "faturamento": fat,
        })
    today = pd.Timestamp.now().normalize()
    dia_rows_sorted = sorted(
        [r for r in dia_rows if r["_dt"] <= today],
        key=lambda x: x["_dt"]
    )
    if dia_rows_sorted:
        last_dt = dia_rows_sorted[-1]["_dt"]
        cutoff = last_dt - pd.Timedelta(days=90)
        dia_rows_sorted = [r for r in dia_rows_sorted if r["_dt"] >= cutoff]
    for r in dia_rows_sorted:
        del r["_dt"]
    summary.por_dia = dia_rows_sorted

    ETAPA_MAP_LEADS = [
        ("pré-qualificação", "Pré-Qualificação"), ("pre-qualificacao", "Pré-Qualificação"),
        ("pré-quali", "Pré-Qualificação"), ("pre-quali", "Pré-Qualificação"),
        ("replay", "Replay"),
        ("lembrete", "Lembrete"),
        ("matrícula", "Matrículas Abertas"), ("matricula", "Matrículas Abertas"), ("abertas", "Matrículas Abertas"),
        ("aula", "Aulas no Ar"), ("tráfego", "Aulas no Ar"), ("trafego", "Aulas no Ar"),
        ("captação", "Captação"), ("captacao", "Captação"), ("capta", "Captação"),
    ]

    def _etapa(camp: str) -> str:
        c = (camp or "").lower()
        for kw, label in ETAPA_MAP_LEADS:
            if kw in c:
                return label
        return "Outros"

    df["etapa"] = df["utm_campaign"].fillna("").apply(_etapa)
    etapa_rows = []
    for etapa, grp in df.groupby("etapa"):
        emails = set(grp["email_norm"])
        v, fat = _vendas_para_emails(emails)
        etapa_rows.append({
            "etapa": etapa,
            "leads": len(grp),
            "compradores": v,
            "faturamento": fat,
            "conversao": v / len(grp) * 100 if len(grp) > 0 else 0.0,
            "ticket": fat / v if v > 0 else 0.0,
        })
    ETAPAS_ORDER = ["Pré-Qualificação", "Captação", "Lembrete", "Aulas no Ar", "Replay", "Matrículas Abertas", "Outros"]
    summary.por_etapa = sorted(etapa_rows, key=lambda x: ETAPAS_ORDER.index(x["etapa"]) if x["etapa"] in ETAPAS_ORDER else 99)

    def _temp(camp: str) -> str:
        c = (camp or "").lower()
        if "específico" in c or "especifico" in c: return "Específico"
        if "quente" in c:  return "Quente"
        if "morno" in c:   return "Morno"
        if "frio" in c:    return "Frio"
        return "Não classificado"

    df["temp"] = df["utm_campaign"].fillna("").apply(_temp)
    temp_rows = []
    for temp, grp in df.groupby("temp"):
        emails = set(grp["email_norm"])
        v, fat = _vendas_para_emails(emails)
        temp_rows.append({
            "temp": temp,
            "leads": len(grp),
            "compradores": v,
            "faturamento": fat,
            "conversao": v / len(grp) * 100 if len(grp) > 0 else 0.0,
            "ticket": fat / v if v > 0 else 0.0,
        })
    TEMP_ORDER = ["Específico", "Quente", "Morno", "Frio", "Não classificado"]
    summary.por_temperatura = sorted(temp_rows, key=lambda x: TEMP_ORDER.index(x["temp"]) if x["temp"] in TEMP_ORDER else 99)

    df["utm_source_norm"] = df["utm_source"].fillna("Sem source").str.strip()
    df["utm_medium_norm"] = df["utm_medium"].fillna("Sem medium").str.strip()
    for src, grp in df.groupby("utm_source_norm"):
        emails = set(grp["email_norm"])
        v, fat = _vendas_para_emails(emails)
        summary.por_utm_source[src] = {"source": src, "leads": len(grp), "vendas": v, "faturamento": fat, "conversao": v / len(grp) * 100 if len(grp) > 0 else 0.0}
    for med, grp in df.groupby("utm_medium_norm"):
        emails = set(grp["email_norm"])
        v, fat = _vendas_para_emails(emails)
        summary.por_utm_medium[med] = {"medium": med, "leads": len(grp), "vendas": v, "faturamento": fat, "conversao": v / len(grp) * 100 if len(grp) > 0 else 0.0}

    return summary


def read_ac_campaigns(launch: Launch) -> AcCampaignSummary:
    """Busca estatísticas de campanhas de e-mail do Active Campaign filtradas por datas e keywords."""
    engine = _get_engine()
    summary = AcCampaignSummary()

    if not launch or not launch.data_inicio or not launch.data_fim:
        return summary

    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT 1 FROM ac_campaigns LIMIT 1"))
        except Exception:
            logger.debug("Tabela ac_campaigns não encontrada; retornando summary vazio")
            return summary

        rows = conn.execute(
            text("""
                SELECT
                    id, nome_campanha, data_envio, envios, aberturas,
                    aberturas_unicas, cliques, descadastros, bounces
                FROM ac_campaigns
                WHERE DATE(data_envio) >= :start_dt AND DATE(data_envio) <= :end_dt
                ORDER BY data_envio DESC
            """),
            {"start_dt": launch.data_inicio, "end_dt": launch.data_fim}
        ).fetchall()

    if not rows:
        return summary

    code_prefix = launch.code.split("-")[0].upper()
    if code_prefix == "PBB":
        keywords = ["bb", "banco do brasil"]
    elif code_prefix == "PI":
        keywords = ["inss"]
    elif code_prefix == "PES":
        keywords = ["tjsp", "escrevente"]
    else:
        keywords = ["inss", "tjsp", "bb", "banco do brasil"]

    for row in rows:
        nome_campanha = (row[1] or "").lower()
        if not any(k in nome_campanha for k in keywords):
            continue

        envios = row[3] or 0
        aberturas = row[4] or 0
        cliques = row[6] or 0
        descadastros = row[7] or 0

        c = AcCampaign(
            id=row[0],
            nome=row[1],
            data_envio=str(row[2])[:10] if row[2] else "",
            envios=envios,
            aberturas=aberturas,
            aberturas_unicas=row[5] or 0,
            cliques=cliques,
            descadastros=descadastros,
            bounces=row[8] or 0,
            tx_abertura=aberturas / envios * 100 if envios > 0 else 0.0,
            tx_clique=cliques / aberturas * 100 if aberturas > 0 else 0.0,
            tx_descadastro=descadastros / envios * 100 if envios > 0 else 0.0
        )
        summary.campanhas.append(c)
        summary.total_envios += envios
        summary.total_aberturas += aberturas
        summary.total_cliques += cliques

    if not summary.campanhas:
        return summary

    summary.has_data = True

    if summary.total_envios > 0:
        summary.tx_abertura_media = summary.total_aberturas / summary.total_envios * 100
    if summary.total_aberturas > 0:
        summary.tx_clique_media = summary.total_cliques / summary.total_aberturas * 100

    df = pd.DataFrame([{
        "data": c.data_envio,
        "envios": c.envios,
        "aberturas": c.aberturas,
        "cliques": c.cliques
    } for c in summary.campanhas if c.data_envio])

    if not df.empty:
        df_grouped = df.groupby("data").sum().reset_index()
        summary.por_dia = df_grouped.to_dict("records")

    return summary
