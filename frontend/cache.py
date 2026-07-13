"""
frontend/cache.py — Cache em memória com TTL para o Brabo Analytics.
"""
from __future__ import annotations

import time as _time_module
from typing import Any

# ── Cache com TTL ──────────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE_TTL: int = 1800       # 30 minutos
_CACHE_MAX_SIZE: int = 2000  # máx de entradas; evicta 20% das mais antigas ao exceder


def _cache_key(launch_code: str, reader: str) -> str:
    return f"{launch_code}::{reader}"


def _get_cached(launch_code: str, reader: str) -> Any:
    entry = _CACHE.get(_cache_key(launch_code, reader))
    if entry is None:
        return None
    value, expires_at = entry
    if _time_module.time() > expires_at:
        del _CACHE[_cache_key(launch_code, reader)]
        return None
    return value


def _set_cached(launch_code: str, reader: str, value: Any) -> None:
    if len(_CACHE) >= _CACHE_MAX_SIZE:
        sorted_keys = sorted(_CACHE, key=lambda k: _CACHE[k][1])
        for k in sorted_keys[:_CACHE_MAX_SIZE // 5]:
            del _CACHE[k]
    _CACHE[_cache_key(launch_code, reader)] = (value, _time_module.time() + _CACHE_TTL)


def _invalidate(launch_code: str) -> None:
    keys = [k for k in _CACHE if k.startswith(f"{launch_code}::")]
    for k in keys:
        del _CACHE[k]
