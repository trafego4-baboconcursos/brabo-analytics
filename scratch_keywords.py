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
    campaign.name,
    ad_group.name,
    ad_group_criterion.keyword.text,
    ad_group_criterion.keyword.match_type,
    ad_group_criterion.status
FROM keyword_view
WHERE campaign.name LIKE '%search%pi-ago-26%'
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
        print("ERRO", r.status_code, r.text[:3000])
        break
    data = r.json()
    rows.extend(data.get("results", []))
    page_token = data.get("nextPageToken")
    if not page_token:
        break

print(f"{len(rows)} palavras-chave configuradas")
for row in rows:
    ag = row.get("adGroup", {})
    crit = row.get("adGroupCriterion", {})
    kw = crit.get("keyword", {})
    print(ag.get("name"), "|", kw.get("text"), "|", kw.get("matchType"), "|", crit.get("status"))

print("\n\n=== Todas as campanhas dessa conta com 'search' no nome ===")
query2 = "SELECT campaign.name, campaign.id FROM campaign WHERE campaign.name LIKE '%search%'"
payload = {"query": query2}
r = requests.post(url, headers=headers, json=payload)
data = r.json()
for row in data.get("results", []):
    print(row["campaign"]["name"], row["campaign"]["id"])
