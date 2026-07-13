"""
etl/db.py — Engines SQLAlchemy cacheadas para os dois bancos Supabase.

Pool tuning e statement_timeout vivem em src/db_engine.py (compartilhado com
frontend/db.py). O ETL não usa o guard de somente-leitura: import_vendas.py
é o autor legítimo de hotmart_clean_oficial/tmb_clean_oficial.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from db_engine import make_engine

_engine = None
_users_engine = None


def get_engine():
    """Engine do banco analytics (meta_ads_daily, google_ads_daily, leads, dim_lancamentos)."""
    global _engine
    if _engine is None:
        _engine = make_engine("SUPABASE_DB_URL")
    return _engine


def get_users_engine():
    """Engine do banco operacional (hotmart_clean_oficial, tmb_clean_oficial, users, launch_config)."""
    global _users_engine
    if _users_engine is None:
        _users_engine = make_engine("SUPABASE_USERS_URL")
    return _users_engine
