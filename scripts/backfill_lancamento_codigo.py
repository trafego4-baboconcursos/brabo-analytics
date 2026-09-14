# -*- coding: utf-8 -*-
"""
Reprocessa o lancamento_codigo das linhas historicas de gasto.

POR QUE: meta_ads_daily/google_ads_daily gravam o lancamento_codigo no momento
da ingestao. As regras de classificacao de Perpetuo/Distribuicao em
etl/launch_resolver.py foram criadas depois de boa parte do historico ja ter
sido ingerido — essas linhas ficaram com lancamento_codigo NULL e nunca foram
reprocessadas. O resolvedor de hoje sabe classifica-las; so ninguem pediu.

O QUE FAZ: para cada linha sem codigo, roda resolve_launch_code(nome, data) e,
se ele devolver um codigo, grava. Nao inventa nada — usa exatamente a mesma
funcao que o ETL usa hoje na ingestao.

SEGURANCA:
  - roda em simulacao por padrao; so altera com --aplicar
  - por padrao SO mexe em linha NULL; nunca sobrescreve codigo existente
    (--reavaliar permite corrigir codigo errado, mas exige --aplicar tambem)
  - antes de aplicar, salva os valores antigos num CSV de reversao
  - imprime contagem antes/depois

    python scripts/backfill_lancamento_codigo.py                  # simula
    python scripts/backfill_lancamento_codigo.py --aplicar        # executa
"""
import argparse
import csv
import datetime
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from etl.launch_resolver import resolve_launch_code

TABELAS = [("meta_ads_daily", "spend"), ("google_ads_daily", "cost")]
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def brl(v):
    return ("R$ %0.2f" % v).replace(".", ",")


def levantar(conn, tabela, custo, reavaliar):
    """Devolve [(campaign_name, date, codigo_atual, codigo_novo, gasto, linhas)]."""
    onde = "" if reavaliar else "where lancamento_codigo is null"
    sql = ("select campaign_name, date, lancamento_codigo, "
           "sum(%s) g, count(*) n from %s %s group by 1,2,3" % (custo, tabela, onde))
    mudancas = []
    for r in conn.execute(text(sql)).mappings():
        novo = resolve_launch_code(r["campaign_name"], r["date"])
        if novo and novo != r["lancamento_codigo"]:
            mudancas.append((r["campaign_name"], r["date"], r["lancamento_codigo"],
                             novo, float(r["g"] or 0), int(r["n"])))
    return mudancas


def main():
    ap = argparse.ArgumentParser(description="Backfill de lancamento_codigo")
    ap.add_argument("--aplicar", action="store_true", help="executa (sem isso, so simula)")
    ap.add_argument("--reavaliar", action="store_true",
                    help="tambem reavalia linhas que JA tem codigo (corrige classificacao errada)")
    a = ap.parse_args()

    load_dotenv()
    eng = create_engine(os.environ["SUPABASE_DB_URL"])
    modo = "APLICANDO" if a.aplicar else "SIMULACAO (nada sera alterado)"
    print("\nBACKFILL DE lancamento_codigo — %s" % modo)
    if a.reavaliar:
        print("escopo: TODAS as linhas (inclusive as que ja tem codigo)")
    else:
        print("escopo: so linhas com lancamento_codigo NULL")

    total_linhas = 0
    total_gasto = 0.0
    por_codigo = Counter()
    gasto_codigo = Counter()
    reversao = []

    with eng.begin() as conn:
        for tabela, custo in TABELAS:
            antes = conn.execute(text(
                "select count(*) from %s where lancamento_codigo is null" % tabela)).scalar()
            mud = levantar(conn, tabela, custo, a.reavaliar)
            print("\n  %s" % tabela)
            print("    linhas sem codigo hoje: %d" % antes)
            print("    combinacoes a corrigir: %d" % len(mud))
            for nome, data, antigo, novo, g, n in mud:
                por_codigo[novo] += n
                gasto_codigo[novo] += g
                total_linhas += n
                total_gasto += g
                reversao.append([tabela, nome, str(data), antigo or "", novo, n])

            if a.aplicar and mud:
                for nome, data, antigo, novo, _g, _n in mud:
                    cond = ("lancamento_codigo is null" if antigo is None
                            else "lancamento_codigo = :antigo")
                    par = {"novo": novo, "nome": nome, "data": data}
                    if antigo is not None:
                        par["antigo"] = antigo
                    conn.execute(text(
                        "update %s set lancamento_codigo = :novo "
                        "where campaign_name = :nome and date = :data and %s"
                        % (tabela, cond)), par)
                depois = conn.execute(text(
                    "select count(*) from %s where lancamento_codigo is null" % tabela)).scalar()
                print("    linhas sem codigo depois: %d  (-%d)" % (depois, antes - depois))

    print("\n  RESULTADO POR CODIGO")
    print("    %-32s %9s %16s" % ("codigo", "linhas", "gasto"))
    for cod, n in por_codigo.most_common():
        print("    %-32s %9d %16s" % (cod, n, brl(gasto_codigo[cod])))
    print("    %-32s %9d %16s" % ("TOTAL", total_linhas, brl(total_gasto)))

    if not a.aplicar:
        print("\n  Nada foi alterado. Rode com --aplicar para executar.\n")
        return 0

    if reversao:
        os.makedirs(os.path.join(RAIZ, "outputs"), exist_ok=True)
        carimbo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        p = os.path.join(RAIZ, "outputs", "backfill_reversao_%s.csv" % carimbo)
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["tabela", "campaign_name", "date", "codigo_antigo", "codigo_novo", "linhas"])
            w.writerows(reversao)
        print("\n  reversao salva em: %s" % os.path.relpath(p, RAIZ))
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
