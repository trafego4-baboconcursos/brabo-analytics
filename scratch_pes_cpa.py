"""
Script de analise de CPA para campanhas PES no Google Ads.
Usa a mesma logica de autenticacao do etl_google_ads.py.
Execute: .venv\\Scripts\\python -X utf8 scratch_pes_cpa.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os, json, re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(".") / "etl"))
sys.path.insert(0, str(Path(".") / "src"))

from dotenv import load_dotenv
load_dotenv()

import google.oauth2.credentials
import google.auth.transport.requests
import requests

DEVELOPER_TOKEN   = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
ALL_CUSTOMER_IDS  = [c.strip().replace("-", "") for c in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if c.strip()]
API_VERSION       = "v22"


def get_access_token() -> str:
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def gaql_search(access_token: str, customer_id: str, query: str) -> list:
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
    headers = {
        "Authorization":   f"Bearer {access_token}",
        "developer-token": DEVELOPER_TOKEN,
        "Content-Type":    "application/json",
    }
    if LOGIN_CUSTOMER_ID:
        headers["login-customer-id"] = LOGIN_CUSTOMER_ID

    results = []
    page_token = None
    while True:
        payload = {"query": query}
        if page_token:
            payload["pageToken"] = page_token
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if not r.ok:
            print(f"  ERRO HTTP {r.status_code}: {r.text[:500]}")
            break
        data = r.json()
        results.extend(data.get("results", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results


def _build_query(captacao_only: bool = False) -> str:
    from datetime import date, timedelta
    today = date.today()
    since = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    until = today.strftime("%Y-%m-%d")
    # Filtro: PES + captacao (exclui rmk, aula, replay, thruplay, pré-quali de video)
    if captacao_only:
        name_filter = r"campaign.name REGEXP_MATCH '(?i).*PES.*capta[çc][aã]o.*'"
    else:
        name_filter = r"campaign.name REGEXP_MATCH '(?i).*PES.*'"
    return f"""
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.bidding_strategy_type,
  campaign.target_cpa.target_cpa_micros,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.cost_per_conversion,
  metrics.all_conversions
FROM campaign
WHERE
  {name_filter}
  AND segments.date BETWEEN '{since}' AND '{until}'
ORDER BY metrics.cost_micros DESC
"""

QUERY_TODAS      = _build_query(captacao_only=False)
QUERY_CAPTACAO   = _build_query(captacao_only=True)



def micros(v) -> float:
    return int(v) / 1_000_000 if v else 0.0

def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def extract_launch(name: str) -> str:
    m = re.search(r"(PES)-\w{3}-\d{2}", name, re.IGNORECASE)
    return m.group(0).upper() if m else "OUTROS"


def process_results(results: list) -> tuple[list, dict]:
    """Processa rows da API e retorna (details, by_launch)."""
    by_launch = {}
    details   = []
    for row in results:
        camp    = row.get("campaign", {})
        met     = row.get("metrics",  {})
        name    = camp.get("name",   "")
        status  = camp.get("status", "")
        bidding = camp.get("biddingStrategyType", camp.get("bidding_strategy_type", ""))
        tc_micros = camp.get("targetCpa", {}).get("targetCpaMicros")
        cost        = micros(met.get("costMicros", 0))
        conversions = float(met.get("conversions",  0) or 0)
        impressions = int(  met.get("impressions",  0) or 0)
        clicks      = int(  met.get("clicks",       0) or 0)
        launch   = extract_launch(name)
        cpa_real = cost / conversions if conversions > 0 else 0.0
        tgt_cpa  = micros(tc_micros) if tc_micros else None
        details.append({
            "name": name, "launch": launch, "status": status,
            "bidding": bidding, "target_cpa": tgt_cpa,
            "cost": cost, "conversions": conversions,
            "cpa_real": cpa_real, "impressions": impressions, "clicks": clicks,
        })
        bl = by_launch.setdefault(launch, {"cost": 0, "conversions": 0, "impressions": 0, "clicks": 0})
        bl["cost"]        += cost
        bl["conversions"] += conversions
        bl["impressions"] += impressions
        bl["clicks"]      += clicks
    return details, by_launch


def print_campaign_table(details: list):
    print(f"  {'CAMPANHA':<52} {'STATUS':<9} {'BIDDING':<16} {'TGT_CPA':>10} {'GASTO':>12} {'CONV':>6} {'CPA':>12}")
    print(f"  {'─'*52} {'─'*9} {'─'*16} {'─'*10} {'─'*12} {'─'*6} {'─'*12}")
    for c in sorted(details, key=lambda x: x["cost"], reverse=True):
        if c["cost"] == 0 and c["conversions"] == 0:
            continue  # oculta campanhas zeradas
        st = (c["status"].replace("ENABLED","ATIVO").replace("PAUSED","PAUSADO").replace("REMOVED","REMOVIDO"))
        bd = (c["bidding"]
              .replace("TARGET_CPA","tCPA")
              .replace("MAXIMIZE_CONVERSIONS","MAX_CONV")
              .replace("MANUAL_CPC","MANUAL")
              .replace("MAXIMIZE_CONVERSION_VALUE","MAX_VAL")
              .replace("TARGET_ROAS","tROAS"))[:14]
        ts = brl(c["target_cpa"]) if c["target_cpa"] else "—"
        cs = brl(c["cpa_real"])   if c["cpa_real"] > 0 else "—"
        print(f"  {c['name'][:52]:<52} {st:<9} {bd:<16} {ts:>10} {brl(c['cost']):>12} {c['conversions']:>6.1f} {cs:>12}")


def aggregate_by_launch(all_data: dict, exclude: str | None = None) -> dict:
    pes_hist = {}
    for cid, data in all_data.items():
        for lc, d in data["by_launch"].items():
            if not lc.startswith("PES"):
                continue
            if exclude and lc == exclude:
                continue
            h = pes_hist.setdefault(lc, {"cost": 0, "conversions": 0})
            h["cost"]        += d["cost"]
            h["conversions"] += d["conversions"]
    return pes_hist


def print_benchmark(label: str, pes_hist: dict):
    print(f"\n  CPAs por lancamento [{label}]:")
    cpas = []
    for lc, d in sorted(pes_hist.items()):
        if d["conversions"] > 0:
            cpa = d["cost"] / d["conversions"]
            cpas.append((lc, cpa))
            print(f"  -> {lc}: {brl(cpa)}  (gasto {brl(d['cost'])} / {d['conversions']:.0f} conv)")
        else:
            print(f"  -> {lc}: sem conversoes  (gasto {brl(d['cost'])})")
    if cpas:
        import statistics
        vals    = [c for _, c in cpas]
        media   = statistics.mean(vals)
        mediana = statistics.median(vals)
        print(f"\n  Media:   {brl(media)}")
        print(f"  Mediana: {brl(mediana)}")
        return media, mediana
    return None, None


def main():
    sep = "=" * 82
    print(sep)
    print("  ANALISE DE CPA - CAMPANHAS PES - GOOGLE ADS")
    print(f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Contas: {', '.join(ALL_CUSTOMER_IDS)}  |  MCC: {LOGIN_CUSTOMER_ID}")
    print(sep)

    access_token = get_access_token()
    print("\nToken OAuth OK\n")

    # ── QUERY 1: Todas campanhas PES ─────────────────────────────────────────
    all_data_todas = {}
    # ── QUERY 2: Apenas campanhas de captação ────────────────────────────────
    all_data_captacao = {}

    for customer_id in ALL_CUSTOMER_IDS:
        r_todas    = gaql_search(access_token, customer_id, QUERY_TODAS)
        r_captacao = gaql_search(access_token, customer_id, QUERY_CAPTACAO)

        if r_todas:
            det, byl = process_results(r_todas)
            all_data_todas[customer_id] = {"details": det, "by_launch": byl}

        if r_captacao:
            det2, byl2 = process_results(r_captacao)
            all_data_captacao[customer_id] = {"details": det2, "by_launch": byl2}

    # ── Detalhe das campanhas de CAPTAÇÃO ────────────────────────────────────
    print(f"\n{sep}")
    print("  CAMPANHAS DE CAPTACAO PES (filtradas por nome)")
    print(sep)
    for cid, data in all_data_captacao.items():
        print(f"\n  Conta {cid} -> {len(data['details'])} campanhas de captacao\n")
        print_campaign_table(data["details"])

        print(f"\n  RESUMO POR LANCAMENTO (captacao):")
        print(f"  {'─'*72}")
        print(f"  {'LANCAMENTO':<15} {'GASTO':>14} {'CONV':>12} {'CPA REAL':>14} {'IMPRESSOES':>12} {'CLIQUES':>10}")
        print(f"  {'─'*15} {'─'*14} {'─'*12} {'─'*14} {'─'*12} {'─'*10}")
        for lc in sorted(data["by_launch"]):
            d   = data["by_launch"][lc]
            cpa = d["cost"] / d["conversions"] if d["conversions"] > 0 else 0
            print(f"  {lc:<15} {brl(d['cost']):>14} {d['conversions']:>12.1f} {brl(cpa) if cpa else '—':>14} {d['impressions']:>12,} {d['clicks']:>10,}")

    # ── Benchmark comparativo ────────────────────────────────────────────────
    print(f"\n\n{sep}")
    print("  BENCHMARK COMPARATIVO (todas vs. apenas captacao)")
    print(sep)

    hist_todas    = aggregate_by_launch(all_data_todas,    exclude="PES-SET-26")
    hist_captacao = aggregate_by_launch(all_data_captacao, exclude="PES-SET-26")

    _, med_todas    = print_benchmark("TODAS campanhas PES",  hist_todas)
    _, med_captacao = print_benchmark("SOMENTE CAPTACAO",     hist_captacao)

    print(f"\n\n  {'─' * 70}")
    print(f"  CONCLUSAO E tCPA SUGERIDO PARA PES-SET-26 (captacao):")
    print(f"  {'─' * 70}")
    if med_captacao:
        print(f"  CPA historico captacao (mediana): {brl(med_captacao)}")
        print(f"")
        print(f"  Conservador  (mediana +15%):  {brl(med_captacao * 1.15)}  <- recomendado no inicio")
        print(f"  Equilibrado  (mediana):        {brl(med_captacao)}")
        print(f"  Agressivo    (mediana -15%):  {brl(med_captacao * 0.85)}")
        if med_todas:
            diff = med_todas - med_captacao if med_todas and med_captacao else 0
            print(f"\n  Diferenca (todas vs captacao): {brl(diff)} a mais quando inclui outras campanhas")
    print(f"{'═' * 82}\n")


if __name__ == "__main__":
    main()
