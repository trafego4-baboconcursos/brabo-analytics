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
    
    # 1. Vincular Hotmart Audience ao grupo 203567200707
    crit_op = {
        "operations": [
            {
                "create": {
                    "adGroup": "customers/6482320788/adGroups/203567200707",
                    "status": "ENABLED",
                    "audience": {"audience": "customers/6482320788/audiences/360376705"}
                }
            }
        ]
    }
    res = mutate_google_ads(cid, "adGroupCriteria:mutate", crit_op)
    print(f"✅ Hotmart Audience vinculada ao Grupo 203567200707: {res is not None}")

    # 2. Pausar os grupos das 2 campanhas antigas para zerar gasto antigo
    print("Pausando grupos das campanhas antigas VVC...")
    pause_ag_payload = {
        "operations": [
            {"update": {"resourceName": "customers/6482320788/adGroups/198243951337", "status": "PAUSED"}, "updateMask": "status"},
            {"update": {"resourceName": "customers/6482320788/adGroups/198243951497", "status": "PAUSED"}, "updateMask": "status"},
            {"update": {"resourceName": "customers/6482320788/adGroups/198243951537", "status": "PAUSED"}, "updateMask": "status"},
            {"update": {"resourceName": "customers/6482320788/adGroups/198243951257", "status": "PAUSED"}, "updateMask": "status"},
            {"update": {"resourceName": "customers/6482320788/adGroups/198243951297", "status": "PAUSED"}, "updateMask": "status"}
        ]
    }
    res_pag = mutate_google_ads(cid, "adGroups:mutate", pause_ag_payload)
    print("Grupos antigos pausados com sucesso:", res_pag is not None)

if __name__ == "__main__":
    main()
