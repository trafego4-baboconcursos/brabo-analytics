"""Backfill do histórico de UTM a partir dos exports do Active Campaign da época.

POR QUE EXISTE. Até 07/10/26 ninguém guardava a UTM que a `leads` perdia quando o
contato se cadastrava num lançamento novo (ver seção 13 de
`docs/sistema/METODOLOGIA_EXTRACAO_DADOS.md`). Os CSV em
`analises/[LANC]/Active Campaign/` foram tirados durante ou logo depois de cada
lançamento e trazem a UTM como ela estava naquele dia. Medido em 08/10/26: ~60 mil
contatos que o export liga a um lançamento e o banco hoje liga a outro.

A REGRA:
  - só entra UTM que NOMEIA o lançamento. Código na `utm_campaign` sempre vale. Os primeiros
    lançamentos (PBB-JUN-26, PES-MAI-26, PI-JAN-26 e outros) tinham campanha SEM o código no nome
    (`[MA][cadastro][captação][...][25.05.26]`), com o código no nome do anúncio (`utm_term`/
    `utm_content`: `AD079 - ... - PBB-JUN-26`). Então, quando a campanha NÃO nomeia nenhum
    lançamento, vale o código nos outros campos. Se a campanha nomeia OUTRO lançamento, não vale:
    o anúncio pode só ter sido reaproveitado, e creditar seria chute;
  - chave (contato, lançamento, trilha): contato ausente no estado → entra no estado;
  - se o estado JÁ tem outra UTM para aquele lançamento, a do export é a MAIS ANTIGA:
    vai para o histórico, nunca vira a atual;
  - nada que já existe é sobrescrito (`ON CONFLICT DO NOTHING`) — rodar de novo é seguro;
  - a data de "visto desde" é a do ARQUIVO (mtime), não a de hoje: o backfill nunca
    se passa pela UTM mais recente.
Cada linha fica com `origem = 'export_ac'`, então dá para localizar e remover.

Uso:
    python scripts/backfill_utm_exports.py --dry-run          # só conta
    python scripts/backfill_utm_exports.py --launch PI-AGO-26
    python scripts/backfill_utm_exports.py --todos
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))
sys.path.insert(0, str(_RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

import pandas as pd  # noqa: E402
from psycopg2.extras import execute_values  # noqa: E402

import historico_utm_trigger as ht  # noqa: E402
from etl_active_campaign import extract_launch_code  # noqa: E402

N = ht.Nomes()
LANCAMENTOS = ["PBB-ABR-26", "PBB-AGO-26", "PBB-JUN-26", "PES-JAN-26", "PES-MAI-26",
               "PES-MAR-26", "PES-SET-26", "PI-ABR-26", "PI-AGO-26", "PI-JAN-26"]
CAMPOS = ["email", *ht.CAMPOS_UTM, *ht.CAMPOS_ID]


def _norm_col(c: str) -> str:
    return re.sub(r"[^a-z_]", "", str(c).lower().replace("*", "").strip())


def _txt(v) -> str:
    v = "" if v is None else str(v).strip()
    return "" if v.lower() in ("nan", "none") else v


def nomeia_o_lancamento(code: str, utm) -> bool:
    """A UTM do export nomeia `code`? Ver a regra no topo do arquivo."""
    da_campanha = extract_launch_code(utm["utm_campaign"])
    if da_campanha:
        return da_campanha == code
    outros = (utm["utm_source"], utm["utm_medium"], utm["utm_content"], utm["utm_term"])
    return any(extract_launch_code(v) == code for v in outros)


def ler_export(code: str) -> tuple[pd.DataFrame, datetime]:
    """Contatos do export cuja UTM nomeia o lançamento, e a data do arquivo."""
    pasta = _RAIZ / "analises" / f"[{code}]" / "Active Campaign"
    # Só os export do Active: a pasta também guarda arquivos de público
    # (customer_match, google-ads-audience), sem UTM, que já enganaram uma comparação.
    arquivos = sorted(pasta.glob("active-campaign*.csv"))
    if not arquivos:
        raise SystemExit(f"{code}: sem active-campaign*.csv em {pasta}")
    data = datetime.fromtimestamp(min(a.stat().st_mtime for a in arquivos))
    quer = {"id", *CAMPOS}
    partes = []
    for arq in arquivos:
        for bloco in pd.read_csv(arq, chunksize=100_000, dtype=str, on_bad_lines="skip", low_memory=False,
                                 encoding="utf-8-sig", usecols=lambda c: _norm_col(c) in quer):
            bloco.columns = [_norm_col(c) for c in bloco.columns]
            partes.append(bloco)
    df = pd.concat(partes, ignore_index=True)
    for c in quer - set(df.columns):
        df[c] = ""
    for c in quer:
        df[c] = df[c].map(_txt)
    df["email"] = df["email"].str.lower()
    df = df[(df["id"] != "") & df.apply(lambda r: nomeia_o_lancamento(code, r), axis=1)]
    return df.drop_duplicates("id", keep="last"), data


def aplicar(conn, code: str, df: pd.DataFrame, data: datetime, dry_run: bool) -> dict:
    cur = conn.cursor()
    cur.execute("SET LOCAL statement_timeout = '900s'")
    cols = ["id", *CAMPOS]
    cur.execute("CREATE TEMP TABLE stg_backfill (" + ", ".join(f"{c} text" for c in cols) + ") ON COMMIT DROP")
    execute_values(cur, f"INSERT INTO stg_backfill ({', '.join(cols)}) VALUES %s",
                   [tuple(r) for r in df[cols].itertuples(index=False, name=None)], page_size=5000)
    cur.execute("CREATE INDEX ON stg_backfill (id)")

    h = f"public.{N.hash_fn}"
    h_s = f"{h}(s.utm_source, s.utm_medium, s.utm_campaign, s.utm_content, s.utm_term)"
    h_e = f"{h}(e.utm_source, e.utm_medium, e.utm_campaign, e.utm_content, e.utm_term)"
    chave = f"e.contact_id = s.id AND e.lancamento_codigo = %s AND e.trilha = ''"

    cur.execute(f"SELECT count(*) FROM stg_backfill s WHERE NOT EXISTS "
                f"(SELECT 1 FROM {N.estado} e WHERE {chave})", (code,))
    novas = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM stg_backfill s JOIN {N.estado} e ON {chave} WHERE {h_e} <> {h_s}", (code,))
    antigas = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM stg_backfill s JOIN {N.estado} e ON {chave} WHERE {h_e} = {h_s}", (code,))
    iguais = cur.fetchone()[0]
    resultado = {"export": len(df), "ja_iguais": iguais, "novas_no_estado": novas, "antigas_no_historico": antigas}
    if dry_run:
        return resultado

    sel = ", ".join(f"s.{c}" for c in (*ht.CAMPOS_UTM, *ht.CAMPOS_ID))
    cols_ins = ", ".join((*ht.CAMPOS_UTM, *ht.CAMPOS_ID))
    cur.execute(
        f"""INSERT INTO {N.estado} (contact_id, lancamento_codigo, trilha, email, {cols_ins},
                                    primeiro_visto_em, ultimo_visto_em, utm_desde, origem)
            SELECT s.id, %s, '', s.email, {sel}, %s, %s, %s, 'export_ac'
            FROM stg_backfill s
            ON CONFLICT (contact_id, lancamento_codigo, trilha) DO NOTHING""", (code, data, data, data))
    resultado["gravadas_no_estado"] = cur.rowcount
    cur.execute(
        f"""INSERT INTO {N.historico} (contact_id, lancamento_codigo, trilha, utm_hash, email, {cols_ins},
                                       visto_desde, substituida_em, origem)
            SELECT s.id, %s, '', {h_s}, s.email, {sel}, %s, NULL, 'export_ac'
            FROM stg_backfill s JOIN {N.estado} e ON {chave}
            WHERE {h_e} <> {h_s}
            ON CONFLICT (contact_id, lancamento_codigo, trilha, utm_hash) DO NOTHING""", (code, data, code))
    resultado["gravadas_no_historico"] = cur.rowcount
    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--launch")
    g.add_argument("--todos", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from frontend.db import _get_engine  # noqa: PLC0415

    codes = [a.launch] if a.launch else LANCAMENTOS
    print(f"backfill de UTM por export ({'DRY-RUN' if a.dry_run else 'GRAVANDO'}) — {len(codes)} lançamento(s)")
    total = {"novas_no_estado": 0, "antigas_no_historico": 0}
    for code in codes:
        df, data = ler_export(code)
        conn = _get_engine().raw_connection()      # uma transação por lançamento
        try:
            r = aplicar(conn, code, df, data, a.dry_run)
            if a.dry_run:
                conn.rollback()
            else:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        total["novas_no_estado"] += r["novas_no_estado"]
        total["antigas_no_historico"] += r["antigas_no_historico"]
        gravou = (f" | gravou estado {r.get('gravadas_no_estado', 0):,}, histórico {r.get('gravadas_no_historico', 0):,}"
                  if not a.dry_run else "")
        print(f"  {code:11s} export {r['export']:>8,} (de {data:%d/%m/%Y}) | já iguais {r['ja_iguais']:>8,} | "
              f"entram no estado {r['novas_no_estado']:>7,} | vão pro histórico {r['antigas_no_historico']:>6,}{gravou}", flush=True)
    print(f"total: {total['novas_no_estado']:,} no estado, {total['antigas_no_historico']:,} no histórico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
