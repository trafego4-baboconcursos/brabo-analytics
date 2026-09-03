"""
frontend/cache.py — Cache em memória com TTL para o Brabo Analytics.
"""
from __future__ import annotations

import contextvars
import threading
import time as _time_module
from typing import Any, Callable

# ── Cache com TTL ──────────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[Any, float]] = {}
_STORED_AT: dict[str, float] = {}   # quando cada chave foi gravada (ver refresh forçado)
_CACHE_TTL: int = 3600       # 60 minutos
_CACHE_MAX_SIZE: int = 2000  # máx de entradas; evicta 20% das mais antigas ao exceder

# ── Refresh forçado (re-aquecimento pós-ETL) ───────────────────────────────────
# Depois do ETL o dado no banco mudou, mas apagar o cache e re-aquecer abria
# uma janela fria de minutos a cada rodada (30 min): quem abrisse a página
# nesse meio-tempo pagava tudo do zero. Em vez disso, o aquecimento roda com
# este contextvar setado (propaga pros threads do run_in_threadpool): dentro
# dele, _get_or_compute recomputa de forma síncrona e grava por cima; fora
# dele, as requisições normais continuam recebendo o valor antigo na hora.
# O timestamp evita recomputar duas vezes a mesma chave num mesmo
# aquecimento (ex.: read_vendas chamado por meta, google e vendas).
_FORCE_REFRESH_SINCE: contextvars.ContextVar[float | None] = contextvars.ContextVar("bs_force_refresh_since", default=None)


def force_refresh_start() -> contextvars.Token:
    return _FORCE_REFRESH_SINCE.set(_time_module.time())


def force_refresh_end(token: contextvars.Token) -> None:
    _FORCE_REFRESH_SINCE.reset(token)


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
            _STORED_AT.pop(k, None)
    key = _cache_key(launch_code, reader)
    now = _time_module.time()
    _CACHE[key] = (value, now + (ttl or _CACHE_TTL))
    _STORED_AT[key] = now


def _invalidate(launch_code: str) -> list[str]:
    # Algumas entradas usam chave composta (ex.: comparativo, que cacheia sob
    # "{codigo_anterior}_{codigo_atual}::comparativo") — códigos de lançamento
    # nunca têm "_" (usam "-"), então dá pra separar com segurança e casar
    # launch_code em qualquer posição, não só como prefixo exato da chave.
    keys = [k for k in _CACHE if launch_code in k.split("::", 1)[0].split("_")]
    for k in keys:
        del _CACHE[k]
        _STORED_AT.pop(k, None)
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


def _store(launch_code: str, reader: str, value: Any, ttl: int | None = None) -> None:
    # "sem dados" expira em 10 min: quando o dado aparecer (ex: carrinho
    # abriu, ETL upsertou), a página reflete logo, sem esperar o TTL padrão.
    if value is None:
        _set_cached(launch_code, reader, _NONE_RESULT, ttl=min(ttl, 600) if ttl else 600)
    else:
        _set_cached(launch_code, reader, value, ttl=ttl)


def _get_or_compute(launch_code: str, reader: str, compute: Callable[[], Any], ttl: int | None = None) -> Any:
    """Cache com single-flight e stale-while-revalidate: com a entrada expirada,
    devolve o valor antigo na hora e recomputa num thread de fundo — nenhum
    request paga a consulta pesada, exceto no primeiro acesso pós-boot.

    `ttl` (segundos) sobrescreve o padrão de 1h — usar em leitores baratos que
    são alimentados por um ETL periódico (ex.: whatsapp_sheets_*, consulta
    leve e atualizada a cada 30 min), pra refletir o dado novo mais rápido
    sem precisar esperar o TTL longo pensado pras consultas pesadas."""
    key = _cache_key(launch_code, reader)
    force_since = _FORCE_REFRESH_SINCE.get()
    if force_since is not None and _STORED_AT.get(key, 0.0) < force_since:
        # Re-aquecimento pós-ETL: recomputa agora e grava por cima (quem está
        # fora deste contexto segue lendo o valor antigo até a gravação).
        with _lock_for(key):
            if _STORED_AT.get(key, 0.0) < force_since:  # outro thread do mesmo aquecimento pode ter gravado
                _store(launch_code, reader, compute(), ttl=ttl)
        value, _ = _CACHE[key]
        return None if value is _NONE_RESULT else value
    entry = _CACHE.get(key)
    if entry is not None:
        value, expires_at = entry
        if _time_module.time() <= expires_at:
            return None if value is _NONE_RESULT else value
        lock = _lock_for(key)
        if lock.acquire(blocking=False):
            def _bg():
                try:
                    _store(launch_code, reader, compute(), ttl=ttl)
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
        _store(launch_code, reader, value, ttl=ttl)
        return value
