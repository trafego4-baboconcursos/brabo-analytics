"""
frontend/db.py — Engines SQLAlchemy cacheadas para os dois bancos Supabase.

Pool tuning, statement_timeout e o guard de somente-leitura vivem em
src/db_engine.py (compartilhado com etl/db.py) para não divergir entre
ETL e frontend.
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text

from db_engine import make_engine

_engine = None        # analytics (meta_ads_daily, google_ads_daily, leads, …)
_users_engine = None  # operacional (users, hotmart, tmb, launch_config, …)


def _get_engine():
    global _engine
    if _engine is None:
        _engine = make_engine("SUPABASE_DB_URL")
    return _engine


def _get_users_engine():
    global _users_engine
    if _users_engine is None:
        _users_engine = make_engine("SUPABASE_USERS_URL", readonly_guard=True)
    return _users_engine


@lru_cache(maxsize=32)
def colunas_da_tabela(tabela: str) -> frozenset[str]:
    """Nomes de coluna de `tabela` no banco analytics, cacheado pelo processo.

    Serve para o reader montar o SELECT sem quebrar quando uma coluna nova ainda
    não foi migrada em produção — o caso de `etapa`/`temperatura`/`segmento`, que
    o ETL passou a gravar em 21/09/26. Sem isso, subir o código antes de rodar
    `scripts/migrar_classificacao_campanhas.py` derrubaria todas as páginas de
    anúncio de uma vez.
    """
    try:
        with _get_engine().connect() as conn:
            linhas = conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
                {"t": tabela},
            ).fetchall()
        return frozenset(r[0] for r in linhas)
    except Exception:
        return frozenset()
