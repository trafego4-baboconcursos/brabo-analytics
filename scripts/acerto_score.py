# -*- coding: utf-8 -*-
"""
Acerto do score de lead A: a nota que o painel mostrava DURANTE a captação antecipou o CPA final?

Passo do fechamento de lançamento (performance/playbooks/FECHAMENTO_LANCAMENTO.md; regra SCORE-1 em
REGRAS_DECISAO.md). Para cada data de corte, recalcula a nota 0–100 (mesma régua de
frontend/services/score_criativos.py) só com o que existia até ali — leads vistos até a data, gasto até a data,
corte de lead A pela mediana dos respondentes que já estavam na base — e compara com o CPA final de cada
unidade: anúncio (lançamento inteiro), conjunto/grupo e anúncio dentro do conjunto.

    python scripts/acerto_score.py PES-NOV-26                       # cortes automáticos: 5º dia, meio, 3/4, fim
    python scripts/acerto_score.py PES-NOV-26 --cortes 2026-10-30 2026-11-05

Critério (SCORE-1): vermelho (nota < 25) acerta 70% ou mais; verde (nota > 75) erra 20% ou menos; o custo por
lead A ordena melhor que o CPL (Spearman com o CPA final, só unidades com 5+ compras).
Só vale como teste o lançamento que ficou FORA do treino do modelo (config/lead_score_modelo.json, "lancamentos").
"CPA final ruim" = acima da mediana do CPA final entre as unidades com nota; sem comprador conta como CPA = gasto.
Só leitura no banco; não imprime e-mail. Vendas: read_vendas (hotmart | tmb), regra VER-2.
"""
import argparse
import io
import logging
import os
import sys
import warnings
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIN_COMPR = 5
NOMES = {"ad": "anúncio", "grupo": "conjunto/grupo", "par": "anúncio no conjunto"}


def _carregar(code):
    import pandas as pd
    from sqlalchemy import text

    from frontend.db import _get_engine
    from frontend.db_readers.publicos import etapa_da_campanha
    from frontend.db_readers.sales import read_vendas
    from frontend.services import lead_score as ls
    from frontend.services import vendas_por_grupo as vg
    from frontend.services.classificadores import _extract_ad_code

    with _get_engine().connect() as c:
        c.execute(text("SET LOCAL statement_timeout = 300000"))
        utm = pd.DataFrame(c.execute(text(
            "SELECT email, utm_source, utm_medium, utm_campaign, utm_content, " + ls._AD_SQL + ", primeiro_visto_em "
            "FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email <> ''"), {"c": code}).fetchall(),
            columns=["email", "source", "medium", "campaign", "content", "ad", "visto"])
        gasto = pd.DataFrame(c.execute(text(
            "SELECT 'meta', date, campaign_name, adset_id::text, ad_name, SUM(spend)::float FROM meta_ads_daily "
            "WHERE lancamento_codigo = :c AND adset_id IS NOT NULL GROUP BY 1,2,3,4,5 UNION ALL "
            "SELECT 'google', date, campaign_name, ad_group_id::text, ad_name, SUM(cost)::float FROM google_ads_daily "
            "WHERE lancamento_codigo = :c AND ad_group_id IS NOT NULL GROUP BY 1,2,3,4,5"), {"c": code}).fetchall(),
            columns=["plat", "dia", "camp", "gid", "ad_name", "gasto"])

    gasto = gasto[[etapa_da_campanha(x or "") == "captacao" for x in gasto["camp"]]].copy()
    gasto["grupo"] = gasto["plat"] + ":" + gasto["gid"]
    gasto["ad"] = [_extract_ad_code(n or "") for n in gasto["ad_name"]]
    gasto["par"] = gasto["grupo"] + "|" + gasto["ad"]
    # mesma ordem do score: o primeiro UTM que traz código de anúncio, depois o mais antigo
    utm = utm.assign(sem_ad=utm["ad"].isna()).sort_values(["email", "sem_ad", "visto"])

    v = read_vendas(code)
    compradores = (v.emails_hotmart | v.emails_tmb) if v else set()
    m = ls._carregar_modelo()
    resp = ls._respostas_df(code, m) if m else None
    if resp is None or resp.empty:
        return None
    resp = resp.assign(respondeu=1).reset_index(drop=True)
    p_de = dict(zip(resp["email"], ls._logit_vetorial(m, resp)))
    casar = vg.casador_de_grupos(vg._grupos_do_lancamento(code))
    return {"utm": utm, "gasto": gasto, "compradores": compradores, "p_de": p_de, "casar": casar,
            "fora_do_treino": code not in (m.get("lancamentos") or [])}


def _ligar(df, casar):
    df = df.drop_duplicates("email")
    g = [casar(s or "", md or "", cp or "", ct or "") for s, md, cp, ct in
         zip(df["source"], df["medium"], df["campaign"], df["content"])]
    df = df.assign(grupo=[f"{x[0]}:{x[1]}" if x else None for x in g])
    return df.assign(par=[f"{gr}|{a}" if gr and a else None for gr, a in zip(df["grupo"], df["ad"])])


def _finais(d):
    import pandas as pd

    final = _ligar(d["utm"], d["casar"])
    final = final.assign(comprou=final["email"].isin(d["compradores"]))
    out = {}
    for nivel in NOMES:
        compr = final[final["comprou"]].groupby(nivel).size()
        g = d["gasto"].groupby(nivel)["gasto"].sum()
        g = g[g.index.notna() & (g.index != "")]
        t = pd.DataFrame({"gasto": g}).join(compr.rename("compr")).fillna({"compr": 0})
        t["cpa"] = t["gasto"] / t["compr"].where(t["compr"] > 0)
        t["cpa_ou_gasto"] = t["cpa"].fillna(t["gasto"])
        out[nivel] = t
    return out


def _no_corte(d, finais, dia):
    import pandas as pd

    from frontend.services.score_criativos import notas_por_anuncio

    lim = datetime(dia.year, dia.month, dia.day, 23, 59, 59, tzinfo=timezone.utc)
    df = _ligar(d["utm"][d["utm"]["visto"] <= lim], d["casar"])
    na_base = set(df["email"]) & set(d["p_de"])
    if not na_base:
        return None
    ps = pd.Series({e: d["p_de"][e] for e in na_base})
    df = df.assign(A=df["email"].isin(set(ps[ps > ps.median()].index)))
    gd = d["gasto"][d["gasto"]["dia"] <= dia]
    out = {}
    for nivel in NOMES:
        leads = df.groupby(nivel).size()
        gs = gd.groupby(nivel)["gasto"].sum()
        gs = gs[gs.index.notna() & (gs.index != "")]
        la = {k: int(v) for k, v in df[df["A"]].groupby(nivel).size().items() if k in gs.index}
        r = notas_por_anuncio(gs.to_dict(), la)["anuncios"]
        t = pd.DataFrame({k: {"nota": x["nota"], "custo_a": x["custo_a"], "gasto_d": gs[k],
                              "cpl": gs[k] / leads[k] if k in leads.index and leads[k] else None}
                          for k, x in r.items()}).T
        out[nivel] = t.join(finais[nivel][["cpa", "cpa_ou_gasto", "compr"]], how="inner")
    return out


def medir(code, cortes=None):
    """[{corte, nivel, n, vermelho, n_verm, sem_selo, verde, n_verde, sp_score, sp_cpl}] ou None sem pesquisa."""
    d = _carregar(code)
    if d is None:
        return None, None
    dias = sorted(d["gasto"]["dia"].unique())
    if not cortes:
        ini, fim = dias[0], dias[-1]
        total = (fim - ini).days
        cortes = sorted({ini + timedelta(days=4), ini + timedelta(days=total // 2),
                         ini + timedelta(days=total * 3 // 4), fim})
    finais = _finais(d)
    linhas = []
    for dia in cortes:
        r = _no_corte(d, finais, dia)
        for nivel, t in (r or {}).items():
            com = t[t["nota"].notna()]
            if com.empty:
                continue
            cpa = com["cpa_ou_gasto"].astype(float)
            acima = cpa > cpa.median()
            nota = com["nota"].astype(float)
            verm, verde = nota < 25, nota > 75
            s5 = com[com["compr"] >= MIN_COMPR]
            sp = (lambda col: s5[col].astype(float).corr(s5["cpa"].astype(float), method="spearman") * 100
                  if len(s5) > 3 else float("nan"))
            linhas.append({"corte": dia, "nivel": nivel, "n": len(com),
                           "vermelho": acima[verm].mean() * 100 if verm.any() else None, "n_verm": int(verm.sum()),
                           "sem_selo": acima[~verm & ~verde].mean() * 100 if (~verm & ~verde).any() else None,
                           "verde": acima[verde].mean() * 100 if verde.any() else None, "n_verde": int(verde.sum()),
                           "sp_score": sp("custo_a"), "sp_cpl": sp("cpl")})
    return d, linhas


def _fmt(v, n=None):
    if v is None:
        return "—"
    return f"{v:.0f}%" + (f" ({n})" if n is not None else "")


def main():
    ap = argparse.ArgumentParser(description="Acerto do score de lead A (nota na captação × CPA final)")
    ap.add_argument("lancamento")
    ap.add_argument("--cortes", nargs="*", type=date.fromisoformat, help="datas AAAA-MM-DD (padrão: 5º dia, meio, 3/4, fim)")
    a = ap.parse_args()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore")

    d, linhas = medir(a.lancamento, a.cortes)
    if d is None:
        print(f"{a.lancamento}: sem pesquisa pontuável (modelo, respostas ou leads) — nada a medir.")
        return 1
    print(f"{a.lancamento}: fora do treino do modelo = {d['fora_do_treino']}"
          + ("" if d["fora_do_treino"] else "  ⚠ o modelo aprendeu com este lançamento: o resultado é otimista"))
    print(f"{d['utm']['email'].nunique()} leads, {len(d['compradores'])} compradores, "
          f"gasto de captação R$ {d['gasto']['gasto'].sum():,.0f}\n")
    print("| nota com dado até | nível | com nota | vermelho → CPA final ruim | sem selo | verde → CPA final ruim | ordem: score × CPL |")
    print("|---|---|---|---|---|---|---|")
    for x in linhas:
        print(f"| {x['corte'].strftime('%d/%m')} | {NOMES[x['nivel']]} | {x['n']} | {_fmt(x['vermelho'], x['n_verm'])} | "
              f"{_fmt(x['sem_selo'])} | {_fmt(x['verde'], x['n_verde'])} | {x['sp_score']:.0f} × {x['sp_cpl']:.0f} |")
    print("\nCritério SCORE-1: vermelho ≥ 70%, verde ≤ 20%, score ordena melhor que o CPL. Revisar o modelo se dois "
          "lançamentos seguidos tiverem vermelho < 60% ou verde > 30% a partir do meio da captação.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
