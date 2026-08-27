"""
frontend/db_readers/instagram_detail.py — Análise por perfil Instagram
(posts recentes, engajamento, evolução de seguidores, alcance), lidos das
tabelas alimentadas pelo etl/etl_instagram.py.

Suporta filtro por período (7/30/90 dias ou custom) e comparação com o
período imediatamente anterior de mesma duração.
"""
from __future__ import annotations

from datetime import date, timedelta
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


def _build_follower_series(growth_rows, followers_now: int) -> list[dict]:
    """Reconstrói o total de seguidores por dia a partir do ganho líquido
    diário (instagram_follower_growth_daily) — a API só dá o total 'de hoje',
    então a série histórica é derivada de trás pra frente a partir dele."""
    if not growth_rows:
        return []
    ordered = sorted(growth_rows, key=lambda r: r.date)
    cumulative: dict[str, int] = {}
    running = followers_now
    for r in reversed(ordered):
        cumulative[str(r.date)] = running
        running -= (r.new_followers or 0)
    return [{"date": d, "followers": cumulative[d]} for d in sorted(cumulative)]


def _pct_delta(curr: float, prev: float) -> float | None:
    if not prev:
        return None
    return round((curr - prev) / prev * 100, 1)


def _post_stats(posts: list[dict]) -> dict:
    total = len(posts)
    avg_likes = round(sum(p["like_count"] for p in posts) / total) if total else 0
    avg_comments = round(sum(p["comments_count"] for p in posts) / total) if total else 0
    avg_engagement_rate = round(sum(p["engagement_rate"] for p in posts) / total, 2) if total else 0
    with_reach = [p for p in posts if p["reach"]]
    avg_reach = round(sum(p["reach"] for p in with_reach) / len(with_reach)) if with_reach else None
    return {
        "total_posts": total,
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "avg_engagement_rate": avg_engagement_rate,
        "avg_reach": avg_reach,
    }


def read_instagram_detail(username: str, days: int = 30, compare: bool = False) -> dict | None:
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
                    "like_count, comments_count, reach, saved, shares, total_interactions "
                    "FROM instagram_media WHERE ig_id = :ig_id ORDER BY posted_at DESC"
                ),
                {"ig_id": ig_id},
            ).fetchall()
            growth_rows = conn.execute(
                text(
                    "SELECT date, new_followers FROM instagram_follower_growth_daily "
                    "WHERE ig_id = :ig_id ORDER BY date"
                ),
                {"ig_id": ig_id},
            ).fetchall()
            account_insight_rows = conn.execute(
                text(
                    "SELECT date, reach, profile_views, accounts_engaged, total_interactions "
                    "FROM instagram_account_insights_daily WHERE ig_id = :ig_id ORDER BY date"
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

    # ── Janela de datas ──────────────────────────────────────────────────
    end = date.today()
    start = end - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    follower_series_full = _build_follower_series(growth_rows, followers_now)
    if not follower_series_full:
        follower_series_full = [{"date": str(r.date), "followers": r.followers_count} for r in profile_rows]
    follower_series = [p for p in follower_series_full if start.isoformat() <= p["date"] <= end.isoformat()]

    def _followers_gained(range_start: date, range_end: date) -> int:
        return sum(
            (r.new_followers or 0) for r in growth_rows
            if range_start <= r.date <= range_end
        )

    def _reach_total(range_start: date, range_end: date) -> tuple[int, int]:
        rows = [r for r in account_insight_rows if range_start <= r.date <= range_end and r.reach]
        return sum(r.reach for r in rows), len(rows)

    followers_gained = _followers_gained(start, end)
    reach_period_total, reach_period_days = _reach_total(start, end)
    last_totals = next((r for r in reversed(account_insight_rows) if r.profile_views is not None), None)

    def _posts_in_range(range_start: date, range_end: date) -> list[dict]:
        out = []
        for r in media_rows:
            if not r.posted_at or not (range_start <= r.posted_at.date() <= range_end):
                continue
            engagement = r.like_count + r.comments_count
            rate = round((engagement / followers_now) * 100, 2) if followers_now else 0
            out.append({
                "media_id": r.media_id,
                "media_type": r.media_type,
                "caption": (r.caption or "")[:180],
                "permalink": r.permalink,
                "thumbnail_url": r.thumbnail_url,
                "posted_at": str(r.posted_at),
                "like_count": r.like_count or 0,
                "comments_count": r.comments_count or 0,
                "reach": r.reach,
                "saved": r.saved,
                "shares": r.shares,
                "total_interactions": r.total_interactions,
                "engagement": engagement,
                "engagement_rate": rate,
            })
        return out

    posts = _posts_in_range(start, end)
    stats = _post_stats(posts)
    top_posts = sorted(posts, key=lambda p: -p["engagement"])[:3]

    result = {
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
        "total_posts_analisados": stats["total_posts"],
        "avg_likes": stats["avg_likes"],
        "avg_comments": stats["avg_comments"],
        "avg_engagement_rate": stats["avg_engagement_rate"],
        "avg_reach": stats["avg_reach"],
        "followers_gained": followers_gained,
        "reach_period_days": reach_period_days,
        "reach_period_total": reach_period_total,
        "profile_views": last_totals.profile_views if last_totals else None,
        "accounts_engaged": last_totals.accounts_engaged if last_totals else None,
        "no_data": False,
        "days": days,
        "compare": compare,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "range_available_from": str(profile_rows[0].date),
    }

    if compare:
        prev_posts = _posts_in_range(prev_start, prev_end)
        prev_stats = _post_stats(prev_posts)
        prev_followers_gained = _followers_gained(prev_start, prev_end)
        prev_reach_total, _ = _reach_total(prev_start, prev_end)
        result["prev_range_start"] = prev_start.isoformat()
        result["prev_range_end"] = prev_end.isoformat()
        result["deltas"] = {
            "followers_gained": _pct_delta(followers_gained, prev_followers_gained),
            "avg_likes": _pct_delta(stats["avg_likes"], prev_stats["avg_likes"]),
            "avg_comments": _pct_delta(stats["avg_comments"], prev_stats["avg_comments"]),
            "avg_engagement_rate": _pct_delta(stats["avg_engagement_rate"], prev_stats["avg_engagement_rate"]),
            "reach_period_total": _pct_delta(reach_period_total, prev_reach_total),
        }
        result["prev"] = {
            "followers_gained": prev_followers_gained,
            "reach_period_total": prev_reach_total,
            **prev_stats,
        }

    return result
