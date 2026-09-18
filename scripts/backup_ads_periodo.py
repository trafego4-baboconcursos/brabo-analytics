"""
scripts/backup_ads_periodo.py — Copia local das linhas de anúncio de um período.

Existe por causa do upsert do ETL: sem `--launch-code`, ele faz DELETE do
período inteiro e reinsere o que a API devolveu. Se a busca vier incompleta
(rate limit, conta fora da lista, queda no meio), o que sumiu não volta. Este
script tira a foto antes, pra dar pra restaurar.

    python scripts/backup_ads_periodo.py --since 2026-05-01 --until 2026-09-18

Gera em outputs/: um CSV por tabela + um resumo por lançamento, que é o que se
compara depois do backfill pra saber se algum lançamento perdeu gasto.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from frontend.db import _get_engine  # noqa: E402

TABELAS = {"meta_ads_daily": "spend", "google_ads_daily": "cost"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Backup das linhas de anúncio de um período.")
    ap.add_argument("--since", required=True, metavar="YYYY-MM-DD")
    ap.add_argument("--until", required=True, metavar="YYYY-MM-DD")
    args = ap.parse_args()

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = Path("outputs")
    destino.mkdir(exist_ok=True)
    engine = _get_engine()

    resumos = []
    for tabela, col_custo in TABELAS.items():
        df = pd.read_sql(
            text(f"SELECT * FROM {tabela} WHERE date BETWEEN :s AND :u"),
            engine, params={"s": args.since, "u": args.until},
        )
        arq = destino / f"backup_{tabela}_{args.since}_a_{args.until}_{carimbo}.csv"
        df.to_csv(arq, index=False, encoding="utf-8")
        print(f"{tabela}: {len(df):,} linhas -> {arq}")

        r = (df.groupby(df["lancamento_codigo"].fillna("(sem codigo)"))[col_custo]
               .sum().round(2).reset_index())
        r.columns = ["lancamento", "gasto"]
        r.insert(0, "tabela", tabela)
        resumos.append(r)

    resumo = pd.concat(resumos, ignore_index=True)
    arq_resumo = destino / f"backup_resumo_{carimbo}.csv"
    resumo.to_csv(arq_resumo, index=False, encoding="utf-8")
    print(f"\nresumo por lançamento -> {arq_resumo}")
    print(resumo.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
