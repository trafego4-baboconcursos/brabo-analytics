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

def mutate_google_ads(customer_id: str, endpoint: str, payload: dict):
    token = get_access_token()
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "9335944411").replace("-", "")
    dev_token = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
        "login-customer-id": login_customer_id
    }
    
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"Erro HTTP {e.code} em {endpoint}: {err_body}")
        return None
    except Exception as e:
        print(f"Erro geral: {e}")
        return None

def main():
    cid = "6482320788"
    
    links = [
        ("customers/6482320788/adGroups/200956244576", "customers/6482320788/audiences/359410473"), # A00
        ("customers/6482320788/adGroups/203567131827", "customers/6482320788/audiences/359408850"), # A01
        ("customers/6482320788/adGroups/200191341509", "customers/6482320788/audiences/359408859"), # A02
        ("customers/6482320788/adGroups/200388484196", "customers/6482320788/audiences/360376705"), # Hotmart
        ("customers/6482320788/adGroups/204252802287", "customers/6482320788/audiences/360380089"), # Black 25
    ]

    print("=== VINCULANDO AUDIENCES AOS 5 GRUPOS DEMAND GEN ===")
    
    for ag_res, aud_res in links:
        crit_op = {
            "operations": [
                {
                    "create": {
                        "adGroup": ag_res,
                        "status": "ENABLED",
                        "audience": {"audience": aud_res}
                    }
                }
            ]
        }
        res = mutate_google_ads(cid, "adGroupCriteria:mutate", crit_op)
        if res:
            print(f"✅ Sucesso! Audience {aud_res.split('/')[-1]} vinculada ao Grupo {ag_res.split('/')[-1]}")
        else:
            print(f"❌ Falha ao vincular Audience {aud_res.split('/')[-1]} ao Grupo {ag_res.split('/')[-1]}")

if __name__ == "__main__":
    main()
