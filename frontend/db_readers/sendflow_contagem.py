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

import csv
import io
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
import yaml

from logger import get_logger

logger = get_logger("db")

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sendflow_contagem.yaml"
_BASE_URL = "https://sendapi.sendflow.pro"
_CACHE_TTL = 1800  # 30 minutos — export-leads é pesado (campanha grande demora),
                    # e a SendFlow tem rate limit; não vale a pena bater toda hora
_CACHE_TTL_FALHA = 120  # se a consulta falhar (rate limit, timeout), tenta de
                         # novo em 2 min em vez de ficar preso 30 min mostrando
                         # fallback (dados da tabela acumulada) sem necessidade
_cache: dict[str, tuple[float, dict | None, bool]] = {}

# Mesma lista do sendflow-analytics-poller (app/config.py::ADMIN_NUMBERS_BASE) —
# contas de marketing/staff da empresa, sempre excluídas do Total Limpo.
ADMIN_NUMBERS_BASE = {
    "5516991876538", "5516991320600", "5516992314699", "5516991525260",
    "5516997353630", "5516993910017", "5516992352349", "5516991081133",
    "5516992345997", "5516993966587", "5516996544873", "5516997384603",
    "5516992359626", "5516994054610", "5516992712899", "5516993678375",
    "5516991268108", "5516992342427", "5516991880994", "5516992162853",
    "5516993230455", "5516992580599", "5516994109165", "5516991262116",
    "5516992243112", "5516994330869", "5516992932850", "5516993643159",
    "5516994602791", "5516991628640",
    # SUNSET
    "5516992346621", "5516994062017", "5516997046751", "5516992308913",
    "5516992365749",
    # DICE
    "5516996101548", "5516992287856", "5516991721165", "5516991047065",
    "5516992718950",
    # SHADOW
    "5516994278676", "5516994081940", "5516992282631", "5516992193391",
    "5516992205157",
    # KNIGHT
    "5516997785568", "5516997901145", "5516994084569", "5516994066837",
    "5516994153971", "5516994081948",
    # DARK
    "5516994338328", "5516994196958", "5516994188660", "5516997263099",
    "5516997080885", "5516997336857",
    # SWORD
    "5516996542640", "5516999921639", "5516994307722", "5516993017738",
    "5516992142972", "5516997068492",
}


def _load_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _headers(token: str) -> dict:
    return {"accept": "application/json", "Authorization": f"Bearer {token}"}


def _numero_do_lead(lead: dict) -> str:
    # Mesma lógica do poller — CSV com colunas Posição;Grupo;Nome;Número.
    raw = lead.get("Número") or lead.get("Numero") or lead.get("number") or ""
    raw = str(raw).lstrip("'").split("@")[0]
    return "".join(ch for ch in raw if ch.isdigit())


def _export_leads(token: str, release_id: str) -> list[dict]:
    resp = requests.post(
        f"{_BASE_URL}/actions/export-leads",
        headers=_headers(token),
        json={"releaseId": release_id},
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    csv_url = data.get("url")
    if not csv_url:
        return []
    csv_resp = requests.get(csv_url, timeout=300)
    csv_resp.raise_for_status()
    content = csv_resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content), delimiter=";")
    return list(reader)


def _get_analytics(token: str, release_id: str) -> dict:
    resp = requests.get(
        f"{_BASE_URL}/releases/{release_id}/analytics",
        headers=_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        data = data[0] if data else {}
    return data


def _contar(token: str, release_id: str, total_limpo_anterior: int | None = None) -> dict | None:
    try:
        leads = _export_leads(token, release_id)
    except Exception:
        logger.exception("sendflow_contagem: falha ao consultar export-leads (release %s)", release_id)
        return None

    numeros_todos: set[str] = set()
    numeros_limpo: set[str] = set()
    for lead in leads:
        numero = _numero_do_lead(lead)
        if not numero:
            continue
        numeros_todos.add(numero)
        if numero not in ADMIN_NUMBERS_BASE:
            numeros_limpo.add(numero)

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
    try:
        analytics = _get_analytics(token, release_id)
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d%m%Y")
        entradas_hoje = analytics.get("add", {}).get("dates", {}).get(hoje, 0)
        saidas_hoje = analytics.get("remove", {}).get("dates", {}).get(hoje, 0)
    except Exception:
        logger.exception("sendflow_contagem: falha ao consultar /analytics (release %s)", release_id)

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

        # completo = toda chave esperada veio de uma leitura NOVA bem-sucedida
        # nesse ciclo — se alguma foi reaproveitada do anterior (ou faltou),
        # cache curto pra tentar de novo em breve.
        completo = blocos_frescos == len(blocos_esperados)
        resultado_final = resultado or None
        _cache[code] = (time.time(), resultado_final, completo)
        return resultado_final
