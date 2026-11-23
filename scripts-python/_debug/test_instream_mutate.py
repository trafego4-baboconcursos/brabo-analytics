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
        print(f"Erro HTTP {e.code}: {err_body}")
        return None
    except Exception as e:
        print(f"Erro geral: {e}")
        return None

def main():
    cid = "6482320788"
    print("Testando criação de Campanha de Vídeo Personalizada (In-stream Pulável) via API...")

    # 1. Testar criação da Campanha com Manual CPV
    camp_payload = {
        "validateOnly": True,
        "operations": [
            {
                "create": {
                    "name": "[GA][trio][mateus][engajamento][aquecimento][alunos-instream][BV-26][25.09.26]",
                    "status": "PAUSED",
                    "advertisingChannelType": "VIDEO",
                    "manualCpv": {},
                    "campaignBudget": "customers/6482320788/campaignBudgets/123456",
                    "networkSettings": {
                        "targetYoutube": True,
                        "targetContentNetwork": True
                    },
                    "startDate": "2026-09-25",
                    "endDate": "2026-10-12"
                }
            }
        ]
    }
    res_c = mutate_google_ads(cid, "campaigns:mutate", camp_payload)
    print("Campaign validateOnly:", res_c)

    # 2. Testar criação do AdGroup tipo VIDEO_TRUE_VIEW_IN_STREAM com CPV Manual
    ag_payload = {
        "validateOnly": True,
        "operations": [
            {
                "create": {
                    "name": "00 - Alunos INSS Engajados - BV-26",
                    "status": "PAUSED",
                    "campaign": "customers/6482320788/campaigns/123456",
                    "type": "VIDEO_TRUE_VIEW_IN_STREAM",
                    "cpvBidMicros": 200000
                }
            }
        ]
    }
    res_ag = mutate_google_ads(cid, "adGroups:mutate", ag_payload)
    print("AdGroup validateOnly:", res_ag)

if __name__ == "__main__":
    main()
