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
    search_term_view.search_term,
    campaign.name,
    ad_group.name,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions
FROM search_term_view
WHERE segments.date BETWEEN '2026-07-27' AND '2026-07-28'
  AND campaign.id = 24074486341
ORDER BY metrics.clicks DESC
"""

url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
rows = []
page_token = None
while True:
    payload = {"query": query}
    if page_token:
        payload["pageToken"] = page_token
    r = requests.post(url, headers=headers, json=payload)
    data = r.json()
    rows.extend(data.get("results", []))
    page_token = data.get("nextPageToken")
    if not page_token:
        break

print(f"{len(rows)} termos (SO PI-AGO-26)")

suspicious = ['aposent','benefic','pericia','perícia','vaga','emprego','advogad','consulta','extrato','loas','bpc','auxilio','auxílio','estagio','estágio','processo seletivo','app','login','telefone','135','agendamento','bahia','salvador','enfermagem','tjsp','concurso publico','concurso p\u00fablico']
seen = set()
print("\n=== Termos potencialmente fora do tema (PI-AGO-26 real) ===")
for row in rows:
    stv = row.get("searchTermView", {})
    term = (stv.get("searchTerm") or "").lower()
    if term in seen: continue
    if any(s in term for s in suspicious):
        seen.add(term)
        m = row.get("metrics", {})
        ag = row.get("adGroup", {})
        print(term, "|", ag.get("name"), "|", m.get("impressions"), m.get("clicks"), m.get("costMicros"), m.get("conversions"))

print(f"\nTotal de termos suspeitos encontrados: {len(seen)}")
