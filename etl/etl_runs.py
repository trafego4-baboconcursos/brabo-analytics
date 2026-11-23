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


def encerrar_orfas(motivo: str = "Interrompida: o scheduler reiniciou (deploy) durante a rodada") -> int:
    """Fecha como 'error' toda rodada ainda 'running'. Chamar SÓ no boot do scheduler.

    Um deploy mata o container no meio de uma rodada; o `finish_run` nunca roda e a linha
    fica 'running' para sempre (viram dias de lixo no etl_runs e escondem se o ETL anda).
    No boot nenhuma rodada deste processo existe ainda, então tudo que está 'running' é de um
    processo morto. Se um container antigo ainda estiver terminando de verdade, o `finish_run`
    dele sobrescreve o status depois (UPDATE por id) — sem perda.
    Devolve quantas linhas fechou (0 se o banco estiver indisponível).
    """
    try:
        from datetime import datetime, timezone
        from sqlalchemy import text
        with _engine().begin() as conn:
            res = conn.execute(
                text("""
                    UPDATE etl_runs
                       SET status = 'error', finished_at = :agora, error_message = :motivo
                     WHERE status = 'running'
                """),
                {"agora": datetime.now(timezone.utc), "motivo": motivo},
            )
            return int(res.rowcount or 0)
    except Exception:
        logger.warning("Não foi possível encerrar as rodadas órfãs do etl_runs", exc_info=True)
        return 0


def minutos_desde_ultimo_ok(fontes: tuple[str, ...]) -> float | None:
    """Minutos desde o fim da última rodada 'ok' de qualquer uma das `fontes` (None se nunca)."""
    try:
        from datetime import datetime, timezone
        from sqlalchemy import bindparam, text
        consulta = text(
            "SELECT MAX(finished_at) FROM etl_runs WHERE status = 'ok' AND source IN :fontes"
        ).bindparams(bindparam("fontes", expanding=True))
        with _engine().connect() as conn:
            ultimo = conn.execute(consulta, {"fontes": list(fontes)}).scalar()
        if ultimo is None:
            return None
        if isinstance(ultimo, str):
            ultimo = datetime.fromisoformat(ultimo)
        if ultimo.tzinfo is None:
            ultimo = ultimo.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ultimo).total_seconds() / 60.0
    except Exception:
        logger.warning("Não foi possível consultar a última rodada ok do etl_runs", exc_info=True)
        return None
