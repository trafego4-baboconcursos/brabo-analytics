"""
frontend/services/fetch.py — Leitores com cache e orquestrador assíncrono de dados.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi.concurrency import run_in_threadpool

from frontend.cache import _get_cached, _get_or_compute, _set_cached
from frontend.database_reader import (
    read_meta, read_google, read_vendas, read_leads,
    read_hotmart_details, read_tmb_details, read_vendas_consolidado,
    read_typeform, read_typeform_count, read_comparativo, read_daily_breakdown,
    read_ac_campaigns, read_youtube_aulas, get_drive_thumbnails, get_platform_thumbnails,
    read_launch_config,
)
from frontend.db_readers.whatsapp_messages import _read_uncached as _read_wa_cost
from frontend.services.attribution import _sales_attribution
from logger import get_logger

logger = get_logger("frontend")

# ── Config helpers ─────────────────────────────────────────────────────────────

def _launch_cfg(launch_code: str) -> dict:
    return _get_or_compute(launch_code, "launch_config", lambda: read_launch_config(launch_code))


def _get_global_start(cfg: dict) -> str:
    return cfg.get("pre_quali_start_date") or cfg.get("captacao_start_date") or cfg.get("evento_start_date") or cfg.get("carrinho_start_date")


def _get_global_end(cfg: dict) -> str:
    return cfg.get("carrinho_end_date") or cfg.get("evento_end_date") or cfg.get("captacao_end_date") or cfg.get("pre_quali_end_date")

# ── Leitores com cache ─────────────────────────────────────────────────────────

def _window(launch: Any) -> tuple:
    cfg = _launch_cfg(launch.code)
    return _get_global_start(cfg), _get_global_end(cfg)


def _meta(launch: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, f"meta::{start}::{end}",
                           lambda: read_meta(launch.folder, start_date=start, end_date=end))


def _google(launch: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, f"google::{start}::{end}",
                           lambda: read_google(launch.folder, start_date=start, end_date=end))


def _vendas(launch: Any):
    start, end = _window(launch)
    return read_vendas(launch.folder, start_date=start, end_date=end)


def _leads(launch: Any, vendas_data: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, f"leads::{start}::{end}",
                           lambda: read_leads(launch.folder, vendas_data, start_date=start, end_date=end))


def _typeform(launch: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, "typeform_data",
                           lambda: read_typeform(launch.folder, start_date=start, end_date=end))


def _hotmart_details(launch: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, f"hotmart_details::{start}::{end}",
                           lambda: read_hotmart_details(launch.folder, start_date=start, end_date=end))


def _tmb_details(launch: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, f"tmb_details::{start}::{end}",
                           lambda: read_tmb_details(launch.folder, start_date=start, end_date=end))


def _vendas_consolidado(launch: Any):
    start, end = _window(launch)
    return _get_or_compute(launch.code, f"vendas_consolidado::{start}::{end}",
                           lambda: read_vendas_consolidado(launch.folder, start_date=start, end_date=end))


def _typeform_count(launch: Any) -> int:
    return _get_or_compute(launch.code, "typeform_count",
                           lambda: read_typeform_count(launch.folder))


def _perfil_por_anuncio(launch: Any):
    from frontend.db_readers.typeform import read_perfil_por_anuncio
    return _get_or_compute(launch.code, "perfil_por_anuncio",
                           lambda: read_perfil_por_anuncio(launch.code))


def _pesquisa_engajamento(launch: Any):
    from frontend.db_readers.typeform import read_pesquisa_engajamento
    return _get_or_compute(launch.code, "pesquisa_engajamento",
                           lambda: read_pesquisa_engajamento(launch.code))


def _leads_x_whatsapp(launch: Any):
    from frontend.db_readers.whatsapp_groups import read_leads_x_whatsapp
    return _get_or_compute(launch.code, "leads_x_whatsapp",
                           lambda: read_leads_x_whatsapp(launch.code))


def _leads_antigos_compradores(launch: Any, vendas_data: Any):
    from frontend.db_readers.leads import read_leads_antigos_compradores
    return _get_or_compute(launch.code, "leads_antigos_compradores",
                           lambda: read_leads_antigos_compradores(launch.code, vendas_data))


def _qualidade_regiao(launch: Any, vendas_data: Any):
    from frontend.db_readers.sales import read_qualidade_regiao
    return _get_or_compute(launch.code, "qualidade_regiao",
                           lambda: read_qualidade_regiao(launch.code, vendas_data))


def _caminho_comprador(launch: Any, vendas_data: Any):
    from frontend.db_readers.caminho_comprador import read_caminho_comprador
    return _get_or_compute(launch.code, "caminho_comprador",
                           lambda: read_caminho_comprador(launch.code, vendas_data))


def _landing_pages_por_etapa(launch: Any):
    from frontend.db_readers.ga4 import read_landing_pages_por_etapa
    return _get_or_compute(launch.code, "landing_pages_por_etapa",
                           lambda: read_landing_pages_por_etapa(launch.code))


def _wa_cost(launch: Any):
    """Custo de WhatsApp (config/whatsapp_accounts.yaml, filtrado por produto)
    na MESMA janela usada pro investimento de Meta/Google (_window), pra somar
    junto no Investimento Total."""
    from frontend.utils import _safe_date

    start, end = _window(launch)
    s, e = _safe_date(start), _safe_date(end)
    if not s or not e:
        return None
    return _get_or_compute(launch.code, f"wa_cost::{start}::{end}",
                           lambda: _read_wa_cost(launch.code, s, e))


def _fetch_prev_for_debriefing(launch: Any) -> dict:
    """Sync: busca meta/google/vendas/custo WhatsApp do lançamento anterior
    para comparações no debriefing."""
    meta    = _meta(launch)    if getattr(launch, "has_meta",   False) else None
    google  = _google(launch)  if getattr(launch, "has_google", False) else None
    vendas  = _vendas(launch)  if getattr(launch, "has_vendas", False) else None
    wa_cost = _wa_cost(launch)
    return {"meta": meta, "google": google, "vendas": vendas, "wa_cost": wa_cost}

async def _warm_debriefing(launch: Any, previous: Any, vendas: Any) -> None:
    """Aquece as leituras que só a página /debriefing usa (Typeform perfil e
    engajamento, leads antigos, qualidade por região, caminho do comprador,
    dados do lançamento anterior). Ficavam fora do pre-warm de boot, então a
    primeira pessoa a abrir o debriefing depois de um deploy pagava tudo
    isso na própria requisição (25-90s medidos)."""
    async def _safe(name, fn, *args):
        try:
            await run_in_threadpool(fn, *args)
        except Exception:
            logger.exception("Pre-warming debriefing (%s) falhou para %s", name, launch.code)

    tasks = [
        _safe("perfil_por_anuncio", _perfil_por_anuncio, launch),
        _safe("pesquisa_engajamento", _pesquisa_engajamento, launch),
    ]
    if vendas:
        tasks += [
            _safe("leads_antigos", _leads_antigos_compradores, launch, vendas),
            _safe("qualidade_regiao", _qualidade_regiao, launch, vendas),
            _safe("caminho_comprador", _caminho_comprador, launch, vendas),
        ]
    if previous:
        async def _prev():
            try:
                prev_d = await run_in_threadpool(_fetch_prev_for_debriefing, previous)
                if getattr(previous, "has_ac", False) and prev_d.get("vendas"):
                    await run_in_threadpool(_sales_attribution, previous, prev_d["vendas"])
            except Exception:
                logger.exception("Pre-warming debriefing (anterior %s) falhou", previous.code)
        tasks.append(_prev())
    await asyncio.gather(*tasks)

# ── Orquestrador assíncrono ────────────────────────────────────────────────────

async def _fetch_all_data(
    launch: Any,
    needs_tf: bool = False,
    needs_daily: bool = False,
    needs_thumbnails: bool = False,
    needs_comparativo: bool = False,
    previous: Any = None,
    needs_vendas_con: bool = False,
    needs_hotmart: bool = False,
    needs_tmb: bool = False,
    needs_ac_camps: bool = False,
    needs_sales_attr: bool = False,
    needs_youtube: bool = False,
    needs_meta_vendas: bool = False,
    needs_google_vendas: bool = False,
) -> dict:
    _errors: list[str] = []

    async def f_meta():
        if not (launch and launch.has_meta): return None
        try: return await run_in_threadpool(_meta, launch)
        except Exception:
            logger.exception("Falha ao ler Meta Ads")
            _errors.append("Meta Ads")
            return None

    async def f_google():
        if not (launch and launch.has_google): return None
        try: return await run_in_threadpool(_google, launch)
        except Exception:
            logger.exception("Falha ao ler Google Ads")
            _errors.append("Google Ads")
            return None

    async def f_vendas():
        if not (launch and launch.has_vendas): return None
        try: return await run_in_threadpool(_vendas, launch)
        except Exception:
            logger.exception("Falha ao ler vendas")
            _errors.append("Vendas")
            return None

    async def f_tfc():
        if not (launch and launch.has_typeform): return 0
        try: return await run_in_threadpool(_typeform_count, launch)
        except Exception:
            logger.exception("Falha ao contar Typeform")
            return 0

    async def f_tf():
        return await run_in_threadpool(_typeform, launch) if launch and needs_tf and launch.has_typeform else None

    async def f_daily():
        # Único f_* que não tinha try/except: uma queda de conexão do pooler
        # aqui (psycopg2 OperationalError) virava 500 na página inteira em vez
        # de só o breakdown diário vazio + aviso (500 real em /debriefing 03/09).
        if not (launch and needs_daily): return ([], [])
        try:
            return await _f_daily_inner()
        except Exception:
            logger.exception("Falha ao ler breakdown diário")
            _errors.append("Breakdown diário")
            return ([], [])

    async def _f_daily_inner():
        _cfg = await run_in_threadpool(_launch_cfg, launch.code)
        capt_filter = _cfg.get("filtro_captacao") or "captação"
        preq_filter = _cfg.get("filtro_pre_quali") or "pré-qualificação"
        capt_start = _cfg.get("captacao_start_date") or _get_global_start(_cfg)
        capt_end   = _cfg.get("captacao_end_date")   or _get_global_end(_cfg)
        preq_start = _cfg.get("pre_quali_start_date") or _get_global_start(_cfg)
        preq_end   = _cfg.get("pre_quali_end_date")   or _get_global_end(_cfg)
        rows_capt, _ = await run_in_threadpool(
            read_daily_breakdown, launch.code,
            start_date=capt_start, end_date=capt_end,
            filtro_captacao=capt_filter, filtro_pre_quali=None,
        )
        _, rows_preq = await run_in_threadpool(
            read_daily_breakdown, launch.code,
            start_date=preq_start, end_date=preq_end,
            filtro_captacao=None, filtro_pre_quali=preq_filter,
        )
        return rows_capt, rows_preq

    async def f_thumb():
        if not (launch and needs_thumbnails): return {}
        drive: dict = {}
        platform: dict = {}
        try:
            drive = await run_in_threadpool(get_drive_thumbnails, launch.code)
        except Exception:
            logger.exception("Falha ao buscar thumbnails do Drive")
        try:
            platform = await run_in_threadpool(get_platform_thumbnails, launch.code)
        except Exception:
            logger.exception("Falha ao buscar thumbnails da API")
        # API tem prioridade (mais estável); Drive preenche o que faltar (ex: Google Ads)
        return {**drive, **platform}

    async def f_comp():
        if not (launch and needs_comparativo and previous): return None
        cache_key = f"{previous.code}_{launch.code}"
        cached = _get_cached(cache_key, "comparativo")
        if cached: return cached
        try:
            comp_data = await run_in_threadpool(read_comparativo, launch, previous)
            _set_cached(cache_key, "comparativo", comp_data)
            return comp_data
        except Exception:
            logger.exception("Falha ao ler dados comparativos")
            _errors.append("Comparativo")
            return None

    async def f_vc():
        if not (launch and needs_vendas_con and launch.has_vendas): return None
        try: return await run_in_threadpool(_vendas_consolidado, launch)
        except Exception:
            logger.exception("Falha ao ler vendas consolidado")
            return None

    async def f_hm():
        if not (launch and needs_hotmart and launch.has_hotmart): return None
        try: return await run_in_threadpool(_hotmart_details, launch)
        except Exception:
            logger.exception("Falha ao ler Hotmart details")
            _errors.append("Hotmart")
            return None

    async def f_tmb():
        if not (launch and needs_tmb and launch.has_tmb): return None
        try: return await run_in_threadpool(_tmb_details, launch)
        except Exception:
            logger.exception("Falha ao ler TMB details")
            _errors.append("TMB")
            return None

    async def f_ac():
        return await run_in_threadpool(read_ac_campaigns, launch) if launch and needs_ac_camps else None

    async def f_youtube():
        if not (launch and needs_youtube): return []
        try: return await run_in_threadpool(read_youtube_aulas, launch.code)
        except Exception:
            logger.exception("Falha ao ler YouTube aulas")
            return []

    async def f_wa_cost():
        if not launch: return None
        try: return await run_in_threadpool(_wa_cost, launch)
        except Exception:
            logger.exception("Falha ao ler custo de WhatsApp")
            return None

    meta, google, vendas, tfc, tf, daily_tuple, thumb, comp, vc, hm, tmb, ac_camps, yt_aulas, wa_cost = await asyncio.gather(
        f_meta(), f_google(), f_vendas(), f_tfc(), f_tf(), f_daily(), f_thumb(), f_comp(), f_vc(), f_hm(), f_tmb(), f_ac(), f_youtube(), f_wa_cost()
    )

    daily_captacao, daily_preq = daily_tuple if isinstance(daily_tuple, tuple) else (daily_tuple, [])

    async def f_leads():
        if not (launch and launch.has_ac): return None
        try: return await run_in_threadpool(_leads, launch, vendas)
        except Exception:
            logger.exception("Falha ao ler Leads")
            _errors.append("Leads")
            return None

    async def f_sales_attr():
        if not (needs_sales_attr and launch and launch.has_ac and vendas):
            return None
        try: return await run_in_threadpool(_sales_attribution, launch, vendas)
        except Exception:
            logger.exception("Falha ao calcular atribuição de vendas")
            _errors.append("Atribuição")
            return None

    # read_meta/read_google não recebem `vendas` como parâmetro — o cruzamento com
    # vendas já é feito internamente por elas via read_vendas(code) (cacheado). Os
    # flags needs_meta_vendas/needs_google_vendas ficam então apenas documentando a
    # intenção de quem chama; o resultado é sempre o mesmo objeto `meta`/`google`.
    async def f_meta_vendas():
        return meta

    async def f_google_vendas():
        return google

    leads, sales_attr, meta_enriched, google_enriched = await asyncio.gather(
        f_leads(), f_sales_attr(), f_meta_vendas(), f_google_vendas()
    )

    return {
        "meta": meta_enriched, "google": google_enriched, "vendas": vendas,
        "typeform_count": tfc, "tf": tf,
        "daily_breakdown": daily_captacao,
        "daily_breakdown_preq": daily_preq,
        "drive_thumbnails": thumb, "comp_data": comp,
        "vendas_con": vc, "hotmart": hm, "tmb": tmb, "ac_summary": ac_camps,
        "leads": leads, "sales_attr": sales_attr,
        "youtube_aulas": yt_aulas,
        "wa_cost": wa_cost,
        "_errors": _errors,
    }
