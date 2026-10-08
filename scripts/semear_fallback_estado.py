"""Copia para o estado (`lead_utm_lancamento`) os contatos que a `leads` marca com um lançamento
SEM que a UTM o nomeie.

POR QUE. O código do lançamento na `leads` nem sempre vem da UTM: o modo CSV (plano B) o preenche
pela pasta do arquivo. Esses contatos contam como "leads do lançamento" nas páginas hoje (no
PI-AGO-26, ~12 mil de 267 mil). O estado só recebe contato cuja UTM nomeia o lançamento, então
sem esta cópia as contagens CAIRIAM quando as páginas passarem a ler o estado — mudança de
definição que ninguém pediu. Com ela, o estado é um superconjunto do que `leads WHERE
lancamento_codigo = X` devolvia, e as contagens só podem subir (pelos contatos recuperados).

Cada linha entra com `origem = 'seed_fallback'` (removível por esse marcador) e a UTM que a
`leads` tem (que NÃO nomeia o lançamento). Idempotente: `ON CONFLICT DO NOTHING`.

    python scripts/semear_fallback_estado.py --dry-run
    python scripts/semear_fallback_estado.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))
sys.path.insert(0, str(_RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

import historico_utm_trigger as ht  # noqa: E402

N = ht.Nomes()
ID_COLS = ht.CAMPOS_ID
UTM_COLS = ht.CAMPOS_UTM


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from frontend.db import _get_engine  # noqa: PLC0415

    conn = _get_engine().raw_connection()
    cur = conn.cursor()
    cur.execute("SET statement_timeout = '600s'")
    cur.execute("SELECT DISTINCT lancamento_codigo FROM leads WHERE lancamento_codigo IS NOT NULL ORDER BY 1")
    codigos = [r[0] for r in cur.fetchall()]
    conn.rollback()
    print(f"semeando fallback em {len(codigos)} lançamento(s) ({'DRY-RUN' if a.dry_run else 'GRAVANDO'})")

    utm = ", ".join(f"coalesce(l.{c}, '')" for c in UTM_COLS)
    ids = ", ".join(f"nullif(l.{c}, '')" for c in ID_COLS)
    cols = ", ".join((*UTM_COLS, *ID_COLS))
    falta = ("FROM public.leads l WHERE l.lancamento_codigo = %s AND NOT EXISTS ("
             "SELECT 1 FROM public.lead_utm_lancamento e "
             "WHERE e.contact_id = l.id AND e.lancamento_codigo = l.lancamento_codigo)")
    total = 0
    for cod in codigos:
        conn = _get_engine().raw_connection()
        try:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '600s'")
            if a.dry_run:
                cur.execute(f"SELECT count(*) {falta}", (cod,))
                n = cur.fetchone()[0]
            else:
                cur.execute(
                    f"""INSERT INTO public.{N.estado}
                        (contact_id, lancamento_codigo, trilha, email, {cols},
                         primeiro_visto_em, ultimo_visto_em, utm_desde, origem)
                        SELECT l.id, l.lancamento_codigo, '', lower(btrim(coalesce(l.email, ''))), {utm}, {ids},
                               coalesce(l.updated_at, now()), coalesce(l.updated_at, now()),
                               coalesce(l.updated_at, now()), 'seed_fallback'
                        {falta}
                        ON CONFLICT (contact_id, lancamento_codigo, trilha) DO NOTHING""", (cod,))
                n = cur.rowcount
                conn.commit()
            conn.rollback() if a.dry_run else None
        finally:
            conn.close()
        total += n
        print(f"  {cod:12s} {n:>8,}", flush=True)
    print(f"total: {total:,} contatos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
