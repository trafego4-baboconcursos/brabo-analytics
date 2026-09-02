"""Helpers utilitários sem dependência de banco de dados."""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

from logger import get_logger

logger = get_logger("db")


def _norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return text.encode("ascii", "ignore").decode("ascii").strip().lower()


def _extract_launch_code(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "code"):
        return str(value.code)
    val_str = str(value)
    match = re.search(r"\[([A-Z0-9_-]+)\]", val_str)
    if match:
        return match.group(1)
    return os.path.basename(val_str).replace("[", "").replace("]", "")


def _safe_div(num: float, den: float) -> float:
    return round(num / den, 2) if den else 0.0


def _normalize_ad_code(code: str) -> str:
    """Normaliza ADxxx pro número sem zero-padding (AD004/AD04/AD4 -> AD4) —
    lançamentos antigos nomeavam sem padronização de zeros, então a
    comparação "já usado antes" tem que ignorar isso."""
    match = re.match(r"AD0*(\d+)$", str(code or "").strip(), re.IGNORECASE)
    return f"AD{match.group(1)}" if match else str(code or "").upper()


def _delta(a: float, b: float) -> float:
    """Retorna Δ% de a→b. Positivo = crescimento."""
    if not a or a == 0:
        return 0.0
    return round((b - a) / abs(a) * 100, 1)


def _safe_date(val):
    """Converte val para datetime.date; retorna None se inválido."""
    from datetime import date as _dt_date, datetime as _dt_datetime
    if val is None:
        return None
    if isinstance(val, _dt_date) and not isinstance(val, _dt_datetime):
        return val
    if isinstance(val, _dt_datetime):
        return val.date()
    try:
        return _dt_datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning("Data inválida ignorada: %r", val)
        return None


def _normalize_product_ids(values: Any) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for item in values:
        token = str(item).strip()
        if token:
            out.append(token)
    return out
