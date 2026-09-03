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
url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"

def run(query):
    rows = []
    page_token = None
    while True:
        payload = {"query": query}
        if page_token: payload["pageToken"] = page_token
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            print("ERRO", r.status_code, r.text[:3000]); return rows
        data = r.json()
        rows.extend(data.get("results", []))
        page_token = data.get("nextPageToken")
        if not page_token: break
    return rows

camp_ids = [24053528552, 24048538302, 24058119820]  # frio principal, quente principal, especifico principal
ids_str = ",".join(str(c) for c in camp_ids)

rows = run(f"""
    SELECT campaign.name, ad_group.name, ad_group_ad.resource_name, ad_group_ad.ad.name, ad_group_ad.status
    FROM ad_group_ad
    WHERE campaign.id IN ({ids_str}) AND ad_group_ad.status != 'REMOVED'
""")

matches = [r for r in rows if r.get("adGroupAd",{}).get("ad",{}).get("name","").startswith("AD127 -")]
print(f"Total ads nas 3 campanhas: {len(rows)} | Matches AD127: {len(matches)}")

operations = []
for m in matches:
    rn = m["adGroupAd"]["resourceName"]
    operations.append({
        "update": {"resourceName": rn, "status": "PAUSED"},
        "updateMask": "status"
    })
    print(rn, "|", m["campaign"]["name"], "|", m["adGroup"]["name"], "|", m["adGroupAd"]["status"])

print(f"\n{len(operations)} operacoes de pausa a executar")

if operations:
    mutate_url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/adGroupAds:mutate"
    r = requests.post(mutate_url, headers=headers, json={"operations": operations})
    print(r.status_code)
    if r.status_code != 200:
        print(r.text[:5000])
    else:
        data = r.json()
        print(f"{len(data.get('results', []))} pausados com sucesso")
