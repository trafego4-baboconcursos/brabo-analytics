"""
frontend/db_readers/launches.py — Configuração e utilitários de lançamentos.

Nota: discover_launches e get_launch ainda estão em database_reader.py pois
dependem de _resolve_typeform_ids (typeform). Serão movidos quando typeform.py
for extraído.
"""
from __future__ import annotations

import os
import json as _json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
from sqlalchemy import text
from logger import get_logger
from frontend.db import _get_engine, _get_users_engine
from frontend.models import Launch
from src.constants import PRODUCT_BY_PREFIX, LAUNCH_ACCENT, LAUNCH_SHORT, LAUNCH_NAMES

logger = get_logger("db")

_ETL_SOURCES = ("meta_ads", "google_ads", "active_campaign")
# "typeform" retirado em 2026-08 (conta cancelada, etl_typeform.py não roda
# mais automaticamente — ver frontend/db_readers/typeform.py); mantê-lo aqui
# faria o alerta de "dados desatualizados" disparar pra sempre sem solução.

_drive_cache: dict[str, tuple[float, dict]] = {}
_DRIVE_CACHE_TTL = 300  # 5 minutos


def autodetect_launch_data(launch_code: str) -> dict:
    """
    Infere metas e filtros a partir dos dados reais já no banco.
    Retorna dict com chaves: meta_leads, meta_investimento_captacao, filtro_pre_quali.
    Nunca lança exceção — retorna {} se o banco estiver indisponível.
    """
    result: dict = {}
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM leads WHERE lancamento_codigo = :code"),
                {"code": launch_code},
            ).fetchone()
            if row and row[0]:
                result["meta_leads"] = int(row[0])

            meta_spend = conn.execute(
                text("SELECT COALESCE(SUM(spend),0) FROM meta_ads_daily WHERE lancamento_codigo = :code"),
                {"code": launch_code},
            ).fetchone()
            google_spend = conn.execute(
                text("SELECT COALESCE(SUM(cost),0) FROM google_ads_daily WHERE lancamento_codigo = :code"),
                {"code": launch_code},
            ).fetchone()
            total_invest = (float(meta_spend[0]) if meta_spend else 0.0) + (float(google_spend[0]) if google_spend else 0.0)
            if total_invest > 0:
                result["meta_investimento_captacao"] = round(total_invest, 2)

            name_rows = list(conn.execute(
                text("SELECT DISTINCT campaign_name FROM meta_ads_daily WHERE lancamento_codigo = :code AND campaign_name IS NOT NULL LIMIT 300"),
                {"code": launch_code},
            ).fetchall()) + list(conn.execute(
                text("SELECT DISTINCT campaign_name FROM google_ads_daily WHERE lancamento_codigo = :code AND campaign_name IS NOT NULL LIMIT 300"),
                {"code": launch_code},
            ).fetchall())

            preq_terms = ["pré-qualificação", "pre-qualificacao", "pré qualificação", "prequalificação", "preq"]
            for (name,) in name_rows:
                if not name:
                    continue
                nl = name.lower().replace("-", " ").replace("_", " ")
                for t in preq_terms:
                    if t.replace("-", " ").replace("_", " ") in nl:
                        result.setdefault("filtro_pre_quali", t)
                        break
                if "filtro_pre_quali" in result:
                    break
    except Exception:
        logger.debug("autodetect_launch_data: DB indisponível para %s", launch_code)
    return result


def read_launch_config(launch_code: str) -> dict:
    """Retorna a config do lançamento ou um dict vazio se não existir."""
    try:
        with _get_users_engine().connect() as conn:
            row = conn.execute(
                text("SELECT * FROM launch_config WHERE lancamento_codigo = :code"),
                {"code": launch_code},
            ).fetchone()
    except Exception as e:
        logger.warning("read_launch_config: DB indisponível para %s — %s", launch_code, e)
        return {}
    if not row:
        return {}
    d = dict(row._mapping)
    for key in ("captacao_start_date", "captacao_end_date", "carrinho_start_date", "carrinho_end_date",
                "pre_quali_start_date", "pre_quali_end_date", "abertura_oficial_carrinho",
                "depoimento_start_date", "depoimento_end_date", "aulas_start_date", "aulas_end_date"):
        if d.get(key):
            d[key] = str(d[key])
    for key in ("meta_ad_account_ids", "google_ad_account_ids", "hotmart_produto_ids", "tmb_produto_ids"):
        if d.get(key) is None:
            d[key] = []
    if d.get("outras_temperaturas") is None:
        d["outras_temperaturas"] = []
    if d.get("youtube_aulas") is None:
        d["youtube_aulas"] = []
    elif isinstance(d["youtube_aulas"], str):
        import json as _j
        try:
            d["youtube_aulas"] = _j.loads(d["youtube_aulas"])
        except Exception:
            d["youtube_aulas"] = []
    if d.get("etapas") is None:
        d["etapas"] = []
    elif isinstance(d["etapas"], str):
        import json as _j
        try:
            d["etapas"] = _j.loads(d["etapas"])
        except Exception:
            d["etapas"] = []
    if d.get("bonus_oferta") is None:
        d["bonus_oferta"] = []
    elif isinstance(d["bonus_oferta"], str):
        import json as _j
        try:
            d["bonus_oferta"] = _j.loads(d["bonus_oferta"])
        except Exception:
            d["bonus_oferta"] = []
    return d


def save_launch_config(launch_code: str, config: dict) -> None:
    """Upsert da configuração do lançamento na tabela launch_config."""
    upsert_sql = text("""
        INSERT INTO launch_config (
            lancamento_codigo,
            pre_quali_start_date, pre_quali_end_date, meta_leads_pre_quali, meta_investimento_pre_quali,
            captacao_start_date, captacao_end_date, meta_leads,
            meta_investimento_captacao, meta_ad_account_ids, google_ad_account_ids,
            filtro_lancamento, filtro_captacao, filtro_pre_quali,
            filtro_quente, filtro_quente_scope,
            filtro_frio, filtro_frio_scope,
            outras_temperaturas,
            carrinho_start_date, carrinho_end_date, abertura_oficial_carrinho,
            depoimento_start_date, depoimento_end_date, aulas_start_date, aulas_end_date,
            hotmart_produto_ids, tmb_produto_ids,
            drive_folder_url,
            youtube_aulas,
            etapas,
            produto_nome, produto_preco_vista, produto_preco_parcelado, bonus_oferta,
            updated_at
        ) VALUES (
            :lancamento_codigo,
            :pre_quali_start_date, :pre_quali_end_date, :meta_leads_pre_quali, :meta_investimento_pre_quali,
            :captacao_start_date, :captacao_end_date, :meta_leads,
            :meta_investimento_captacao, :meta_ad_account_ids, :google_ad_account_ids,
            :filtro_lancamento, :filtro_captacao, :filtro_pre_quali,
            :filtro_quente, :filtro_quente_scope,
            :filtro_frio, :filtro_frio_scope,
            :outras_temperaturas,
            :carrinho_start_date, :carrinho_end_date, :abertura_oficial_carrinho,
            :depoimento_start_date, :depoimento_end_date, :aulas_start_date, :aulas_end_date,
            :hotmart_produto_ids, :tmb_produto_ids,
            :drive_folder_url,
            :youtube_aulas,
            :etapas,
            :produto_nome, :produto_preco_vista, :produto_preco_parcelado, :bonus_oferta,
            NOW()
        )
        ON CONFLICT (lancamento_codigo) DO UPDATE SET
            pre_quali_start_date       = EXCLUDED.pre_quali_start_date,
            pre_quali_end_date         = EXCLUDED.pre_quali_end_date,
            meta_leads_pre_quali       = EXCLUDED.meta_leads_pre_quali,
            meta_investimento_pre_quali= EXCLUDED.meta_investimento_pre_quali,
            captacao_start_date        = EXCLUDED.captacao_start_date,
            captacao_end_date          = EXCLUDED.captacao_end_date,
            meta_leads                 = EXCLUDED.meta_leads,
            meta_investimento_captacao = EXCLUDED.meta_investimento_captacao,
            meta_ad_account_ids        = EXCLUDED.meta_ad_account_ids,
            google_ad_account_ids      = EXCLUDED.google_ad_account_ids,
            filtro_lancamento          = EXCLUDED.filtro_lancamento,
            filtro_captacao            = EXCLUDED.filtro_captacao,
            filtro_pre_quali           = EXCLUDED.filtro_pre_quali,
            filtro_quente              = EXCLUDED.filtro_quente,
            filtro_quente_scope        = EXCLUDED.filtro_quente_scope,
            filtro_frio                = EXCLUDED.filtro_frio,
            filtro_frio_scope          = EXCLUDED.filtro_frio_scope,
            outras_temperaturas        = EXCLUDED.outras_temperaturas,
            carrinho_start_date        = EXCLUDED.carrinho_start_date,
            carrinho_end_date          = EXCLUDED.carrinho_end_date,
            abertura_oficial_carrinho  = EXCLUDED.abertura_oficial_carrinho,
            depoimento_start_date      = EXCLUDED.depoimento_start_date,
            depoimento_end_date        = EXCLUDED.depoimento_end_date,
            aulas_start_date           = EXCLUDED.aulas_start_date,
            aulas_end_date             = EXCLUDED.aulas_end_date,
            hotmart_produto_ids        = EXCLUDED.hotmart_produto_ids,
            tmb_produto_ids            = EXCLUDED.tmb_produto_ids,
            drive_folder_url           = EXCLUDED.drive_folder_url,
            youtube_aulas              = EXCLUDED.youtube_aulas,
            etapas                     = EXCLUDED.etapas,
            produto_nome               = EXCLUDED.produto_nome,
            produto_preco_vista        = EXCLUDED.produto_preco_vista,
            produto_preco_parcelado    = EXCLUDED.produto_preco_parcelado,
            bonus_oferta               = EXCLUDED.bonus_oferta,
            updated_at                 = NOW()
    """)

    def _or_none(val):
        return val if val not in ("", None) else None

    def _or_zero(val):
        try:
            return float(val) if val not in ("", None) else None
        except (ValueError, TypeError):
            return None

    def _or_int(val):
        try:
            return int(val) if val not in ("", None) else None
        except (ValueError, TypeError):
            return None

    params = {
        "lancamento_codigo":              launch_code,
        "pre_quali_start_date":           _or_none(config.get("pre_quali_start_date")),
        "pre_quali_end_date":             _or_none(config.get("pre_quali_end_date")),
        "meta_leads_pre_quali":           _or_int(config.get("meta_leads_pre_quali")),
        "meta_investimento_pre_quali":    _or_zero(config.get("meta_investimento_pre_quali")),
        "captacao_start_date":            _or_none(config.get("captacao_start_date")),
        "captacao_end_date":              _or_none(config.get("captacao_end_date")),
        "meta_leads":                     _or_int(config.get("meta_leads")),
        "meta_investimento_captacao":     _or_zero(config.get("meta_investimento_captacao")),
        "meta_ad_account_ids":            config.get("meta_ad_account_ids") or [],
        "google_ad_account_ids":          config.get("google_ad_account_ids") or [],
        "filtro_lancamento":              _or_none(config.get("filtro_lancamento")),
        "filtro_captacao":                _or_none(config.get("filtro_captacao")),
        "filtro_pre_quali":               _or_none(config.get("filtro_pre_quali")),
        "filtro_quente":                  _or_none(config.get("filtro_quente")),
        "filtro_quente_scope":            config.get("filtro_quente_scope") or "campanhas",
        "filtro_frio":                    _or_none(config.get("filtro_frio")),
        "filtro_frio_scope":              config.get("filtro_frio_scope") or "campanhas",
        "outras_temperaturas":            _json.dumps(config.get("outras_temperaturas") or []),
        "carrinho_start_date":            _or_none(config.get("carrinho_start_date")),
        "carrinho_end_date":              _or_none(config.get("carrinho_end_date")),
        "abertura_oficial_carrinho":      _or_none(config.get("abertura_oficial_carrinho")),
        "depoimento_start_date":          _or_none(config.get("depoimento_start_date")),
        "depoimento_end_date":            _or_none(config.get("depoimento_end_date")),
        "aulas_start_date":               _or_none(config.get("aulas_start_date")),
        "aulas_end_date":                 _or_none(config.get("aulas_end_date")),
        "hotmart_produto_ids":            config.get("hotmart_produto_ids") or [],
        "tmb_produto_ids":                config.get("tmb_produto_ids") or [],
        "drive_folder_url":               _or_none(config.get("drive_folder_url")),
        "youtube_aulas":                  _json.dumps(config.get("youtube_aulas") or []),
        "etapas":                         _json.dumps(config.get("etapas") or []),
        "produto_nome":                   _or_none(config.get("produto_nome")),
        "produto_preco_vista":            _or_zero(config.get("produto_preco_vista")),
        "produto_preco_parcelado":        _or_zero(config.get("produto_preco_parcelado")),
        "bonus_oferta":                   _json.dumps([b for b in (config.get("bonus_oferta") or []) if b]),
    }

    with _get_users_engine().connect() as conn:
        conn.execute(upsert_sql, params)
        conn.commit()

    sync_launch_dates(launch_code, config)


def create_launch(code: str, nome: str, projeto: str, data_inicio: str, data_fim: str) -> None:
    """Registra um novo lançamento em dim_lancamentos (analytics DB) — passo
    necessário antes do wizard de Configurações aceitar o código, já que
    get_launches()/discover_launches só enxerga códigos cadastrados lá."""
    with _get_engine().connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM dim_lancamentos WHERE codigo = :code"),
            {"code": code},
        ).fetchone()
        if exists:
            raise ValueError(f"O lançamento {code} já está cadastrado.")
        conn.execute(
            text("""
                INSERT INTO dim_lancamentos (codigo, nome, projeto, data_inicio, data_fim, updated_at)
                VALUES (:codigo, :nome, :projeto, :data_inicio, :data_fim, NOW())
            """),
            {"codigo": code, "nome": nome, "projeto": projeto,
             "data_inicio": data_inicio, "data_fim": data_fim},
        )
        conn.commit()


def sync_launch_dates(code: str, config: dict) -> None:
    """Mantém dim_lancamentos.data_inicio/data_fim alinhados com as datas
    reais cadastradas no launch_config (usadas por find_previous_launch para
    achar o 'lançamento anterior' do mesmo produto) — evita que essas datas
    fiquem desatualizadas conforme o calendário de cada lançamento é ajustado."""
    date_keys = (
        "pre_quali_start_date", "captacao_start_date", "depoimento_start_date",
        "aulas_start_date", "carrinho_start_date",
        "pre_quali_end_date", "captacao_end_date", "depoimento_end_date",
        "aulas_end_date", "carrinho_end_date",
    )
    dates = [d for k in date_keys if (d := config.get(k))]
    if not dates:
        return
    try:
        with _get_engine().connect() as conn:
            conn.execute(
                text("""
                    UPDATE dim_lancamentos
                    SET data_inicio = :d_min,
                        data_fim    = :d_max,
                        updated_at  = NOW()
                    WHERE codigo = :code
                """),
                {"code": code, "d_min": min(dates), "d_max": max(dates)},
            )
            conn.commit()
    except Exception:
        logger.exception("sync_launch_dates: falha ao sincronizar dim_lancamentos para %s", code)


def get_platform_thumbnails(launch_code: str) -> dict[str, dict]:
    """Thumbnails buscadas direto da API do Meta (tabela ad_creatives).
    Quando os bytes estão persistidos (migration 006), serve pelo endpoint
    local /api/meta-creative — as URLs do CDN do Facebook são assinadas e
    expiram em poucas semanas; a URL crua fica só como fallback de transição
    pra linhas antigas que ainda não têm bytes."""
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT ad_code, ad_name, thumbnail_url, image_url,
                       (thumb_data IS NOT NULL) AS has_thumb,
                       (image_data IS NOT NULL) AS has_image
                FROM ad_creatives
                WHERE lancamento_codigo = :code AND thumbnail_url IS NOT NULL
            """),
            {"code": launch_code},
        ).fetchall()
    thumbnails: dict[str, dict] = {}
    for ad_code, ad_name, thumbnail_url, image_url, has_thumb, has_image in rows:
        thumb = f"/api/meta-creative/{launch_code}/{ad_code}/thumb" if has_thumb else thumbnail_url
        if has_image:
            preview = f"/api/meta-creative/{launch_code}/{ad_code}/image"
        elif has_thumb and not image_url:
            preview = thumb
        else:
            preview = image_url or thumbnail_url
        thumbnails[ad_code] = {
            "thumb": thumb,
            "preview": preview,
            "name": ad_name,
        }
    return thumbnails


def get_drive_thumbnails(launch_code: str, subfolder: str = "captação") -> dict[str, dict]:
    """
    Lista arquivos do Google Drive na pasta configurada para o lançamento,
    extrai código AD (ex: AD054) do nome do arquivo e retorna {ad_code: thumbnail_url}.
    Resultado é cacheado por 5 minutos.
    """
    import time as _time
    import re as _re
    cache_key = f"{launch_code}:{subfolder}"
    cached = _drive_cache.get(cache_key)
    if cached and (_time.time() - cached[0]) < _DRIVE_CACHE_TTL:
        return cached[1]

    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    cfg = read_launch_config(launch_code)
    folder_url = cfg.get("drive_folder_url") or ""
    if not folder_url:
        return {}

    m = _re.search(r"/folders/([a-zA-Z0-9_-]+)", folder_url)
    if not m:
        return {}
    root_folder_id = m.group(1)

    # Em produção (Docker) a pasta json/ não vai na imagem (.dockerignore) —
    # a credencial da service account entra pela env GOOGLE_SERVICE_ACCOUNT_JSON
    # (conteúdo do arquivo JSON). Localmente, cai no arquivo da pasta json/.
    _SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        import json as _json
        creds = service_account.Credentials.from_service_account_info(
            _json.loads(sa_json), scopes=_SCOPES
        )
    else:
        KEY_FILE = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "json",
                         "uplifted-kit-499213-d8-6c09276f2753.json")
        )
        creds = service_account.Credentials.from_service_account_file(
            KEY_FILE, scopes=_SCOPES
        )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_files(folder_id: str) -> list[dict]:
        results = []
        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, thumbnailLink)",
                pageToken=page_token,
                pageSize=200,
            ).execute()
            results.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    root_items = list_files(root_folder_id)
    target_folder_id = root_folder_id
    if subfolder:
        subfolder_lower = subfolder.lower().strip()
        for item in root_items:
            if item["mimeType"] == "application/vnd.google-apps.folder":
                if item["name"].lower().strip() == subfolder_lower:
                    target_folder_id = item["id"]
                    break

    def _variant_num(name: str) -> int:
        """Número de variante/card no nome do arquivo (ex: '... V3.png' -> 3). Um
        arquivo sem número (a "capa" de uma pasta de carrossel, ex: 'AD322 - ....png')
        retorna 0 e vence qualquer variante numerada."""
        m = _re.search(r"\bV(\d+)\b", name, flags=_re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = _re.search(r"(\d+)\s*\.\w+$", name)
        if m:
            return int(m.group(1))
        return 0

    items = list_files(target_folder_id)
    # Carrossel = pasta no Drive. Entra um nível para achar a imagem/vídeo capa
    # (o arquivo que já carrega o código AD, ex: 'AD322 - Carrossel ... .png');
    # ignora docs/prompts de texto dentro da pasta.
    candidates: list[dict] = []
    for f in items:
        if f["mimeType"] == "application/vnd.google-apps.folder":
            for inner in list_files(f["id"]):
                if inner["mimeType"].startswith("image/") or inner["mimeType"].startswith("video/"):
                    candidates.append(inner)
        else:
            candidates.append(f)

    thumbnails: dict[str, dict] = {}
    best_variant: dict[str, int] = {}
    ad_pattern = _re.compile(r"\bAD\d+\b", _re.IGNORECASE)
    best_file: dict[str, dict] = {}
    for f in candidates:
        match = ad_pattern.search(f["name"])
        if not match:
            continue
        ad_code = match.group(0).upper()
        variant = _variant_num(f["name"])
        if ad_code in best_variant and variant >= best_variant[ad_code]:
            continue
        best_variant[ad_code] = variant
        best_file[ad_code] = f
        thumbnails[ad_code] = {
            "thumb": f"/api/drive-thumb/{f['id']}",
            "preview": f"https://drive.google.com/file/d/{f['id']}/preview",
            "name": f["name"],
        }

    _ensure_thumbnails_stored(launch_code, best_file)
    stored_ad_codes = _stored_thumbnail_ad_codes(launch_code)
    for ad_code in thumbnails:
        if ad_code in stored_ad_codes:
            thumbnails[ad_code]["thumb"] = f"/api/creative-image/{launch_code}/{ad_code}"

    _drive_cache[cache_key] = (_time.time(), thumbnails)
    return thumbnails


def _stored_thumbnail_ad_codes(launch_code: str) -> set[str]:
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT ad_code FROM creative_thumbnails WHERE lancamento_codigo = :code"),
            {"code": launch_code},
        ).fetchall()
    return {r[0] for r in rows}


def _ensure_thumbnails_stored(launch_code: str, best_file: dict[str, dict]) -> None:
    """
    Baixa e grava no banco (bytea) a imagem de thumbnail (thumbnailLink do Drive)
    de cada ad_code que ainda não tem cópia persistida. Idempotente: uma vez
    guardada, nunca mais depende do arquivo continuar existindo no Drive.
    """
    import requests

    engine = _get_engine()
    with engine.connect() as conn:
        already_stored = {
            r[0] for r in conn.execute(
                text("SELECT ad_code FROM creative_thumbnails WHERE lancamento_codigo = :code"),
                {"code": launch_code},
            ).fetchall()
        }

    upsert_sql = text("""
        INSERT INTO creative_thumbnails (lancamento_codigo, ad_code, content_type, image_data, drive_file_id, updated_at)
        VALUES (:code, :ad_code, :content_type, :image_data, :file_id, NOW())
        ON CONFLICT (lancamento_codigo, ad_code) DO UPDATE SET
            content_type = EXCLUDED.content_type,
            image_data   = EXCLUDED.image_data,
            drive_file_id = EXCLUDED.drive_file_id,
            updated_at   = NOW()
    """)

    for ad_code, f in best_file.items():
        if ad_code in already_stored:
            continue
        thumbnail_link = f.get("thumbnailLink")
        if not thumbnail_link:
            continue
        try:
            resp = requests.get(thumbnail_link, timeout=15)
            resp.raise_for_status()
        except Exception:
            logger.warning("Falha ao baixar thumbnail do Drive para %s/%s", launch_code, ad_code)
            continue
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        with engine.begin() as conn:
            conn.execute(upsert_sql, {
                "code": launch_code,
                "ad_code": ad_code,
                "content_type": content_type,
                "image_data": resp.content,
                "file_id": f["id"],
            })


def count_campaigns_for_filter(launch_code: str, term: str) -> dict:
    """Conta campanhas distintas do Meta que contenham o termo informado."""
    engine = _get_engine()
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(DISTINCT campaign_name) FROM meta_ads_daily WHERE lancamento_codigo = :code"),
            {"code": launch_code},
        ).scalar() or 0

        matched = 0
        if term:
            matched = conn.execute(
                text("""
                    SELECT COUNT(DISTINCT campaign_name)
                    FROM meta_ads_daily
                    WHERE lancamento_codigo = :code
                      AND LOWER(campaign_name) LIKE LOWER(:term)
                """),
                {"code": launch_code, "term": f"%{term}%"},
            ).scalar() or 0

    return {"total": int(total), "matched": int(matched)}


def get_etl_status() -> dict[str, dict]:
    """
    Retorna o status da última execução bem-sucedida de cada fonte ETL.
    Resultado: dict keyed por source com hours_ago, last_ok_at, rows_upserted.
    """
    result: dict[str, dict] = {s: {"status": "unknown", "hours_ago": None, "last_ok_at": None} for s in _ETL_SOURCES}
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT ON (source)
                    source, finished_at, rows_upserted
                FROM etl_runs
                WHERE status = 'ok'
                ORDER BY source, finished_at DESC
            """)).fetchall()
        now = datetime.now(timezone.utc)
        for row in rows:
            source, finished_at, rows_upserted = row
            if source not in result or finished_at is None:
                continue
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=timezone.utc)
            hours_ago = (now - finished_at).total_seconds() / 3600
            local_dt = finished_at.astimezone(ZoneInfo("America/Sao_Paulo"))
            result[source] = {
                "status": "ok",
                "hours_ago": round(hours_ago, 1),
                "last_ok_at": finished_at,
                "last_ok_at_local": local_dt.strftime("%d/%m %H:%M"),
                "rows_upserted": rows_upserted,
            }
    except Exception:
        logger.debug("etl_runs indisponível (tabela ainda não existe ou DB offline)")
    return result


def discover_launches(analises_dir: Any = None) -> list[Launch]:
    """Busca os lançamentos cadastrados na dim_lancamentos e retorna com as flags de dados."""
    from frontend.db_readers.typeform import _resolve_typeform_ids  # noqa: PLC0415

    launches: list[Launch] = []

    try:
        with _get_users_engine().connect() as ops_conn:
            hm_projects = {r[0] for r in ops_conn.execute(text(
                "SELECT DISTINCT CASE WHEN produto ILIKE '%inss%' THEN 'INSS'"
                " WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'"
                " WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'"
                " ELSE 'OUTRO' END FROM hotmart_clean_oficial"
            )).fetchall()}
            tmb_projects = {r[0] for r in ops_conn.execute(text(
                "SELECT DISTINCT CASE WHEN produto ILIKE '%inss%' THEN 'INSS'"
                " WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'"
                " WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'"
                " ELSE 'OUTRO' END FROM tmb_clean_oficial"
            )).fetchall()}
    except Exception:
        logger.exception("Falha ao carregar projetos Hotmart/TMB; usando conjuntos vazios")
        hm_projects, tmb_projects = set(), set()

    query = text("""
        SELECT codigo, nome, projeto, data_inicio, data_fim
        FROM dim_lancamentos
        ORDER BY data_inicio ASC
    """)

    # DISTINCT de lancamento_codigo em leads via loose index scan (CTE recursiva):
    # com 1,2M+ linhas, tanto EXISTS por lançamento quanto SELECT DISTINCT viram
    # scan de ~4s — a CTE faz ~1 sonda no índice por código distinto (<50ms).
    leads_codes_sql = text("""
        WITH RECURSIVE t AS (
          (SELECT lancamento_codigo FROM leads ORDER BY lancamento_codigo LIMIT 1)
          UNION ALL
          SELECT (SELECT l.lancamento_codigo FROM leads l
                  WHERE l.lancamento_codigo > t.lancamento_codigo
                  ORDER BY l.lancamento_codigo LIMIT 1)
          FROM t WHERE t.lancamento_codigo IS NOT NULL
        )
        SELECT lancamento_codigo FROM t WHERE lancamento_codigo IS NOT NULL
    """)

    try:
        with _get_engine().connect() as conn:
            result = conn.execute(query).fetchall()
            meta_codes = {r[0] for r in conn.execute(text("SELECT DISTINCT lancamento_codigo FROM meta_ads_daily")).fetchall()}
            google_codes = {r[0] for r in conn.execute(text("SELECT DISTINCT lancamento_codigo FROM google_ads_daily")).fetchall()}
            ac_codes = {r[0] for r in conn.execute(leads_codes_sql).fetchall()}
            # Une a tabela viva com os 2 backups (conta Typeform cancelada em
            # ago/2026) — senão lançamentos cujo form_id só existe no backup
            # ficam com "Pesquisas" desabilitado no menu mesmo tendo dados.
            tf_form_ids_in_db: set[str] = {
                r[0].upper()
                for r in conn.execute(text("""
                    SELECT DISTINCT upper(form_id) FROM typeform_respostas WHERE form_id IS NOT NULL
                    UNION SELECT DISTINCT upper(form_id) FROM typeform_respostas_backup WHERE form_id IS NOT NULL
                    UNION SELECT DISTINCT upper(form_id) FROM typeform_respostas_backup_2 WHERE form_id IS NOT NULL
                """)).fetchall()
            }
            # Sistema de pesquisa interno (substituiu o Typeform a partir do
            # PBB-AGO-26) — título do formulário contém o código do lançamento.
            novo_sistema_titulos: list[str] = [
                r[0].lower()
                for r in conn.execute(text("SELECT titulo FROM formularios WHERE publicado = true")).fetchall()
            ]

            for row in result:
                code = row[0]
                prefix = code.split("-")[0]
                product, product_name, product_order = PRODUCT_BY_PREFIX.get(prefix, (prefix, prefix, 99))

                has_hotmart = row[2] in hm_projects
                has_tmb = row[2] in tmb_projects

                proj_id, alunos_id = _resolve_typeform_ids(code)
                has_pesquisa_nova = any(code.lower() in t for t in novo_sistema_titulos)
                has_typeform = bool(
                    (proj_id and proj_id.upper() in tf_form_ids_in_db)
                    or (alunos_id and alunos_id.upper() in tf_form_ids_in_db)
                    or has_pesquisa_nova
                )

                launch = Launch(
                    code=code,
                    folder=Path("analises") / f"[{code}]",
                    accent=LAUNCH_ACCENT.get(code, "#2f5ee3"),
                    short=LAUNCH_SHORT.get(code, code.split("-")[1] if "-" in code else code),
                    name=LAUNCH_NAMES.get(code, code),
                    product=product,
                    product_name=product_name,
                    product_order=product_order,
                    has_meta=code in meta_codes,
                    has_google=code in google_codes,
                    has_vendas=has_hotmart or has_tmb,
                    has_hotmart=has_hotmart,
                    has_tmb=has_tmb,
                    has_ac=code in ac_codes,
                    has_typeform=has_typeform,
                    project=row[2],
                    data_inicio=row[3],
                    data_fim=row[4]
                )
                launches.append(launch)
    except Exception:
        logger.exception("Falha ao carregar lista de lançamentos do DB analytics; retornando vazio")
        return []

    return launches


def get_launch(launches: list[Launch], code: str) -> Launch | None:
    for launch in launches:
        if launch.code == code:
            return launch
    return None
