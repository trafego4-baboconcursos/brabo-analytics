"""Acesso à área Comercial: nível por e-mail (`comercial_acessos`) e matriz de permissões."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from frontend.db import _get_users_engine

_CACHE_TTL = 60.0
_cache: dict[str, tuple[float, dict | None]] = {}

# master == coordenador (decisão 06/11/26): tudo. vendedor: só o próprio + reivindicar.
_TUDO = {"ver_time", "editar_regras", "editar_participacoes", "aprovar", "lancar_bonus",
         "fechar_mes", "ver_proprio", "reivindicar"}
_PERMISSOES: dict[str, set[str]] = {
    "master": _TUDO,
    "coordenador": _TUDO,
    "vendedor": {"ver_proprio", "reivindicar"},
}


@dataclass(frozen=True)
class AcessoComercial:
    nivel: str
    vendedor_codigo: str | None = None


def limpar_cache() -> None:
    _cache.clear()


def _ler_banco(email: str) -> dict | None:
    with _get_users_engine().connect() as conn:
        r = conn.execute(
            text("SELECT nivel, vendedor_codigo FROM comercial_acessos WHERE lower(email) = :e"),
            {"e": email},
        ).mappings().first()
    return dict(r) if r else None


def _ler_padrao(email: str) -> dict | None:
    agora = time.monotonic()
    hit = _cache.get(email)
    if hit and agora - hit[0] < _CACHE_TTL:
        return hit[1]
    try:
        linha = _ler_banco(email)
    except ProgrammingError as exc:
        if "comercial_acessos" in str(exc) and "does not exist" in str(exc):
            return None  # tabela ainda não criada (nasce na 1ª escrita)
        raise
    _cache[email] = (agora, linha)
    return linha


def acesso_comercial(user: dict, *, ler: Callable[[str], dict | None] | None = None) -> AcessoComercial | None:
    if (user or {}).get("role") == "admin":
        return AcessoComercial("master", None)
    email = ((user or {}).get("email") or "").strip().lower()
    if not email:
        return None
    linha = (ler or _ler_padrao)(email)
    if not linha:
        return None
    return AcessoComercial(linha["nivel"], linha.get("vendedor_codigo"))


def nivel_comercial(user: dict, *, ler: Callable[[str], dict | None] | None = None) -> str | None:
    a = acesso_comercial(user, ler=ler)
    return a.nivel if a else None


def pode(nivel: str | None, acao: str) -> bool:
    return acao in _PERMISSOES.get(nivel or "", set())
