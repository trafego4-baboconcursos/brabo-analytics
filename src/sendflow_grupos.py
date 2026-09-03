"""
src/sendflow_grupos.py — Primitivas compartilhadas de acesso à API da SendFlow
pra contagem de grupos de WhatsApp (export-leads, analytics, grupos cheios).

Compartilhado entre frontend/db_readers/sendflow_contagem.py (cálculo "hoje",
ao vivo, cacheado em memória por request) e etl/etl_whatsapp_grupos.py
(snapshot diário persistido no banco) — pra ADMIN_NUMBERS_BASE e a lógica de
extração/dedupe nunca divergirem entre os dois usos, mesmo padrão de
src/db_engine.py (compartilhado entre etl/db.py e frontend/db.py).

Config (release_id por lançamento) em config/sendflow_contagem.yaml; token
por env var (token_env indicado na config).
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any

import requests
import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sendflow_contagem.yaml"
BASE_URL = "https://sendapi.sendflow.pro"

# Releases que devolveram erro de CONFIGURAÇÃO (400/404) — ex: "Campanha sem
# contas associadas!", release inexistente. Não adianta tentar de novo: só se
# resolve mexendo na configuração lá no SendFlow. Uma vez bloqueado, para de
# bater na API pra esse release_id até o processo reiniciar (ex: próximo
# deploy, depois de alguém corrigir lá). Compartilhado entre frontend e ETL
# (cada processo mantém sua própria lista, reiniciando quando o processo dele
# reinicia — não é persistido).
#
# 401/403 ficam DE FORA de propósito: a SendFlow devolve 403 quando está
# limitando taxa (não 429), então tratar 403 como permanente bloquearia pra
# sempre um release que só estava momentaneamente limitado — confirmado em
# 2026-09-03, quando PBB-AGO-26 normal deu 403 numa chamada e 200 na
# seguinte. Esses continuam no retry curto.
RELEASES_BLOQUEADOS: set[str] = set()
STATUS_PERMANENTES = {400, 404}

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


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _headers(token: str) -> dict:
    return {"accept": "application/json", "Authorization": f"Bearer {token}"}


def numero_do_lead(lead: dict) -> str:
    # Mesma lógica do poller — CSV com colunas Posição;Grupo;Nome;Número.
    raw = lead.get("Número") or lead.get("Numero") or lead.get("number") or ""
    raw = str(raw).lstrip("'").split("@")[0]
    return "".join(ch for ch in raw if ch.isdigit())


def export_leads(token: str, release_id: str) -> list[dict]:
    resp = requests.post(
        f"{BASE_URL}/actions/export-leads",
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


def tratar_falha_export_leads(exc: Exception, release_id: str, logger) -> None:
    """Chamado do except de export_leads(): se o erro for de configuração
    (400/404), marca o release em RELEASES_BLOQUEADOS pra parar de repetir a
    consulta; senão só loga normal (401/403 é rate limit, continua no retry)."""
    status = None
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        status = exc.response.status_code
    if status in STATUS_PERMANENTES:
        RELEASES_BLOQUEADOS.add(release_id)
        corpo = ""
        try:
            corpo = (exc.response.json() or {}).get("message") or ""
        except Exception:
            pass
        logger.warning(
            "release %s devolveu %s%s — erro de configuração no SendFlow, não adianta "
            "repetir; parando de consultar esse release até o processo reiniciar",
            release_id, status, f' ("{corpo}")' if corpo else "",
        )
    else:
        logger.exception("falha ao consultar export-leads (release %s)", release_id)


def get_analytics(token: str, release_id: str) -> dict:
    """Retorna {"add": {"total":N, "dates":{"ddmmyyyy":n,...}}, "remove": {...}}
    — histórico DIÁRIO completo desde o início da campanha, não só hoje."""
    resp = requests.get(
        f"{BASE_URL}/releases/{release_id}/analytics",
        headers=_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        data = data[0] if data else {}
    return data


def list_groups(token: str, release_id: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/releases/{release_id}/groups",
        headers=_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("data", [])


def contar_grupos_cheios(token: str, release_id: str) -> int:
    grupos = list_groups(token, release_id)
    return sum(1 for g in grupos if g.get("full"))


def contar_numeros(leads: list[dict]) -> tuple[set[str], set[str]]:
    """Retorna (numeros_todos, numeros_limpo_sem_admin)."""
    numeros_todos: set[str] = set()
    numeros_limpo: set[str] = set()
    for lead in leads:
        numero = numero_do_lead(lead)
        if not numero:
            continue
        numeros_todos.add(numero)
        if numero not in ADMIN_NUMBERS_BASE:
            numeros_limpo.add(numero)
    return numeros_todos, numeros_limpo
