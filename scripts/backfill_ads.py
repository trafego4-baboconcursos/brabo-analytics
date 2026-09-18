"""
scripts/backfill_ads.py — Reprocessa anúncio por fatias mensais.

Por que fatiar: pedir insights de vários meses numa sequência só faz o Meta
devolver **500 Internal Server Error** — a consulta é nível anúncio com quebra
diária, e o volume estoura do lado deles (aconteceu em 18/09/26 com a janela
mai–set). Fatiar por mês também reduz o estrago de uma falha: o upsert do ETL
apaga o período pedido antes de reinserir, então um mês que falha deixa os
outros intactos, em vez de comprometer tudo.

    python scripts/backfill_ads.py --since 2026-05-01 --until 2026-09-18 --fonte meta
    python scripts/backfill_ads.py --since 2026-05-01 --until 2026-09-18 --fonte google

Rode `scripts/backup_ads_periodo.py` antes: sem `--launch-code`, o ETL apaga o
período inteiro e reinsere só o que a API devolveu.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

SCRIPTS = {
    "meta": "etl/etl_meta_ads.py",
    "google": "etl/etl_google_ads.py",
}


def _fatias(since: date, until: date):
    """Fatias mensais [inicio, fim] cobrindo o período, sem sobrepor."""
    ini = since
    while ini <= until:
        prox = (ini.replace(day=1) + timedelta(days=32)).replace(day=1)
        fim = min(prox - timedelta(days=1), until)
        yield ini, fim
        ini = fim + timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill de anúncios em fatias mensais.")
    ap.add_argument("--since", required=True, metavar="YYYY-MM-DD")
    ap.add_argument("--until", required=True, metavar="YYYY-MM-DD")
    ap.add_argument("--fonte", required=True, choices=sorted(SCRIPTS))
    args = ap.parse_args()

    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until)
    script = SCRIPTS[args.fonte]

    fatias = list(_fatias(since, until))
    print(f"{args.fonte}: {len(fatias)} fatia(s) de {since} a {until}\n", flush=True)

    falhas = []
    for i, (a, b) in enumerate(fatias, 1):
        print(f"[{i}/{len(fatias)}] {a} -> {b}", flush=True)
        r = subprocess.run(
            [sys.executable, "-u", script, "--since", str(a), "--until", str(b)],
            cwd=RAIZ,
        )
        if r.returncode != 0:
            falhas.append(f"{a}..{b}")
            print(f"    FALHOU (exit {r.returncode}) — as outras fatias seguem", flush=True)
        else:
            print("    ok", flush=True)

    if falhas:
        print(f"\nfatias com falha: {', '.join(falhas)}")
        print("Rode de novo só essas — cada fatia é independente.")
        return 1
    print("\nTodas as fatias concluídas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
