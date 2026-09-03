"""
frontend/db_readers/sendflow_contagem.py — Total/Total Limpo/Entrada/Saída
calculados direto da API da SendFlow, replicando exatamente o mesmo padrão
de contagem do sendflow-analytics-poller (o que alimenta o Sheets):

  - TOTAL (bruto) = números de telefone ÚNICOS na lista de participantes
    dos grupos (POST /actions/export-leads), admins/bots ainda inclusos.
  - TOTAL LIMPO = mesma lista, excluindo os números da lista de admin/bot
    da empresa (ADMIN_NUMBERS_BASE, mesma lista do poller).
  - ENTRADA/SAÍDA de hoje = GET /releases/{id}/analytics, contagem oficial
    do dia (não depende de deduplicação nossa).

Não lê Sheets nem a tabela de leads acumulada no Supabase — cálculo
independente, direto da fonte, pra não depender do Sheets no futuro nem
herdar o problema de acúmulo por LID instável entre sincronizações.

Credenciais por lançamento em config/sendflow_contagem.yaml.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from logger import get_logger
from sendflow_grupos import (
    load_config as _load_config,
    export_leads as _export_leads,
    get_analytics as _get_analytics,
    contar_grupos_cheios as _contar_grupos_cheios,
    contar_numeros as _contar_numeros,
    tratar_falha_export_leads as _tratar_falha_export_leads,
    RELEASES_BLOQUEADOS as _releases_bloqueados,
)

logger = get_logger("db")

_CACHE_TTL = 1800  # 30 minutos — export-leads é pesado (campanha grande demora),
                    # e a SendFlow tem rate limit; não vale a pena bater toda hora
_CACHE_TTL_FALHA = 120  # se a consulta falhar (rate limit, timeout), tenta de
                         # novo em 2 min em vez de ficar preso 30 min mostrando
                         # fallback (dados da tabela acumulada) sem necessidade
_cache: dict[str, tuple[float, dict | None, bool]] = {}


def _contar(token: str, release_id: str, total_limpo_anterior: int | None = None) -> dict | None:
    try:
        leads = _export_leads(token, release_id)
    except Exception as e:
        _tratar_falha_export_leads(e, release_id, logger)
        return None

    numeros_todos, numeros_limpo = _contar_numeros(leads)

    # Proteção contra leitura parcial (mesma lógica do sendflow-analytics-
    # poller): o CSV do export-leads vem de um download separado do Firebase
    # Storage — se cortar no meio por rate limit/timeout, csv.DictReader
    # processa só o que chegou, sem erro nenhum, e o total fica baixo demais
    # sem nenhum aviso. Uma queda >10% de um ciclo pro outro é implausível
    # pra uma campanha só crescendo — nesse caso não confia nessa leitura.
    if total_limpo_anterior and total_limpo_anterior > 0 and len(numeros_limpo) < total_limpo_anterior * 0.9:
        logger.warning(
            "sendflow_contagem: total_limpo (%s) caiu mais de 10%% em relação ao anterior "
            "(%s) para release %s — parece leitura parcial, descartando",
            len(numeros_limpo), total_limpo_anterior, release_id,
        )
        return None

    entradas_hoje = saidas_hoje = 0
    historico_entradas: dict[str, int] = {}
    historico_saidas: dict[str, int] = {}
    try:
        analytics = _get_analytics(token, release_id)
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d%m%Y")
        historico_entradas = analytics.get("add", {}).get("dates", {}) or {}
        historico_saidas = analytics.get("remove", {}).get("dates", {}) or {}
        entradas_hoje = historico_entradas.get(hoje, 0)
        saidas_hoje = historico_saidas.get(hoje, 0)
    except Exception:
        logger.exception("sendflow_contagem: falha ao consultar /analytics (release %s)", release_id)

    grupos_cheios = None
    try:
        grupos_cheios = _contar_grupos_cheios(token, release_id)
    except Exception:
        logger.exception("sendflow_contagem: falha ao consultar /groups (release %s)", release_id)

    return {
        # "Total" replica o que o Sheets mostra hoje: contagem de LINHA do
        # export-leads (uma por participação em grupo — quem está em vários
        # grupos conta mais de uma vez), não de pessoa única. Sim, é a mesma
        # conta que já foi identificada como "errada" no poller (corrigida
        # lá em 27/08, commit e5ce4bf) — mas aqui o objetivo é bater com o
        # que o Sheets mostra agora, não com a versão corrigida.
        "total": len(leads),
        "total_limpo": len(numeros_limpo),
        "entradas_hoje": int(entradas_hoje or 0),
        "saidas_hoje": int(saidas_hoje or 0),
        # TOTAL GRUPOS CHEIOS do Sheets: GET /releases/{id}/groups, conta
        # quem tem full=true — None (não 0) se a consulta falhar, pra não
        # sobrescrever um valor bom anterior com zero errado.
        "grupos_cheios": grupos_cheios,
        # Histórico diário completo (chave "ddmmyyyy") de entradas/saídas —
        # a SendFlow devolve isso retroativo desde o início da campanha, não
        # precisa de snapshot pra ter esse dado (ao contrário de total/total
        # limpo, que só existem "ao vivo"). Vem de graça no mesmo /analytics
        # já consultado acima pra "hoje" — não é uma chamada extra.
        "historico_entradas": historico_entradas,
        "historico_saidas": historico_saidas,
    }


_cache_locks: dict[str, threading.Lock] = {}
_cache_locks_guard = threading.Lock()


def _lock_for(code: str) -> threading.Lock:
    with _cache_locks_guard:
        return _cache_locks.setdefault(code, threading.Lock())


# Cache guarda (timestamp, resultado, completo) — "completo" indica se TODOS
# os blocos esperados (normal/vip) vieram com sucesso. Incompleto usa TTL
# curto, pra não ficar preso 30 min mostrando fallback por causa de uma
# falha pontual (rate limit, timeout) na SendFlow.
def _cache_valido(cached: tuple[float, dict | None, bool]) -> bool:
    _, _, completo = cached
    ttl = _CACHE_TTL if completo else _CACHE_TTL_FALHA
    return (time.time() - cached[0]) < ttl


def contar_lancamento(code: str) -> dict | None:
    """Retorna {"normal": {...}, "vip": {...}} pro lançamento, calculado
    direto da SendFlow. None se não houver mapeamento pra esse código.

    Single-flight: se duas requisições baterem no mesmo lançamento com cache
    frio ao mesmo tempo, só a primeira consulta a SendFlow (export-leads é
    lento e tem rate limit) — a segunda espera e reaproveita o resultado
    em vez de disparar uma chamada duplicada.
    """
    cached = _cache.get(code)
    if cached and _cache_valido(cached):
        return cached[1]

    with _lock_for(code):
        # outra thread pode ter computado enquanto esperávamos o lock
        cached = _cache.get(code)
        if cached and _cache_valido(cached):
            return cached[1]

        cfg = _load_config().get(code)
        if not cfg:
            return None

        resultado_anterior = cached[1] if cached else None

        blocos_esperados = [c for c in ("normal", "vip") if cfg.get(c)]
        resultado = {}
        blocos_frescos = 0  # só conta leitura NOVA e bem-sucedida, não reaproveitada
        primeira = True
        for chave in blocos_esperados:
            bloco = cfg[chave]
            if bloco["release_id"] in _releases_bloqueados:
                continue  # já sabemos que dá 400/401/403/404 — não bate na API de novo
            token = os.environ.get(bloco["token_env"])
            if not token:
                logger.warning("sendflow_contagem: env var %s não configurada", bloco["token_env"])
                continue
            if not primeira:
                time.sleep(1.5)  # espaça chamadas ao mesmo token (rate limit da SendFlow)
            primeira = False
            anterior = (resultado_anterior or {}).get(chave, {}).get("total_limpo")
            r = _contar(token, bloco["release_id"], total_limpo_anterior=anterior)
            if r:
                resultado[chave] = r
                blocos_frescos += 1
            elif anterior is not None:
                # leitura descartada (parcial) ou falhou — mantém o último
                # valor bom conhecido em vez de mostrar zero/fallback errado
                resultado[chave] = resultado_anterior[chave]

        # completo = toda chave ATIVA (exclui as já bloqueadas por 400/401/
        # 403/404 — essas nunca vão ficar "frescas" de novo) veio de uma
        # leitura NOVA bem-sucedida nesse ciclo. Sem isso, um release
        # permanentemente bloqueado forçaria cache curto pra sempre, fazendo
        # bater na API a cada 2 min até pros releases que estão funcionando.
        blocos_ativos = [c for c in blocos_esperados if cfg[c]["release_id"] not in _releases_bloqueados]
        completo = blocos_frescos == len(blocos_ativos)
        resultado_final = resultado or None
        _cache[code] = (time.time(), resultado_final, completo)
        return resultado_final
