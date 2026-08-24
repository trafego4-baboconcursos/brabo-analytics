"""
frontend/core.py — Estado compartilhado, lógica de negócio e orquestrador do Brabo Analytics.
Importado por frontend/app.py e por todos os módulos em frontend/routes/.
"""
from __future__ import annotations
import sys
import io
import re
import os
import threading as _threading
import time as _time_module
from pathlib import Path
from fastapi import Request
from fastapi.templating import Jinja2Templates

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ANALISES_DIR   = WORKSPACE_ROOT / "analises"
IMG_DIR        = WORKSPACE_ROOT / "img"
SRC_DIR        = WORKSPACE_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from frontend.database_reader import (
    discover_launches, get_launch, Launch,
    read_comparativo, AcCampaignSummary,
    read_launch_config, save_launch_config, count_campaigns_for_filter, get_drive_thumbnails,
    autodetect_launch_data,
    KNOWN_META_ACCOUNTS, KNOWN_GOOGLE_ACCOUNTS,
    get_user_by_email, get_user_by_id, list_users, create_user,
    update_user, update_last_login, bootstrap_admin_if_needed,
    create_invite, get_invite, use_invite, list_invites, delete_invite,
    ROLE_LABELS, PRODUCT_LABELS,
    get_etl_status as _db_get_etl_status,
)
from frontend.calendar_parser import parse_calendar
from frontend.utils import _norm_text
from frontend.formatters import fmt_brl, fmt_num, fmt_pct, fmt_br_date
from frontend.cache import _get_cached, _set_cached, _invalidate, _CACHE  # noqa: E402
from frontend.auth import (  # noqa: E402
    BRABO_USER, BRABO_PASS, COOKIE_SECURE, ROUTE_PERMISSIONS,
    _hash_password, _verify_password,
    _decode_session, _set_session_cookie,
    _get_current_user, _filter_launches_for_user,
    _check_login_rate_limit, _record_login_attempt,
)
from frontend.services.attribution import (  # noqa: F401
    _extract_ad_code, _classify_campaign, _classify_google_campaign_type,
    _utm_score, _inc_sales,
    _sales_attribution, _creative_overview,
)
from frontend.services.fetch import (  # noqa: E402
    _fetch_all_data, _fetch_prev_for_debriefing,
)
from frontend.services.debriefing import _compute_debriefing_ctx  # noqa: F401,E402
from logger import get_logger

logger = get_logger("frontend")

# ── Validação de variáveis de ambiente críticas ────────────────────────────────
_REQUIRED_ENV = ["SUPABASE_DB_URL", "SUPABASE_USERS_URL"]
_MISSING_ENV = [v for v in _REQUIRED_ENV if not os.environ.get(v)]
if _MISSING_ENV:
    logger.error(
        "Variáveis de ambiente obrigatórias ausentes: %s — o app vai falhar ao acessar o banco de dados",
        _MISSING_ENV,
    )
if os.environ.get("SECRET_KEY", "").startswith("brabo-dev"):
    logger.warning("SECRET_KEY usando valor padrão inseguro — configure uma chave forte em produção")

_APP_START_TIME = _time_module.time()

# ── Templates ──────────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Compatibilidade do Jinja2Templates com assinaturas Starlette antigas
_original_template_response = templates.TemplateResponse
def _compat_template_response(*args, **kwargs):
    if len(args) >= 1 and isinstance(args[0], str):
        name = args[0]
        context = args[1] if len(args) > 1 else kwargs.get("context", {})
        request = context.get("request")
        return _original_template_response(request=request, name=name, context=context, **{k: v for k, v in kwargs.items() if k not in ("name", "context", "request")})
    return _original_template_response(*args, **kwargs)
templates.TemplateResponse = _compat_template_response

# ── Formatadores Jinja2 ────────────────────────────────────────────────────────
templates.env.filters["brl"] = fmt_brl
templates.env.filters["num"] = fmt_num
templates.env.filters["pct"] = fmt_pct
templates.env.filters["br_date"] = fmt_br_date

# ── Cache de lançamentos ───────────────────────────────────────────────────────
_LAUNCHES_CACHE: list[Launch] = []
_LAUNCHES_CACHE_AT: float = 0.0
_LAUNCHES_CACHE_TTL: int = 300
_LAUNCHES_DB_OK: bool = True
_LAUNCHES_REFRESHING = _threading.Lock()

def _refresh_launches() -> list[Launch]:
    global _LAUNCHES_CACHE, _LAUNCHES_CACHE_AT, _LAUNCHES_DB_OK
    result = discover_launches(ANALISES_DIR)
    if result:
        _LAUNCHES_CACHE = result
        _LAUNCHES_CACHE_AT = _time_module.time()
        _LAUNCHES_DB_OK = True
    else:
        _LAUNCHES_DB_OK = False
    return result

def get_launches() -> list[Launch]:
    """Stale-while-revalidate: com cache expirado, devolve a lista antiga na hora
    e atualiza num thread de fundo — nenhum request paga o custo do discover."""
    now = _time_module.time()
    if _LAUNCHES_CACHE and (now - _LAUNCHES_CACHE_AT) < _LAUNCHES_CACHE_TTL:
        return _LAUNCHES_CACHE
    if _LAUNCHES_CACHE:
        if _LAUNCHES_REFRESHING.acquire(blocking=False):
            def _bg():
                try:
                    _refresh_launches()
                except Exception:
                    logger.exception("Refresh de lançamentos em background falhou")
                finally:
                    _LAUNCHES_REFRESHING.release()
            _threading.Thread(target=_bg, daemon=True).start()
        return _LAUNCHES_CACHE
    # cache frio (primeiro request pós-boot): não tem o que servir, computa inline
    return _refresh_launches() or _LAUNCHES_CACHE

def reset_launches_cache() -> None:
    global _LAUNCHES_CACHE_AT
    _LAUNCHES_CACHE_AT = 0.0

def resolve_launch(launch_code: str | None, launches: list[Launch]) -> Launch | None:
    if launch_code:
        return get_launch(launches, launch_code)
    for launch in reversed(launches):
        if launch.has_meta and launch.has_google and launch.has_vendas:
            return launch
    for launch in reversed(launches):
        if launch.has_meta or launch.has_google or launch.has_vendas or launch.has_ac or launch.has_typeform:
            return launch
    return launches[-1] if launches else None

def find_previous_launch(launch: Launch, all_launches: list[Launch]) -> Launch | None:
    if not launch or not launch.product or not launch.data_inicio:
        return None
    same_product = [
        l for l in all_launches
        if l.product == launch.product
        and l.data_inicio is not None
        and l.data_inicio < launch.data_inicio
        and l.code != launch.code
    ]
    if not same_product:
        return None
    return max(same_product, key=lambda l: l.data_inicio)

# ── V1 Reports ────────────────────────────────────────────────────────────────
V1_REPORTS = [
    {"key": "dashboard", "label": "Dashboard / Indice", "v2_path": "/captacao", "v1_file": "INDEX_[{code}].html", "needs": []},
    {"key": "funil", "label": "Funil", "v2_path": "/funil", "v1_file": "ANALISE_FUNIL_[{code}].html", "needs": ["meta", "google", "vendas"]},
    {"key": "meta", "label": "Meta Ads", "v2_path": "/meta", "v1_file": "ANALISE_META_ADS_[{code}].html", "needs": ["meta"]},
    {"key": "google", "label": "Google Ads", "v2_path": "/google", "v1_file": "ANALISE_GOOGLE_ADS_[{code}].html", "needs": ["google"]},
    {"key": "vendas", "label": "Vendas", "v2_path": "/vendas", "v1_file": "ANALISE_VENDAS_[{code}].html", "needs": ["vendas"]},
    {"key": "meta_audiences", "label": "Meta Audiencias", "v2_path": "/meta-audiences", "v1_file": "ANALISE_META_AUDIENCES_[{code}].html", "needs": ["meta"]},
    {"key": "google_audiences", "label": "Google Audiencias", "v2_path": "/google-audiences", "v1_file": "ANALISE_GOOGLE_AUDIENCES_[{code}].html", "needs": ["google"]},
    {"key": "crm_campanhas", "label": "CRM Campanhas", "v2_path": "/crm-campanhas", "v1_file": "ANALISE_CRM_CAMPANHAS_[{code}].html", "needs": []},
]

def _v1_url_if_exists(launch: Launch | None, filename_template: str) -> str | None:
    if not launch:
        return None
    filename = filename_template.format(code=launch.code)
    if (launch.folder / filename).exists():
        return f"/analises/[{launch.code}]/{filename}"
    return None

def _v2_url(path: str, launch: Launch | None) -> str:
    if not launch:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}launch_code={launch.code}"

def _v1_reports_for_launch(launch: Launch | None) -> list[dict]:
    data_flags = {
        "meta": bool(launch and launch.has_meta),
        "google": bool(launch and launch.has_google),
        "vendas": bool(launch and launch.has_vendas),
        "ac": bool(launch and launch.has_ac),
        "typeform": bool(launch and launch.has_typeform),
    }
    reports: list[dict] = []
    for report in V1_REPORTS:
        v1_url = _v1_url_if_exists(launch, report["v1_file"])
        missing_needs = [need for need in report["needs"] if not data_flags.get(need)]
        reports.append({
            **report,
            "v1_url": v1_url,
            "v1_exists": bool(v1_url),
            "v2_url": _v2_url(report["v2_path"], launch),
            "v2_ready": not missing_needs,
            "missing_needs": missing_needs,
        })
    return reports

# ── Contexto base ──────────────────────────────────────────────────────────────

def _base_ctx(
    request: Request,
    page: str,
    title: str,
    launch: Launch | None,
    launches: list[Launch],
    **extra,
) -> dict:
    current_user = _get_current_user(request)
    visible_launches = _filter_launches_for_user(launches, current_user)

    month_order = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
    launch_groups: list[dict] = []
    grouped_launches = sorted(
        visible_launches,
        key=lambda item: (item.product_order, month_order.get(item.short, 99), item.code),
    )
    for item in grouped_launches:
        if not launch_groups or launch_groups[-1]["product"] != item.product:
            launch_groups.append({
                "product": item.product,
                "product_name": item.product_name,
                "launches": [],
            })
        launch_groups[-1]["launches"].append(item)

    v1_launch_url = None
    if launch:
        v1_launch_url = _v1_url_if_exists(launch, "INDEX_[{code}].html")

    return {
        "request":         request,
        "page":            page,
        "title":           title,
        "launch":          launch,
        "launches":        visible_launches,
        "launch_groups":   launch_groups,
        "v1_launch_url":   v1_launch_url,
        "active_code":     launch.code if launch else None,
        "accent":          launch.accent if launch else "#2f5ee3",
        "previous_launch": find_previous_launch(launch, launches) if launch else None,
        "current_user":    current_user,
        "db_ok":           _LAUNCHES_DB_OK,
        "etl_status":      get_etl_status(),
        "etl_stale_hours": ETL_STALE_HOURS,
        **extra,
    }

# ── Contas de anúncio por projeto (config/project_accounts.yaml) ──────────────
_PROJECT_ACCOUNTS_PATH = WORKSPACE_ROOT / "config" / "project_accounts.yaml"
_PROJECT_ACCOUNTS_CACHE: dict | None = None

def _project_accounts() -> dict:
    global _PROJECT_ACCOUNTS_CACHE
    if _PROJECT_ACCOUNTS_CACHE is None:
        import yaml
        try:
            _PROJECT_ACCOUNTS_CACHE = yaml.safe_load(_PROJECT_ACCOUNTS_PATH.read_text(encoding="utf-8")) or {}
        except FileNotFoundError:
            logger.error("config/project_accounts.yaml não encontrado — contas de anúncio ficarão vazias")
            _PROJECT_ACCOUNTS_CACHE = {}
    return _PROJECT_ACCOUNTS_CACHE

# ── Defaults de lançamento ─────────────────────────────────────────────────────

def _compute_launch_defaults(launch_code: str) -> dict:
    cal = parse_calendar(WORKSPACE_ROOT)
    bounds = cal.get(launch_code.upper(), {})
    stages = bounds.get("stages", {})

    def _stage_dates(key):
        if key in stages:
            return str(stages[key]["start"]), str(stages[key]["end"])
        return None, None

    if "captacao" in stages:
        captacao_start, captacao_end = _stage_dates("captacao")
    elif bounds.get("start"):
        captacao_start = str(bounds["start"])
        captacao_end   = str(bounds["end"]) if bounds.get("end") else None
    else:
        captacao_start = captacao_end = None

    carrinho_start, carrinho_end = _stage_dates("carrinho")
    pre_quali_start, pre_quali_end = _stage_dates("pre_quali")
    evento_start, evento_end = _stage_dates("evento") if "evento" in stages else _stage_dates("aulas")

    launches = get_launches()
    launch = get_launch(launches, launch_code)
    project = launch.project if launch else None

    accounts = _project_accounts().get(project, {})
    meta_ids    = accounts.get("meta_ad_account_ids", [])
    google_ids  = accounts.get("google_ad_account_ids", [])
    hotmart_ids = accounts.get("hotmart_produto_ids", [])
    tmb_ids     = accounts.get("tmb_produto_ids", [])

    db_data = autodetect_launch_data(launch_code)

    return {
        "captacao_start_date":        captacao_start,
        "captacao_end_date":          captacao_end,
        "carrinho_start_date":        carrinho_start,
        "carrinho_end_date":          carrinho_end,
        "pre_quali_start_date":       pre_quali_start,
        "pre_quali_end_date":         pre_quali_end,
        "evento_start_date":          evento_start,
        "evento_end_date":            evento_end,
        "meta_ad_account_ids":        meta_ids,
        "google_ad_account_ids":      google_ids,
        "filtro_lancamento":          launch_code,
        "filtro_captacao":            "captação",
        "filtro_pre_quali":           db_data.get("filtro_pre_quali", "pré-qualificação"),
        "filtro_quente":              "quente",
        "filtro_quente_scope":        "campanhas",
        "filtro_frio":                "frio",
        "filtro_frio_scope":          "campanhas",
        "hotmart_produto_ids":        hotmart_ids,
        "tmb_produto_ids":            tmb_ids,
        "outras_temperaturas":        [],
        "meta_leads":                 db_data.get("meta_leads"),
        "meta_investimento_captacao": db_data.get("meta_investimento_captacao"),
        "drive_folder_url":           None,
    }

# ── Health check cache ─────────────────────────────────────────────────────────
_HEALTH_CACHE: dict = {}
_HEALTH_CACHE_AT: float = 0.0
_HEALTH_CACHE_TTL: int = 30

# ── ETL Status cache ───────────────────────────────────────────────────────────
_ETL_STATUS_CACHE: dict = {}
_ETL_STATUS_CACHE_AT: float = 0.0
_ETL_STATUS_CACHE_TTL: int = 300          # 5 minutos
ETL_STALE_HOURS: float = float(os.environ.get("ETL_STALE_HOURS", "25"))

def get_etl_status() -> dict:
    global _ETL_STATUS_CACHE, _ETL_STATUS_CACHE_AT
    now = _time_module.time()
    if _ETL_STATUS_CACHE and (now - _ETL_STATUS_CACHE_AT) < _ETL_STATUS_CACHE_TTL:
        return _ETL_STATUS_CACHE
    try:
        _ETL_STATUS_CACHE = _db_get_etl_status()
        _ETL_STATUS_CACHE_AT = now
    except Exception:
        logger.debug("Falha ao buscar ETL status")
    return _ETL_STATUS_CACHE

# ── Drive thumb cache ──────────────────────────────────────────────────────────
_thumb_url_cache: dict[str, tuple[float, str]] = {}
_THUMB_URL_TTL = 600
