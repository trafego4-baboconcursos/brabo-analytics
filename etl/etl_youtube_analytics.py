"""
ETL: YouTube Data API + YouTube Analytics API → Supabase (youtube_aulas_stats)

Pré-requisito (execute uma vez):
    python etl/get_youtube_token.py

Uso:
    python etl/etl_youtube_analytics.py --ativos          # scheduler: lançamentos na semana da live
    python etl/etl_youtube_analytics.py --launch-code PES-MAI-26

Sem video IDs cadastrados, as aulas são as lives do canal dentro do evento do
wizard (`descobrir_aulas`). Cadastrar só quando o canal fez outra live na semana.
Os video IDs ficam no wizard (`youtube_aulas`) ou no YAML de config do lançamento:
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
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Um canal por expert: o prefixo do lançamento escolhe o token.
TOKEN_VAR_MAP = {"PI": "YOUTUBE_REFRESH_TOKEN_PI", "PES": "YOUTUBE_REFRESH_TOKEN_PES", "PBB": "YOUTUBE_REFRESH_TOKEN"}


# ─── Credenciais ─────────────────────────────────────────────────────────────

def _load_client_credentials(launch_code: str = "") -> tuple[str, str, str]:
    """Retorna (client_id, client_secret, refresh_token).

    Prioridade:
    1. YOUTUBE_REFRESH_TOKEN no .env + client_secrets.json  (token com escopo analytics)
    2. youtube/token_bb.json                                 (fallback — escopo force-ssl)
    3. GOOGLE_ADS_CLIENT_ID/SECRET + YOUTUBE_REFRESH_TOKEN env
    """
    import json
    secrets_path = Path(__file__).parent.parent / "youtube" / "client_secrets.json"

    # 1. .env tem refresh token dedicado ao analytics → usa com client_secrets.json
    prefix = launch_code.upper().split("-")[0] if launch_code else ""
    token_var = TOKEN_VAR_MAP.get(prefix, "YOUTUBE_REFRESH_TOKEN")
    rt_env = os.environ.get(token_var, "")
    if rt_env:
        logger.info("Usando %s para launch_code=%s", token_var, launch_code or "(nao definido)")
    else:
        rt_env = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
        if rt_env:
            logger.warning(
                "%s vazio para %s — caindo em YOUTUBE_REFRESH_TOKEN, que e de outro canal. "
                "O analytics vai voltar zerado. Rode get_youtube_token.py na conta certa.",
                token_var, launch_code or "(nao definido)",
            )
    # Servidor: client_secrets.json é gitignored e não vai no deploy, então o
    # par do app OAuth do YouTube vem do ambiente. Não é o GOOGLE_ADS_CLIENT_*:
    # os refresh tokens foram emitidos pelo app do YouTube e o do Ads devolve
    # `unauthorized_client`.
    cid_env = os.environ.get("YOUTUBE_CLIENT_ID", "")
    csecret_env = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    if rt_env and cid_env and csecret_env:
        return cid_env, csecret_env, rt_env

    if rt_env and secrets_path.exists():
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        installed = data.get("installed") or data.get("web") or {}
        cid = installed.get("client_id", "")
        csecret = installed.get("client_secret", "")
        if cid and csecret:
            logger.info("Credenciais de client_secrets.json + %s (escopo analytics)", token_var)
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

def _get_access_token(launch_code: str = "") -> str:
    try:
        import google.oauth2.credentials
        import google.auth.transport.requests
    except ImportError:
        sys.exit("Instale google-auth:  pip install google-auth")

    client_id, client_secret, refresh_token = _load_client_credentials(launch_code)
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


def _curva_de_rows(rows: list[list]) -> list[dict]:
    """[[posição_seg, média, pico], ...] → linhas de youtube_live_curva."""
    return [
        {"posicao_seg": int(pos), "media_simult": int(media or 0), "simultaneos": int(pico or 0)}
        for pos, media, pico in rows
    ]


def fetch_live_curve(video_id: str, start_date: str, end_date: str, token: str, channel_id: str = "MINE") -> list[dict]:
    """Simultâneos minuto a minuto de uma live — continua disponível depois que ela acaba.

    É a mesma série do `liveViewership_*.csv` do Studio: `simultaneos` = pico do
    minuto, `media_simult` = média do minuto. Chat e reações não existem aqui —
    vêm de `youtube_live_chat.py` (capturado durante a live) ou do CSV.
    """
    r = requests.get(
        f"{YT_ANALYTICS_BASE}/reports",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "ids":        f"channel=={channel_id}",
            "filters":    f"video=={video_id}",
            "startDate":  start_date,
            "endDate":    end_date,
            "dimensions": "livestreamPosition",
            "metrics":    "averageConcurrentViewers,peakConcurrentViewers",
            "sort":       "livestreamPosition",
        },
        timeout=30,
    )
    r.raise_for_status()
    return _curva_de_rows(r.json().get("rows") or [])


# ─── Descoberta das aulas ────────────────────────────────────────────────────

# Lives para quem já é aluno, que caem na mesma semana das aulas: "Dominando a
# Plataforma" (17h do dia da Aula 1 ou da 5) e as "Mentoria" do pós-venda.
_NAO_AULA = re.compile(r"dominando a plataforma|mentoria", re.IGNORECASE)


def _aulas_na_janela(broadcasts: list[dict], inicio: date, fim: date) -> list[dict]:
    """Lives que começaram de fato entre `inicio` e `fim` (data de Brasília), em ordem.

    A posição na lista é o número da aula — o mesmo critério serve para o ETL e
    para a captura do chat, então as duas gravam no mesmo `aula_num`. Live
    agendada que não começou não tem `actualStartTime` e fica de fora.
    """
    aulas = []
    for b in broadcasts:
        snip = b.get("snippet") or {}
        ini = snip.get("actualStartTime")
        if not ini:
            continue
        ini_dt = datetime.fromisoformat(ini.replace("Z", "+00:00"))
        if not (inicio <= ini_dt.astimezone(_TZ_BR).date() <= fim):
            continue
        if _NAO_AULA.search(snip.get("title", "")):
            continue
        aulas.append({
            "id":       b["id"],
            "label":    snip.get("title", ""),
            "inicio":   ini_dt,
            "no_ar":    (b.get("status") or {}).get("lifeCycleStatus") == "live",
            "chat_id":  snip.get("liveChatId"),
        })
    return sorted(aulas, key=lambda a: a["inicio"])


def descobrir_aulas(token: str, inicio: date, fim: date) -> list[dict]:
    """Aulas do lançamento = lives do canal do token dentro da janela do evento.

    Dispensa cadastrar `video_id`. Quando o canal faz outra live na semana do
    evento, ela entra na conta — aí vale cadastrar `youtube_aulas` no wizard,
    que tem prioridade (ver `_load_videos`).
    """
    broadcasts: list[dict] = []
    page = None
    for _ in range(10):  # 500 lives; a lista vem da mais recente para a mais antiga
        params = {"part": "snippet,status", "broadcastStatus": "all", "maxResults": 50}
        if page:
            params["pageToken"] = page
        r = requests.get(f"{YT_API_BASE}/liveBroadcasts", headers={"Authorization": f"Bearer {token}"},
                         params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        itens = data.get("items", [])
        broadcasts += itens
        page = data.get("nextPageToken")
        mais_antiga = min((i["snippet"].get("scheduledStartTime") or "9999" for i in itens), default="")
        if not page or mais_antiga[:10] < inicio.isoformat():
            break
    return _aulas_na_janela(broadcasts, inicio, fim)


# ─── Lançamentos na semana da live ───────────────────────────────────────────

def _janelas(cfg: dict, hoje: date) -> tuple[tuple[date, date], tuple[date, date]] | None:
    """(janela das aulas, período de atualização) se `hoje` cai no período, senão None.

    A atualização vai do início das aulas até o carrinho fechar, porque o replay
    continua somando views enquanto a venda está aberta.
    """
    aulas = _janela_aulas(cfg)
    if not aulas:
        return None
    ev_ini, ev_fim = aulas
    fim = _to_date(cfg.get("carrinho_end_date")) or ev_fim + timedelta(days=3)
    fim = max(fim, ev_fim)
    if not (ev_ini <= hoje <= fim):
        return None
    return (ev_ini, ev_fim), (ev_ini, fim)


def _janela_aulas(cfg: dict) -> tuple[date, date] | None:
    """Dias em que as lives do lançamento podem cair.

    Padrão de todos os lançamentos de 2025–26: Aulas 1–4 de segunda a quinta,
    a última no dia da abertura do carrinho, e uma Aula 5 ("Como revisar…") na
    segunda seguinte. Daí os 4 dias depois do fim do evento — a 5ª do PI-ABR-26
    caiu fora da janela do wizard. Sem evento no wizard (lançamentos antigos),
    a semana vem da abertura do carrinho.
    """
    ev_ini = _to_date(cfg.get("evento_start_date"))
    ev_fim = _to_date(cfg.get("evento_end_date"))
    abertura = _to_date(cfg.get("abertura_oficial_carrinho")) or _to_date(cfg.get("carrinho_start_date"))
    if ev_ini:
        ultimo = ev_fim or ev_ini + timedelta(days=3)
    elif abertura:
        ev_ini, ultimo = abertura - timedelta(days=6), abertura
    else:
        return None
    return ev_ini, max(ultimo, ev_ini) + timedelta(days=4)


def _to_date(val) -> date | None:
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def lancamentos_na_janela(hoje: date) -> list[tuple[str, tuple[date, date], tuple[date, date]]]:
    """[(código, janela das aulas, período de atualização)] dos lançamentos com live agora.

    Só os prefixos que têm canal próprio (TOKEN_VAR_MAP): a Black e o perpétuo
    não têm aula num canal único. Sem data de evento nem de carrinho no wizard
    o lançamento não entra — e isso é avisado, para não sumir em silêncio.
    """
    from db import get_users_engine
    with get_users_engine().connect() as conn:
        cfgs = conn.execute(text("""
            SELECT lancamento_codigo, evento_start_date, evento_end_date, carrinho_start_date,
                   abertura_oficial_carrinho, carrinho_end_date
            FROM launch_config
        """)).mappings().all()

    escolhidos = []
    for cfg in cfgs:
        code = (cfg["lancamento_codigo"] or "").upper()
        if code.split("-")[0] not in TOKEN_VAR_MAP:
            continue
        if not _janela_aulas(dict(cfg)):
            logger.warning("%s sem data de evento nem de carrinho no wizard — aulas do YouTube não serão buscadas.",
                           code)
            continue
        jan = _janelas(dict(cfg), hoje)
        if jan:
            escolhidos.append((code, *jan))
    return escolhidos


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
            -- concurrentViewers da Data API só existe com a live no ar: depois
            -- vem 0, e 0 não pode apagar o pico que a curva ou o CSV gravaram.
            peak_concurrent = COALESCE(NULLIF(EXCLUDED.peak_concurrent, 0), {TABLE}.peak_concurrent),
            fetched_at      = NOW()
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    logger.info("Upsert: %d aulas para %s", len(rows), rows[0]["launch_code"] if rows else "?")


def adotar_linhas_manuais(launch_code: str, video_por_aula: dict[int, str]) -> None:
    """Dá o `video_id` real à linha que o CSV gravou como `manual-aula-N`.

    Sem isso a aula vira dois cartões na página (a linha do CSV e a da API,
    com o mesmo `aula_num`). Renomeando, o upsert seguinte cai na mesma linha e
    só atualiza o que a API mede — `viewers_fim`, `chat_msgs` e `reacoes` do
    Studio ficam.
    """
    sql = text(f"""
        UPDATE {TABLE} m SET video_id = :vid
        WHERE m.launch_code = :code AND m.video_id = :manual
          AND NOT EXISTS (SELECT 1 FROM {TABLE} a WHERE a.launch_code = :code AND a.video_id = :vid)
    """)
    with get_engine().begin() as conn:
        for num, vid in video_por_aula.items():
            n = conn.execute(sql, {"code": launch_code, "vid": vid, "manual": f"manual-aula-{num}"}).rowcount
            if n:
                logger.info("%s Aula %d: linha do CSV passa a usar o video_id %s", launch_code, num, vid)


def upsert_curva(launch_code: str, aula_num: int, pontos: list[dict]) -> None:
    """Grava a curva de simultâneos sem tocar em chat/reações/envolvimentos.

    Essas colunas vêm de outra fonte (captura ao vivo ou CSV do Studio) e
    sobrescrevê-las com 0 apagaria o único registro que existe delas.
    """
    if not pontos:
        return
    sql = text("""
        INSERT INTO youtube_live_curva (launch_code, aula_num, posicao_seg, simultaneos, media_simult)
        VALUES (:launch_code, :aula_num, :posicao_seg, :simultaneos, :media_simult)
        ON CONFLICT (launch_code, aula_num, posicao_seg) DO UPDATE SET
            simultaneos  = EXCLUDED.simultaneos,
            media_simult = EXCLUDED.media_simult
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, [{"launch_code": launch_code, "aula_num": aula_num, **p} for p in pontos])


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(launch_code: str, start_date: str, end_date: str, janela_aulas: tuple[date, date] | None = None) -> bool:
    """Totais + curva de cada aula. Devolve False só em falha (credencial, API).

    Sem `youtube_aulas` cadastrado, as aulas são descobertas no canal dentro de
    `janela_aulas` (por padrão, o evento do wizard).
    """
    aulas, channel_id = _load_videos(launch_code)
    token = _get_access_token(launch_code)

    if not aulas:
        if janela_aulas is None:
            from frontend.db_readers.launches import read_launch_config
            janela_aulas = _janela_aulas(read_launch_config(launch_code) or {})
        if janela_aulas is None:
            logger.error("%s: sem youtube_aulas e sem evento_start_date no wizard — não há como achar as aulas.",
                         launch_code)
            return False
        aulas = descobrir_aulas(token, *janela_aulas)
        logger.info("%s: %d live(s) no canal entre %s e %s", launch_code, len(aulas), *janela_aulas)
        if not aulas:
            return True  # semana do evento antes da Aula 1: nada a buscar ainda

    logger.info("Lançamento: %s | %d aulas | %s -> %s | channel=%s", launch_code, len(aulas), start_date, end_date, channel_id)

    video_ids = [a["id"] for a in aulas]

    logger.info("Buscando detalhes via YouTube Data API...")
    details = fetch_video_details(video_ids, token)

    rows = []
    curvas: dict[int, list[dict]] = {}
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

        # Vídeo que não foi live devolve 0 linhas — não é erro.
        try:
            curvas[idx] = fetch_live_curve(vid, start_date, end_date, token, channel_id)
        except Exception as e:
            logger.warning("Curva da live falhou para %s: %s", vid, e)
            curvas[idx] = []

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
            "peak_concurrent": max((p["simultaneos"] for p in curvas[idx]), default=0)
                               or d.get("peak_concurrent", 0),
        })

    adotar_linhas_manuais(launch_code.upper(), {r["aula_num"]: r["video_id"] for r in rows})
    upsert_rows(rows)
    for idx, pontos in curvas.items():
        upsert_curva(launch_code.upper(), idx, pontos)
    logger.info("Concluído: %d aulas salvas para %s (%d com curva)", len(rows), launch_code,
                sum(1 for p in curvas.values() if p))
    return True


def run_ativos(hoje: date | None = None) -> int:
    """Modo do scheduler: todo lançamento entre a Aula 1 e o fim do carrinho."""
    hoje = hoje or datetime.now(_TZ_BR).date()
    lancamentos = lancamentos_na_janela(hoje)
    if not lancamentos:
        logger.info("Nenhum lançamento na semana da live (%s).", hoje)
        return 0
    falhas = []
    for code, janela_aulas, (ini, fim) in lancamentos:
        try:
            if not run(code, ini.isoformat(), min(hoje, fim).isoformat(), janela_aulas):
                falhas.append(code)
        except Exception as e:
            logger.error("%s: YouTube falhou: %s", code, e)
            falhas.append(code)
    if falhas:
        logger.error("YouTube falhou para: %s", ", ".join(falhas))
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="ETL YouTube Analytics → Supabase")
    parser.add_argument("--launch-code", help="Ex: PES-MAI-26")
    parser.add_argument("--ativos", action="store_true",
                        help="Todo lançamento entre o início do evento e o fim do carrinho (modo do scheduler)")
    parser.add_argument("--start-date", help="AAAA-MM-DD (padrão: data_inicio do lançamento)")
    parser.add_argument("--end-date",   help="AAAA-MM-DD (padrão: data_fim do lançamento)")
    args = parser.parse_args()

    if args.ativos:
        sys.exit(run_ativos())
    if not args.launch_code:
        parser.error("--launch-code ou --ativos")

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

    sys.exit(0 if run(args.launch_code.upper(), start, end) else 1)


if __name__ == "__main__":
    main()
