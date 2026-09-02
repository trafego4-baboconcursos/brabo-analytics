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
    _invalidate, reset_launches_cache,
)
from frontend.services.fetch import _warm_debriefing

# Um aquecimento por vez: cada warm_launch já dispara ~15 leituras paralelas;
# dois aquecimentos simultâneos (boot + ETL, ou dois ETLs seguidos) saturam
# o pool de conexões do banco (pool_size=10+5, ver src/db_engine.py).
_WARM_LOCK = asyncio.Lock()
MAX_LAUNCHES = 5


def select_launches_to_warm(launches: list, codes: Iterable[str] | None = None) -> list:
    """Mais recente por produto + qualquer lançamento ainda em andamento
    (data_fim no futuro ou nos últimos 7 dias), limitado a MAX_LAUNCHES. Se
    `codes` vier, restringe a esses códigos (na ordem em que aparecem)."""
    if codes:
        wanted = [c.strip().upper() for c in codes if c and c.strip()]
        by_code = {l.code: l for l in launches}
        return [by_code[c] for c in wanted if c in by_code]

    cutoff = date.today() - timedelta(days=7)
    latest_by_product: dict = {}
    for l in launches:
        latest_by_product[l.product] = l  # get_launches vem em ordem cronológica; o último de cada produto fica
    to_warm = {l.code: l for l in latest_by_product.values()}
    active = [l for l in launches if l.data_fim and l.data_fim >= cutoff and l.code not in to_warm]
    for l in active[: max(0, MAX_LAUNCHES - len(to_warm))]:
        to_warm[l.code] = l
    return list(to_warm.values())


async def warm_launch(launch: Any, previous: Any) -> None:
    logger.info("Pre-warming cache para %s...", launch.code)
    d: dict = {}
    try:
        d = await _fetch_all_data(
            launch,
            needs_tf=True,
            needs_daily=True,
            needs_thumbnails=True,
            needs_comparativo=True,
            previous=previous,
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

    # Contagem SendFlow (/whatsapp) fica de fora do _fetch_all_data porque é
    # uma fonte externa lenta (export-leads da SendFlow).
    try:
        from frontend.db_readers.whatsapp_groups import read_whatsapp_groups  # noqa: PLC0415
        await run_in_threadpool(read_whatsapp_groups, launch.code)
        logger.info("Pre-warming de WhatsApp/SendFlow para %s concluído.", launch.code)
    except Exception:
        logger.exception("Falha no pre-warming de WhatsApp/SendFlow para %s", launch.code)


async def warm_active(codes: Iterable[str] | None = None, invalidate: bool = False, origem: str = "boot") -> list[str]:
    """Aquece os lançamentos ativos (ou só `codes`), um por vez. Com
    `invalidate=True`, apaga antes o cache de cada um — é o caminho pós-ETL:
    os dados no banco mudaram e o valor em memória está desatualizado."""
    async with _WARM_LOCK:
        if invalidate:
            reset_launches_cache()  # lançamento criado/renomeado pelo ETL aparece na lista
        launches = await run_in_threadpool(get_launches)
        to_warm = select_launches_to_warm(launches, codes)
        logger.info("Aquecimento (%s) de %d lançamento(s): %s", origem, len(to_warm), ", ".join(l.code for l in to_warm) or "-")
        for l in to_warm:
            if invalidate:
                _invalidate(l.code)
            await warm_launch(l, find_previous_launch(l, launches))
        logger.info("Aquecimento (%s) concluído.", origem)
        return [l.code for l in to_warm]


# asyncio só guarda referência fraca às tasks: sem segurar a referência aqui,
# um aquecimento em andamento pode ser coletado pelo GC no meio do caminho.
_TASKS: set = set()


def schedule_warm(codes: Iterable[str] | None = None, invalidate: bool = False, origem: str = "boot") -> asyncio.Task:
    task = asyncio.create_task(warm_active(codes, invalidate=invalidate, origem=origem))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task
