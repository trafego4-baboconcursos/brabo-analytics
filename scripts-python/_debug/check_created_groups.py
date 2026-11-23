import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
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
            print(f"Erro HTTP na conta {customer_id}: {e.code} - {err_body}", flush=True)
            break
        except Exception as e:
            print(f"Erro geral: {e}", flush=True)
            break
    return results

def main():
    cid = "6482320788"
    for c_id in [24288446069, 24294246907]:
        q = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE campaign.id = {c_id}
        """
        res = query_google_ads(cid, q)
        print(f"\n--- CAMPANHA {c_id} ---")
        for r in res:
            print(f"Grupo [{r.get('adGroup', {}).get('id')}]: {r.get('adGroup', {}).get('name')} | Status: {r.get('adGroup', {}).get('status')}")

if __name__ == "__main__":
    main()
