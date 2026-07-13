"""
ETL: YouTube Data API + YouTube Analytics API → Supabase (youtube_aulas_stats)

Pré-requisito (execute uma vez):
    python etl/get_youtube_token.py

Uso:
    python etl/etl_youtube_analytics.py --launch-code PES-MAI-26

Os video IDs devem estar no YAML de config do lançamento:
    config/launches/pes-mai-26.yaml
    ...
    youtube:
      aulas:
        - id: "dQw4w9WgXcQ"
          label: "Aula 1 — Introdução"
        - id: "abc123def456"
          label: "Aula 2 — Direitos e Deveres"

Variáveis de ambiente necessárias:
    GOOGLE_ADS_CLIENT_ID
    GOOGLE_ADS_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN     (gerado com get_youtube_token.py)
    SUPABASE_DB_URL
"""
from __future__ import annotations

import os
import sys
import re
import argparse
import isodate
from pathlib import Path
from datetime import datetime, timezone

import requests
import yaml
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()
logger = get_logger("etl.youtube")

TABLE = "youtube_aulas_stats"
YT_API_BASE      = "https://www.googleapis.com/youtube/v3"
YT_ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2"


# ─── Credenciais ─────────────────────────────────────────────────────────────

def _load_client_credentials() -> tuple[str, str, str]:
    """Retorna (client_id, client_secret, refresh_token).

    Prioridade:
    1. YOUTUBE_REFRESH_TOKEN no .env + client_secrets.json  (token com escopo analytics)
    2. youtube/token_bb.json                                 (fallback — escopo force-ssl)
    3. GOOGLE_ADS_CLIENT_ID/SECRET + YOUTUBE_REFRESH_TOKEN env
    """
    import json
    secrets_path = Path(__file__).parent.parent / "youtube" / "client_secrets.json"

    # 1. .env tem refresh token dedicado ao analytics → usa com client_secrets.json
    rt_env = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
    if rt_env and secrets_path.exists():
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        installed = data.get("installed") or data.get("web") or {}
        cid = installed.get("client_id", "")
        csecret = installed.get("client_secret", "")
        if cid and csecret:
            logger.info("Usando YOUTUBE_REFRESH_TOKEN do .env (escopo analytics)")
            return cid, csecret, rt_env

    # 2. Fallback: token_bb.json (escopo youtube.force-ssl — sem analytics)
    token_path = Path(__file__).parent.parent / "youtube" / "token_bb.json"
    if token_path.exists():
        data = json.loads(token_path.read_text(encoding="utf-8"))
        cid = data.get("client_id", "")
        csecret = data.get("client_secret", "")
        rt = data.get("refresh_token", "")
        if cid and csecret and rt:
            logger.warning("Usando token_bb.json (escopo force-ssl) — analytics ficara zerado. Rode get_youtube_token.py para corrigir.")
            return cid, csecret, rt

    # 3. Variáveis de ambiente avulsas
    cid = os.environ.get("GOOGLE_ADS_CLIENT_ID", "")
    csecret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")
    return cid, csecret, rt_env


# ─── OAuth ───────────────────────────────────────────────────────────────────

def _get_access_token() -> str:
    try:
        import google.oauth2.credentials
        import google.auth.transport.requests
    except ImportError:
        sys.exit("Instale google-auth:  pip install google-auth")

    client_id, client_secret, refresh_token = _load_client_credentials()
    if not all([client_id, client_secret, refresh_token]):
        sys.exit(
            "Erro: credenciais incompletas. Coloque youtube/token_bb.json ou defina "
            "GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET e YOUTUBE_REFRESH_TOKEN no .env"
        )
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_videos(launch_code: str) -> tuple[list[dict], str]:
    """Retorna (aulas, channel_id).

    Prioridade: DB (launch_config.youtube_aulas) → YAML.
    channel_id padrão: "MINE" (canal do token autorizado).
    """
    # 1. Tenta DB
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from frontend.db_readers.launches import read_launch_config
        cfg = read_launch_config(launch_code)
        aulas_db = cfg.get("youtube_aulas") or []
        channel_id = cfg.get("youtube_channel_id") or "MINE"
        if aulas_db:
            logger.info("Usando %d aula(s) do banco de dados para %s", len(aulas_db), launch_code)
            return [a for a in aulas_db if a.get("id")], channel_id
    except Exception as e:
        logger.debug("DB indisponível para youtube_aulas: %s", e)

    # 2. Fallback: YAML
    slug = launch_code.lower().replace("_", "-")
    yaml_path = Path(__file__).parent.parent / "config" / "launches" / f"{slug}.yaml"
    if not yaml_path.exists():
        logger.warning("Nenhuma fonte de vídeos encontrada para %s", launch_code)
        return [], "MINE"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    yt = data.get("youtube") or {}
    aulas = yt.get("aulas") or []
    channel_id = yt.get("channel_id") or "MINE"
    logger.info("Usando %d aula(s) do YAML para %s (channel_id=%s)", len(aulas), launch_code, channel_id)
    return [a for a in aulas if a.get("id")], channel_id


def _iso_duration_to_sec(iso: str) -> int:
    try:
        return int(isodate.parse_duration(iso).total_seconds())
    except Exception:
        return 0


# ─── YouTube Data API v3 ─────────────────────────────────────────────────────

def fetch_video_details(video_ids: list[str], token: str) -> dict[str, dict]:
    """Retorna stats e detalhes por video_id."""
    if not video_ids:
        return {}
    url = f"{YT_API_BASE}/videos"
    params = {
        "part": "statistics,contentDetails,liveStreamingDetails,snippet",
        "id": ",".join(video_ids),
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()

    result: dict[str, dict] = {}
    for item in r.json().get("items", []):
        vid = item["id"]
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        live = item.get("liveStreamingDetails", {})
        snippet = item.get("snippet", {})
        result[vid] = {
            "titulo":           snippet.get("title", ""),
            "published_at":     snippet.get("publishedAt"),
            "duration_sec":     _iso_duration_to_sec(content.get("duration", "PT0S")),
            "views_total":      int(stats.get("viewCount", 0)),
            "likes":            int(stats.get("likeCount", 0)),
            "comments":         int(stats.get("commentCount", 0)),
            "peak_concurrent":  int(live.get("concurrentViewers", 0) or 0),
        }
    return result


# ─── YouTube Analytics API ───────────────────────────────────────────────────

def fetch_video_analytics(video_id: str, start_date: str, end_date: str, token: str, channel_id: str = "MINE") -> dict:
    """Retorna watch_time_min, avg_view_dur_sec, avg_view_pct, views_live, views_replay."""
    headers = {"Authorization": f"Bearer {token}"}
    base_params = {
        "ids":       f"channel=={channel_id}",
        "filters":   f"video=={video_id}",
        "startDate": start_date,
        "endDate":   end_date,
    }

    # Total: views, estimatedMinutesWatched, averageViewDuration
    r_total = requests.get(
        f"{YT_ANALYTICS_BASE}/reports",
        headers=headers,
        params={**base_params, "metrics": "views,estimatedMinutesWatched,averageViewDuration"},
        timeout=30,
    )
    r_total.raise_for_status()
    rows_total = r_total.json().get("rows", [])
    views_t = watch_min = avg_dur = 0
    if rows_total:
        views_t  = int(rows_total[0][0])
        watch_min = float(rows_total[0][1])
        avg_dur  = float(rows_total[0][2])

    avg_pct = (avg_dur / 3600 * 100) if avg_dur > 0 else 0  # será corrigido com duration_sec no upsert

    # Split live vs replay
    views_live = views_replay = 0
    try:
        r_split = requests.get(
            f"{YT_ANALYTICS_BASE}/reports",
            headers=headers,
            params={**base_params, "metrics": "views", "dimensions": "liveOrOnDemand"},
            timeout=30,
        )
        r_split.raise_for_status()
        for row in r_split.json().get("rows", []):
            mode, count = row[0], int(row[1])
            if mode == "LIVE":
                views_live = count
            elif mode == "ON_DEMAND":
                views_replay = count
    except Exception as e:
        logger.warning("Analytics split live/replay falhou para %s: %s", video_id, e)

    return {
        "views_total":     views_t,
        "watch_time_min":  round(watch_min, 1),
        "avg_view_dur_sec": round(avg_dur, 1),
        "avg_view_pct":    round(avg_pct, 1),
        "views_live":      views_live,
        "views_replay":    views_replay,
    }


# ─── Upsert ──────────────────────────────────────────────────────────────────

def upsert_rows(rows: list[dict]):
    engine = get_engine()
    sql = text(f"""
        INSERT INTO {TABLE} (
            launch_code, video_id, aula_num, titulo, published_at,
            duration_sec, views_total, views_live, views_replay,
            likes, comments, watch_time_min, avg_view_dur_sec,
            avg_view_pct, peak_concurrent, fetched_at
        ) VALUES (
            :launch_code, :video_id, :aula_num, :titulo, :published_at,
            :duration_sec, :views_total, :views_live, :views_replay,
            :likes, :comments, :watch_time_min, :avg_view_dur_sec,
            :avg_view_pct, :peak_concurrent, NOW()
        )
        ON CONFLICT (launch_code, video_id) DO UPDATE SET
            aula_num        = EXCLUDED.aula_num,
            titulo          = EXCLUDED.titulo,
            published_at    = EXCLUDED.published_at,
            duration_sec    = EXCLUDED.duration_sec,
            views_total     = EXCLUDED.views_total,
            views_live      = EXCLUDED.views_live,
            views_replay    = EXCLUDED.views_replay,
            likes           = EXCLUDED.likes,
            comments        = EXCLUDED.comments,
            watch_time_min  = EXCLUDED.watch_time_min,
            avg_view_dur_sec= EXCLUDED.avg_view_dur_sec,
            avg_view_pct    = EXCLUDED.avg_view_pct,
            peak_concurrent = EXCLUDED.peak_concurrent,
            fetched_at      = NOW()
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    logger.info("Upsert: %d aulas para %s", len(rows), rows[0]["launch_code"] if rows else "?")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(launch_code: str, start_date: str, end_date: str):
    aulas, channel_id = _load_videos(launch_code)
    if not aulas:
        logger.error("Nenhum video_id encontrado no YAML para %s", launch_code)
        logger.error("Adicione ao config/launches/%s.yaml:", launch_code.lower())
        logger.error("  youtube:")
        logger.error("    aulas:")
        logger.error('      - id: "VIDEO_ID"')
        logger.error('        label: "Aula 1 — Titulo"')
        return

    logger.info("Lançamento: %s | %d aulas | %s → %s | channel=%s", launch_code, len(aulas), start_date, end_date, channel_id)

    token = _get_access_token()
    video_ids = [a["id"] for a in aulas]

    logger.info("Buscando detalhes via YouTube Data API...")
    details = fetch_video_details(video_ids, token)

    rows = []
    for idx, aula in enumerate(aulas, start=1):
        vid = aula["id"]
        d = details.get(vid, {})
        label = aula.get("label", f"Aula {idx}")

        logger.info("Analytics para %s (%s)...", vid, label)
        try:
            analytics = fetch_video_analytics(vid, start_date, end_date, token, channel_id)
        except Exception as e:
            logger.warning("Analytics falhou para %s: %s — usando zeros", vid, e)
            analytics = {"views_total": 0, "watch_time_min": 0, "avg_view_dur_sec": 0,
                         "avg_view_pct": 0, "views_live": 0, "views_replay": 0}

        # Corrige avg_view_pct usando duration real
        dur = d.get("duration_sec") or 0
        avg_dur = analytics["avg_view_dur_sec"]
        avg_pct = round(avg_dur / dur * 100, 1) if dur > 0 and avg_dur > 0 else 0

        rows.append({
            "launch_code":     launch_code.upper(),
            "video_id":        vid,
            "aula_num":        idx,
            "titulo":          d.get("titulo") or label,
            "published_at":    d.get("published_at"),
            "duration_sec":    dur,
            "views_total":     analytics["views_total"] or d.get("views_total", 0),
            "views_live":      analytics["views_live"],
            "views_replay":    analytics["views_replay"],
            "likes":           d.get("likes", 0),
            "comments":        d.get("comments", 0),
            "watch_time_min":  analytics["watch_time_min"],
            "avg_view_dur_sec": avg_dur,
            "avg_view_pct":    avg_pct,
            "peak_concurrent": d.get("peak_concurrent", 0),
        })

    upsert_rows(rows)
    logger.info("Concluído: %d aulas salvas para %s", len(rows), launch_code)


def main():
    parser = argparse.ArgumentParser(description="ETL YouTube Analytics → Supabase")
    parser.add_argument("--launch-code", required=True, help="Ex: PES-MAI-26")
    parser.add_argument("--start-date", help="AAAA-MM-DD (padrão: data_inicio do lançamento)")
    parser.add_argument("--end-date",   help="AAAA-MM-DD (padrão: data_fim do lançamento)")
    args = parser.parse_args()

    # Se datas não fornecidas, tenta pegar do YAML
    start = args.start_date
    end   = args.end_date
    if not start or not end:
        slug = args.launch_code.lower().replace("_", "-")
        yaml_path = Path(__file__).parent.parent / "config" / "launches" / f"{slug}.yaml"
        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            dr = (data.get("launch") or {}).get("date_range") or {}
            start = start or str(dr.get("start", ""))
            end   = end   or str(dr.get("end", ""))
        if not start or not end:
            parser.error("--start-date e --end-date são obrigatórios (ou adicione date_range ao YAML)")

    run(args.launch_code.upper(), start, end)


if __name__ == "__main__":
    main()
