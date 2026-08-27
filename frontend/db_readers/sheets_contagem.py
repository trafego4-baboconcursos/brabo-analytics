"""
frontend/db_readers/sheets_contagem.py — Lê TOTAL LEADS / TOTAL LIMPO direto
da planilha do Google Sheets que o sendflow-analytics-poller mantém
atualizada (mesmo número que a equipe já acompanha lá).

Não recalcula nada aqui — o poller é quem calcula (dedup por telefone,
exclusão de admin) e escreve na planilha; este módulo só lê essas duas
células. Mapeamento lançamento -> planilha em config/sheets_contagem.yaml.

Credencial: GOOGLE_SHEETS_CONTAGEM_JSON (conteúdo do JSON da service
account) — a mesma usada pelo próprio poller pra escrever nessas
planilhas, então já tem acesso garantido sem precisar compartilhar de
novo. Separada da GOOGLE_SERVICE_ACCOUNT_JSON existente (essa é de outra
conta, usada só pras miniaturas do Drive).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import yaml

from logger import get_logger

logger = get_logger("db")

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sheets_contagem.yaml"
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_CACHE_TTL = 900  # 15 minutos — evita bater na API do Sheets a cada request
_cache: dict[str, tuple[float, dict | None]] = {}


def _load_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _service():
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    sa_json = os.environ.get("GOOGLE_SHEETS_CONTAGEM_JSON")
    if not sa_json:
        return None
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json), scopes=_SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ler_bloco(svc, sheet_id: str, bloco: dict) -> dict | None:
    aba = bloco["aba"]
    linha_resumo = bloco["linha_resumo"]
    linha_total_limpo = bloco["linha_total_limpo"]
    try:
        r = svc.spreadsheets().values().batchGet(
            spreadsheetId=sheet_id,
            ranges=[
                f"'{aba}'!G{linha_resumo}",
                f"'{aba}'!G{linha_total_limpo}",
            ],
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        valores = r.get("valueRanges", [])
        total = valores[0].get("values", [[0]])[0][0] if valores[0].get("values") else 0
        total_limpo = valores[1].get("values", [[0]])[0][0] if valores[1].get("values") else 0
        return {"total": int(total or 0), "total_limpo": int(total_limpo or 0)}
    except Exception:
        logger.exception("sheets_contagem: falha ao ler aba '%s' da planilha %s", aba, sheet_id)
        return None


def ler_contagem_sheets(code: str) -> dict | None:
    """Retorna {"normal": {"total":.., "total_limpo":..}, "vip": {...}} pro
    lançamento, lendo direto do Sheets. None se não houver credencial, não
    houver mapeamento pra esse código, ou a leitura falhar."""
    cached = _cache.get(code)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]

    cfg = _load_config().get(code)
    if not cfg:
        return None

    svc = _service()
    if svc is None:
        return None

    sheet_id = cfg["sheet_id"]
    resultado = {}
    if "normal" in cfg:
        r = _ler_bloco(svc, sheet_id, cfg["normal"])
        if r:
            resultado["normal"] = r
    if "vip" in cfg:
        r = _ler_bloco(svc, sheet_id, cfg["vip"])
        if r:
            resultado["vip"] = r

    resultado = resultado or None
    _cache[code] = (time.time(), resultado)
    return resultado
