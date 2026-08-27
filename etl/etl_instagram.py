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
from datetime import date, datetime, timezone
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
            })
        logger.info("Instagram posts: %s -> %d posts", acc.get("name"), len(items))
    return pd.DataFrame(records)


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
            conn.execute(
                text("""
                    INSERT INTO instagram_media
                        (media_id, ig_id, media_type, caption, permalink, thumbnail_url,
                         posted_at, like_count, comments_count, updated_at)
                    VALUES
                        (:media_id, :ig_id, :media_type, :caption, :permalink, :thumbnail_url,
                         :posted_at, :like_count, :comments_count, NOW())
                    ON CONFLICT (media_id) DO UPDATE SET
                        like_count = EXCLUDED.like_count,
                        comments_count = EXCLUDED.comments_count,
                        thumbnail_url = EXCLUDED.thumbnail_url,
                        updated_at = NOW()
                """),
                row,
            )
    logger.info("Upsert concluído: %d posts em 'instagram_media'", len(df))


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


if __name__ == "__main__":
    main()
