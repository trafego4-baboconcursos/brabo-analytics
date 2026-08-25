"""
frontend/db_readers/ads_meta.py — Leitor de dados do Meta Ads (banco analytics).
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code
from frontend.db import _get_engine
from frontend.models import MetaCriativo, MetaSummary
from src.constants import ETAPAS_ORDEM

logger = get_logger("db")


def get_historico_ad_codes(code: str) -> set[str]:
    """Retorna todos os AD\\d+ já usados em lançamentos ANTERIORES do mesmo produto."""
    produto_prefix = code.split("-")[0].upper() if code else ""
    if not produto_prefix:
        return set()
    engine = _get_engine()
    _TABELAS_VALIDAS = {"meta_ads_daily", "google_ads_daily"}
    vistos: set[str] = set()
    try:
        with engine.connect() as conn:
            for tabela in ("meta_ads_daily", "google_ads_daily"):
                assert tabela in _TABELAS_VALIDAS, f"tabela inválida: {tabela}"
                rows = conn.execute(
                    text(f"""
                        SELECT DISTINCT ad_name FROM {tabela}
                        WHERE lancamento_codigo != :code
                          AND lancamento_codigo ILIKE :prefix
                    """),
                    {"code": code, "prefix": f"{produto_prefix}-%"},
                ).fetchall()
                for row in rows:
                    m = re.search(r"\bAD\d+\b", str(row[0] or ""), flags=re.IGNORECASE)
                    if m:
                        vistos.add(m.group(0).upper())
    except Exception:
        logger.exception("Falha ao buscar histórico de ad codes; retornando vazio")
    return vistos


ETAPA_MAP = {
    "pré-qualificação": "Pré-Qualificação", "pre-qualificacao": "Pré-Qualificação",
    "pré-quali": "Pré-Qualificação", "pre-quali": "Pré-Qualificação",
    "captação": "Captação", "captacao": "Captação", "capta": "Captação",
    "lembrete": "Lembrete",
    "depoimento": "Depoimento", "depoimentos": "Depoimento",
    "replay aulas": "Replay", "replay": "Replay",  # deve vir antes de aula para [replay][aula N] → Replay
    "aulas no ar": "Aulas no Ar", "aulas-no-ar": "Aulas no Ar",
    "aula 1": "Aulas no Ar", "aula 2": "Aulas no Ar", "aula 3": "Aulas no Ar", "aula 4": "Aulas no Ar",
    "matrículas abertas": "Matrículas Abertas", "matriculas abertas": "Matrículas Abertas",
    "matrículas": "Matrículas Abertas", "matriculas": "Matrículas Abertas",
}
TEMPERATURA_MAP = {
    "quente": "Quente", "frio": "Frio", "específico": "Específico", "especifico": "Específico", "lookalike": "Frio",
}
BUCKET_MAP = {
    "principal": "Principal", "potencial": "Potencial", "reels": "Reels",
    "imagem": "Imagem", "search": "Search", "p-max": "P-Max",
    "shorts": "Shorts",
    "novos-ads": "Novos Ads", "novos_ads": "Novos Ads",
}
MODIFIER_MAP = {
    "otimizada": "otimizada", "teste": "teste",
    "melhores-ads": "melhores ads", "new-ads": "new ads",
}


_PUBLICO_ORDEM = [
    "Cadastrados", "Envolvimento", "Vídeo", "Lista", "Semelhante",
    "Pág. de Captura", "Pág. de Vendas", "Advantage+", "Interesses", "Outros",
]


def _categorize_publico(adset: Any) -> str:
    """Classifica o adset numa categoria de público (base do cascateamento 00-06).

    Envolvimento retorna com a janela ("Envolvimento 30D") quando o nome traz
    o sufixo de dias; as demais categorias são agregadas sem sub-janela.
    """
    a = str(adset or "").lower()
    dias = re.search(r"(\d+)\s*d\b", a)
    janela = f" {dias.group(1)}D" if dias else ""
    if "cadastrad" in a:
        return "Cadastrados"
    if "envolvimento" in a or "engajamento" in a:
        return f"Envolvimento{janela}"
    if re.search(r"viu\s|v[íi]deo|\d+\s*%", a):
        return "Vídeo"
    if "lista" in a or "e-mail" in a or "email" in a or "[m]" in a or "checkout" in a:
        return "Lista"
    if "semelhante" in a or "lookalike" in a or "look alike" in a:
        return "Semelhante"
    if "captura" in a:
        return "Pág. de Captura"
    if "vendas" in a or "[site]" in a:
        return "Pág. de Vendas"
    if "advantage" in a:
        return "Advantage+"
    if "interesse" in a or "education" in a or "higher" in a:
        return "Interesses"
    return "Outros"


def _categorize_campaign(camp: str) -> tuple[str, str, str, str]:
    camp = str(camp).lower()
    etapa = "Outros"
    for k, v in ETAPA_MAP.items():
        if f"[{k}]" in camp or f"][{k}]" in camp:
            etapa = v
            break
    temp = "Outros"
    for k, v in TEMPERATURA_MAP.items():
        if f"[{k}]" in camp:
            temp = v
            break
    bucket = "Outros"
    for k, v in BUCKET_MAP.items():
        if f"[{k}]" in camp:
            bucket = v
            break
    modifier = None
    for k, v in MODIFIER_MAP.items():
        if f"[{k}]" in camp:
            modifier = v
            break
    seg_parts = [p for p in [temp if temp != "Outros" else None,
                              bucket if bucket != "Outros" else None] if p]
    segmento = " ".join(seg_parts) if seg_parts else "Outros"
    if modifier:
        segmento += f" ({modifier})"
    return etapa, temp, bucket, segmento


def read_meta(launch_folder_or_code: Any, start_date=None, end_date=None) -> MetaSummary | None:
    # deferred import to avoid circular dependency (read_vendas still in database_reader)
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    _COLS = "date, ad_id, ad_name, adset_name, campaign_name, impressions, clicks, spend, leads, video_thruplays"
    if start_date and end_date:
        df = pd.read_sql(
            text(f"SELECT {_COLS} FROM meta_ads_daily WHERE lancamento_codigo = :code AND date BETWEEN :start AND :end"),
            engine,
            params={"code": code, "start": start_date, "end": end_date}
        )
    else:
        df = pd.read_sql(
            text(f"SELECT {_COLS} FROM meta_ads_daily WHERE lancamento_codigo = :code"),
            engine,
            params={"code": code}
        )
    if df.empty:
        return None

    summary = MetaSummary()
    summary.data_inicio = df["date"].min().strftime("%Y-%m-%d")
    summary.data_fim = df["date"].max().strftime("%Y-%m-%d")
    summary.total_gasto = float(df["spend"].sum())
    summary.total_leads = int(df["leads"].sum())
    summary.total_cliques = int(df["clicks"].sum())
    summary.total_impressoes = int(df["impressions"].sum())
    summary.total_thruplays = int(df["video_thruplays"].sum())

    summary.cpl_medio = summary.total_gasto / summary.total_leads if summary.total_leads > 0 else 0.0
    summary.ctr_medio = summary.total_cliques / summary.total_impressoes * 100 if summary.total_impressoes > 0 else 0.0
    summary.cpm_medio = summary.total_gasto / summary.total_impressoes * 1000 if summary.total_impressoes > 0 else 0.0

    df["etapa"] = "Outros"
    df["temperatura"] = "Outros"
    df["bucket"] = "Outros"

    df["etapa"], df["temperatura"], df["bucket"], df["segmento"] = zip(
        *df["campaign_name"].map(_categorize_campaign)
    )

    # Agrupamentos
    etapa_grouped = df.groupby("etapa").agg(
        custo=("spend", "sum"),
        leads=("leads", "sum"),
        thruplays=("video_thruplays", "sum"),
        num_campanhas=("campaign_name", "nunique"),
    ).reset_index()
    total_spend_etapas = etapa_grouped["custo"].sum() or 1
    etapa_data_raw: dict[str, dict] = {}
    for _, r in etapa_grouped.iterrows():
        etapa_data_raw[r["etapa"]] = {
            "etapa": r["etapa"],
            "custo": float(r["custo"]),
            "gasto": float(r["custo"]),
            "leads": int(r["leads"]),
            "thruplays": int(r["thruplays"]),
            "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
            "custo_thruplay": float(r["custo"] / r["thruplays"]) if r["thruplays"] > 0 else 0.0,
            "pct": float(r["custo"] / total_spend_etapas * 100),
            "num_campanhas": int(r["num_campanhas"]),
        }
    zero_meta = {"custo": 0.0, "gasto": 0.0, "leads": 0, "thruplays": 0, "cpl": 0.0, "custo_thruplay": 0.0, "pct": 0.0, "num_campanhas": 0}
    for etapa in ETAPAS_ORDEM:
        summary.por_etapa[etapa] = etapa_data_raw.get(etapa, {"etapa": etapa, **zero_meta})
    for etapa, data in etapa_data_raw.items():
        if etapa not in summary.por_etapa:
            summary.por_etapa[etapa] = data

    temp_grouped = df.groupby("temperatura").agg(custo=("spend", "sum"), leads=("leads", "sum")).reset_index()
    total_spend_temperaturas = temp_grouped["custo"].sum() or 1
    for _, r in temp_grouped.iterrows():
        summary.por_temperatura[r["temperatura"]] = {
            "temperatura": r["temperatura"],
            "custo": float(r["custo"]),
            "gasto": float(r["custo"]),
            "leads": int(r["leads"]),
            "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
            "pct": float(r["custo"] / total_spend_temperaturas * 100)
        }

    df_cap = df[df["etapa"] == "Captação"]
    cap_grouped = df_cap.groupby("temperatura").agg(custo=("spend", "sum"), leads=("leads", "sum")).reset_index()
    total_spend_cap = cap_grouped["custo"].sum() or 1
    for _, r in cap_grouped.iterrows():
        summary.por_temperatura_captacao[r["temperatura"]] = {
            "temperatura": r["temperatura"],
            "custo": float(r["custo"]),
            "gasto": float(r["custo"]),
            "leads": int(r["leads"]),
            "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
            "pct": float(r["custo"] / total_spend_cap * 100)
        }

    bucket_grouped = df.groupby("bucket").agg(custo=("spend", "sum"), leads=("leads", "sum")).reset_index()
    total_spend_buckets = bucket_grouped["custo"].sum() or 1
    for _, r in bucket_grouped.iterrows():
        summary.por_bucket[r["bucket"]] = {
            "bucket": r["bucket"],
            "custo": float(r["custo"]),
            "gasto": float(r["custo"]),
            "leads": int(r["leads"]),
            "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
            "pct": float(r["custo"] / total_spend_buckets * 100)
        }

    # Segmento — apenas campanhas de Captação
    df_cap = df[df["etapa"] == "Captação"]
    if not df_cap.empty:
        # Mesma janela usada pela query principal deste reader — evita duplicar a
        # consulta inteira de Hotmart+TMB com uma cache-key diferente (start=None).
        vendas = read_vendas(code, start_date=start_date, end_date=end_date)
        buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()
        sales_by_content = {}
        if buyers:
            df_leads = pd.read_sql(
                text("SELECT utm_content, email FROM leads WHERE lancamento_codigo = :code AND (utm_source ILIKE '%facebook%' OR utm_source ILIKE '%ig%' OR utm_source ILIKE '%meta%')"),
                engine,
                params={"code": code}
            )
            if not df_leads.empty:
                df_leads["is_buyer"] = df_leads["email"].isin(buyers)
                df_leads["receita"] = df_leads["email"].map(lambda e: vendas.receita_por_email.get(e, 0.0))
                sales_by_content = df_leads[df_leads["is_buyer"]].groupby("utm_content").agg(
                    sales=("is_buyer", "sum"),
                    receita=("receita", "sum")
                ).to_dict("index")

        seg_grouped = df_cap.groupby("segmento").agg(
            custo=("spend", "sum"), leads=("leads", "sum"),
            num_campanhas=("campaign_name", "nunique"),
        ).reset_index()
        total_seg = seg_grouped["custo"].sum() or 1
        for _, r in seg_grouped.iterrows():
            summary.por_segmento[r["segmento"]] = {
                "gasto": float(r["custo"]),
                "leads": int(r["leads"]),
                "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
                "pct": float(r["custo"] / total_seg * 100),
                "num_campanhas": int(r["num_campanhas"]),
            }

        # Públicos - agrupamento por adset_name
        adset_grouped = df_cap.groupby("adset_name").agg(
            custo=("spend", "sum"),
            leads=("leads", "sum"),
            cliques=("clicks", "sum"),
            impressions=("impressions", "sum"),
            campaign_name=("campaign_name", "first")
        ).reset_index().sort_values(by="custo", ascending=False)
        for _, r in adset_grouped.iterrows():
            cost = float(r["custo"] or 0)
            leads = int(r["leads"] or 0)
            clicks = int(r["cliques"] or 0)
            impr = int(r["impressions"] or 0)

            adset = r["adset_name"] or "Sem Nome"
            agg_data = sales_by_content.get(adset, {"sales": 0, "receita": 0.0})
            vendas_cruzadas = int(agg_data["sales"])
            receita_cruzada = float(agg_data["receita"])

            summary.publicos.append({
                "segmento": adset,
                "campanha": str(r["campaign_name"]),
                "custo": cost,
                "cliques": clicks,
                "conversoes": leads,
                "cpl": cost / leads if leads > 0 else 0.0,
                "vendas": vendas_cruzadas,
                "receita": receita_cruzada,
                "cpa_vendas": cost / vendas_cruzadas if vendas_cruzadas > 0 else 0.0,
                "cpc": cost / clicks if clicks > 0 else 0.0,
                "ctr": clicks / impr * 100 if impr > 0 else 0.0
            })

    # Categorias de público por clima — só Captação (pauta debriefing:
    # "Detalhamento dos públicos", ex. Quente: Envolvimento 30D/180D, Vídeo, Lista)
    if not df_cap.empty:
        df_pub = df_cap.copy()
        df_pub["publico"] = df_pub["adset_name"].map(_categorize_publico)
        pub_grouped = df_pub.groupby(["temperatura", "publico"]).agg(
            custo=("spend", "sum"), leads=("leads", "sum"),
            num_adsets=("adset_name", "nunique"),
        ).reset_index()
        for temp in pub_grouped["temperatura"].unique():
            sub = pub_grouped[pub_grouped["temperatura"] == temp].sort_values("custo", ascending=False)
            total_temp = sub["custo"].sum() or 1
            summary.por_publico_captacao[temp] = [
                {
                    "publico": r["publico"],
                    "gasto": float(r["custo"]),
                    "leads": int(r["leads"]),
                    "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
                    "pct": float(r["custo"] / total_temp * 100),
                    "num_adsets": int(r["num_adsets"]),
                }
                for _, r in sub.iterrows()
            ]

    # Por dia e etapa
    dia_grouped = df.groupby(["date", "etapa"]).agg(
        custo=("spend", "sum"), leads=("leads", "sum"),
        cliques=("clicks", "sum"), impressions=("impressions", "sum"),
        thruplays=("video_thruplays", "sum")
    ).reset_index()
    dias: dict[str, dict] = {}
    for _, r in dia_grouped.iterrows():
        dia = r["date"].strftime("%Y-%m-%d")
        etapa = r["etapa"]
        if dia not in dias:
            dias[dia] = {
                "data": dia,
                "dia": dia,
                "custo": 0.0,
                "gasto": 0.0,
                "leads": 0,
                "cliques": 0,
                "impressoes": 0,
                "thruplays": 0,
                "cpl": 0.0,
                "por_etapa": {},
            }
        etapa_data = {
            "etapa": etapa,
            "custo": float(r["custo"]),
            "gasto": float(r["custo"]),
            "leads": int(r["leads"]),
            "cliques": int(r["cliques"]),
            "impressoes": int(r["impressions"]),
            "thruplays": int(r["thruplays"]),
            "cpl": float(r["custo"] / r["leads"]) if r["leads"] > 0 else 0.0,
        }
        dias[dia]["por_etapa"][etapa] = etapa_data
        dias[dia]["custo"] += etapa_data["custo"]
        dias[dia]["gasto"] += etapa_data["gasto"]
        dias[dia]["leads"] += etapa_data["leads"]
        dias[dia]["cliques"] += etapa_data["cliques"]
        dias[dia]["impressoes"] += etapa_data["impressoes"]
        dias[dia]["thruplays"] += etapa_data["thruplays"]
    for dia_data in dias.values():
        dia_data["cpl"] = dia_data["gasto"] / dia_data["leads"] if dia_data["leads"] > 0 else 0.0
    summary.por_dia = list(dias.values())

    # Ad codes que já apareceram em lançamentos ANTERIORES do mesmo produto
    _ad_codes_vistos_antes: set[str] = get_historico_ad_codes(code)

    ad_grouped = df.groupby("ad_name").agg(
        ad_id=("ad_id", "first"), campaign_name=("campaign_name", "first"),
        adset_name=("adset_name", "first"), etapa=("etapa", "first"),
        temperatura=("temperatura", "first"), bucket=("bucket", "first"),
        gasto=("spend", "sum"), impressoes=("impressions", "sum"),
        cliques=("clicks", "sum"), leads=("leads", "sum"),
        thruplays=("video_thruplays", "sum")
    ).reset_index()

    for _, r in ad_grouped.iterrows():
        name = r["ad_name"]
        match = re.search(r"\bAD\d+\b", name, flags=re.IGNORECASE)
        ad_code = match.group(0).upper() if match else ""

        c = MetaCriativo(
            nome=name,
            campanha=r["campaign_name"],
            conjunto=r["adset_name"],
            etapa=r["etapa"],
            temperatura=r["temperatura"],
            bucket=r["bucket"],
            ad_code=ad_code,
            gasto=float(r["gasto"]),
            impressoes=int(r["impressoes"]),
            cliques=int(r["cliques"]),
            leads=int(r["leads"]),
            thruplays=int(r["thruplays"]),
            cpl=float(r["gasto"] / r["leads"]) if r["leads"] > 0 else 0.0,
            ctr=float(r["cliques"] / r["impressoes"] * 100) if r["impressoes"] > 0 else 0.0,
            cpc=float(r["gasto"] / r["cliques"]) if r["cliques"] > 0 else 0.0,
            cpm=float(r["gasto"] / r["impressoes"] * 1000) if r["impressoes"] > 0 else 0.0,
            custo_thruplay=float(r["gasto"] / r["thruplays"]) if r["thruplays"] > 0 else 0.0
        )

        ad_dict = {
            "ad_code": ad_code,
            "nome": c.nome,
            "gasto": c.gasto,
            "leads": c.leads,
            "cpl": c.cpl,
            "ctr": c.ctr,
            "cpm": c.cpm,
            "thruplays": c.thruplays,
            "cliques": c.cliques,
            "impressoes": c.impressoes,
            "origem": "Meta Ads"
        }

        if r["etapa"] == "Captação":
            summary.captacao_por_ad.append(ad_dict)

            if ad_code and ad_code in _ad_codes_vistos_antes:
                summary.validados.append(c)
            else:
                summary.novos.append(c)
        elif r["etapa"] == "Pré-Qualificação":
            summary.preq_por_ad.append(ad_dict)

    summary.captacao_por_ad = sorted(summary.captacao_por_ad, key=lambda x: x["leads"], reverse=True)
    summary.preq_por_ad = sorted(summary.preq_por_ad, key=lambda x: x["leads"], reverse=True)
    summary.validados = sorted(summary.validados, key=lambda x: x.leads, reverse=True)
    summary.novos = sorted(summary.novos, key=lambda x: x.leads, reverse=True)

    with_leads = [c for c in summary.validados + summary.novos if c.leads >= 10]
    summary.top_por_leads = sorted(summary.validados + summary.novos, key=lambda x: x.leads, reverse=True)[:20]
    summary.top_por_cpl = sorted(with_leads, key=lambda x: x.cpl)[:5]
    summary.piores_cpl = sorted(with_leads, key=lambda x: x.cpl, reverse=True)[:5]

    # Demographics Meta
    try:
        df_demo = pd.read_sql(
            text("SELECT age, gender, SUM(cost) as cost, SUM(clicks) as clicks, SUM(leads) as leads, SUM(impressions) as impressions FROM meta_ads_demographics_daily WHERE lancamento_codigo = :code GROUP BY age, gender"),
            engine,
            params={"code": code}
        )
        if not df_demo.empty:
            df_age = df_demo.groupby("age", as_index=False, dropna=False).agg({"cost": "sum", "clicks": "sum", "leads": "sum", "impressions": "sum"})
            df_age["cpl"] = np.where(df_age["leads"] > 0, df_age["cost"] / df_age["leads"], 0)
            df_age["ctr"] = np.where(df_age["impressions"] > 0, (df_age["clicks"] / df_age["impressions"]) * 100, 0)
            df_age = df_age.sort_values(by="cost", ascending=False).round(2)
            summary.demografia_idade = df_age.to_dict("records")

            df_gender = df_demo.groupby("gender", as_index=False, dropna=False).agg({"cost": "sum", "clicks": "sum", "leads": "sum", "impressions": "sum"})
            df_gender["cpl"] = np.where(df_gender["leads"] > 0, df_gender["cost"] / df_gender["leads"], 0)
            df_gender["ctr"] = np.where(df_gender["impressions"] > 0, (df_gender["clicks"] / df_gender["impressions"]) * 100, 0)
            df_gender = df_gender.sort_values(by="cost", ascending=False).round(2)
            summary.demografia_genero = df_gender.to_dict("records")
    except Exception:
        logger.exception("Erro ao ler demografia Meta")

    return summary
