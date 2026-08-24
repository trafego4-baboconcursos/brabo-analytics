"""
frontend/cache.py — Cache em memória com TTL para o Brabo Analytics.
"""
from __future__ import annotations

import threading
import time as _time_module
from typing import Any, Callable

# ── Cache com TTL ──────────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE_TTL: int = 3600       # 60 minutos
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


def _set_cached(launch_code: str, reader: str, value: Any, ttl: int | None = None) -> None:
    if len(_CACHE) >= _CACHE_MAX_SIZE:
        sorted_keys = sorted(_CACHE, key=lambda k: _CACHE[k][1])
        for k in sorted_keys[:_CACHE_MAX_SIZE // 5]:
            del _CACHE[k]
    _CACHE[_cache_key(launch_code, reader)] = (value, _time_module.time() + (ttl or _CACHE_TTL))


def _invalidate(launch_code: str) -> list[str]:
    # Algumas entradas usam chave composta (ex.: comparativo, que cacheia sob
    # "{codigo_anterior}_{codigo_atual}::comparativo") — códigos de lançamento
    # nunca têm "_" (usam "-"), então dá pra separar com segurança e casar
    # launch_code em qualquer posição, não só como prefixo exato da chave.
    keys = [k for k in _CACHE if launch_code in k.split("::", 1)[0].split("_")]
    for k in keys:
        del _CACHE[k]
    return sorted({k.split("::", 1)[1] if "::" in k else k for k in keys})


# ── Single-flight ──────────────────────────────────────────────────────────────
# Requisições paralelas com cache frio disparavam a mesma consulta 3-4x
# (ex.: read_vendas via f_meta + f_google + f_vendas no mesmo gather).
# Com um lock por chave, a primeira chamada computa e as demais aguardam
# e reutilizam o resultado.
_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        return _KEY_LOCKS.setdefault(key, threading.Lock())


# Sentinela para memorizar "compute() retornou None" — sem isso, lançamentos ainda
# sem dados (ex: em captação, carrinho fechado) pagavam a consulta pesada em toda
# visita, porque None nunca entrava no cache. Fica encapsulado aqui: quem usa
# _get_cached/_set_cached direto nunca vê o sentinela.
_NONE_RESULT = object()


def _store(launch_code: str, reader: str, value: Any) -> None:
    # "sem dados" expira em 10 min: quando o dado aparecer (ex: carrinho
    # abriu, ETL upsertou), a página reflete logo, sem esperar o TTL de 1h.
    if value is None:
        _set_cached(launch_code, reader, _NONE_RESULT, ttl=600)
    else:
        _set_cached(launch_code, reader, value)


def _get_or_compute(launch_code: str, reader: str, compute: Callable[[], Any]) -> Any:
    """Cache com single-flight e stale-while-revalidate: com a entrada expirada,
    devolve o valor antigo na hora e recomputa num thread de fundo — nenhum
    request paga a consulta pesada, exceto no primeiro acesso pós-boot."""
    key = _cache_key(launch_code, reader)
    entry = _CACHE.get(key)
    if entry is not None:
        value, expires_at = entry
        if _time_module.time() <= expires_at:
            return None if value is _NONE_RESULT else value
        lock = _lock_for(key)
        if lock.acquire(blocking=False):
            def _bg():
                try:
                    _store(launch_code, reader, compute())
                except Exception:
                    from logger import get_logger  # noqa: PLC0415 — evita import na carga do módulo
                    get_logger("cache").exception("Refresh em background falhou: %s", key)
                finally:
                    lock.release()
            threading.Thread(target=_bg, daemon=True).start()
        return None if value is _NONE_RESULT else value
    with _lock_for(key):
        entry = _CACHE.get(key)
        if entry is not None:  # outro thread computou enquanto esperávamos o lock
            value, _ = entry
            return None if value is _NONE_RESULT else value
        value = compute()
        _store(launch_code, reader, value)
        return value
