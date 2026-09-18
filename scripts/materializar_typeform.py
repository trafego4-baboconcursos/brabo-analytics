"""Recria `typeform_respostas_valores` a partir das três tabelas de origem.

Roda uma vez. Só precisa rodar de novo se `typeform_respostas` receber dado novo
— o que hoje só acontece se alguém executar `etl/etl_typeform.py` à mão (a conta
do Typeform foi cancelada e o script saiu do scheduler).

Por que a tabela existe: o `answers` cru carrega o metadado do Typeform (id, tipo
e ref de cada resposta) que o frontend descarta em `_reconstruct_tabular_df`.
São 4.844 bytes por linha contra 951 só dos valores. Uma leitura do PI-AGO-26
caiu de 464 MB para 48 MB, e a consulta parou de estourar o `statement_timeout`
de 30s, que derrubava a seção metade das vezes.

A extração roda toda no servidor (jsonb_array_elements + jsonb_object_agg), então
a recriação não transporta dado nenhum — não gera egress.

Uso:
    python scripts/materializar_typeform.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

from sqlalchemy import text  # noqa: E402

from frontend.db import _get_engine  # noqa: E402

SQL_PATH = _RAIZ / "etl" / "materializar_typeform.sql"


def _statements(sql: str) -> list[str]:
    # Split simples por ";" — o arquivo não tem ponto e vírgula dentro de
    # literal nem de comentário (já quebrou por causa disso uma vez).
    return [
        s.strip()
        for s in sql.split(";")
        if s.strip()
        and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines())
    ]


def main() -> int:
    sql = SQL_PATH.read_text(encoding="utf-8")
    with _get_engine().connect() as conn:
        conn.execute(text("COMMIT"))
        # O CREATE TABLE AS explode ~990 mil arrays jsonb e derrama pra disco:
        # levou ~25 min na primeira carga, muito acima dos 30s do pool.
        conn.execute(text("SET statement_timeout = '3600s'"))
        conn.execute(text("COMMIT"))
        for i, stmt in enumerate(_statements(sql), 1):
            cabeca = " ".join(stmt.split())[:60]
            t0 = time.time()
            conn.execute(text(stmt))
            conn.execute(text("COMMIT"))
            print(f"{i}. ok ({time.time() - t0:>5.0f}s)  {cabeca}", flush=True)

        n = conn.execute(text("SELECT count(*) FROM typeform_respostas_valores")).scalar()
        med = conn.execute(
            text("SELECT avg(octet_length(valores::text)) FROM typeform_respostas_valores")
        ).scalar()
    print(f"pronto: {n:,} linhas, {float(med or 0):,.0f} bytes por linha em média")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
