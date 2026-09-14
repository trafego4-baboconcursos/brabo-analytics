# -*- coding: utf-8 -*-
"""
Mede o efeito de uma acao nas metricas reais.

As acoes vem da tabela eventos_trafego (indice dos diarios, ver scripts/eventos.py);
o banco tem a metrica diaria por campanha. Este script junta os dois: para uma data
de acao, compara a janela ANTES com a janela DEPOIS. Funciona para qualquer escopo
— lancamento, distribuicao ou perpetuo.

    # lista as acoes registradas (com o contexto ja medido)
    python scripts/efeito_acao.py PES-SET-26 --itens
    python scripts/efeito_acao.py DISTRIBUICAO-IVAN-NETO --itens

    # efeito de tudo que foi feito em 07/09, janela de 7 dias
    python scripts/efeito_acao.py PES-SET-26 --data 2026-09-07

    # so nas campanhas cujo nome contem "Reels", janela de 3 dias
    python scripts/efeito_acao.py PES-SET-26 --data 2026-09-07 --campanha Reels --dias 3

Regra CPA-1: CPA sai em toda analise. Fonte de gasto/conversao e o banco analytics
(meta_ads_daily / google_ads_daily); VENDAS nao saem daqui (ver regra VER-2).
"""
import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def listar_itens(codigo):
    """Lista os eventos do escopo, lendo a tabela eventos_trafego.

    Antes isto parseava o titulo das secoes do .md — fragil, e so funcionava
    pra lancamento. Lendo a tabela, distribuicao e perpetuo funcionam igual, e
    o contexto ja medido aparece junto.
    """
    load_dotenv()
    eng = create_engine(os.environ["SUPABASE_DB_URL"])
    with eng.connect() as c:
        linhas = c.execute(text(
            "select data, tipo, plataforma, coalesce(regra,'-') regra, "
            "coalesce(contexto_metrica,'') ctx, titulo "
            "from eventos_trafego where codigo = :c order by data, id"),
            {"c": codigo}).mappings().all()
    if not linhas:
        print("nenhum evento pra %s." % codigo)
        print("Rode: python scripts/eventos.py --importar --aplicar")
        return 1
    for r in linhas:
        print("  %s  %-10s %-7s %-6s %s" % (r["data"], r["tipo"], r["plataforma"] or "-",
                                            r["regra"], r["titulo"][:78]))
        if r["ctx"]:
            print("  %s  %s" % (" " * 10, r["ctx"]))
    print("%d eventos. Use --data YYYY-MM-DD para medir um dia." % len(linhas))
    return 0


def janela(conn, tabela, col_custo, col_conv, codigo, ini, fim, filtro):
    sql = ("select coalesce(sum(%s),0) custo, coalesce(sum(%s),0) conv, "
           "coalesce(sum(impressions),0) impr, coalesce(sum(clicks),0) cli "
           "from %s where lancamento_codigo = :cod and date >= :ini and date <= :fim"
           % (col_custo, col_conv, tabela))
    par = {"cod": codigo, "ini": ini, "fim": fim}
    if filtro:
        sql += " and campaign_name ilike :f"
        par["f"] = "%" + filtro + "%"
    r = conn.execute(text(sql), par).one()
    return {"custo": float(r[0]), "conv": float(r[1]), "impr": int(r[2]), "cli": int(r[3])}


def cpa(d):
    return d["custo"] / d["conv"] if d["conv"] else None


def fmt_brl(v):
    if v is None:
        return "-"
    return ("R$ %0.2f" % v).replace(".", ",")


def variacao(antes, depois):
    if antes in (None, 0) or depois is None:
        return "-"
    p = (depois - antes) / antes * 100
    seta = "v" if p < 0 else "^"
    return "%s %+.1f%%" % (seta, p)


def medir(codigo, data, dias, filtro):
    load_dotenv()
    eng = create_engine(os.environ["SUPABASE_DB_URL"])
    d = datetime.date.fromisoformat(data)
    ini_a, fim_a = d - datetime.timedelta(days=dias), d - datetime.timedelta(days=1)
    ini_d, fim_d = d, d + datetime.timedelta(days=dias - 1)

    print("\nEFEITO DA ACAO — %s em %s" % (codigo, d.strftime("%d/%m/%Y")))
    if filtro:
        print("filtro de campanha: *%s*" % filtro)
    print("antes:  %s a %s   |   depois: %s a %s  (%d dias cada)"
          % (ini_a, fim_a, ini_d, fim_d, dias))

    fontes = [("Meta", "meta_ads_daily", "spend", "leads"),
              ("Google", "google_ads_daily", "cost", "conversions")]
    total = {}
    with eng.connect() as c:
        for nome, tab, cc, cv in fontes:
            a = janela(c, tab, cc, cv, codigo, ini_a, fim_a, filtro)
            b = janela(c, tab, cc, cv, codigo, ini_d, fim_d, filtro)
            if not a["custo"] and not b["custo"]:
                continue
            print("\n  %s" % nome)
            print("    %-12s %14s %14s   %s" % ("", "antes", "depois", "variacao"))
            for rot, ka in (("gasto", "custo"), ("conversoes", "conv"), ("cliques", "cli")):
                va, vb = a[ka], b[ka]
                sa = fmt_brl(va) if ka == "custo" else "%0.0f" % va
                sb = fmt_brl(vb) if ka == "custo" else "%0.0f" % vb
                print("    %-12s %14s %14s   %s" % (rot, sa, sb, variacao(va, vb)))
            print("    %-12s %14s %14s   %s" % ("CPA", fmt_brl(cpa(a)), fmt_brl(cpa(b)),
                                                variacao(cpa(a), cpa(b))))
            for k in a:
                total[k] = total.get(k, 0) + a[k]
            for k in b:
                total["d_" + k] = total.get("d_" + k, 0) + b[k]

    if not total:
        print("\n  sem dado no periodo para esse lancamento/filtro.")
        return 1
    ta = {"custo": total.get("custo", 0), "conv": total.get("conv", 0)}
    tb = {"custo": total.get("d_custo", 0), "conv": total.get("d_conv", 0)}
    print("\n  TOTAL (Meta + Google)")
    print("    %-12s %14s %14s   %s" % ("gasto", fmt_brl(ta["custo"]), fmt_brl(tb["custo"]),
                                        variacao(ta["custo"], tb["custo"])))
    print("    %-12s %14.0f %14.0f   %s" % ("conversoes", ta["conv"], tb["conv"],
                                            variacao(ta["conv"], tb["conv"])))
    print("    %-12s %14s %14s   %s" % ("CPA", fmt_brl(cpa(ta)), fmt_brl(cpa(tb)),
                                        variacao(cpa(ta), cpa(tb))))
    print("\n  Leitura: a janela pega TUDO que mudou no periodo, nao so a acao medida.")
    print("  Trate como sinal a investigar, nao como prova de causa.\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Efeito de uma acao do diario nas metricas")
    ap.add_argument("lancamento", help="codigo do escopo: PES-SET-26, DISTRIBUICAO-IVAN-NETO...")
    ap.add_argument("--itens", action="store_true", help="lista as acoes registradas")
    ap.add_argument("--data", help="data da acao (YYYY-MM-DD)")
    ap.add_argument("--dias", type=int, default=7, help="tamanho da janela (padrao 7)")
    ap.add_argument("--campanha", help="filtra campanhas cujo nome contem este texto")
    a = ap.parse_args()

    if a.itens:
        return listar_itens(a.lancamento)
    if not a.data:
        ap.error("informe --data YYYY-MM-DD ou --itens")
    return medir(a.lancamento, a.data, a.dias, a.campanha)


if __name__ == "__main__":
    sys.exit(main())
