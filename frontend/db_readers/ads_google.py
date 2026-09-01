"""
frontend/db_readers/ads_google.py — Leitor de dados do Google Ads (banco analytics).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code
from frontend.db import _get_engine
from frontend.models import GoogleCampanha, GoogleSummary
from frontend.db_readers.ads_meta import get_historico_ad_codes
from src.constants import ETAPAS_ORDEM

logger = get_logger("db")


def _classify_google_type(campaign_name: str) -> str:
    n = (campaign_name or "").lower()
    if "search" in n:    return "search"
    if "p-max" in n:     return "pmax"
    if "display" in n:   return "display"
    return "youtube"


ETAPA_MAP = {
    "pré-qualificação": "Pré-Qualificação", "pre-qualificacao": "Pré-Qualificação",
    "pré-quali": "Pré-Qualificação", "pre-quali": "Pré-Qualificação",
    "captação": "Captação", "captacao": "Captação", "capta": "Captação",
    "lembrete": "Lembrete",
    "depoimento": "Depoimento",
    "replay": "Replay",  # deve vir antes de aula para [replay aula N] → Replay
    "aulas no ar": "Aulas no Ar", "aulas-no-ar": "Aulas no Ar",
    "aula": "Aulas no Ar",  # cobre aula 1/2/3/4 sem replay
    "matrículas abertas": "Matrículas Abertas", "matriculas abertas": "Matrículas Abertas",
    "matrículas": "Matrículas Abertas", "matriculas": "Matrículas Abertas",
    "performance max": "Performance Max", "pmax": "Performance Max",
}
TEMPERATURA_MAP = {
    "quente": "Quente", "frio": "Frio", "específico": "Específico", "especifico": "Específico",
}
BUCKET_MAP_G = {
    "principal": "Principal", "potencial": "Potencial", "reels": "Reels",
    "imagem": "Imagem", "search": "Search", "p-max": "P-Max",
    "shorts": "Shorts",
    "novos-ads": "Novos Ads", "novos_ads": "Novos Ads",
}
MODIFIER_MAP_G = {
    "otimizada": "otimizada", "teste": "teste",
    "melhores-ads": "melhores ads", "new-ads": "new ads",
}


def _categorize_campaign(camp: str) -> tuple[str, str, str]:
    camp = str(camp).lower()
    etapa = "Outros"
    for k, v in ETAPA_MAP.items():
        if k in camp:
            etapa = v
            break
    temp = "Outros"
    for k, v in TEMPERATURA_MAP.items():
        if f"[{k}]" in camp or f"]{k}[" in camp:
            temp = v
            break
    bucket = "Outros"
    for k, v in BUCKET_MAP_G.items():
        if f"[{k}]" in camp:
            bucket = v
            break
    modifier = None
    for k, v in MODIFIER_MAP_G.items():
        if f"[{k}]" in camp:
            modifier = v
            break
    seg_parts = [p for p in [temp if temp != "Outros" else None,
                              bucket if bucket != "Outros" else None] if p]
    segmento = " ".join(seg_parts) if seg_parts else "Outros"
    if modifier:
        segmento += f" ({modifier})"
    return etapa, temp, segmento


def read_google(launch_folder_or_code: Any, start_date=None, end_date=None) -> GoogleSummary | None:
    # deferred import to avoid circular dependency (read_vendas still in database_reader)
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    _COLS = "date, ad_name, campaign_name, impressions, clicks, cost, conversions, video_views, video_views_50, video_views_100, video_id, avg_cpv"
    if start_date and end_date:
        df = pd.read_sql(
            text(f"SELECT {_COLS} FROM google_ads_daily WHERE lancamento_codigo = :code AND date BETWEEN :start AND :end"),
            engine,
            params={"code": code, "start": start_date, "end": end_date}
        )
    else:
        df = pd.read_sql(
            text(f"SELECT {_COLS} FROM google_ads_daily WHERE lancamento_codigo = :code"),
            engine,
            params={"code": code}
        )
    if df.empty:
        return None

    summary = GoogleSummary()
    summary.data_inicio = df["date"].min().strftime("%Y-%m-%d")
    summary.data_fim = df["date"].max().strftime("%Y-%m-%d")
    summary.total_custo = float(df["cost"].sum())
    summary.total_cliques = int(df["clicks"].sum())
    summary.total_impressoes = int(df["impressions"].sum())
    summary.total_conversoes = float(df["conversions"].sum())
    summary.total_visualizacoes = int(df["video_views"].sum())

    summary.custo_conv_medio = summary.total_custo / summary.total_conversoes if summary.total_conversoes > 0 else 0.0
    summary.ctr_medio = summary.total_cliques / summary.total_impressoes * 100 if summary.total_impressoes > 0 else 0.0

    df["etapa"], df["temperatura"], df["segmento"] = zip(
        *df["campaign_name"].map(_categorize_campaign)
    )

    # Campanhas detalhadas
    camp_grouped = df.groupby("campaign_name").agg(
        custo=("cost", "sum"), cliques=("clicks", "sum"),
        impressoes=("impressions", "sum"), conversions=("conversions", "sum"),
        views=("video_views", "sum"), etapa=("etapa", "first"),
        temperatura=("temperatura", "first")
    ).reset_index()

    for _, r in camp_grouped.iterrows():
        cliq = int(r["cliques"])
        conv = float(r["conversions"])
        summary.campanhas.append(GoogleCampanha(
            nome=r["campaign_name"],
            etapa=r["etapa"],
            temperatura=r["temperatura"],
            tipo=_classify_google_type(r["campaign_name"]),
            cliques=cliq,
            impressoes=int(r["impressoes"]),
            ctr=float(cliq / r["impressoes"] * 100) if r["impressoes"] > 0 else 0.0,
            custo=float(r["custo"]),
            cpc=float(r["custo"] / cliq) if cliq > 0 else 0.0,
            conversoes=conv,
            custo_conv=float(r["custo"] / conv) if conv > 0 else 0.0,
            taxa_conv=float(conv / cliq * 100) if cliq > 0 else 0.0,
            visualizacoes=int(r["views"])
        ))
    summary.campanhas = sorted(summary.campanhas, key=lambda x: x.custo, reverse=True)

    # Mapa ad_name → video_id buscando em TODAS as etapas
    _video_id_by_ad_name: dict[str, str] = {}
    if "video_id" in df.columns:
        df_with_vid = df[df["video_id"].notna() & (df["video_id"] != "")]
        for ad_name, vid in df_with_vid[["ad_name", "video_id"]].values:
            if ad_name not in _video_id_by_ad_name:
                _video_id_by_ad_name[str(ad_name)] = str(vid)

    agg_cols = {"campaign_name": ("campaign_name", "first"),
                "etapa": ("etapa", "first"),
                "custo": ("cost", "sum"), "cliques": ("clicks", "sum"),
                "impressoes": ("impressions", "sum"), "conversions": ("conversions", "sum"),
                "video_views": ("video_views", "sum")}
    if "video_views_100" in df.columns:
        agg_cols["views_100"] = ("video_views_100", "sum")
    ad_grouped = df.groupby("ad_name").agg(**agg_cols).reset_index()

    _ad_codes_vistos_antes = get_historico_ad_codes(code)

    for _, r in ad_grouped.iterrows():
        name = r["ad_name"]
        camp = r["campaign_name"]
        etapa = r["etapa"]
        if etapa == "Captação":
            target_list = summary.anuncios_por_ad
        elif etapa == "Pré-Qualificação" and _classify_google_type(camp) == "youtube":
            target_list = summary.preq_por_ad
        else:
            continue
        match = re.search(r"\bAD\d+\b", name, flags=re.IGNORECASE)
        if not match:
            continue
        ad_code = match.group(0).upper()

        gasto = float(r["custo"])
        leads = float(r["conversions"])
        cliq = int(r["cliques"])
        impr = int(r["impressoes"])
        vviews = int(r["video_views"])
        views_100 = int(r["views_100"]) if "views_100" in r else 0
        video_id = _video_id_by_ad_name.get(name)
        if not video_id:
            for k, v in _video_id_by_ad_name.items():
                m = re.search(r"\bAD\d+\b", k, flags=re.IGNORECASE)
                if m and m.group(0).upper() == ad_code:
                    video_id = v
                    break

        target_list.append({
            "ad_code": ad_code,
            "nome": name,
            "gasto": gasto,
            "leads": int(round(leads)),
            "cliques": cliq,
            "impressoes": impr,
            "cpl": gasto / leads if leads > 0 else 0.0,
            "ctr": cliq / impr * 100 if impr > 0 else 0.0,
            "cpm": gasto / impr * 1000 if impr > 0 else 0.0,
            "video_views": vviews,
            "video_views_100": views_100,
            "hook_rate": vviews / impr * 100 if impr > 0 else 0.0,
            "body_rate": views_100 / vviews * 100 if vviews > 0 else 0.0,
            "origem": "Google Ads",
            "video_id": video_id,
            "antigo": bool(ad_code in _ad_codes_vistos_antes),
        })
    summary.anuncios_por_ad = sorted(summary.anuncios_por_ad, key=lambda x: x["leads"], reverse=True)
    summary.preq_por_ad = sorted(summary.preq_por_ad, key=lambda x: x["leads"], reverse=True)

    # Agrega por etapa
    etapa_grouped = df.groupby("etapa").agg(
        custo=("cost", "sum"), conversoes=("conversions", "sum"),
        cliques=("clicks", "sum"), impressoes=("impressions", "sum"),
        views=("video_views", "sum"),
        num_campanhas=("campaign_name", "nunique"),
    ).reset_index()

    etapa_data_inicio = df[df["cost"] > 0].groupby("etapa")["date"].min()
    total_custo_etapas = etapa_grouped["custo"].sum() or 1
    etapa_google_raw: dict[str, dict] = {}
    for _, r in etapa_grouped.iterrows():
        conv = float(r["conversoes"])
        etapa_google_raw[r["etapa"]] = {
            "etapa": r["etapa"],
            "custo": float(r["custo"]),
            "conversoes": conv,
            "cliques": int(r["cliques"]),
            "impressoes": int(r["impressoes"]),
            "visualizacoes": int(r["views"]),
            "custo_conv": float(r["custo"] / conv) if conv > 0 else 0.0,
            "pct": float(r["custo"] / total_custo_etapas * 100),
            "num_campanhas": int(r["num_campanhas"]),
            "data_inicio": (
                etapa_data_inicio[r["etapa"]].strftime("%Y-%m-%d")
                if r["etapa"] in etapa_data_inicio.index and pd.notna(etapa_data_inicio[r["etapa"]])
                else ""
            ),
        }
    zero_google = {"custo": 0.0, "conversoes": 0.0, "cliques": 0, "impressoes": 0, "visualizacoes": 0, "custo_conv": 0.0, "pct": 0.0, "num_campanhas": 0}
    for etapa in ETAPAS_ORDEM:
        summary.por_etapa[etapa] = etapa_google_raw.get(etapa, {"etapa": etapa, **zero_google})
    for etapa, data in etapa_google_raw.items():
        if etapa not in summary.por_etapa:
            summary.por_etapa[etapa] = data

    # Agrega por temperatura (só captação)
    temp_grouped = df[df["etapa"] == "Captação"].groupby("temperatura").agg(
        custo=("cost", "sum"), conversoes=("conversions", "sum")
    ).reset_index()
    for _, r in temp_grouped.iterrows():
        conv = float(r["conversoes"])
        summary.por_temperatura[r["temperatura"]] = {
            "temperatura": r["temperatura"],
            "custo": float(r["custo"]),
            "conversoes": conv,
            "custo_conv": float(r["custo"] / conv) if conv > 0 else 0.0
        }

    # Agrega por temperatura — pré-qualificação
    preq_grouped = df[df["etapa"] == "Pré-Qualificação"].groupby("temperatura").agg(
        custo=("cost", "sum"), conversoes=("conversions", "sum"),
        views=("video_views", "sum"), views_50=("video_views_50", "sum"),
    ).reset_index()
    for _, r in preq_grouped.iterrows():
        conv = float(r["conversoes"])
        views = int(r["views"])
        summary.por_temperatura_prequali[r["temperatura"]] = {
            "temperatura": r["temperatura"],
            "custo": float(r["custo"]),
            "gasto": float(r["custo"]),
            "conversoes": conv,
            "leads": conv,
            "custo_conv": float(r["custo"] / conv) if conv > 0 else 0.0,
            "thruplays": views,
            "custo_thruplay": float(r["custo"] / views) if views > 0 else 0.0,
            "views_50": int(r["views_50"]),
        }

    # Segmento Google (temperatura + bucket) — apenas captação
    df_cap_g = df[df["etapa"] == "Captação"]
    if not df_cap_g.empty:
        seg_grouped_g = df_cap_g.groupby("segmento").agg(
            custo=("cost", "sum"), conversoes=("conversions", "sum"),
            num_campanhas=("campaign_name", "nunique"),
        ).reset_index()
        total_seg_g = seg_grouped_g["custo"].sum() or 1
        for _, r in seg_grouped_g.iterrows():
            conv = float(r["conversoes"])
            summary.por_segmento[r["segmento"]] = {
                "gasto": float(r["custo"]),
                "conversoes": conv,
                "custo_conv": float(r["custo"] / conv) if conv > 0 else 0.0,
                "pct": float(r["custo"] / total_seg_g * 100),
                "num_campanhas": int(r["num_campanhas"]),
            }

    # Públicos Google Ads (API)
    try:
        df_aud = pd.read_sql(
            text("SELECT audience_name, SUM(cost) as cost, SUM(clicks) as clicks, SUM(conversions) as conversions, SUM(impressions) as impressions FROM google_ads_audiences_daily WHERE lancamento_codigo = :code GROUP BY audience_name ORDER BY cost DESC"),
            engine,
            params={"code": code}
        )
    except Exception:
        logger.exception("Falha ao buscar audiências Google; usando DataFrame vazio")
        df_aud = pd.DataFrame()

    # Cruzamento de Vendas via Leads (Google)
    # Mesma janela usada pela query principal deste reader — evita duplicar a
    # consulta inteira de Hotmart+TMB com uma cache-key diferente (start=None).
    # NÃO trocar pela mv_atribuicao_publicos: as tabelas de vendas do banco
    # analytics que a alimentam estão desatualizadas; a fonte correta é o
    # read_vendas (banco operacional + IDs de produto do launch_config).
    vendas = read_vendas(code, start_date=start_date, end_date=end_date)
    buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()
    sales_by_content = {}
    if buyers:
        df_leads = pd.read_sql(
            text("SELECT utm_content, email FROM leads WHERE lancamento_codigo = :code AND (utm_source ILIKE '%google%' OR utm_source ILIKE '%youtube%')"),
            engine,
            params={"code": code}
        )
        if not df_leads.empty:
            df_leads = df_leads.drop_duplicates(subset="email")
            df_leads["is_buyer"] = df_leads["email"].isin(buyers)
            df_leads["receita"] = df_leads["email"].map(lambda e: vendas.receita_por_email.get(e, 0.0))
            sales_by_content = df_leads[df_leads["is_buyer"]].groupby("utm_content").agg(
                sales=("is_buyer", "sum"),
                receita=("receita", "sum")
            ).to_dict("index")

    def _clean_str(s):
        if not s:
            return ""
        s = str(s).lower()
        s = re.sub(r'[^a-z0-9]', '', s)
        s = re.sub(r'^\d+', '', s)
        for w in ['todos', 'pbbjun26', 'pbbabr26', 'site', 'lancamentosanteriores', 'pesquisagoogle', 'captura']:
            s = s.replace(w, '')
        return s

    def _match_score(utm, api):
        u, a = _clean_str(utm), _clean_str(api)
        if not u or not a:
            return 0
        if u in a or a in u:
            return 1.0
        return SequenceMatcher(None, u, a).ratio()

    summary.publicos = []
    api_to_sales: dict = {}
    if not df_aud.empty:
        api_audiences = df_aud["audience_name"].tolist()

        utm_to_api = {}
        for utm, data in sales_by_content.items():
            best_api = None
            best_score = 0
            for api in api_audiences:
                score = _match_score(utm, api)
                if score > best_score:
                    best_score = score
                    best_api = api
            if best_score > 0.55:
                utm_to_api[utm] = {"api": best_api, "sales": data["sales"], "receita": data["receita"]}

        api_to_sales = {}
        for utm, data in utm_to_api.items():
            api = data["api"]
            if api not in api_to_sales:
                api_to_sales[api] = {"sales": 0, "receita": 0.0}
            api_to_sales[api]["sales"] += data["sales"]
            api_to_sales[api]["receita"] += data["receita"]

        for _, r in df_aud.iterrows():
            leads = float(r["conversions"] or 0)
            cost = float(r["cost"] or 0)
            clicks = int(r["clicks"] or 0)
            impr = int(r["impressions"] or 0)

            segmento = r["audience_name"]
            if isinstance(segmento, str) and segmento.startswith("uservertical::"):
                segmento = f"Público de Afinidade/Mercado ({segmento.split('::')[-1]})"

            agg_data = api_to_sales.get(r["audience_name"], {"sales": 0, "receita": 0.0})
            vendas_cruzadas = int(agg_data["sales"])
            receita_cruzada = float(agg_data["receita"])

            summary.publicos.append({
                "segmento": segmento,
                "custo": cost,
                "cliques": clicks,
                "conversoes": leads,
                "impressoes": impr,
                "cpl": cost / leads if leads > 0 else 0.0,
                "vendas": vendas_cruzadas,
                "receita": receita_cruzada,
                "cpa_vendas": cost / vendas_cruzadas if vendas_cruzadas > 0 else 0.0,
                "cpc": cost / clicks if clicks > 0 else 0.0,
                "ctr": clicks / impr * 100 if impr > 0 else 0.0
            })

    # Detalhamento dos públicos por clima — Captação (pauta debriefing, igual
    # à seção já existente do Meta). Reaproveita o cruzamento de vendas por
    # audiência (api_to_sales) já calculado acima.
    try:
        df_aud_temp = pd.read_sql(
            text("""
                SELECT audience_name, campaign_name, SUM(cost) as cost,
                       SUM(conversions) as conversions
                FROM google_ads_audiences_daily
                WHERE lancamento_codigo = :code
                GROUP BY audience_name, campaign_name
            """),
            engine, params={"code": code},
        )
    except Exception:
        logger.exception("Falha ao buscar audiências por campanha (Google); usando DataFrame vazio")
        df_aud_temp = pd.DataFrame()

    if not df_aud_temp.empty:
        df_aud_temp["etapa"], df_aud_temp["temperatura"], _ = zip(
            *df_aud_temp["campaign_name"].map(_categorize_campaign)
        )
        df_aud_cap = df_aud_temp[df_aud_temp["etapa"] == "Captação"].copy()
        if not df_aud_cap.empty:
            def _label_publico(nome):
                if isinstance(nome, str) and nome.startswith("uservertical::"):
                    return f"Público de Afinidade/Mercado ({nome.split('::')[-1]})"
                return nome or "Sem Nome"
            df_aud_cap["publico"] = df_aud_cap["audience_name"].map(_label_publico)

            pub_grouped_g = df_aud_cap.groupby(["temperatura", "publico"]).agg(
                custo=("cost", "sum"), conversoes=("conversions", "sum"),
                num_audiencias=("audience_name", "nunique"),
            ).reset_index()
            aud_by_group = df_aud_cap.groupby(["temperatura", "publico"])["audience_name"].unique()
            for temp in pub_grouped_g["temperatura"].unique():
                sub = pub_grouped_g[pub_grouped_g["temperatura"] == temp].sort_values("custo", ascending=False)
                total_temp = sub["custo"].sum() or 1
                rows = []
                for _, r in sub.iterrows():
                    audiencias = aud_by_group.get((temp, r["publico"]), [])
                    vendas_pub = sum(int(api_to_sales.get(a, {}).get("sales", 0) or 0) for a in audiencias)
                    receita_pub = sum(float(api_to_sales.get(a, {}).get("receita", 0.0) or 0.0) for a in audiencias)
                    custo = float(r["custo"])
                    leads = float(r["conversoes"])
                    rows.append({
                        "publico": r["publico"],
                        "gasto": custo,
                        "leads": leads,
                        "cpl": custo / leads if leads > 0 else 0.0,
                        "pct": custo / total_temp * 100,
                        "num_adsets": int(r["num_audiencias"]),
                        "vendas": vendas_pub,
                        "receita": receita_pub,
                        "roas": (receita_pub / custo) if custo > 0 else 0.0,
                    })
                summary.por_publico_captacao[temp] = rows

    # Demographics Google
    try:
        df_demo = pd.read_sql(
            text("SELECT demographic_type, demographic_value, SUM(cost) as cost, SUM(clicks) as clicks, SUM(conversions) as conversions, SUM(impressions) as impressions FROM google_ads_demographics_daily WHERE lancamento_codigo = :code GROUP BY demographic_type, demographic_value"),
            engine,
            params={"code": code}
        )
        if not df_demo.empty:
            df_age = df_demo[df_demo["demographic_type"] == "AGE"].copy()
            if not df_age.empty:
                df_age["cpa"] = np.where(df_age["conversions"] > 0, df_age["cost"] / df_age["conversions"], 0)
                df_age["ctr"] = np.where(df_age["impressions"] > 0, (df_age["clicks"] / df_age["impressions"]) * 100, 0)
                df_age = df_age.sort_values(by="cost", ascending=False).round(2)
                summary.demografia_idade = df_age.rename(columns={"demographic_value": "age"}).to_dict("records")

            df_gender = df_demo[df_demo["demographic_type"] == "GENDER"].copy()
            if not df_gender.empty:
                df_gender["cpa"] = np.where(df_gender["conversions"] > 0, df_gender["cost"] / df_gender["conversions"], 0)
                df_gender["ctr"] = np.where(df_gender["impressions"] > 0, (df_gender["clicks"] / df_gender["impressions"]) * 100, 0)
                df_gender = df_gender.sort_values(by="cost", ascending=False).round(2)
                summary.demografia_genero = df_gender.rename(columns={"demographic_value": "gender"}).to_dict("records")
    except Exception:
        logger.exception("Erro ao ler demografia Google")

    return summary


def read_daily_breakdown(
    launch_folder_or_code: Any,
    start_date=None,
    end_date=None,
    filtro_captacao: str | None = None,
    filtro_pre_quali: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Retorna (rows_captacao, rows_pre_quali): dois breakdowns diários filtrados por
    nome de campanha (case-insensitive substring). Se os filtros forem None/vazios,
    retorna o total geral na primeira lista e lista vazia na segunda.
    Cada lista contém dicts com: date, weekday, total_leads, total_gasto,
    meta_leads, meta_gasto, yt_leads, yt_gasto, search_leads, search_gasto,
    pmax_leads, pmax_gasto, display_leads, display_gasto.
    """
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    date_clause = "AND date BETWEEN :start AND :end" if (start_date and end_date) else ""
    params_base: dict = {"code": code}
    if start_date and end_date:
        params_base.update({"start": start_date, "end": end_date})

    meta_df = pd.read_sql(
        text(f"SELECT date, campaign_name, SUM(spend) AS gasto, SUM(leads) AS leads FROM meta_ads_daily WHERE lancamento_codigo = :code {date_clause} GROUP BY date, campaign_name"),
        engine, params=params_base
    )
    google_df = pd.read_sql(
        text(f"SELECT date, campaign_name, SUM(cost) AS gasto, SUM(conversions) AS conv FROM google_ads_daily WHERE lancamento_codigo = :code {date_clause} GROUP BY date, campaign_name"),
        engine, params=params_base
    )

    def _build_rows(mdf, gdf) -> list[dict]:
        all_dates: set = set()
        if not mdf.empty:
            all_dates |= set(mdf["date"])
        if not gdf.empty:
            all_dates |= set(gdf["date"])
        if not all_dates:
            return []

        meta_by_date: dict = {}
        if not mdf.empty:
            for _, row in mdf.iterrows():
                d = row["date"]
                if d not in meta_by_date:
                    meta_by_date[d] = {"leads": 0.0, "gasto": 0.0}
                meta_by_date[d]["leads"] += float(row["leads"] or 0)
                meta_by_date[d]["gasto"] += float(row["gasto"] or 0)

        google_by_date: dict = {}
        if not gdf.empty:
            gdf = gdf.copy()
            gdf["tipo"] = gdf["campaign_name"].apply(_classify_google_type)
            for _, row in gdf.iterrows():
                d = row["date"]
                if d not in google_by_date:
                    google_by_date[d] = {t: {"leads": 0.0, "gasto": 0.0} for t in ("youtube", "search", "pmax", "display")}
                t = row["tipo"]
                google_by_date[d][t]["leads"] += float(row["conv"] or 0)
                google_by_date[d][t]["gasto"] += float(row["gasto"] or 0)

        WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        _empty_g = {t: {"leads": 0.0, "gasto": 0.0} for t in ("youtube", "search", "pmax", "display")}
        rows = []
        for d in sorted(all_dates):
            m = meta_by_date.get(d, {"leads": 0.0, "gasto": 0.0})
            g = google_by_date.get(d, _empty_g)
            g_yt = g["youtube"]; g_s = g["search"]; g_pm = g["pmax"]; g_d = g["display"]
            total_leads = m["leads"] + g_yt["leads"] + g_s["leads"] + g_pm["leads"] + g_d["leads"]
            total_gasto = m["gasto"] + g_yt["gasto"] + g_s["gasto"] + g_pm["gasto"] + g_d["gasto"]
            dt = d if hasattr(d, "weekday") else pd.Timestamp(d)
            rows.append({
                "date": dt.strftime("%d/%m"),
                "weekday": WEEKDAYS_PT[dt.weekday()],
                "total_leads": total_leads, "total_gasto": total_gasto,
                "total_cpl": total_gasto / total_leads if total_leads > 0 else 0.0,
                "meta_leads": m["leads"], "meta_gasto": m["gasto"],
                "meta_cpl": m["gasto"] / m["leads"] if m["leads"] > 0 else 0.0,
                "yt_leads": g_yt["leads"], "yt_gasto": g_yt["gasto"],
                "yt_cpl": g_yt["gasto"] / g_yt["leads"] if g_yt["leads"] > 0 else 0.0,
                "search_leads": g_s["leads"], "search_gasto": g_s["gasto"],
                "search_cpl": g_s["gasto"] / g_s["leads"] if g_s["leads"] > 0 else 0.0,
                "pmax_leads": g_pm["leads"], "pmax_gasto": g_pm["gasto"],
                "pmax_cpl": g_pm["gasto"] / g_pm["leads"] if g_pm["leads"] > 0 else 0.0,
                "display_leads": g_d["leads"], "display_gasto": g_d["gasto"],
                "display_cpl": g_d["gasto"] / g_d["leads"] if g_d["leads"] > 0 else 0.0,
            })
        return rows

    def _filter_df(df, col, term):
        if df.empty or not term:
            return df
        t = term.lower()
        return df[df[col].fillna("").str.lower().str.contains(t, regex=False)]

    capt = filtro_captacao.strip() if filtro_captacao else ""
    preq = filtro_pre_quali.strip() if filtro_pre_quali else ""

    if not capt and not preq:
        return _build_rows(meta_df, google_df), []

    meta_capt   = _filter_df(meta_df,   "campaign_name", capt)
    google_capt = _filter_df(google_df, "campaign_name", capt)
    meta_preq   = _filter_df(meta_df,   "campaign_name", preq)
    google_preq = _filter_df(google_df, "campaign_name", preq)

    return _build_rows(meta_capt, google_capt), _build_rows(meta_preq, google_preq)
