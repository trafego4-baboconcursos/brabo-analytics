"""
ETL: Meta Ads Marketing API → Supabase (tabela: meta_ads_daily)

Modo API (dados diários):
    python etl/etl_meta_ads.py --since 2026-04-01 --until 2026-04-30

Modo CSV (importa export manual do Ads Manager — sem daily breakdown):
    python etl/etl_meta_ads.py --from-csv "analises/[PBB-ABR-26]/Meta Ads/meta-pbb-abr-26.csv" --campaign-period 2026-04

Pré-requisitos .env:
    META_ACCESS_TOKEN   — token com permissão ads_read / read_insights
    META_AD_ACCOUNT_ID  — ex: act_123456789
"""
import os
import sys
import argparse
import re
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import requests
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get
from validation import validate_dataframe

load_dotenv()

logger = get_logger("etl.meta")

API_VERSION = "v22.0"
TABLE       = "meta_ads_daily"

AD_CODE_RE = re.compile(r"(AD\d+)", re.IGNORECASE)

def extract_launch_code(campaign_name: str) -> str | None:
    if pd.isna(campaign_name) or not campaign_name:
        return None
    match = re.search(r'(PBB|PES|PI)-\w{3}-\d{2}', str(campaign_name), re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None

def parse_number(value) -> float:
    if pd.isna(value):
        return 0.0
    text_value = str(value).strip().replace("R$", "").replace(" ", "")
    if not text_value or text_value.lower() in {"nan", "none", "-"}:
        return 0.0
    if "," in text_value and "." in text_value:
        if text_value.rfind(",") > text_value.rfind("."):
            text_value = text_value.replace(".", "").replace(",", ".")
        else:
            text_value = text_value.replace(",", "")
    elif "," in text_value:
        text_value = text_value.replace(".", "").replace(",", ".")
    parsed = pd.to_numeric(text_value, errors="coerce")
    return 0.0 if pd.isna(parsed) else float(parsed)


# ─────────────────────────────────────────────────────────────────────────────
# Modo API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_insights(since: str, until: str, account_ids: list[str] | None = None) -> list[dict]:
    """Busca insights diários por anúncio via Marketing API para múltiplas contas."""
    account_ids = account_ids or [acc.strip() for acc in os.environ["META_AD_ACCOUNT_ID"].split(",") if acc.strip()]
    token      = os.environ["META_ACCESS_TOKEN"]

    rows = []
    for account_id in account_ids:
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        logger.info("Buscando insights da conta Meta: %s", account_id)
        url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"

        params = {
            "access_token":  token,
            "fields":        "ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,"
                             "impressions,clicks,spend,actions,outbound_clicks,"
                             "video_p25_watched_actions,video_p50_watched_actions,"
                             "video_p75_watched_actions,video_p100_watched_actions,"
                             "video_thruplay_watched_actions",
            "level":         "ad",
            "time_range":    f'{{"since":"{since}","until":"{until}"}}',
            "time_increment": 1,       # breakdown diário
            "limit":         50,
        }

        while url:
            r = http_get(url, params=params)
            data = r.json()
            rows.extend(data.get("data", []))
            url    = data.get("paging", {}).get("next")
            params = {}   # próxima página já vem com todos os parâmetros na URL

    return rows


def fetch_campaign_status(account_ids: list[str] | None = None) -> dict[str, str]:
    """Retorna {campaign_name: effective_status} das campanhas das contas informadas."""
    account_ids = account_ids or [acc.strip() for acc in os.environ["META_AD_ACCOUNT_ID"].split(",") if acc.strip()]
    token = os.environ["META_ACCESS_TOKEN"]

    result: dict[str, str] = {}
    for account_id in account_ids:
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/campaigns"
        params = {"access_token": token, "fields": "name,effective_status", "limit": 200}
        while url:
            r = http_get(url, params=params)
            data = r.json()
            for c in data.get("data", []):
                result[c.get("name")] = c.get("effective_status")
            url = data.get("paging", {}).get("next")
            params = {}
    return result


def _action_value(actions: list, action_type: str) -> int:
    for a in (actions or []):
        if a.get("action_type") == action_type:
            return int(float(a.get("value", 0)))
    return 0


def _action_list_value(action_list: list) -> int:
    if not action_list or not isinstance(action_list, list):
        return 0
    return int(float(action_list[0].get("value", 0)))


def build_df_from_api(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        campaign_name = r.get("campaign_name")
        records.append({
            "date":             r.get("date_start"),
            "ad_id":            r.get("ad_id"),
            "ad_name":          r.get("ad_name"),
            "adset_id":         r.get("adset_id"),
            "adset_name":       r.get("adset_name"),
            "campaign_id":      r.get("campaign_id"),
            "campaign_name":    campaign_name,
            "lancamento_codigo": extract_launch_code(campaign_name),
            "impressions":      int(r.get("impressions", 0)),
            "clicks":           int(r.get("clicks", 0)),
            "spend":            float(r.get("spend", 0)),
            "leads":            _action_value(r.get("actions"), "lead"),
            "link_clicks":      _action_value(r.get("actions"), "link_click"),
            "outbound_clicks":  _action_list_value(r.get("outbound_clicks")),
            "video_views_3s":   _action_value(r.get("actions"), "video_view"),
            "video_views_25":   _action_list_value(r.get("video_p25_watched_actions")),
            "video_views_50":   _action_list_value(r.get("video_p50_watched_actions")),
            "video_views_75":   _action_list_value(r.get("video_p75_watched_actions")),
            "video_views_100":  _action_list_value(r.get("video_p100_watched_actions")),
            "video_thruplays":  _action_list_value(r.get("video_thruplay_watched_actions")),
        })
    return pd.DataFrame(records)


    return pd.DataFrame(records)


def fetch_demographics(since: str, until: str) -> list[dict]:
    account_ids = [acc.strip() for acc in os.environ["META_AD_ACCOUNT_ID"].split(",") if acc.strip()]
    token      = os.environ["META_ACCESS_TOKEN"]

    rows = []
    for account_id in account_ids:
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        logger.info("Buscando demografia da conta Meta: %s", account_id)
        url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"

        params = {
            "access_token":  token,
            "fields":        "campaign_name,impressions,clicks,spend,actions",
            "level":         "campaign",
            "breakdowns":    "age,gender",
            "time_range":    f'{{"since":"{since}","until":"{until}"}}',
            "time_increment": 1,
            "limit":         50,
        }

        while url:
            r = http_get(url, params=params)
            data = r.json()
            rows.extend(data.get("data", []))
            url    = data.get("paging", {}).get("next")
            params = {}   # próxima página já vem com todos os parâmetros na URL

    return rows

def build_df_from_demographics_api(rows: list[dict]) -> pd.DataFrame:
    records = []
    for r in rows:
        campaign_name = r.get("campaign_name", "")
        records.append({
            "date":             r.get("date_start"),
            "age":              r.get("age", ""),
            "gender":           r.get("gender", ""),
            "campaign_name":    campaign_name,
            "lancamento_codigo": extract_launch_code(campaign_name),
            "impressions":      int(r.get("impressions", 0)),
            "clicks":           int(r.get("clicks", 0)),
            "cost":             float(r.get("spend", 0)),
            "leads":            _action_value(r.get("actions"), "lead"),
        })
    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# Modo CSV (export manual do Ads Manager)
# O CSV do Ads Manager já tem breakdown diário — coluna "Dia"
# ─────────────────────────────────────────────────────────────────────────────

def build_df_from_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, dtype=str)

    col_map = {
        "Dia":                                "date",
        "Nome da campanha":                   "campaign_name",
        "Nome do conjunto de anúncios":        "adset_name",
        "Nome do anúncio":                    "ad_name",
        "Impressões":                         "impressions",
        "Cliques no link":                    "clicks",
        "Valor usado (BRL)":                  "spend",
        "Leads":                              "leads",
        "Cliques (todos)":                    "link_clicks",
        "Cliques de saída únicos":             "outbound_clicks",
        "Cliques de saída":                   "outbound_clicks",
        "Reproduções de vídeo de 3 segundos": "video_views_3s",
        "Visualizações do vídeo em 25%":      "video_views_25",
        "Visualizações do vídeo em 50%":      "video_views_50",
        "Visualizações do vídeo em 75%":      "video_views_75",
        "Visualizações do vídeo em 100%":     "video_views_100",
        "ThruPlays":                          "video_thruplays",
    }
    
    # Renomeia se existir
    for k, v in col_map.items():
        if k in df.columns:
            df = df.rename(columns={k: v})
            
    # Cria colunas de destino que não existirem no CSV original
    dest_cols = ["date", "campaign_name", "adset_name", "ad_name", "impressions", 
                 "clicks", "spend", "leads", "link_clicks", "outbound_clicks",
                 "video_views_3s", "video_views_25", "video_views_50", 
                 "video_views_75", "video_views_100", "video_thruplays"]
                 
    for col in dest_cols:
        if col not in df.columns:
            df[col] = "0"

    # Colunas numéricas — remove pontos de milhar e troca vírgula por ponto
    numeric_cols = ["impressions", "clicks", "spend", "leads", "link_clicks", "outbound_clicks",
                    "video_views_3s", "video_views_25", "video_views_50", 
                    "video_views_75", "video_views_100", "video_thruplays"]
                    
    for col in numeric_cols:
        df[col] = df[col].apply(parse_number)

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Gera ad_id sintético a partir do nome (ADXXX) — o export CSV não tem ID numérico
    extracted = df["ad_name"].str.extract(r"(AD\d+)", flags=re.IGNORECASE)[0].str.upper()
    # Anúncios sem padrão ADXXX (ex: Lembrete, Replay) recebem slug do nome como ID
    fallback = df["ad_name"].str.upper().str.replace(r"[^A-Z0-9]", "-", regex=True).str.strip("-").str[:30]
    df["ad_id"]       = extracted.combine_first(fallback)
    df["adset_id"]    = None
    df["campaign_id"] = None
    df["lancamento_codigo"] = df["campaign_name"].apply(extract_launch_code)

    df = df.dropna(subset=["ad_id", "date"])
    df = df[["date", "ad_id", "ad_name", "adset_id", "adset_name",
             "campaign_id", "campaign_name", "lancamento_codigo", "impressions", "clicks",
             "spend", "leads", "link_clicks", "outbound_clicks",
             "video_views_3s", "video_views_25", "video_views_50",
             "video_views_75", "video_views_100", "video_thruplays"]]

    # O CSV do Ads Manager pode repetir ADXXX no mesmo dia em conjuntos diferentes.
    # A tabela historica e a API usam uma linha por ad_id + date, entao agregamos.
    numeric_cols = ["impressions", "clicks", "spend", "leads", "link_clicks", "outbound_clicks",
                    "video_views_3s", "video_views_25", "video_views_50",
                    "video_views_75", "video_views_100", "video_thruplays"]
    first_cols = ["ad_name", "adset_id", "adset_name", "campaign_id", "campaign_name", "lancamento_codigo"]
    agg = {col: "sum" for col in numeric_cols}
    agg.update({col: "first" for col in first_cols})
    return df.groupby(["date", "ad_id"], as_index=False).agg(agg)


# ─────────────────────────────────────────────────────────────────────────────
# Upsert
# ─────────────────────────────────────────────────────────────────────────────

_META_REQUIRED_COLS = ["date", "ad_id", "ad_name", "spend", "impressions", "clicks"]

def upsert(df: pd.DataFrame, since: str, until: str, launch_code: str | None = None):
    if not validate_dataframe(df, _META_REQUIRED_COLS, "meta_ads_daily", logger):
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    with engine.begin() as conn:
        if launch_code:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE date BETWEEN :s AND :u AND lancamento_codigo = :code"),
                {"s": since, "u": until, "code": launch_code.upper()},
            )
        else:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE date BETWEEN :s AND :u"),
                {"s": since, "u": until},
            )
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), TABLE)


def upsert_demographics(df: pd.DataFrame, since: str, until: str, launch_code: str | None = None):
    if df.empty:
        logger.warning("Nenhum dado de demografia Meta Ads para gravar.")
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    table = "meta_ads_demographics_daily"
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
# Thumbnails de criativos — busca direto da API (substitui dependência do Drive)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_creative_details(ad_ids: list[str]) -> dict[str, dict]:
    """Busca nome + thumbnail/image_url só dos ad_ids informados, em lotes
    (endpoint de batch por 'ids='), evitando escanear a conta inteira."""
    token = os.environ["META_ACCESS_TOKEN"]
    result: dict[str, dict] = {}
    batch_size = 25
    unique_ids = list(dict.fromkeys(ad_ids))
    for i in range(0, len(unique_ids), batch_size):
        chunk = unique_ids[i:i + batch_size]
        params = {
            "access_token": token,
            "ids": ",".join(chunk),
            "fields": "name,creative{thumbnail_url,image_url,object_story_spec}",
        }
        try:
            r = http_get(f"https://graph.facebook.com/{API_VERSION}/", params=params, timeout=60)
        except Exception:
            logger.exception("Falha ao buscar detalhes de criativo para lote de %d ads; pulando lote", len(chunk))
            continue
        data = r.json()
        for ad_id, obj in data.items():
            result[ad_id] = obj
    return result


def fetch_all_ads_listing() -> pd.DataFrame:
    """Lista id/nome/campanha de TODOS os anuncios de cada conta (sem
    metricas diarias, bem mais leve que /insights). Usado para popular
    thumbnails de anuncios antigos que ja saíram da janela do scheduler
    (ultimos 3 dias)."""
    account_ids = [acc.strip() for acc in os.environ["META_AD_ACCOUNT_ID"].split(",") if acc.strip()]
    token = os.environ["META_ACCESS_TOKEN"]

    records = []
    for account_id in account_ids:
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        logger.info("Listando anuncios da conta Meta: %s", account_id)
        url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/ads"
        params = {
            "access_token": token,
            "fields": "id,name,campaign{name}",
            "limit": 200,
        }
        while url:
            r = http_get(url, params=params, timeout=60)
            data = r.json()
            for r_ad in data.get("data", []):
                campaign_name = (r_ad.get("campaign") or {}).get("name")
                records.append({
                    "ad_id":             r_ad.get("id"),
                    "ad_name":           r_ad.get("name"),
                    "lancamento_codigo": extract_launch_code(campaign_name),
                })
            url = data.get("paging", {}).get("next")
            params = {}
    return pd.DataFrame(records)


def build_thumbnails_df(insights_df: pd.DataFrame) -> pd.DataFrame:
    """A partir do df de insights (que já tem ad_id + lancamento_codigo),
    busca os detalhes do criativo só para os anúncios com AD\\d+ no nome."""
    if insights_df.empty:
        return pd.DataFrame()
    ad_meta = (
        insights_df[["ad_id", "ad_name", "lancamento_codigo"]]
        .dropna(subset=["lancamento_codigo"])
        .drop_duplicates(subset=["ad_id"])
    )
    ad_meta = ad_meta[ad_meta["ad_name"].str.contains(AD_CODE_RE, na=False)]
    if ad_meta.empty:
        return pd.DataFrame()

    details = fetch_creative_details(ad_meta["ad_id"].astype(str).tolist())

    records = []
    for _, row in ad_meta.iterrows():
        ad_id = str(row["ad_id"])
        name = row["ad_name"] or ""
        match = AD_CODE_RE.search(name)
        if not match:
            continue
        obj = details.get(ad_id) or {}
        creative = obj.get("creative") or {}
        image_url = creative.get("image_url")
        if not image_url:
            story = creative.get("object_story_spec") or {}
            video_data = story.get("video_data") or {}
            image_url = video_data.get("image_url")
        records.append({
            "platform":           "meta",
            "ad_code":            match.group(1).upper(),
            "ad_name":            name,
            "lancamento_codigo":  row["lancamento_codigo"],
            "thumbnail_url":      creative.get("thumbnail_url"),
            "image_url":          image_url,
        })
    return pd.DataFrame(records)


def _download_image(url: str | None) -> tuple[bytes, str] | None:
    """Baixa a imagem enquanto a URL assinada do CDN ainda está fresca.
    Sem retry de propósito: imagem indisponível (403/404) não volta com
    backoff, e o retry exponencial fazia o backfill levar horas."""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200 or not r.content:
            return None
        content_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
        if not content_type.startswith("image/"):
            return None
        return r.content, content_type
    except Exception:
        logger.debug("Falha ao baixar imagem de criativo: %s", url[:80])
        return None


def upsert_thumbnails(df: pd.DataFrame):
    if df.empty:
        logger.info("Nenhum criativo com código AD encontrado para thumbnails.")
        return
    df = df.dropna(subset=["lancamento_codigo"])
    df = df.drop_duplicates(subset=["platform", "ad_code", "lancamento_codigo"], keep="last")
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    df = df.astype(object).where(df.notna(), None)
    engine = get_engine()

    # As URLs do CDN do Facebook expiram — persiste os BYTES da imagem no
    # momento do ETL (mesma lição do Drive/creative_thumbnails). Só baixa
    # quando a linha ainda não tem bytes, pra não re-baixar tudo a cada hora.
    with engine.connect() as conn:
        have_bytes = {
            (r[0], r[1], r[2])
            for r in conn.execute(text(
                "SELECT platform, ad_code, lancamento_codigo FROM ad_creatives WHERE thumb_data IS NOT NULL"
            )).fetchall()
        }

    upsert_sql = text("""
        INSERT INTO ad_creatives (platform, ad_code, ad_name, lancamento_codigo, thumbnail_url, image_url,
                                  thumb_data, thumb_content_type, image_data, image_content_type, updated_at)
        VALUES (:platform, :ad_code, :ad_name, :lancamento_codigo, :thumbnail_url, :image_url,
                :thumb_data, :thumb_content_type, :image_data, :image_content_type, :updated_at)
        ON CONFLICT (platform, ad_code, lancamento_codigo)
        DO UPDATE SET ad_name = EXCLUDED.ad_name, thumbnail_url = EXCLUDED.thumbnail_url,
                       image_url = EXCLUDED.image_url, updated_at = EXCLUDED.updated_at,
                       thumb_data = COALESCE(EXCLUDED.thumb_data, ad_creatives.thumb_data),
                       thumb_content_type = COALESCE(EXCLUDED.thumb_content_type, ad_creatives.thumb_content_type),
                       image_data = COALESCE(EXCLUDED.image_data, ad_creatives.image_data),
                       image_content_type = COALESCE(EXCLUDED.image_content_type, ad_creatives.image_content_type)
    """)

    records = df.to_dict("records")
    baixadas = 0
    # grava em lotes conforme baixa, pra um backfill longo interrompido não
    # perder o progresso (os já-com-bytes são pulados na próxima rodada)
    batch: list[dict] = []
    def _flush():
        if not batch:
            return
        with engine.begin() as conn:
            for rec in batch:
                conn.execute(upsert_sql, rec)
        batch.clear()

    for i, rec in enumerate(records):
        rec["thumb_data"] = rec["thumb_content_type"] = None
        rec["image_data"] = rec["image_content_type"] = None
        if (rec["platform"], rec["ad_code"], rec["lancamento_codigo"]) not in have_bytes:
            thumb = _download_image(rec.get("thumbnail_url"))
            if thumb:
                rec["thumb_data"], rec["thumb_content_type"] = thumb
            image = _download_image(rec.get("image_url"))
            if image:
                rec["image_data"], rec["image_content_type"] = image
            if thumb or image:
                baixadas += 1
        batch.append(rec)
        if len(batch) >= 50:
            _flush()
            logger.info("Thumbnails: %d/%d processados (%d imagens baixadas)", i + 1, len(records), baixadas)
    _flush()
    logger.info("Thumbnails: %d criativos gravados em 'ad_creatives' (%d imagens baixadas)", len(records), baixadas)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ETL Meta Ads - Supabase")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--since", metavar="YYYY-MM-DD", help="Data inicial (modo API)")
    group.add_argument("--from-csv", metavar="FILE",    help="CSV exportado do Ads Manager")
    group.add_argument("--thumbnails-only", action="store_true",
                        help="So busca/atualiza thumbnails de criativos (todos os anuncios, sem limite de data)")
    parser.add_argument("--until",  metavar="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--since-csv", metavar="YYYY-MM-DD", help="Data mínima ao importar via CSV (filtra linhas)")
    parser.add_argument("--until-csv", metavar="YYYY-MM-DD", help="Data máxima ao importar via CSV")
    parser.add_argument("--launch-code", metavar="CODE", help="Filtra e substitui dados apenas de um lancamento")
    args = parser.parse_args()

    if args.thumbnails_only:
        logger.info("[Meta Ads] Atualizando thumbnails de criativos (todos os anúncios)")
        ads_df = fetch_all_ads_listing()
        logger.info("%d anúncios listados nas contas", len(ads_df))
        if args.launch_code:
            ads_df = ads_df[ads_df["lancamento_codigo"] == args.launch_code.upper()]
        df_thumb = build_thumbnails_df(ads_df)
        upsert_thumbnails(df_thumb)
        return

    if args.from_csv:
        logger.info("[Meta Ads] %s <- CSV: %s", TABLE, args.from_csv)
        df = build_df_from_csv(args.from_csv)
        since = args.since_csv or str(df["date"].min())
        until = args.until_csv or str(df["date"].max())
        if args.since_csv or args.until_csv:
            df = df[df["date"].between(since, until)]
        if args.launch_code:
            df = df[df["lancamento_codigo"] == args.launch_code.upper()]
        logger.info("%d linhas  [%s -> %s]", len(df), since, until)
        upsert(df, since, until, args.launch_code)
    else:
        logger.info("[Meta Ads] %s  [%s -> %s]  (API)", TABLE, args.since, args.until)
        rows = fetch_insights(args.since, args.until)
        logger.info("%d registros retornados da API", len(rows))
        df   = build_df_from_api(rows)
        if args.launch_code:
            df = df[df["lancamento_codigo"] == args.launch_code.upper()]
        upsert(df, args.since, args.until, args.launch_code)

        # Demografia
        demo_rows = fetch_demographics(args.since, args.until)
        if demo_rows:
            logger.info("%d registros de demografia retornados", len(demo_rows))
            df_demo = build_df_from_demographics_api(demo_rows)
            if args.launch_code:
                df_demo = df_demo[df_demo["lancamento_codigo"] == args.launch_code.upper()]
            upsert_demographics(df_demo, args.since, args.until, args.launch_code)

        # Thumbnails de criativos: reaproveita ad_id/ad_name/lancamento_codigo
        # ja retornados pelos insights, so busca creative{} para eles.
        # Nao deve derrubar o resto do ETL se a API de criativos falhar/atrasar.
        try:
            df_thumb = build_thumbnails_df(df)
            if args.launch_code:
                df_thumb = df_thumb[df_thumb["lancamento_codigo"] == args.launch_code.upper()] if not df_thumb.empty else df_thumb
            upsert_thumbnails(df_thumb)
        except Exception:
            logger.exception("Falha ao atualizar thumbnails de criativos; seguindo sem elas")


if __name__ == "__main__":
    main()
