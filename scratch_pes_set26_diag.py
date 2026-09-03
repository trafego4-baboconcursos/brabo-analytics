"""Analisa campanhas de captacao do PES-SET-26 em tempo real."""
import sys, io, os, json, re, statistics
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
sys.path.insert(0, str(Path(".") / "etl"))
from dotenv import load_dotenv
load_dotenv()

import google.oauth2.credentials, google.auth.transport.requests, requests

DEVELOPER_TOKEN   = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
CUSTOMER_ID       = "6482320788"
API_VERSION       = "v22"

def get_token():
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token

def search(token, query):
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{CUSTOMER_ID}/googleAds:search"
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": DEVELOPER_TOKEN,
        "Content-Type": "application/json",
        "login-customer-id": LOGIN_CUSTOMER_ID,
    }
    results, page_token = [], None
    while True:
        payload = {"query": query}
        if page_token:
            payload["pageToken"] = page_token
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if not r.ok:
            print(f"ERRO {r.status_code}: {r.text[:400]}")
            break
        data = r.json()
        results.extend(data.get("results", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return results

def micros(v): return int(v) / 1_000_000 if v else 0.0
def brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ── Query 1: Campanhas PES-SET-26 (agregado total desde o inicio) ─────────────
Q_CAMP = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.bidding_strategy_type,
  campaign.target_cpa.target_cpa_micros,
  metrics.cost_micros,
  metrics.conversions,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.average_cpc,
  metrics.cost_per_conversion
FROM campaign
WHERE
  campaign.name REGEXP_MATCH '(?i).*PES-SET-26.*'
  AND segments.date BETWEEN '2026-08-01' AND '2026-08-31'
ORDER BY metrics.cost_micros DESC
"""

# ── Query 2: Por dia (últimos 14 dias) ────────────────────────────────────────
Q_DIARIO = """
SELECT
  campaign.name,
  campaign.target_cpa.target_cpa_micros,
  metrics.cost_micros,
  metrics.conversions,
  segments.date
FROM campaign
WHERE
  campaign.name REGEXP_MATCH '(?i).*PES-SET-26.*'
  AND campaign.name REGEXP_MATCH '(?i).*(capta|captação|captacao).*'
  AND segments.date BETWEEN '2026-08-17' AND '2026-08-31'
ORDER BY segments.date DESC, metrics.cost_micros DESC
"""

# ── Query 3: Ad groups das campanhas SET-26 ───────────────────────────────────
Q_ADGROUPS = """
SELECT
  campaign.name,
  campaign.target_cpa.target_cpa_micros,
  ad_group.name,
  ad_group.status,
  ad_group.target_cpa_micros,
  metrics.cost_micros,
  metrics.conversions,
  metrics.impressions,
  metrics.clicks
FROM ad_group
WHERE
  campaign.name REGEXP_MATCH '(?i).*PES-SET-26.*'
  AND segments.date BETWEEN '2026-08-01' AND '2026-08-31'
ORDER BY metrics.cost_micros DESC
"""

def main():
    print("=" * 82)
    print("  CAMPANHAS DE CAPTACAO PES-SET-26 — ANALISE ATUAL")
    print(f"  Data: 31/08/2026")
    print("=" * 82)

    token = get_token()
    print("Token OK\n")

    # ── Campanhas ─────────────────────────────────────────────────────────────
    rows = search(token, Q_CAMP)
    print(f"{'─'*82}")
    print(f"  TODAS AS CAMPANHAS PES-SET-26 (agosto/26)")
    print(f"{'─'*82}")
    print(f"  {'CAMPANHA':<52} {'STATUS':<9} {'TGT CPA':>10} {'GASTO':>12} {'CONV':>6} {'CPA REAL':>12} {'CTR':>6}")
    print(f"  {'─'*52} {'─'*9} {'─'*10} {'─'*12} {'─'*6} {'─'*12} {'─'*6}")

    captacao_rows = []
    for row in rows:
        camp = row.get("campaign", {})
        met  = row.get("metrics", {})
        name   = camp.get("name", "")
        status = camp.get("status", "")
        tc     = camp.get("targetCpa", {}).get("targetCpaMicros")
        cost   = micros(met.get("costMicros", 0))
        conv   = float(met.get("conversions", 0) or 0)
        impr   = int(met.get("impressions", 0) or 0)
        clicks = int(met.get("clicks", 0) or 0)
        ctr    = float(met.get("ctr", 0) or 0) * 100
        tgt    = micros(tc) if tc else None
        cpa_r  = cost / conv if conv > 0 else 0.0

        st = status.replace("ENABLED","ATIVO").replace("PAUSED","PAUSADO").replace("REMOVED","REMOVIDO")
        ts = brl(tgt) if tgt else "—"
        cs = brl(cpa_r) if cpa_r > 0 else "—"
        print(f"  {name[:52]:<52} {st:<9} {ts:>10} {brl(cost):>12} {conv:>6.0f} {cs:>12} {ctr:>5.2f}%")

        # Detecta captacao
        is_capt = bool(re.search(r'capta', name, re.IGNORECASE))
        captacao_rows.append({
            "name": name, "status": status, "tgt_cpa": tgt, "cost": cost,
            "conv": conv, "cpa_real": cpa_r, "impressions": impr, "clicks": clicks,
            "ctr": ctr, "is_captacao": is_capt,
        })

    # ── Análise por campanha ──────────────────────────────────────────────────
    print(f"\n{'─'*82}")
    print(f"  DIAGNOSTICO POR CAMPANHA DE CAPTACAO")
    print(f"{'─'*82}")

    REF_CPA = 12.70  # mediana historica captacao pura

    for c in sorted(captacao_rows, key=lambda x: x["cost"], reverse=True):
        if not c["is_captacao"]:
            continue

        tgt_str = brl(c["tgt_cpa"]) if c["tgt_cpa"] else "—"
        status_label = c["status"].replace("ENABLED","ATIVO").replace("PAUSED","PAUSADO")
        print(f"\n  [{status_label}] {c['name'][:70]}")
        print(f"    tCPA configurado: {tgt_str}")
        print(f"    Gasto:            {brl(c['cost'])}")
        print(f"    Conversoes:       {c['conv']:.0f}")
        print(f"    CPA real:         {brl(c['cpa_real']) if c['cpa_real'] > 0 else 'sem conversoes'}")

        if c["tgt_cpa"]:
            ratio = c["cpa_real"] / c["tgt_cpa"] if c["cpa_real"] > 0 else None
            if ratio:
                if ratio > 1.3:
                    diag = f"CPA ACIMA do target ({ratio:.1f}x) — campanha em dificuldade"
                elif ratio > 1.0:
                    diag = f"CPA ligeiramente acima do target ({ratio:.1f}x) — normal em learning"
                elif ratio < 0.7:
                    diag = f"CPA MUITO ABAIXO do target ({ratio:.1f}x) — possivel sub-entrega"
                else:
                    diag = f"CPA dentro do target ({ratio:.1f}x) — saudavel"
            else:
                diag = "Sem conversoes ainda — muito cedo para avaliar"

            diff_hist = c["tgt_cpa"] - REF_CPA
            hist_label = f"+{brl(diff_hist)}" if diff_hist >= 0 else brl(diff_hist)
            print(f"    Diagnostico:      {diag}")
            print(f"    vs. historico:    tCPA {hist_label} em relacao a mediana (R$ 12,70)")

            # Sugestao
            if c["cpa_real"] > 0 and c["cpa_real"] > c["tgt_cpa"] * 1.2:
                novo = round(c["cpa_real"] * 1.1, 2)
                print(f"    ACAO SUGERIDA:    Subir tCPA para ~{brl(novo)} para dar margem ao algoritmo")
            elif c["conv"] < 10 and c["cost"] > 500:
                novo = round((c["tgt_cpa"] or REF_CPA) * 1.15, 2)
                print(f"    ACAO SUGERIDA:    Poucas conversoes p/ volume gasto — subir tCPA para ~{brl(novo)}")
            elif c["cpa_real"] > 0 and c["cpa_real"] < c["tgt_cpa"] * 0.8:
                print(f"    ACAO SUGERIDA:    CPA bem abaixo do target — pode tentar baixar tCPA gradualmente")
            else:
                print(f"    ACAO SUGERIDA:    Manter e aguardar mais dados")

    # ── Dados diarios de captacao ─────────────────────────────────────────────
    print(f"\n{'─'*82}")
    print(f"  EVOLUCAO DIARIA DAS CAMPANHAS DE CAPTACAO (desde 17/08)")
    print(f"{'─'*82}")
    rows_d = search(token, Q_DIARIO)

    by_date: dict = {}
    for row in rows_d:
        met  = row.get("metrics", {})
        seg  = row.get("segments", {})
        date = seg.get("date", "")
        cost = micros(met.get("costMicros", 0))
        conv = float(met.get("conversions", 0) or 0)
        e = by_date.setdefault(date, {"cost": 0, "conv": 0})
        e["cost"] += cost
        e["conv"]  += conv

    print(f"  {'DATA':<12} {'GASTO':>12} {'CONV':>8} {'CPA DIA':>12}")
    print(f"  {'─'*12} {'─'*12} {'─'*8} {'─'*12}")
    for d in sorted(by_date.keys(), reverse=True):
        e   = by_date[d]
        cpa = e["cost"] / e["conv"] if e["conv"] > 0 else 0
        print(f"  {d:<12} {brl(e['cost']):>12} {e['conv']:>8.0f} {brl(cpa) if cpa else '—':>12}")

    print(f"\n{'='*82}\n")


if __name__ == "__main__":
    main()
