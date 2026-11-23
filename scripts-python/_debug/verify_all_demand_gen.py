import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_VERSION = "v22"

def get_access_token():
    import google.oauth2.credentials
    import google.auth.transport.requests
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token

def query_google_ads(customer_id: str, query: str):
    token = get_access_token()
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "9335944411").replace("-", "")
    dev_token = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
        "login-customer-id": login_customer_id
    }
    
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
    results = []
    page_token = None
    
    while True:
        payload = {"query": query}
        if page_token:
            payload["pageToken"] = page_token
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                results.extend(data.get("results", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"Erro HTTP {e.code}: {err_body}")
            break
        except Exception as e:
            print(f"Erro geral: {e}")
            break
    return results

def main():
    cid = "6482320788"
    campaign_ids = [24288446069, 24294246907]
    
    for c_id in campaign_ids:
        q_c = f"SELECT campaign.id, campaign.name, campaign.status, campaign_budget.amount_micros FROM campaign WHERE campaign.id = {c_id}"
        c_res = query_google_ads(cid, q_c)
        if not c_res:
            continue
        c_data = c_res[0]["campaign"]
        b_micros = int(c_res[0].get("campaignBudget", {}).get("amountMicros", 0))
        b_reais = b_micros / 1_000_000
        
        print(f"\n{'='*70}")
        print(f"🎯 CAMPANHA: {c_data['name']} (ID: {c_data['id']})")
        print(f"   Status: {c_data['status']} | Orçamento: R$ {b_reais:.2f}/dia")
        print(f"{'='*70}")
        
        q_ag = f"SELECT ad_group.id, ad_group.name, ad_group.status FROM ad_group WHERE campaign.id = {c_id} ORDER BY ad_group.name"
        ag_res = query_google_ads(cid, q_ag)
        
        for ag_item in ag_res:
            ag = ag_item["adGroup"]
            ag_id = ag["id"]
            
            # Get criteria
            q_crit = f"SELECT ad_group_criterion.criterion_id, ad_group_criterion.type, ad_group_criterion.status FROM ad_group_criterion WHERE ad_group.id = {ag_id}"
            crit_res = query_google_ads(cid, q_crit)
            
            # Get ads
            q_ads = f"SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.status FROM ad_group_ad WHERE ad_group.id = {ag_id} AND ad_group_ad.status != 'REMOVED'"
            ads_res = query_google_ads(cid, q_ads)
            
            print(f"  📁 Grupo: {ag['name']} (ID: {ag_id}) [{ag['status']}]")
            print(f"     - Público/Critérios vinculados: {len(crit_res)}")
            print(f"     - Total de Anúncios Ativos: {len(ads_res)}")
            for ad_item in ads_res:
                ad = ad_item["adGroupAd"]
                print(f"       * {ad['ad']['name']} (ID: {ad['ad']['id']}) [{ad['status']}]")

if __name__ == "__main__":
    main()
