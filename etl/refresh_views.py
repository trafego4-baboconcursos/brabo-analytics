"""
Atualiza as materialized views de atribuição (rodado ao fim de cada ciclo do
run_all.py). Hoje: mv_atribuicao_publicos (vendas por público/conjunto).

    python etl/refresh_views.py
"""
import sys
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from db import get_engine
from logger import get_logger

logger = get_logger("etl.refresh_views")

MVS = ["mv_atribuicao_publicos"]


def main():
    engine = get_engine()
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text("SET statement_timeout = '300000'"))
        for mv in MVS:
            exists = conn.execute(
                text("SELECT 1 FROM pg_matviews WHERE matviewname = :m"), {"m": mv}
            ).fetchone()
            if not exists:
                logger.info("Criando materialized view %s...", mv)
                conn.execute(text(
                    f"CREATE MATERIALIZED VIEW {mv} AS SELECT * FROM view_atribuicao_publicos"
                ))
                conn.execute(text(
                    f"CREATE UNIQUE INDEX idx_{mv} ON {mv} (lancamento_codigo, fonte, publico)"
                ))
            else:
                # CONCURRENTLY: leitores do dashboard não bloqueiam durante o refresh
                conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}"))
            logger.info("%s atualizada.", mv)


if __name__ == "__main__":
    main()
