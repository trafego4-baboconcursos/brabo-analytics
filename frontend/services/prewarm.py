"""
frontend/services/prewarm.py — Aquecimento do cache em memória.

Usado em dois momentos:
- no boot do dashboard (app.py, evento de startup), pra ninguém pagar a
  primeira leitura pesada na própria requisição depois de um deploy;
- depois de cada rodada do ETL (POST /api/etl/refresh, chamado pelo
  etl/scheduler.py), pra que os dados novos apareçam na hora em vez de
  esperar o TTL de 1h do cache — e sem que a primeira pessoa a abrir a
  página depois do ETL pague a recarga.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Iterable

from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    logger,
    get_launches, _fetch_all_data, find_previous_launch,
    reset_launches_cache,
)
from frontend.cache import force_refresh_start, force_refresh_end
from frontend.services.fetch import _warm_debriefing

# Um aquecimento por vez: cada warm_launch já dispara ~15 leituras paralelas;
# dois aquecimentos simultâneos (boot + ETL, ou dois ETLs seguidos) saturam
# o pool de conexões do banco (pool_size=10+5, ver src/db_engine.py).
_WARM_LOCK = asyncio.Lock()
MAX_LAUNCHES = 5

# Leitores (prefixo da chave de cache, antes de "::") que dependem de cada
# fonte do ETL. Quando o scheduler avisa que uma rodada terminou
# (/api/etl/refresh), só os leitores das fontes que rodaram são recomputados;
# o resto segue no TTL de 1h e no aquecimento periódico, que continua
# recomputando tudo. Antes, o ciclo curto (a cada 30 min) recomputava tudo —
# Typeform congelado, pesquisa nova, leads, grupos de WhatsApp — e isso era a
# maior parte do egress que sobrou depois de 14-18/09 (medido em 30/09/26).
# Vendas não têm fonte no ETL (Hotmart/TMB sincronizam por fora), mas ficam no
# ciclo curto de propósito: o dia 1 do carrinho é acompanhado hora a hora.
LEITORES_POR_FONTE: dict[str, set[str]] = {
    "meta_ads":        {"meta", "meta_temp", "sales_attribution", "utm_cobertura"},
    "google_ads":      {"google", "sales_attribution", "utm_cobertura"},
    "ga4":             {"landing_pages_por_etapa", "conversao_pagina_captura"},
    "sheets_contagem": {"whatsapp_sheets", "whatsapp_sheets_diario"},
    "active_campaign": {"leads", "utm_cobertura", "sales_attribution", "leads_antigos_compradores",
                        "cadastrados_lancamentos_anteriores", "caminho_comprador", "qualidade_regiao",
                        "typeform_data", "typeform_count", "perfil_por_anuncio"},
    "ac_ebook":        {"ebook_compradores"},
    "whatsapp":        {"wa_cost", "disparo_resumo", "whatsapp", "whatsapp_groups_resumo",
                        "leads_x_whatsapp", "vendas_grupos_whatsapp", "compradores_por_dia_grupo"},
}
LEITORES_VENDAS: set[str] = {
    "vendas", "vendas_consolidado", "dia1_sales", "hotmart_details", "tmb_details",
    "forma_pagamento_entrada", "compradores_por_dia_grupo",
}


def leitores_para_fontes(fontes: Iterable[str] | None) -> set[str] | None:
    """Prefixos a recomputar para as fontes que rodaram. None = tudo (aquecimento
    periódico, ETL manual, ou quando não deu pra saber o que rodou)."""
    if fontes is None:
        return None
    escopo = set(LEITORES_VENDAS)
    for fonte in fontes:
        escopo |= LEITORES_POR_FONTE.get(fonte, set())
    return escopo


def fontes_recem_concluidas(minutos: int = 15) -> list[str] | None:
    """Fontes com rodada 'ok' terminada nos últimos `minutos`, lidas de etl_runs —
    é como o dashboard descobre o que o scheduler acabou de rodar quando o aviso
    não diz. None se não der pra saber (aí recomputa tudo, como antes)."""
    from sqlalchemy import text  # noqa: PLC0415
    from frontend.db import _get_engine  # noqa: PLC0415
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT DISTINCT source FROM etl_runs "
                "WHERE status = 'ok' AND finished_at > now() - make_interval(mins => :m)"
            ), {"m": minutos}).fetchall()
        return [r[0] for r in rows] or None
    except Exception:
        logger.exception("Não deu pra ler etl_runs pra descobrir as fontes da rodada")
        return None


def select_launches_to_warm(launches: list, codes: Iterable[str] | None = None) -> list:
    """Mais recente por produto (só se ainda em andamento ou encerrado há até
    7 dias) + qualquer outro lançamento na mesma janela, limitado a
    MAX_LAUNCHES. Se `codes` vier, restringe a esses códigos (na ordem em que
    aparecem).

    Antes, o "mais recente por produto" entrava sempre, mesmo encerrado há
    meses (ex.: PI sem lançamento novo desde PI-AGO-26) — isso mantinha
    Typeform/Meta/Google/etc. desse lançamento morto sendo relidos por
    inteiro a cada ciclo, pra sempre, sem ninguém visitando a página (ver
    ARQUITETURA.md, 18/09/26 — egress). Fora da janela de 7 dias, quem visitar
    ainda é atendido — só não por aquecimento automático (ver
    schedule_snapshot_only), que aquece na hora e cacheia pra próxima visita.
    """
    if codes:
        wanted = [c.strip().upper() for c in codes if c and c.strip()]
        by_code = {l.code: l for l in launches}
        return [by_code[c] for c in wanted if c in by_code]

    cutoff = date.today() - timedelta(days=7)
    latest_by_product: dict = {}
    for l in launches:
        latest_by_product[l.product] = l  # get_launches vem em ordem cronológica; o último de cada produto fica
    to_warm = {
        l.code: l for l in latest_by_product.values()
        if l.data_fim is None or l.data_fim >= cutoff
    }
    active = [l for l in launches if l.data_fim and l.data_fim >= cutoff and l.code not in to_warm]
    for l in active[: max(0, MAX_LAUNCHES - len(to_warm))]:
        to_warm[l.code] = l
    # O lançamento anterior de cada ativo só entra se também estiver na janela.
    # Antes entrava sempre (o debriefing do ativo compara com ele, e era o
    # segundo debriefing mais aberto), mas isso mantinha um lançamento fechado
    # há meses sendo relido por inteiro a cada ciclo. O comparativo do ativo
    # continua quente pelo aquecimento do próprio ativo (needs_comparativo);
    # o debriefing do anterior é servido pelo snapshot já gravado e só
    # recalcula sob demanda (schedule_snapshot_only / ?ao_vivo=1).
    for l in list(to_warm.values()):
        prev = find_previous_launch(l, launches)
        if prev and prev.code not in to_warm and (prev.data_fim is None or prev.data_fim >= cutoff):
            to_warm[prev.code] = prev
    return list(to_warm.values())


async def warm_launch(launch: Any, previous: Any, launches: list | None = None) -> None:
    logger.info("Pre-warming cache para %s...", launch.code)
    launches = launches if launches is not None else ([previous] if previous else [])
    # O /comparativo cacheia por (anterior, atual, anterior-do-anterior) — sem o
    # terceiro aqui o aquecimento grava numa chave que a rota nunca lê.
    previous2 = find_previous_launch(previous, launches) if previous else None
    d: dict = {}
    try:
        d = await _fetch_all_data(
            launch,
            needs_tf=True,
            needs_daily=True,
            needs_thumbnails=True,
            needs_comparativo=True,
            previous=previous,
            previous2=previous2,
            needs_vendas_con=True,
            needs_hotmart=True,
            needs_tmb=True,
            needs_ac_camps=True,
            needs_sales_attr=True,
            needs_youtube=True,
        )
        logger.info("Pre-warming de %s concluído com sucesso!", launch.code)
    except Exception:
        logger.exception("Falha no pre-warming de %s", launch.code)

    # Leituras exclusivas do /debriefing (Typeform, caminho do comprador,
    # etc.) — sem isso, a primeira abertura do debriefing pagava 25-90s.
    try:
        await _warm_debriefing(launch, previous, d.get("vendas"))
        logger.info("Pre-warming do debriefing de %s concluído.", launch.code)
    except Exception:
        logger.exception("Falha no pre-warming do debriefing de %s", launch.code)

    # Com os caches quentes, monta o contexto completo do /debriefing e grava
    # em debriefing_snapshot: a página passa a ler uma linha e renderizar,
    # mesmo depois de um restart (cache frio) — ver debriefing_build.py.
    try:
        from frontend.services.debriefing_build import refresh_debriefing_snapshot  # noqa: PLC0415
        await refresh_debriefing_snapshot(launch, launches)
    except Exception:
        logger.exception("Falha ao gravar snapshot do debriefing de %s", launch.code)

    # Contagem SendFlow (/whatsapp) fica de fora do _fetch_all_data porque é
    # uma fonte externa lenta (export-leads da SendFlow).
    try:
        from frontend.db_readers.whatsapp_groups import read_whatsapp_groups  # noqa: PLC0415
        await run_in_threadpool(read_whatsapp_groups, launch.code)
        logger.info("Pre-warming de WhatsApp/SendFlow para %s concluído.", launch.code)
    except Exception:
        logger.exception("Falha no pre-warming de WhatsApp/SendFlow para %s", launch.code)


async def warm_active(codes: Iterable[str] | None = None, invalidate: bool = False, origem: str = "boot",
                      fontes: Iterable[str] | None = None) -> list[str]:
    """Aquece os lançamentos ativos (ou só `codes`), um por vez. Com
    `invalidate=True` (caminho pós-ETL: o banco mudou), recomputa cada
    leitura NO LUGAR — quem abrir a página durante o re-aquecimento segue
    recebendo o valor anterior na hora, sem janela fria (ver
    force_refresh_start em frontend/cache.py). Apagar o cache antes, como
    era feito, deixava a página fria por minutos a cada rodada do ETL.

    `fontes` (só com invalidate): quais fontes do ETL acabaram de rodar —
    limita a recomputação aos leitores delas (LEITORES_POR_FONTE). None
    recomputa tudo."""
    async with _WARM_LOCK:
        if invalidate:
            reset_launches_cache()  # lançamento criado/renomeado pelo ETL aparece na lista
        launches = await run_in_threadpool(get_launches)
        to_warm = select_launches_to_warm(launches, codes)
        logger.info("Aquecimento (%s) de %d lançamento(s): %s", origem, len(to_warm), ", ".join(l.code for l in to_warm) or "-")
        escopo = leitores_para_fontes(list(fontes) if fontes is not None else None) if invalidate else None
        if invalidate:
            logger.info("Aquecimento (%s): fontes=%s -> recomputa %s", origem,
                        ", ".join(fontes) if fontes else "todas",
                        "todos os leitores" if escopo is None else ", ".join(sorted(escopo)))
        # O escopo por código deixa o lançamento anterior (lido pelo comparativo
        # do ativo) no TTL normal em vez de recomputá-lo a cada aviso do ETL.
        token = force_refresh_start(readers=escopo, codes={l.code for l in to_warm}) if invalidate else None
        try:
            for l in to_warm:
                await warm_launch(l, find_previous_launch(l, launches), launches)
        finally:
            if token is not None:
                force_refresh_end(token)
        logger.info("Aquecimento (%s) concluído.", origem)
        return [l.code for l in to_warm]


# asyncio só guarda referência fraca às tasks: sem segurar a referência aqui,
# um aquecimento em andamento pode ser coletado pelo GC no meio do caminho.
_TASKS: set = set()


def schedule_warm(codes: Iterable[str] | None = None, invalidate: bool = False, origem: str = "boot",
                  fontes: Iterable[str] | None = None) -> asyncio.Task:
    task = asyncio.create_task(warm_active(codes, invalidate=invalidate, origem=origem, fontes=fontes))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


# Snapshot sob demanda: lançamento aberto sem snapshot (antigo, fora do
# conjunto aquecido) é servido ao vivo nesta visita e ganha snapshot em
# segundo plano — a próxima visita já é instantânea. Um por código por vez.
_SNAPSHOT_INFLIGHT: set[str] = set()
# Códigos que precisam de MAIS uma montagem assim que a atual terminar (ver
# `force` abaixo).
_SNAPSHOT_REFAZER: set[str] = set()


def schedule_snapshot_only(launch: Any, launches: list, force: bool = False) -> asyncio.Task | None:
    """Monta e grava o snapshot do /debriefing em segundo plano.

    `force=True` quando a config do lançamento mudou: uma montagem que já estava
    em curso leu a config antiga e vai gravar isso por cima, então em vez de
    simplesmente desistir (o guard de in-flight), marca pra refazer assim que
    ela terminar. Sem isso, salvar o wizard no meio de um aquecimento deixava a
    página com o valor velho até a próxima rodada periódica."""
    code = launch.code
    if code in _SNAPSHOT_INFLIGHT:
        if force:
            _SNAPSHOT_REFAZER.add(code)
            logger.info("Snapshot de %s já em curso; re-montagem marcada pro fim dela.", code)
        return None
    _SNAPSHOT_INFLIGHT.add(code)

    async def _run():
        try:
            from frontend.services.debriefing_build import refresh_debriefing_snapshot  # noqa: PLC0415
            await refresh_debriefing_snapshot(launch, launches)
        except Exception:
            logger.exception("Snapshot sob demanda falhou para %s", code)
        finally:
            _SNAPSHOT_INFLIGHT.discard(code)
        if code in _SNAPSHOT_REFAZER:
            _SNAPSHOT_REFAZER.discard(code)
            logger.info("Re-montando snapshot de %s: a config mudou durante a montagem anterior.", code)
            schedule_snapshot_only(launch, launches)

    task = asyncio.create_task(_run())
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    logger.info("Snapshot sob demanda agendado para %s.", code)
    return task


async def _periodic_warm(interval_min: int) -> None:
    """Re-aquece sozinho a cada `interval_min`, independente do scheduler do
    ETL avisar via /api/etl/refresh (que exige ETL_REFRESH_TOKEN nos dois
    processos). Sem isso, num deploy sem o token o snapshot do debriefing
    ficaria com os dados do boot pra sempre. O lock em warm_active serializa
    com o aviso do ETL quando os dois coincidem."""
    import os  # noqa: PLC0415
    while True:
        await asyncio.sleep(interval_min * 60)
        if os.environ.get("PRE_WARM_CACHE", "true").lower() != "true":
            continue
        try:
            await warm_active(invalidate=True, origem=f"periodico/{interval_min}min")
        except Exception:
            logger.exception("Re-aquecimento periódico falhou")


def schedule_periodic_warm(interval_min: int) -> asyncio.Task | None:
    if interval_min <= 0:
        logger.info("Re-aquecimento periódico desativado (PRE_WARM_INTERVAL_MIN=%s)", interval_min)
        return None
    task = asyncio.create_task(_periodic_warm(interval_min))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    logger.info("Re-aquecimento periódico agendado a cada %d min.", interval_min)
    return task
