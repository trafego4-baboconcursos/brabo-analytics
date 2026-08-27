"""
frontend/db_readers/instagram_detail.py — Análise por perfil Instagram
(posts recentes, engajamento, evolução de seguidores), lidos das tabelas
alimentadas pelo etl/etl_instagram.py.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine

logger = get_logger("db")

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "instagram_accounts.yaml"


def _load_accounts() -> list[dict]:
    cfg = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return cfg.get("accounts", [])


def _find_account(username: str) -> dict | None:
    for acc in _load_accounts():
        if acc.get("username") == username:
            return acc
    return None


def read_instagram_detail(username: str) -> dict | None:
    account = _find_account(username)
    if not account:
        return None
    ig_id = account["ig_id"]

    try:
        with _get_engine().connect() as conn:
            profile_rows = conn.execute(
                text(
                    "SELECT date, followers_count, media_count, biography, profile_picture_url, name "
                    "FROM instagram_profile_daily WHERE ig_id = :ig_id ORDER BY date"
                ),
                {"ig_id": ig_id},
            ).fetchall()
            media_rows = conn.execute(
                text(
                    "SELECT media_id, media_type, caption, permalink, thumbnail_url, posted_at, "
                    "like_count, comments_count FROM instagram_media "
                    "WHERE ig_id = :ig_id ORDER BY posted_at DESC"
                ),
                {"ig_id": ig_id},
            ).fetchall()
    except Exception:
        logger.exception("read_instagram_detail: falha para %s", username)
        return None

    if not profile_rows:
        return {
            "name": account.get("name"),
            "username": username,
            "profile_url": f"https://instagram.com/{username}",
            "no_data": True,
        }

    latest = profile_rows[-1]
    followers_now = latest.followers_count or 0

    follower_series = [{"date": str(r.date), "followers": r.followers_count} for r in profile_rows]

    posts = []
    for r in media_rows:
        engagement = r.like_count + r.comments_count
        rate = round((engagement / followers_now) * 100, 2) if followers_now else 0
        posts.append({
            "media_id": r.media_id,
            "media_type": r.media_type,
            "caption": (r.caption or "")[:180],
            "permalink": r.permalink,
            "thumbnail_url": r.thumbnail_url,
            "posted_at": str(r.posted_at) if r.posted_at else None,
            "like_count": r.like_count or 0,
            "comments_count": r.comments_count or 0,
            "engagement": engagement,
            "engagement_rate": rate,
        })

    total_posts = len(posts)
    avg_likes = round(sum(p["like_count"] for p in posts) / total_posts) if total_posts else 0
    avg_comments = round(sum(p["comments_count"] for p in posts) / total_posts) if total_posts else 0
    avg_engagement_rate = round(sum(p["engagement_rate"] for p in posts) / total_posts, 2) if total_posts else 0
    top_posts = sorted(posts, key=lambda p: -p["engagement"])[:3]

    return {
        "name": latest.name or account.get("name"),
        "username": username,
        "profile_url": f"https://instagram.com/{username}",
        "biography": latest.biography,
        "profile_picture_url": latest.profile_picture_url,
        "followers_count": followers_now,
        "media_count": latest.media_count,
        "follower_series": follower_series,
        "posts": posts,
        "top_posts": top_posts,
        "total_posts_analisados": total_posts,
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "avg_engagement_rate": avg_engagement_rate,
        "no_data": False,
    }
