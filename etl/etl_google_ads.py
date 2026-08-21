"""
ETL: Google Ads REST API → Supabase (tabela: google_ads_daily)

Modo API (dados diários por anúncio):
    python etl/etl_google_ads.py --since 2026-04-01 --until 2026-04-30

Modo CSV (importa export do Google Ads — dados agregados, sem daily breakdown):
    python etl/etl_google_ads.py --from-csv "analises/[PBB-ABR-26]/Google Ads/google-ads-performance-dos-anuncios-pbb-abr-26.csv" --period 2026-04

Setup OAuth (execute uma vez para obter o refresh token):
    python etl/etl_google_ads.py --get-token

Pré-requisitos .env:
    GOOGLE_ADS_DEVELOPER_TOKEN
    GOOGLE_ADS_CLIENT_ID
    GOOGLE_ADS_CLIENT_SECRET
    GOOGLE_ADS_REFRESH_TOKEN          (gerado com --get-token)
    GOOGLE_ADS_CUSTOMER_ID
    GOOGLE_ADS_LOGIN_CUSTOMER_ID      (ID da MCC, se aplicável)
"""
import os
import sys
import argparse
import re
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_post
from validation import validate_dataframe

load_dotenv()

logger = get_logger("etl.google")

API_VERSION = "v22"
TABLE       = "google_ads_daily"

def extract_launch_code(campaign_name: str) -> str | None:
    if not campaign_name or pd.isna(campaign_name):
        return None
    match = re.search(r'(PBB|PES|PI)-\w{3}-\d{2}', campaign_name, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None

def parse_number(value) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "--"}:
        return 0.0
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return 0.0
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(pd.to_numeric(text, errors="coerce") or 0.0)

GAQL = """
SELECT
  ad_group_ad.ad.id,
  ad_group_ad.ad.name,
  ad_group_ad.ad.video_responsive_ad.videos,
  ad_group.id,
  ad_group.name,
  campaign.id,
  campaign.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.video_trueview_views,
  metrics.video_quartile_p25_rate,
  metrics.video_quartile_p50_rate,
  metrics.video_quartile_p75_rate,
  metrics.video_quartile_p100_rate,
  segments.date
FROM ad_group_ad
WHERE segments.date BETWEEN '{since}' AND '{until}'
  AND ad_group_ad.status != 'REMOVED'
ORDER BY segments.date, ad_group_ad.ad.id
"""

# P-Max — asset_group é o equivalente ao "ad" (tem nome como AD333)
GAQL_PMAX = """
SELECT
  asset_group.id,
  asset_group.name,
  campaign.id,
  campaign.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  segments.date
FROM asset_group
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND segments.date BETWEEN '{since}' AND '{until}'
ORDER BY segments.date, asset_group.id
"""

GAQL_AUDIENCES = """
SELECT
  ad_group_criterion.display_name,
  ad_group.id,
  ad_group.name,
  campaign.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  segments.date
FROM ad_group_audience_view
WHERE segments.date BETWEEN '{since}' AND '{until}'
  AND ad_group.status != 'REMOVED'
ORDER BY segments.date
"""

GAQL_AGE = """
SELECT
  ad_group_criterion.age_range.type,
  campaign.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  segments.date
FROM age_range_view
WHERE segments.date BETWEEN '{since}' AND '{until}'
  AND ad_group.status != 'REMOVED'
ORDER BY segments.date
"""

GAQL_GENDER = """
SELECT
  ad_group_criterion.gender.type,
  campaign.name,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  segments.date
FROM gender_view
WHERE segments.date BETWEEN '{since}' AND '{until}'
  AND ad_group.status != 'REMOVED'
ORDER BY segments.date
"""


# ─────────────────────────────────────────────────────────────────────────────
# OAuth helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_access_token() -> str:
    """Troca o refresh token por um access token."""
    try:
        import google.oauth2.credentials
        import google.auth.transport.requests
    except ImportError:
        sys.exit("Instale google-auth:  pip install google-auth")

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def setup_oauth():
    """Fluxo interativo para gerar o GOOGLE_ADS_REFRESH_TOKEN (execute uma vez)."""
    import get_google_ads_token
    get_google_ads_token.main()


# ─────────────────────────────────────────────────────────────────────────────
# Modo API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_report(since: str, until: str, customer_ids: list[str] | None = None) -> list[dict]:
    customer_ids = customer_ids or [cid.strip() for cid in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if cid.strip()]
    customer_ids = [cid.replace("-", "") for cid in customer_ids]
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")

    headers = {
        "Authorization":   f"Bearer {_get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type":    "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id.replace("-", "")

    rows = []
    for customer_id in customer_ids:
        logger.info("Buscando relatório da conta Google Ads: %s", customer_id)
        search_url = (
            f"https://googleads.googleapis.com/{API_VERSION}"
            f"/customers/{customer_id}/googleAds:search"
        )

        page_token = None
        while True:
            payload = {"query": GAQL.format(since=since, until=until)}
            if page_token:
                payload["pageToken"] = page_token
            r = http_post(search_url, headers=headers, json=payload)
            data = r.json()
            rows.extend(data.get("results", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return rows


GAQL_STATUS = """
SELECT campaign.name, campaign.status
FROM campaign
WHERE campaign.status != 'REMOVED'
"""


def fetch_campaign_status(customer_ids: list[str] | None = None) -> dict[str, str]:
    """Retorna {campaign_name: status} (ENABLED/PAUSED) das contas informadas."""
    customer_ids = customer_ids or [cid.strip() for cid in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if cid.strip()]
    customer_ids = [cid.replace("-", "") for cid in customer_ids]
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")

    headers = {
        "Authorization":   f"Bearer {_get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type":    "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id

    result: dict[str, str] = {}
    for customer_id in customer_ids:
        search_url = (
            f"https://googleads.googleapis.com/{API_VERSION}"
            f"/customers/{customer_id}/googleAds:search"
        )
        page_token = None
        while True:
            payload = {"query": GAQL_STATUS}
            if page_token:
                payload["pageToken"] = page_token
            r = http_post(search_url, headers=headers, json=payload)
            data = r.json()
            for row in data.get("results", []):
                camp = row.get("campaign", {})
                result[camp.get("name")] = camp.get("status")
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    return result


def fetch_youtube_video_ids(asset_resources: set[str]) -> dict[str, str]:
    """Resolve asset resource names → youtube_video_id via query FROM asset."""
    if not asset_resources:
        return {}
    customer_ids = [cid.strip().replace("-", "") for cid in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if cid.strip()]
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    token = _get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type": "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id.replace("-", "")

    result: dict[str, str] = {}
    for customer_id in customer_ids:
        search_url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
        # Filtra apenas assets deste customer
        customer_assets = [r for r in asset_resources if f"customers/{customer_id}/" in r]
        if not customer_assets:
            continue
        gaql = "SELECT asset.resource_name, asset.youtube_video_asset.youtube_video_id FROM asset WHERE asset.type = 'YOUTUBE_VIDEO'"
        try:
            r = http_post(search_url, headers=headers, json={"query": gaql})
            for row in r.json().get("results", []):
                asset = row.get("asset", {})
                rname = asset.get("resourceName", "")
                vid = (asset.get("youtubeVideoAsset") or {}).get("youtubeVideoId", "")
                if rname and vid:
                    result[rname] = vid
        except Exception:
            pass
    return result


def fetch_pmax_report(since: str, until: str, customer_ids: list[str] | None = None) -> list[dict]:
    customer_ids = customer_ids or [cid.strip() for cid in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if cid.strip()]
    customer_ids = [cid.replace("-", "") for cid in customer_ids]
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")

    headers = {
        "Authorization":   f"Bearer {_get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type":    "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id.replace("-", "")

    rows = []
    for customer_id in customer_ids:
        search_url = (
            f"https://googleads.googleapis.com/{API_VERSION}"
            f"/customers/{customer_id}/googleAds:search"
        )
        page_token = None
        while True:
            payload = {"query": GAQL_PMAX.format(since=since, until=until)}
            if page_token:
                payload["pageToken"] = page_token
            r = http_post(search_url, headers=headers, json=payload)
            data = r.json()
            rows.extend(data.get("results", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    return rows


def build_df_from_pmax_api(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        ag   = r.get("assetGroup", {})
        camp = r.get("campaign", {})
        met  = r.get("metrics", {})
        seg  = r.get("segments", {})
        campaign_id   = str(camp.get("id", ""))
        campaign_name = camp.get("name", "")
        ag_id   = str(ag.get("id", ""))
        ag_name = ag.get("name", "") or campaign_name
        records.append({
            "date":            seg.get("date"),
            "ad_id":           ag_id if ag_id else f"PMAX-{campaign_id}",
            "ad_name":         ag_name,
            "ad_group_id":     None,
            "ad_group_name":   None,
            "campaign_id":     campaign_id,
            "campaign_name":   campaign_name,
            "lancamento_codigo": extract_launch_code(campaign_name),
            "impressions":     int(met.get("impressions", 0)),
            "clicks":          int(met.get("clicks", 0)),
            "cost":            round(int(met.get("costMicros", 0)) / 1_000_000, 2),
            "conversions":     float(met.get("conversions", 0)),
            "video_views":     0,
            "video_views_25":  0,
            "video_views_50":  0,
            "video_views_75":  0,
            "video_views_100": 0,
        })
    return pd.DataFrame(records)


def fetch_audiences_report(since: str, until: str) -> list[dict]:
    customer_ids = [cid.strip().replace("-", "") for cid in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if cid.strip()]
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")

    headers = {
        "Authorization":   f"Bearer {_get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type":    "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id.replace("-", "")

    rows = []
    for customer_id in customer_ids:
        search_url = (
            f"https://googleads.googleapis.com/{API_VERSION}"
            f"/customers/{customer_id}/googleAds:search"
        )
        page_token = None
        while True:
            payload = {"query": GAQL_AUDIENCES.format(since=since, until=until)}
            if page_token:
                payload["pageToken"] = page_token
            r = http_post(search_url, headers=headers, json=payload)
            data = r.json()
            rows.extend(data.get("results", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    return rows


def fetch_demographics_report(since: str, until: str) -> list[dict]:
    customer_ids = [cid.strip().replace("-", "") for cid in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if cid.strip()]
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")

    headers = {
        "Authorization":   f"Bearer {_get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type":    "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id.replace("-", "")

    rows = []
    for customer_id in customer_ids:
        search_url = (
            f"https://googleads.googleapis.com/{API_VERSION}"
            f"/customers/{customer_id}/googleAds:search"
        )
        for gaql, demo_type in [(GAQL_AGE, "AGE"), (GAQL_GENDER, "GENDER")]:
            page_token = None
            while True:
                payload = {"query": gaql.format(since=since, until=until)}
                if page_token:
                    payload["pageToken"] = page_token
                r = http_post(search_url, headers=headers, json=payload)
                data = r.json()
                results = data.get("results", [])
                for res in results:
                    res["_demo_type"] = demo_type
                rows.extend(results)
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
    return rows


def build_df_from_demographics_api(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        crit  = r.get("adGroupCriterion", {})
        camp  = r.get("campaign", {})
        met   = r.get("metrics", {})
        seg   = r.get("segments", {})
        demo_type = r.get("_demo_type", "")
        if demo_type == "AGE":
            val = crit.get("ageRange", {}).get("type", "")
        else:
            val = crit.get("gender", {}).get("type", "")
            
        campaign_name = camp.get("name", "")
        records.append({
            "date":              seg.get("date"),
            "demographic_type":  demo_type,
            "demographic_value": val,
            "campaign_name":     campaign_name,
            "lancamento_codigo": extract_launch_code(campaign_name),
            "impressions":       int(met.get("impressions", 0)),
            "clicks":            int(met.get("clicks", 0)),
            "cost":              round(int(met.get("costMicros", 0)) / 1_000_000, 2),
            "conversions":       float(met.get("conversions", 0)),
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.groupby(
            ["date", "demographic_type", "demographic_value", "campaign_name", "lancamento_codigo"],
            dropna=False,
            as_index=False
        ).sum()
    return df


def build_df_from_audiences_api(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        crit     = r.get("adGroupCriterion", {})
        ad_group = r.get("adGroup", {})
        camp     = r.get("campaign", {})
        met      = r.get("metrics", {})
        seg      = r.get("segments", {})
        campaign_name = camp.get("name", "")
        records.append({
            "date":              seg.get("date"),
            "audience_name":     crit.get("displayName", ""),
            "ad_group_name":     ad_group.get("name", ""),
            "campaign_name":     campaign_name,
            "lancamento_codigo": extract_launch_code(campaign_name),
            "impressions":       int(met.get("impressions", 0)),
            "clicks":            int(met.get("clicks", 0)),
            "cost":              round(int(met.get("costMicros", 0)) / 1_000_000, 2),
            "conversions":       float(met.get("conversions", 0)),
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.groupby(
            ["date", "audience_name", "campaign_name", "lancamento_codigo"],
            dropna=False,
            as_index=False
        ).agg({
            "ad_group_name": "first",
            "impressions": "sum",
            "clicks": "sum",
            "cost": "sum",
            "conversions": "sum",
        })
    return df


def build_df_from_api(rows: list[dict]) -> pd.DataFrame:
    # 1ª passagem: coleta asset resources de vídeo para resolver YouTube IDs
    asset_resources: set[str] = set()
    for r in rows:
        ad = r.get("adGroupAd", {}).get("ad", {})
        for video in (ad.get("videoResponsiveAd") or {}).get("videos", []):
            asset = video.get("asset", "")
            if asset:
                asset_resources.add(asset)

    video_id_map = fetch_youtube_video_ids(asset_resources) if asset_resources else {}

    records = []
    for r in rows:
        ad    = r.get("adGroupAd", {}).get("ad", {})
        group = r.get("adGroup",   {})
        camp  = r.get("campaign",  {})
        met   = r.get("metrics",   {})
        seg   = r.get("segments",  {})

        imp = int(met.get("impressions", 0))
        q25 = float(met.get("videoQuartileP25Rate", 0.0))
        q50 = float(met.get("videoQuartileP50Rate", 0.0))
        q75 = float(met.get("videoQuartileP75Rate", 0.0))
        q100 = float(met.get("videoQuartileP100Rate", 0.0))

        # Tenta extrair o primeiro YouTube video ID associado ao anúncio
        video_id = None
        for video in (ad.get("videoResponsiveAd") or {}).get("videos", []):
            asset = video.get("asset", "")
            if asset and asset in video_id_map:
                video_id = video_id_map[asset]
                break

        # Responsive Search Ads não têm campo "name" preenchível na API do Google Ads
        # (fica None). Sem isso, o spend de Search nunca casa com o ad_code AD400
        # usado nas UTMs (tracking template não consegue inserir ADxxx por anúncio
        # em Search, só por grupo de anúncios — por isso o AD400 genérico).
        ad_name = ad.get("name") or "AD400 - Busca Genérica"

        records.append({
            "date":           seg.get("date"),
            "ad_id":          str(ad.get("id")),
            "ad_name":        ad_name,
            "ad_group_id":    str(group.get("id")),
            "ad_group_name":  group.get("name"),
            "campaign_id":    str(camp.get("id")),
            "campaign_name":  camp.get("name"),
            "lancamento_codigo": extract_launch_code(camp.get("name")),
            "impressions":    imp,
            "clicks":         int(met.get("clicks", 0)),
            "cost":           round(int(met.get("costMicros", 0)) / 1_000_000, 2),
            "conversions":    float(met.get("conversions", 0)),
            "video_views":     int(met.get("videoTrueviewViews", 0)),
            "video_views_25":  round(imp * q25),
            "video_views_50":  round(imp * q50),
            "video_views_75":  round(imp * q75),
            "video_views_100": round(imp * q100),
            "video_id":        video_id,
        })
    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# Modo CSV (export manual — sem data diária, dados agregados do período)
# O CSV usa skiprows=2 (linha de título + linha de intervalo de datas)
# ─────────────────────────────────────────────────────────────────────────────

def build_df_from_csv(filepath: str, period: str) -> pd.DataFrame:
    """
    Importa o CSV de performance de anúncios do Google Ads.
    Como o export não tem daily breakdown, grava com a data do primeiro dia
    do período informado (ex: '2026-04' → '2026-04-01').
    """
    df = pd.read_csv(filepath, skiprows=2, dtype=str)

    col_map = {
        "Nome do anúncio":                 "ad_name",
        "Campanha":                        "campaign_name",
        "Grupo de anúncios":               "ad_group_name",
        "Cliques":                         "clicks",
        "Impr.":                           "impressions",
        "Custo":                           "cost",
        "Conversões":                      "conversions",
        "Visualizações":                   "video_views",
        "Vídeo reproduzido em até 25%":    "video_views_25",
        "Vídeo reproduzido em até 50%":    "video_views_50",
        "Vídeo reproduzido em até 75%":    "video_views_75",
        "Vídeo reproduzido em até 100%":   "video_views_100",
    }
    
    # Renomeia se existir
    for k, v in col_map.items():
        if k in df.columns:
            df = df.rename(columns={k: v})
            
    # Cria colunas de destino que não existirem no CSV original
    dest_cols = ["date", "ad_name", "campaign_name", "ad_group_name", "clicks", 
                 "impressions", "cost", "conversions", "video_views", 
                 "video_views_25", "video_views_50", "video_views_75", "video_views_100"]
                 
    for col in dest_cols:
        if col not in df.columns:
            df[col] = "0"

    # Normaliza números (formato pt-BR)
    numeric_cols = ["clicks", "impressions", "cost", "conversions", "video_views", 
                    "video_views_25", "video_views_50", "video_views_75", "video_views_100"]
                    
    for col in numeric_cols:
        df[col] = df[col].apply(parse_number)

    # Data sintética: primeiro dia do período
    try:
        df["date"] = pd.to_datetime(period, format="%Y-%m").strftime("%Y-%m-01")
    except ValueError:
        df["date"] = period  # aceita YYYY-MM-DD direto

    # ad_id sintético a partir do nome do anúncio (ADXXX)
    df["ad_id"]          = df["ad_name"].str.extract(r"(AD\d+)", flags=re.IGNORECASE)[0].str.upper()
    df["ad_group_id"]    = None
    df["campaign_id"] = None
    df["ad_group_name"]  = df.get("ad_group_name")
    df["lancamento_codigo"] = df["campaign_name"].apply(extract_launch_code)
 
    df = df.dropna(subset=["ad_id"])
    numeric_cols = ["impressions", "clicks", "cost", "conversions", "video_views",
                    "video_views_25", "video_views_50", "video_views_75", "video_views_100"]
    first_cols = ["ad_name", "ad_group_id", "ad_group_name", "campaign_id", "campaign_name", "lancamento_codigo"]
    agg = {col: "sum" for col in numeric_cols}
    agg.update({col: "first" for col in first_cols})
    df = df.groupby(["date", "ad_id"], as_index=False).agg(agg)
    return df[["date", "ad_id", "ad_name", "ad_group_id", "ad_group_name",
               "campaign_id", "campaign_name", "lancamento_codigo", "impressions", "clicks", "cost", "conversions",
               "video_views", "video_views_25", "video_views_50", "video_views_75", "video_views_100"]]

def total_cost_from_csv(filepath: str, launch_code: str | None = None) -> tuple[float, float, int]:
    for skiprows in (2, 0, 1, 3):
        try:
            df = pd.read_csv(filepath, skiprows=skiprows, dtype=str)
        except Exception:
            continue
        cost_col = next((c for c in df.columns if "Custo" in c or "Cost" in c), None)
        conv_col = next((c for c in df.columns if "Convers" in c or "Conv." in c), None)
        campaign_col = next((c for c in df.columns if "Campanha" in c or "Campaign" in c), None)
        if not cost_col:
            continue
        if launch_code and campaign_col:
            df = df[df[campaign_col].apply(extract_launch_code).fillna("").str.upper() == launch_code.upper()]
        cost = float(df[cost_col].apply(parse_number).sum())
        conv = float(df[conv_col].apply(parse_number).sum()) if conv_col else 0.0
        return cost, conv, len(df)
    return 0.0, 0.0, 0


# ─────────────────────────────────────────────────────────────────────────────
# Upsert
# ─────────────────────────────────────────────────────────────────────────────

_GOOGLE_REQUIRED_COLS = ["date", "ad_id", "ad_name", "cost", "impressions", "clicks"]

def upsert(df: pd.DataFrame, since: str, until: str, launch_code: str | None = None):
    if not validate_dataframe(df, _GOOGLE_REQUIRED_COLS, "google_ads_daily", logger):
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    with engine.begin() as conn:
        if launch_code:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE date BETWEEN :s AND :u AND lancamento_codigo = :launch_code"),
                {"s": since, "u": until, "launch_code": launch_code},
            )
        else:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE date BETWEEN :s AND :u"),
                {"s": since, "u": until},
            )
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), TABLE)


def upsert_audiences(df: pd.DataFrame, since: str, until: str, launch_code: str | None = None):
    if df.empty:
        logger.warning("Nenhum dado de públicos Google Ads para gravar.")
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    table = "google_ads_audiences_daily"
    with engine.begin() as conn:
        if launch_code:
            conn.execute(
                text(f"DELETE FROM {table} WHERE date BETWEEN :s AND :u AND lancamento_codigo = :launch_code"),
                {"s": since, "u": until, "launch_code": launch_code},
            )
        else:
            conn.execute(
                text(f"DELETE FROM {table} WHERE date BETWEEN :s AND :u"),
                {"s": since, "u": until},
            )
    df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), table)


def upsert_demographics(df: pd.DataFrame, since: str, until: str, launch_code: str | None = None):
    if df.empty:
        logger.warning("Nenhum dado de demografia Google Ads para gravar.")
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    table = "google_ads_demographics_daily"
    with engine.begin() as conn:
        if launch_code:
            conn.execute(
                text(f"DELETE FROM {table} WHERE date BETWEEN :s AND :u AND lancamento_codigo = :launch_code"),
                {"s": since, "u": until, "launch_code": launch_code},
            )
        else:
            conn.execute(
                text(f"DELETE FROM {table} WHERE date BETWEEN :s AND :u"),
                {"s": since, "u": until},
            )
    df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), table)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ETL Google Ads - Supabase")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--since",     metavar="YYYY-MM-DD", help="Data inicial (modo API)")
    group.add_argument("--from-csv",  metavar="FILE",       help="CSV exportado do Google Ads")
    group.add_argument("--get-token", action="store_true",  help="Gera o GOOGLE_ADS_REFRESH_TOKEN (OAuth)")
    parser.add_argument("--until",    metavar="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--period",   metavar="YYYY-MM",    help="Período do CSV (ex: 2026-04), usado como data de referência")
    parser.add_argument("--launch-code", metavar="CODE", help="Filtra e substitui dados apenas de um lancamento")
    parser.add_argument("--campaign-total-csv", metavar="FILE", help="CSV de campanhas para ajustar o total do lancamento")
    args = parser.parse_args()

    if args.get_token:
        setup_oauth()
        return

    if args.from_csv:
        period = args.period or datetime.now().strftime("%Y-%m")
        logger.info("[Google Ads] %s <- CSV: %s  (periodo: %s)", TABLE, args.from_csv, period)
        df    = build_df_from_csv(args.from_csv, period)
        if args.launch_code:
            df = df[df["lancamento_codigo"].fillna("").str.upper() == args.launch_code.upper()]
        if args.campaign_total_csv and args.launch_code and not df.empty:
            campaign_cost, campaign_conv, _ = total_cost_from_csv(args.campaign_total_csv, args.launch_code)
            current_cost = float(df["cost"].sum())
            diff = round(campaign_cost - current_cost, 2)
            if abs(diff) >= 0.01:
                adjustment = {col: 0 for col in ["impressions", "clicks", "cost", "conversions", "video_views", "video_views_25", "video_views_50", "video_views_75", "video_views_100"]}
                adjustment.update({
                    "date": df["date"].iloc[0],
                    "ad_id": f"AJUSTE-{args.launch_code.upper()}",
                    "ad_name": f"Ajuste total Google Ads - {args.launch_code.upper()}",
                    "ad_group_id": None,
                    "ad_group_name": "Ajuste total",
                    "campaign_id": None,
                    "campaign_name": f"[GA][ajuste][{args.launch_code.upper()}]",
                    "lancamento_codigo": args.launch_code.upper(),
                    "cost": diff,
                    "conversions": round(campaign_conv - float(df["conversions"].sum()), 2),
                })
                df = pd.concat([df, pd.DataFrame([adjustment])], ignore_index=True)
        # Aceita YYYY-MM (adiciona -01 / -30) ou YYYY-MM-DD direto
        if len(period) == 7:  # YYYY-MM
            since = f"{period}-01"
            until = f"{period}-30"
        else:  # YYYY-MM-DD
            since = period
            until = str(df["date"].max())
        logger.info("%d anúncios", len(df))
        upsert(df, since, until, args.launch_code)
    else:
        logger.info("[Google Ads] %s  [%s -> %s]  (API)", TABLE, args.since, args.until)
        rows = fetch_report(args.since, args.until)
        logger.info("%d registros retornados (ad_group_ad)", len(rows))
        df = build_df_from_api(rows)

        # P-Max — query separada a nível de campanha
        pmax_rows = fetch_pmax_report(args.since, args.until)
        if pmax_rows:
            logger.info("%d registros P-Max retornados", len(pmax_rows))
            df_pmax = build_df_from_pmax_api(pmax_rows)
            df = pd.concat([df, df_pmax], ignore_index=True)
        else:
            logger.info("Nenhuma campanha P-Max encontrada no período")

        if args.launch_code:
            df = df[df["lancamento_codigo"].fillna("").str.upper() == args.launch_code.upper()]
        upsert(df, args.since, args.until, args.launch_code)

        # Públicos
        aud_rows = fetch_audiences_report(args.since, args.until)
        if aud_rows:
            logger.info("%d registros de Públicos retornados", len(aud_rows))
            df_aud = build_df_from_audiences_api(aud_rows)
            if args.launch_code:
                df_aud = df_aud[df_aud["lancamento_codigo"].fillna("").str.upper() == args.launch_code.upper()]
            upsert_audiences(df_aud, args.since, args.until, args.launch_code)

        # Demografia
        demo_rows = fetch_demographics_report(args.since, args.until)
        if demo_rows:
            logger.info("%d registros de Demografia retornados", len(demo_rows))
            df_demo = build_df_from_demographics_api(demo_rows)
            if args.launch_code:
                df_demo = df_demo[df_demo["lancamento_codigo"].fillna("").str.upper() == args.launch_code.upper()]
            upsert_demographics(df_demo, args.since, args.until, args.launch_code)


if __name__ == "__main__":
    main()
