"""Registra execuções de ETL na tabela etl_runs para histórico e alertas."""
from __future__ import annotations
import sys
from pathlib import Path

_ETL_DIR = Path(__file__).parent
# src/ primeiro, depois etl/ por cima — etl/ precisa vencer a resolução de
# "import db" (existe um pacote src/db/ com o mesmo nome, camada legada de
# SQLite, que não tem get_engine() e quebrava start_run/finish_run em silêncio).
sys.path.insert(0, str(_ETL_DIR.parent / "src"))
sys.path.insert(0, str(_ETL_DIR))
from logger import get_logger

logger = get_logger("etl.runs")


def _engine():
    from db import get_engine
    return get_engine()


def start_run(source: str) -> int | None:
    """Insere registro 'running' e retorna run_id (None se DB indisponível)."""
    try:
        from sqlalchemy import text
        with _engine().begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO etl_runs (source, started_at, status)
                    VALUES (:source, NOW(), 'running')
                    RETURNING id
                """),
                {"source": source},
            ).fetchone()
            return row[0] if row else None
    except Exception:
        logger.warning("Não foi possível registrar início do ETL '%s' — continuando sem tracking", source)
        return None


def finish_run(
    run_id: int | None,
    *,
    status: str,
    rows: int = 0,
    error: str | None = None,
) -> None:
    """Atualiza registro com resultado final. Silencioso se run_id for None."""
    if run_id is None:
        return
    try:
        from sqlalchemy import text
        with _engine().begin() as conn:
            conn.execute(
                text("""
                    UPDATE etl_runs
                       SET finished_at    = NOW(),
                           status         = :status,
                           rows_upserted  = :rows,
                           error_message  = :error
                     WHERE id = :id
                """),
                {"id": run_id, "status": status, "rows": rows, "error": error},
            )
    except Exception:
        logger.warning("Não foi possível registrar fim do ETL (run_id=%s)", run_id)
