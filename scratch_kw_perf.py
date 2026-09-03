import sys, os
sys.path.insert(0,'src')
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0,'etl')
from etl_google_ads import _get_access_token, API_VERSION
import requests

customer_id = '6482320788'
login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")

headers = {
    "Authorization": f"Bearer {_get_access_token()}",
    "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
    "Content-Type": "application/json",
}
if login_customer_id:
    headers["login-customer-id"] = login_customer_id

query = """
SELECT
    ad_group.name,
    ad_group_criterion.keyword.text,
    ad_group_criterion.keyword.match_type,
    ad_group_criterion.quality_info.quality_score,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions,
    metrics.average_cpc
FROM keyword_view
WHERE campaign.id = 24074486341
  AND segments.date BETWEEN '2026-07-27' AND '2026-07-28'
"""

url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
rows = []
page_token = None
while True:
    payload = {"query": query}
    if page_token:
        payload["pageToken"] = page_token
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        print("ERRO", r.status_code, r.text[:2000]); break
    data = r.json()
    rows.extend(data.get("results", []))
    page_token = data.get("nextPageToken")
    if not page_token:
        break

# agrupar por keyword (soma os 2 dias)
agg = {}
for row in rows:
    ag = row.get("adGroup", {}).get("name")
    crit = row.get("adGroupCriterion", {})
    kw = crit.get("keyword", {}).get("text")
    mt = crit.get("keyword", {}).get("matchType")
    qs = crit.get("qualityInfo", {}).get("qualityScore")
    m = row.get("metrics", {})
    key = (ag, kw, mt)
    if key not in agg:
        agg[key] = {"impr":0, "clicks":0, "cost":0, "conv":0.0, "qs": qs}
    agg[key]["impr"] += int(m.get("impressions",0) or 0)
    agg[key]["clicks"] += int(m.get("clicks",0) or 0)
    agg[key]["cost"] += int(m.get("costMicros",0) or 0)/1_000_000
    agg[key]["conv"] += float(m.get("conversions",0) or 0)
    if qs: agg[key]["qs"] = qs

print(f"{len(agg)} palavras-chave (agregado 2 dias)\n")
for (ag,kw,mt), v in sorted(agg.items(), key=lambda x: -x[1]["cost"]):
    ctr = v["clicks"]/v["impr"]*100 if v["impr"] else 0
    cpc = v["cost"]/v["clicks"] if v["clicks"] else 0
    cpa = v["cost"]/v["conv"] if v["conv"] else None
    print(f"{ag:35s} | {kw:35s} | QS={v['qs']} | impr={v['impr']:5d} clk={v['clicks']:3d} CTR={ctr:5.2f}% custo=R${v['cost']:7.2f} CPC=R${cpc:.2f} conv={v['conv']:.0f} CPA={cpa}")
