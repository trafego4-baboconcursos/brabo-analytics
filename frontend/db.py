"""
frontend/db.py — Engines SQLAlchemy cacheadas para os dois bancos Supabase.

Pool tuning, statement_timeout e o guard de somente-leitura vivem em
src/db_engine.py (compartilhado com etl/db.py) para não divergir entre
ETL e frontend.
"""
from __future__ import annotations

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
