"""
src/db_engine.py — Fábrica compartilhada de engines SQLAlchemy para os dois bancos Supabase.

Usado por etl/db.py (leitura+escrita) e frontend/db.py (leitura, com guard de
escrita nas tabelas somente-leitura). Centraliza pool tuning e statement_timeout
para não divergir entre ETL e frontend.
"""
from __future__ import annotations

import os
from sqlalchemy import create_engine

READONLY_TABLES = {"tmb_clean_oficial", "hotmart_clean_oficial"}

# Analytics DB: pool maior para suportar gather() paralelo (6+ threads simultâneas).
# Operacional: menor pois Supabase hobby tem limite de conexões.
_POOL_CONFIG = {
    "SUPABASE_DB_URL":    {"pool_size": 10, "max_overflow": 5},
    "SUPABASE_USERS_URL": {"pool_size": 3,  "max_overflow": 2},
}


def make_engine(env_var: str, readonly_guard: bool = False):
    """Cria uma engine SQLAlchemy configurada a partir da URL em `env_var`.

    `readonly_guard=True` bloqueia INSERT/UPDATE/DELETE/TRUNCATE/DROP/ALTER
    contra as tabelas em READONLY_TABLES (usado pelo frontend, que só lê essas
    tabelas — quem escreve nelas é o ETL, com readonly_guard=False).
    """
    from sqlalchemy import event
    from sqlalchemy.engine import URL as SA_URL
    from urllib.parse import urlparse, unquote

    raw = os.environ[env_var]
    p = urlparse(raw)
    pool = _POOL_CONFIG.get(env_var, {"pool_size": 5, "max_overflow": 5})
    eng = create_engine(
        SA_URL.create(
            "postgresql+psycopg2",
            username=unquote(p.username or ""),
            password=unquote(p.password or ""),
            host=p.hostname,
            port=p.port or 5432,
            database=(p.path or "/postgres").lstrip("/"),
        ),
        pool_size=pool["pool_size"], max_overflow=pool["max_overflow"],
        pool_timeout=60, pool_recycle=1800, pool_pre_ping=True,
    )

    @event.listens_for(eng, "checkout")
    def _set_statement_timeout(dbapi_conn, connection_record, connection_proxy):
        # SET via SQL (não connect_args={"options": ...}) porque em pooler de
        # transaction mode (porta 6543) a conexão física é compartilhada entre
        # clientes diferentes — opções de startup só valem na primeira vez que
        # aquela conexão física foi aberta, não a cada checkout. Rodar o SET
        # aqui garante o limite de 30s em qualquer modo do pooler.
        cursor = dbapi_conn.cursor()
        cursor.execute("SET statement_timeout = 30000")
        cursor.close()

    if readonly_guard:
        @event.listens_for(eng, "before_cursor_execute")
        def _block_writes(conn, cursor, statement, parameters, context, executemany):
            stmt_upper = statement.strip().upper()
            if stmt_upper.startswith(("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER")):
                for table in READONLY_TABLES:
                    if table.upper() in stmt_upper:
                        raise PermissionError(f"Escrita bloqueada: tabela '{table}' é somente leitura.")
    return eng
