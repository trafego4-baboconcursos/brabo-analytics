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
            print(f"Erro HTTP {e.code}: {err_body}")
            break
        except Exception as e:
            print(f"Erro geral: {e}")
            break
    return results

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
    ag_id = 200194462789 # Grupo 01 - VIP
    
    q = f"""
    SELECT
      ad_group_ad.ad.id,
      ad_group_ad.ad.name,
      ad_group_ad.status
    FROM ad_group_ad
    WHERE ad_group.id = {ag_id} AND ad_group_ad.status != 'REMOVED'
    """
    res = query_google_ads(cid, q)
    print(f"Anúncios existentes no grupo 200194462789: {len(res)}")
    
    if len(res) == 0:
        print("Reenviando anúncios para o grupo 01...")
        logo_asset = "customers/6482320788/assets/398565635065"
        business_name = "Brabo Concursos"
        url_final = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1b/"
        criativos = [
            {"name": "AD-TR08 - Discursão BV - BV-26 (Multi-Formato)", "video_assets": ["customers/6482320788/assets/424294921364", "customers/6482320788/assets/424589027945", "customers/6482320788/assets/424589014982"]},
            {"name": "AD-TR10 - Discursão BV - BV-26 (Multi-Formato)", "video_assets": ["customers/6482320788/assets/424294801655", "customers/6482320788/assets/424774655625", "customers/6482320788/assets/424589039657"]},
            {"name": "AD-TR11 - Discursão BV p aluno - BV-26 (Multi-Formato)", "video_assets": ["customers/6482320788/assets/424396558774", "customers/6482320788/assets/424690590598", "customers/6482320788/assets/424589040548"]},
            {"name": "AD-TR13 - Discursão BV - BV-26 (Multi-Formato)", "video_assets": ["customers/6482320788/assets/424394291746", "customers/6482320788/assets/424774667556", "customers/6482320788/assets/424690595464"]},
            {"name": "ADC-TR25 - Felipe Ivan e Mateus - BV-26 (Multi-Formato)", "video_assets": ["customers/6482320788/assets/424293019268", "customers/6482320788/assets/424589095562", "customers/6482320788/assets/424774701591"]},
            {"name": "ADC-TR26 - Felipe Ivan e Mateus - BV-26 (Multi-Formato)", "video_assets": ["customers/6482320788/assets/424394466457", "customers/6482320788/assets/424690611781", "customers/6482320788/assets/424690612156"]}
        ]
        ad_ops = []
        for c in criativos:
            v_list = [{"asset": a_res} for a_res in c["video_assets"]]
            ad_ops.append({
                "create": {
                    "adGroup": f"customers/6482320788/adGroups/{ag_id}",
                    "status": "ENABLED",
                    "ad": {
                        "name": c["name"],
                        "finalUrls": [url_final],
                        "demandGenVideoResponsiveAd": {
                            "businessName": {"text": business_name},
                            "logoImages": [{"asset": logo_asset}],
                            "headlines": [{"text": "Black Vitalícia"}],
                            "longHeadlines": [{"text": "Black Vitalícia dos Concursos - Brabo"}],
                            "descriptions": [{"text": "Garanta sua vaga na melhor condição do ano!"}],
                            "videos": v_list
                        }
                    }
                }
            })
        res_ad = mutate_google_ads(cid, "adGroupAds:mutate", {"operations": ad_ops})
        print(f"✅ Anúncios criados no grupo 01: {res_ad is not None}")

if __name__ == "__main__":
    main()
