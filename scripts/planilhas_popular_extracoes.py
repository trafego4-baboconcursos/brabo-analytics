"""Popula as abas EXTRACAO-* das planilhas "Anúncios" e "Captação" de um lançamento com o banco (meta_ads_daily /
google_ads_daily) e o GA4, na ordem de colunas do Stract (docs/performance/playbooks/PADRAO_PLANILHAS_LANCAMENTO.md).
Provisório: serve para a planilha funcionar antes de o Stract ser ligado; quando o Stract roda, ele sobrescreve.
Apaga e regrava da linha 2 em diante (cabeçalho mantido). Sem --apply só mostra o que gravaria.

    python scripts/planilhas_popular_extracoes.py PI-NOV-26 <ID_ANUNCIOS> <ID_CAPTACAO> --ga4 503309358 --inicio 2026-10-12 [--apply]
"""
import os, sys, datetime as dt, requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
import logging; logging.disable(logging.WARNING)
from sqlalchemy import text
from etl.db import get_engine

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("lancamento"); ap.add_argument("anuncios_id"); ap.add_argument("captacao_id")
ap.add_argument("--ga4", required=True, help="property do GA4 das LPs (INSS 503309358)")
ap.add_argument("--inicio", required=True, help="AAAA-MM-DD, início da pré-quali (janela do GA4)")
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()
APPLY, LANC, ANUN, CAPT, GA4_PROP, GA4_INICIO = a.apply, a.lancamento, a.anuncios_id, a.captacao_id, a.ga4, a.inicio
EPOCH = dt.date(1899, 12, 30)
serial = lambda d: (d - EPOCH).days
f = lambda x: round(float(x or 0), 2)

tok = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    "refresh_token": os.environ["GOOGLE_SHEETS_REFRESH_TOKEN"], "grant_type": "refresh_token"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}


def base(s): return f"https://sheets.googleapis.com/v4/spreadsheets/{s}"


def cabecalho(s, aba):
    return requests.get(f"{base(s)}/values/'{aba}'!A1:Z1", headers=H).json().get("values", [[]])[0]


with get_engine().connect() as c:
    q = lambda sql: [tuple(r) for r in c.execute(text(sql), {"l": LANC})]
    # Anúncios — por anúncio × dia, só captação
    an_bm = q("""select ad_name, campaign_name, sum(spend), sum(leads), adset_name, ad_id, date from meta_ads_daily
                 where lancamento_codigo=:l and campaign_name ilike '%[captação]%' group by 1,2,5,6,7 order by 7,1""")
    an_ga = q("""select ad_name, campaign_name, sum(cost), sum(conversions), ad_group_name, date, max(video_id) from google_ads_daily
                 where lancamento_codigo=:l and campaign_name ilike '%[captação]%' group by 1,2,5,6 order by 6,1""")
    # Captação — por campanha × dia, lançamento inteiro
    cp_bm = q("""select date, campaign_name, sum(spend), sum(leads), sum(link_clicks) from meta_ads_daily
                 where lancamento_codigo=:l group by 1,2 order by 1,2""")
    cp_ga = q("""select date, campaign_name, sum(cost), sum(conversions) from google_ads_daily
                 where lancamento_codigo=:l group by 1,2 order by 1,2""")

tipo_ga = lambda n: "SEARCH" if "[search]" in n else "PMAX" if "[p-max]" in n else "GA DISPLAY" if "[display]" in n else "GA"
cpl = lambda v, n: round(float(v) / float(n), 2) if n else 0
dados = {
    (ANUN, "EXTRACAO-BM"): [[a, b, f(s), int(l or 0), st, aid, "", "", "", ""] for a, b, s, l, st, aid, d in an_bm],
    (ANUN, "EXTRACAO-GA"): [[a, b, f(s), f(cv), cpl(s, cv), g, serial(d), vid or ""] for a, b, s, cv, g, d, vid in an_ga],
    (CAPT, "EXTRACAO-BM"): [[serial(d), b, f(s), int(l or 0), cpl(s, l), int(k or 0), ""] for d, b, s, l, k in cp_bm],
}
for t in ("GA", "SEARCH", "PMAX", "GA DISPLAY"):
    dados[(CAPT, f"EXTRACAO-{t}")] = [[serial(d), b, f(s), f(cv), cpl(s, cv)] for d, b, s, cv in cp_ga if tipo_ga(b) == t]

# GA4 — página × evento (totalUsers, pagePath, sessions, eventName, eventCount)
t4 = requests.post("https://oauth2.googleapis.com/token", data={"client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
                   "refresh_token": os.environ["GA4_REFRESH_TOKEN"], "grant_type": "refresh_token"}).json()["access_token"]
r = requests.post(f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROP}:runReport", headers={"Authorization": f"Bearer {t4}"}, json={
    "dateRanges": [{"startDate": GA4_INICIO, "endDate": "today"}], "dimensions": [{"name": "pagePath"}, {"name": "eventName"}],
    "metrics": [{"name": "totalUsers"}, {"name": "sessions"}, {"name": "eventCount"}], "limit": 10000,
    "dimensionFilter": {"filter": {"fieldName": "pagePath", "stringFilter": {"matchType": "CONTAINS", "value": LANC.lower()}}}}).json()
ga4 = [[int(x["metricValues"][0]["value"]), x["dimensionValues"][0]["value"], int(x["metricValues"][1]["value"]),
        x["dimensionValues"][1]["value"], int(x["metricValues"][2]["value"])] for x in r.get("rows", [])]
dados[(CAPT, "EXTRACAO-GA4")] = sorted(ga4, key=lambda x: -x[0])

ESPERADO = {"EXTRACAO-BM": ("Ad Name", "Campaign Name"), "EXTRACAO-GA": ("Ad Name", "Campaign Name")}
for (s, aba), linhas in dados.items():
    cab = cabecalho(s, aba)
    plan = "Anúncios" if s == ANUN else "Captação"
    print(f"{plan:9} {aba:20} {len(linhas):>5} linhas | cabeçalho: {cab[:8]}")
    if linhas: print(f"{'':31} ex.: {linhas[0][:8]}")
tot = lambda k, i: sum(x[i] for x in dados[k])
print(f"\nconferência: Anúncios FB R$ {tot((ANUN,'EXTRACAO-BM'),2):,.2f} / {tot((ANUN,'EXTRACAO-BM'),3)} leads · Anúncios GA R$ {tot((ANUN,'EXTRACAO-GA'),2):,.2f}"
      f" · Captação FB R$ {tot((CAPT,'EXTRACAO-BM'),2):,.2f} · Captação GA R$ {tot((CAPT,'EXTRACAO-GA'),2):,.2f}")
if not APPLY:
    sys.exit("[dry-run] nada gravado")
for (s, aba), linhas in dados.items():
    requests.post(f"{base(s)}/values:batchClear", headers=H, json={"ranges": [f"'{aba}'!A2:Z"]}).raise_for_status()
    if linhas:
        requests.put(f"{base(s)}/values/'{aba}'!A2", params={"valueInputOption": "RAW"}, headers=H, json={"values": linhas}).raise_for_status()
print("gravado")
