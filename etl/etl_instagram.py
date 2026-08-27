"""
ETL: Instagram (Meta Graph API) → Supabase
    - instagram_profile_daily: 1 snapshot/dia por conta (seguidores, posts, bio)
    - instagram_media: posts recentes, com like_count/comments_count atualizados
      a cada rodada

Contas monitoradas: config/instagram_accounts.yaml (contas Business próprias,
vinculadas às nossas Páginas — não precisa de business_discovery nem
autorização extra).

Uso:
    python etl/etl_instagram.py
    python etl/etl_instagram.py --media-limit 30
"""
import os
import sys
import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get

load_dotenv()

logger = get_logger("etl.instagram")

API_VERSION = "v22.0"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "instagram_accounts.yaml"
PROFILE_FIELDS = "username,name,biography,followers_count,media_count,profile_picture_url"
MEDIA_FIELDS = "id,caption,media_type,permalink,timestamp,like_count,comments_count,media_url,thumbnail_url"
MEDIA_INSIGHTS_METRICS = "reach,saved,shares,total_interactions"
# reach e follower_count são os únicos que aceitam metric_type=time_series
# (histórico dia a dia); os demais só dão total agregado do período (total_value).
DAILY_TIME_SERIES_METRICS = "reach"
PERIOD_TOTAL_METRICS = "profile_views,accounts_engaged,total_interactions"


def load_accounts() -> list[dict]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return cfg.get("accounts", [])


def fetch_profile(ig_id: str) -> dict | None:
    token = os.environ["META_ACCESS_TOKEN"]
    r = http_get(
        f"https://graph.facebook.com/{API_VERSION}/{ig_id}",
        params={"fields": PROFILE_FIELDS, "access_token": token},
    )
    return r.json()


def fetch_media(ig_id: str, limit: int) -> list[dict]:
    token = os.environ["META_ACCESS_TOKEN"]
    r = http_get(
        f"https://graph.facebook.com/{API_VERSION}/{ig_id}/media",
        params={"fields": MEDIA_FIELDS, "limit": limit, "access_token": token},
    )
    return r.json().get("data", [])


def fetch_media_insights(media_id: str) -> dict:
    """reach/saved/shares/total_interactions de um post — requer
    instagram_manage_insights. Retorna {} se o app/conta ainda não tiver
    esse escopo (mensagem fica só em log, não interrompe o resto do ETL)."""
    token = os.environ["META_ACCESS_TOKEN"]
    try:
        r = http_get(
            f"https://graph.facebook.com/{API_VERSION}/{media_id}/insights",
            params={"metric": MEDIA_INSIGHTS_METRICS, "access_token": token},
        )
    except Exception:
        return {}
    out = {}
    for item in r.json().get("data", []):
        values = item.get("values") or []
        if values:
            out[item["name"]] = values[0].get("value")
    return out


def fetch_daily_time_series(ig_id: str, metric: str, since: str, until: str) -> list[dict]:
    """Histórico dia a dia — só reach e follower_count aceitam isso, e só
    pros últimos 30 dias (limite da própria API, não é filtro nosso)."""
    token = os.environ["META_ACCESS_TOKEN"]
    r = http_get(
        f"https://graph.facebook.com/{API_VERSION}/{ig_id}/insights",
        params={
            "metric": metric, "period": "day", "metric_type": "time_series",
            "since": since, "until": until, "access_token": token,
        },
    )
    data = r.json().get("data", [])
    if not data:
        return []
    return data[0].get("values", [])


def fetch_period_totals(ig_id: str) -> dict:
    """Total agregado (não dia a dia) de profile_views/accounts_engaged/
    total_interactions — a API não permite time_series pra esses. Sem
    since/until = janela padrão da própria API (últimos dias correntes)."""
    token = os.environ["META_ACCESS_TOKEN"]
    try:
        r = http_get(
            f"https://graph.facebook.com/{API_VERSION}/{ig_id}/insights",
            params={
                "metric": PERIOD_TOTAL_METRICS, "period": "day",
                "metric_type": "total_value", "access_token": token,
            },
        )
    except Exception:
        return {}
    out = {}
    for item in r.json().get("data", []):
        tv = item.get("total_value") or {}
        out[item["name"]] = tv.get("value")
    return out


def build_profile_df(accounts: list[dict]) -> pd.DataFrame:
    today = date.today().isoformat()
    records = []
    for acc in accounts:
        try:
            p = fetch_profile(acc["ig_id"])
        except Exception:
            logger.warning("Instagram: falha ao buscar perfil %s (%s)", acc.get("name"), acc["ig_id"], exc_info=True)
            continue
        records.append({
            "date": today,
            "ig_id": acc["ig_id"],
            "username": p.get("username"),
            "name": p.get("name"),
            "followers_count": p.get("followers_count"),
            "media_count": p.get("media_count"),
            "biography": p.get("biography"),
            "profile_picture_url": p.get("profile_picture_url"),
        })
        logger.info("Instagram perfil: %s -> %s seguidores", acc.get("name"), p.get("followers_count"))
    return pd.DataFrame(records)


def build_media_df(accounts: list[dict], limit: int) -> pd.DataFrame:
    records = []
    for acc in accounts:
        try:
            items = fetch_media(acc["ig_id"], limit)
        except Exception:
            logger.warning("Instagram: falha ao buscar posts de %s (%s)", acc.get("name"), acc["ig_id"], exc_info=True)
            continue
        for m in items:
            insights = fetch_media_insights(m.get("id"))
            records.append({
                "media_id": m.get("id"),
                "ig_id": acc["ig_id"],
                "media_type": m.get("media_type"),
                "caption": m.get("caption"),
                "permalink": m.get("permalink"),
                "thumbnail_url": m.get("thumbnail_url") or m.get("media_url"),
                "posted_at": m.get("timestamp"),
                "like_count": m.get("like_count", 0),
                "comments_count": m.get("comments_count", 0),
                "reach": insights.get("reach"),
                "saved": insights.get("saved"),
                "shares": insights.get("shares"),
                "total_interactions": insights.get("total_interactions"),
            })
        logger.info("Instagram posts: %s -> %d posts", acc.get("name"), len(items))
    return pd.DataFrame(records)


def build_follower_growth_df(accounts: list[dict]) -> pd.DataFrame:
    """Backfill + atualização diária do ganho de seguidores. A API só aceita
    consultar os últimos 30 dias (excluindo hoje) — por isso o range fixo."""
    until = (date.today() - timedelta(days=1)).isoformat()
    since = (date.today() - timedelta(days=29)).isoformat()
    records = []
    for acc in accounts:
        try:
            values = fetch_daily_time_series(acc["ig_id"], "follower_count", since, until)
        except Exception:
            logger.warning("Instagram: falha ao buscar follower_count de %s", acc.get("name"), exc_info=True)
            continue
        for v in values:
            records.append({
                "date": v["end_time"][:10],
                "ig_id": acc["ig_id"],
                "new_followers": v.get("value"),
            })
        logger.info("Instagram crescimento: %s -> %d dias", acc.get("name"), len(values))
    return pd.DataFrame(records)


def build_account_insights_df(accounts: list[dict]) -> pd.DataFrame:
    """reach diário (time_series, 30d) + profile_views/accounts_engaged/
    total_interactions (só total do período corrente, sem backfill)."""
    until = (date.today() - timedelta(days=1)).isoformat()
    since = (date.today() - timedelta(days=29)).isoformat()
    by_date: dict[tuple[str, str], dict] = {}
    for acc in accounts:
        ig_id = acc["ig_id"]
        try:
            reach_values = fetch_daily_time_series(ig_id, "reach", since, until)
        except Exception:
            logger.warning("Instagram: falha ao buscar reach diário de %s", acc.get("name"), exc_info=True)
            reach_values = []
        for v in reach_values:
            key = (v["end_time"][:10], ig_id)
            by_date.setdefault(key, {"date": key[0], "ig_id": ig_id})["reach"] = v.get("value")

        totals = fetch_period_totals(ig_id)
        if totals:
            today_key = (date.today().isoformat(), ig_id)
            row = by_date.setdefault(today_key, {"date": today_key[0], "ig_id": ig_id})
            row["profile_views"] = totals.get("profile_views")
            row["accounts_engaged"] = totals.get("accounts_engaged")
            row["total_interactions"] = totals.get("total_interactions")
        logger.info("Instagram insights de conta: %s -> %d dias de reach, totais=%s",
                    acc.get("name"), len(reach_values), bool(totals))
    return pd.DataFrame(list(by_date.values()))


def upsert_profile(df: pd.DataFrame):
    if df.empty:
        logger.warning("Nenhum snapshot de perfil Instagram para gravar.")
        return
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    engine = get_engine()
    today = date.today().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM instagram_profile_daily WHERE date = :d AND ig_id = ANY(:ids)"),
            {"d": today, "ids": df["ig_id"].tolist()},
        )
    df.to_sql("instagram_profile_daily", engine, if_exists="append", index=False, method="multi")
    logger.info("Upsert concluído: %d linhas em 'instagram_profile_daily'", len(df))


def upsert_media(df: pd.DataFrame):
    if df.empty:
        logger.warning("Nenhum post Instagram para gravar.")
        return
    engine = get_engine()
    with engine.begin() as conn:
        for row in df.to_dict("records"):
            row = {k: (None if isinstance(v, float) and v != v else v) for k, v in row.items()}
            conn.execute(
                text("""
                    INSERT INTO instagram_media
                        (media_id, ig_id, media_type, caption, permalink, thumbnail_url,
                         posted_at, like_count, comments_count, reach, saved, shares,
                         total_interactions, updated_at)
                    VALUES
                        (:media_id, :ig_id, :media_type, :caption, :permalink, :thumbnail_url,
                         :posted_at, :like_count, :comments_count, :reach, :saved, :shares,
                         :total_interactions, NOW())
                    ON CONFLICT (media_id) DO UPDATE SET
                        like_count = EXCLUDED.like_count,
                        comments_count = EXCLUDED.comments_count,
                        thumbnail_url = EXCLUDED.thumbnail_url,
                        reach = COALESCE(EXCLUDED.reach, instagram_media.reach),
                        saved = COALESCE(EXCLUDED.saved, instagram_media.saved),
                        shares = COALESCE(EXCLUDED.shares, instagram_media.shares),
                        total_interactions = COALESCE(EXCLUDED.total_interactions, instagram_media.total_interactions),
                        updated_at = NOW()
                """),
                row,
            )
    logger.info("Upsert concluído: %d posts em 'instagram_media'", len(df))


def upsert_follower_growth(df: pd.DataFrame):
    if df.empty:
        logger.warning("Nenhum dado de crescimento de seguidores para gravar.")
        return
    engine = get_engine()
    with engine.begin() as conn:
        for row in df.to_dict("records"):
            conn.execute(
                text("""
                    INSERT INTO instagram_follower_growth_daily (date, ig_id, new_followers, updated_at)
                    VALUES (:date, :ig_id, :new_followers, NOW())
                    ON CONFLICT (date, ig_id) DO UPDATE SET
                        new_followers = EXCLUDED.new_followers, updated_at = NOW()
                """),
                row,
            )
    logger.info("Upsert concluído: %d linhas em 'instagram_follower_growth_daily'", len(df))


def upsert_account_insights(df: pd.DataFrame):
    if df.empty:
        logger.warning("Nenhum insight de conta Instagram para gravar.")
        return
    for col in ("reach", "profile_views", "accounts_engaged", "total_interactions"):
        if col not in df.columns:
            df[col] = None
    engine = get_engine()
    with engine.begin() as conn:
        for row in df.to_dict("records"):
            row = {k: (None if isinstance(v, float) and v != v else v) for k, v in row.items()}
            conn.execute(
                text("""
                    INSERT INTO instagram_account_insights_daily
                        (date, ig_id, reach, profile_views, accounts_engaged, total_interactions, updated_at)
                    VALUES
                        (:date, :ig_id, :reach, :profile_views, :accounts_engaged, :total_interactions, NOW())
                    ON CONFLICT (date, ig_id) DO UPDATE SET
                        reach = COALESCE(EXCLUDED.reach, instagram_account_insights_daily.reach),
                        profile_views = COALESCE(EXCLUDED.profile_views, instagram_account_insights_daily.profile_views),
                        accounts_engaged = COALESCE(EXCLUDED.accounts_engaged, instagram_account_insights_daily.accounts_engaged),
                        total_interactions = COALESCE(EXCLUDED.total_interactions, instagram_account_insights_daily.total_interactions),
                        updated_at = NOW()
                """),
                row,
            )
    logger.info("Upsert concluído: %d linhas em 'instagram_account_insights_daily'", len(df))


def main():
    parser = argparse.ArgumentParser(description="ETL Instagram (perfil + posts) -> Supabase")
    parser.add_argument("--media-limit", type=int, default=24, help="Quantos posts recentes sincronizar por conta")
    args = parser.parse_args()

    accounts = load_accounts()
    if not accounts:
        logger.error("Nenhuma conta configurada em %s", CONFIG_PATH)
        sys.exit(1)

    upsert_profile(build_profile_df(accounts))
    upsert_media(build_media_df(accounts, args.media_limit))
    upsert_follower_growth(build_follower_growth_df(accounts))
    upsert_account_insights(build_account_insights_df(accounts))


if __name__ == "__main__":
    main()
