"""
frontend/services/debriefing_build.py — Monta o contexto completo do /debriefing.

Extraído da rota pra ser usado em dois lugares:
- pela própria rota, quando não há snapshot gravado (cálculo ao vivo);
- pelo aquecimento (frontend/services/prewarm.py), que calcula com tudo
  inline (lazy=False) e grava o resultado em `debriefing_snapshot` — a
  página então lê uma linha só, sem as dezenas de consultas sequenciais.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    logger,
    find_previous_launch,
    _fetch_all_data, _creative_overview,
    _fetch_prev_for_debriefing, _compute_debriefing_ctx,
    _sales_attribution,
)
from frontend.services.fetch import (
    _perfil_por_anuncio, _pesquisa_engajamento,
    _leads_antigos_compradores, _qualidade_regiao, _caminho_comprador,
    _landing_pages_por_etapa, _leads_x_whatsapp, _vendas_grupos_whatsapp,
    _disparo_resumo, _ebook_compradores, _hotmart_recompra,
)


async def build_debriefing_context(launch: Any, launches: list, lazy: bool) -> dict:
    """Devolve {dbf, drive_thumbnails, data_errors, creative_data_error}.

    `lazy=True` deixa de fora as seções pesadas (Typeform perfil/engajamento,
    qualidade por estado, caminho do comprador, leads × WhatsApp) — o
    template as renderiza como esqueleto e o navegador busca cada uma em
    /debriefing/secao/<nome>. `lazy=False` calcula tudo inline (slides/PDF
    e snapshot)."""
    previous = find_previous_launch(launch, launches) if launch else None

    d = await _fetch_all_data(launch, needs_daily=True, needs_hotmart=True, needs_tmb=True, needs_sales_attr=True, needs_youtube=True, needs_thumbnails=True) if launch else {}
    meta          = d.get("meta")
    google        = d.get("google")
    vendas        = d.get("vendas")
    sales_attr    = d.get("sales_attr")
    daily         = d.get("daily_breakdown") or []
    hotmart       = d.get("hotmart")
    tmb           = d.get("tmb")
    youtube_aulas = d.get("youtube_aulas") or []
    thumb         = d.get("drive_thumbnails") or {}

    data_errors = list(d.get("_errors", []))
    # Blocos que falharam nesta montagem (além dos _errors do _fetch_all_data).
    # O snapshot usa isso pra não gravar por cima de um snapshot completo com
    # um degradado por falha transitória (pooler caiu, consulta estourou).
    falhas: list[str] = list(data_errors)

    # Blocos independentes entre si (só dependem do que já foi buscado acima):
    # rodam em paralelo.

    async def f_creative():
        if not (launch and (meta or google)):
            return None, False
        try:
            data = await run_in_threadpool(
                _creative_overview, meta, google, vendas, sales_attr,
                launch_code=launch.code if launch else "",
            )
            return data, False
        except Exception:
            logger.exception("Debriefing: falha ao montar creative overview")
            falhas.append("creative_overview")
            return None, True

    async def f_leads_antigos():
        if not (launch and vendas):
            return None
        try:
            return await run_in_threadpool(_leads_antigos_compradores, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao classificar leads antigos × novos")
            falhas.append("leads_antigos")
            return None

    async def f_perfil_pesquisa():
        if not launch or lazy:
            return None, None
        try:
            return await asyncio.gather(
                run_in_threadpool(_perfil_por_anuncio, launch),
                run_in_threadpool(_pesquisa_engajamento, launch),
            )
        except Exception:
            logger.exception("Debriefing: falha ao montar perfil do lead por anúncio")
            falhas.append("perfil_pesquisa")
            return None, None

    async def f_qualidade_regiao():
        if not launch or lazy:
            return None
        try:
            return await run_in_threadpool(_qualidade_regiao, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar qualidade por regiao")
            falhas.append("qualidade_regiao")
            return None

    async def f_caminho_comprador():
        if not (launch and vendas) or lazy:
            return None
        try:
            return await run_in_threadpool(_caminho_comprador, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar caminho do comprador")
            falhas.append("caminho_comprador")
            return None

    async def f_landing_pages():
        if not launch:
            return None
        try:
            return await run_in_threadpool(_landing_pages_por_etapa, launch)
        except Exception:
            logger.exception("Debriefing: falha ao montar landing pages por etapa (GA4)")
            falhas.append("landing_pages")
            return None

    async def f_leads_x_whatsapp():
        if not launch or lazy:
            return None
        try:
            return await run_in_threadpool(_leads_x_whatsapp, launch)
        except Exception:
            logger.exception("Debriefing: falha ao montar leads x grupos de WhatsApp")
            falhas.append("leads_x_whatsapp")
            return None

    async def f_vendas_grupos_whatsapp():
        if not launch or lazy:
            return None
        try:
            return await run_in_threadpool(_vendas_grupos_whatsapp, launch)
        except Exception:
            logger.exception("Debriefing: falha ao montar vendas x grupos de WhatsApp")
            falhas.append("vendas_grupos_whatsapp")
            return None

    async def f_disparo_resumo():
        if not launch or lazy:
            return None
        try:
            return await run_in_threadpool(_disparo_resumo, launch)
        except Exception:
            logger.exception("Debriefing: falha ao montar resumo do disparo WhatsApp")
            falhas.append("disparo_resumo")
            return None

    async def f_ebook():
        if not (launch and vendas):
            return None
        try:
            return await run_in_threadpool(_ebook_compradores, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar ebook × compra")
            falhas.append("ebook_compradores")
            return None

    async def f_hotmart_recompra():
        if not (launch and launch.has_hotmart):
            return None
        try:
            return await run_in_threadpool(_hotmart_recompra, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar recompra boleto/cartão")
            falhas.append("hotmart_recompra")
            return None

    async def f_previous():
        if not previous:
            return None, None, None, None, None, None
        try:
            prev_d = await run_in_threadpool(_fetch_prev_for_debriefing, previous)
            p_meta    = prev_d.get("meta")
            p_google  = prev_d.get("google")
            p_vendas  = prev_d.get("vendas")
            p_wa_cost = prev_d.get("wa_cost")
            p_hotmart = prev_d.get("hotmart")
            p_sales_attr = None
            if getattr(previous, "has_ac", False) and p_vendas:
                p_sales_attr = await run_in_threadpool(_sales_attribution, previous, p_vendas)
            return p_meta, p_google, p_vendas, p_wa_cost, p_sales_attr, p_hotmart
        except Exception:
            logger.exception("Debriefing: falha ao buscar dados do lançamento anterior")
            falhas.append("lancamento_anterior")
            return None, None, None, None, None, None

    (
        (creative_data, creative_data_error),
        leads_antigos,
        (perfil_por_anuncio, pesquisa_engajamento),
        qualidade_regiao,
        caminho_comprador,
        (prev_meta, prev_google, prev_vendas, prev_wa_cost, prev_sales_attr, prev_hotmart),
        landing_pages_por_etapa,
        leads_x_whatsapp,
        vendas_grupos_whatsapp,
        disparo_resumo,
        ebook_compradores,
        hotmart_recompra,
    ) = await asyncio.gather(
        f_creative(), f_leads_antigos(), f_perfil_pesquisa(),
        f_qualidade_regiao(), f_caminho_comprador(), f_previous(),
        f_landing_pages(), f_leads_x_whatsapp(), f_vendas_grupos_whatsapp(),
        f_disparo_resumo(), f_ebook(), f_hotmart_recompra(),
    )

    dbf = _compute_debriefing_ctx(
        launch, previous,
        meta, google, vendas, sales_attr, daily, hotmart, creative_data,
        prev_meta, prev_google, prev_vendas,
        youtube_aulas=youtube_aulas,
        prev_sales_attr=prev_sales_attr,
        tmb=tmb,
        leads_antigos=leads_antigos,
        perfil_por_anuncio=perfil_por_anuncio,
        pesquisa_engajamento=pesquisa_engajamento,
        qualidade_regiao=qualidade_regiao,
        caminho_comprador=caminho_comprador,
        landing_pages_por_etapa=landing_pages_por_etapa,
        leads_x_whatsapp=leads_x_whatsapp,
        vendas_grupos_whatsapp=vendas_grupos_whatsapp,
        disparo_resumo=disparo_resumo,
        ebook_compradores=ebook_compradores,
        hotmart_recompra=hotmart_recompra,
        prev_hotmart=prev_hotmart,
        wa_cost=d.get("wa_cost"),
        prev_wa_cost=prev_wa_cost,
    )
    return {
        "dbf": dbf,
        "drive_thumbnails": thumb,
        "data_errors": data_errors,
        "creative_data_error": creative_data_error,
        "falhas": falhas,
    }


async def refresh_debriefing_snapshot(launch: Any, launches: list) -> None:
    """Calcula o contexto completo (tudo inline) e grava em debriefing_snapshot.
    Chamado pelo aquecimento, com os caches já quentes — custa só a montagem.

    Se algum bloco falhou nesta montagem (falha transitória: pooler caiu,
    consulta estourou memória), NÃO grava por cima de um snapshot já
    existente — senão uma seção some da página por 30 min até o próximo
    aquecimento. Sem snapshot anterior, grava mesmo assim (melhor que nada)."""
    from frontend.db_readers.debriefing_snapshot import read_snapshot, write_snapshot  # noqa: PLC0415

    t0 = time.perf_counter()
    built = await build_debriefing_context(launch, launches, lazy=False)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    falhas = built.get("falhas") or []
    if falhas:
        existente = await run_in_threadpool(read_snapshot, launch.code)
        if existente:
            logger.warning("Snapshot do debriefing de %s NÃO regravado: falhas em %s (mantido o de %s).",
                           launch.code, ", ".join(falhas), existente.get("computed_at"))
            return
        logger.warning("Snapshot do debriefing de %s gravado com falhas em %s (não havia snapshot anterior).",
                       launch.code, ", ".join(falhas))
    size = await run_in_threadpool(write_snapshot, launch.code, built, duration_ms)
    logger.info("Snapshot do debriefing de %s gravado (%d KB, montado em %d ms).", launch.code, size // 1024, duration_ms)
