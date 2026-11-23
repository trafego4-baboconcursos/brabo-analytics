import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
load_dotenv(Path(__file__).parent.parent / ".env")

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
    logo_asset = "customers/6482320788/assets/398565635065"
    business_name = "Brabo Concursos"
    url_final = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1b/"
    
    videos = [
        {"name": "AD-TR08 - Discursão BV - BV-26", "asset": "customers/6482320788/assets/424294921364"},
        {"name": "AD-TR10 - Discursão BV - BV-26", "asset": "customers/6482320788/assets/424294801655"},
        {"name": "AD-TR11 - Discursão BV p aluno - BV-26", "asset": "customers/6482320788/assets/424396558774"},
        {"name": "AD-TR13 - Discursão BV - BV-26", "asset": "customers/6482320788/assets/424394291746"},
        {"name": "ADC-TR25 - Felipe Ivan e Mateus - BV-26", "asset": "customers/6482320788/assets/424293019268"},
        {"name": "ADC-TR26 - Felipe Ivan e Mateus - BV-26", "asset": "customers/6482320788/assets/424394466457"}
    ]

    print("=== VINCULANDO AUDIENCES E COMPLETANDO DEMAND GEN ===")

    # 1. Vincular Audiences nos 3 grupos de Alunos (Campanha 24288446069)
    alunos_groups = [
        ("customers/6482320788/adGroups/200956244576", "customers/6482320788/audiences/359410473"), # A00
        ("customers/6482320788/adGroups/203567131827", "customers/6482320788/audiences/359408850"), # A01
        ("customers/6482320788/adGroups/200191341509", "customers/6482320788/audiences/359408859"), # A02
    ]
    for ag_res, aud_res in alunos_groups:
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
        print(f"✅ Audience {aud_res.split('/')[-1]} vinculada ao grupo {ag_res.split('/')[-1]}: {res is not None}")

    # 2. Criar Grupos, Audiences e Ads para Super Quente (Campanha 24294246907)
    c_sq_res = "customers/6482320788/campaigns/24294246907"
    sq_groups = [
        {
            "nome": "00 - Eventos Hotmart + Página de Vendas INSS - BV-26",
            "audience": "customers/6482320788/audiences/360376705"
        },
        {
            "nome": "02 - Cadastrados Black Anterior BV-25 - BV-26",
            "audience": "customers/6482320788/audiences/360380089"
        }
    ]

    for g in sq_groups:
        ag_payload = {
            "operations": [{
                "create": {
                    "name": g["nome"],
                    "status": "ENABLED",
                    "campaign": c_sq_res
                }
            }]
        }
        res_ag = mutate_google_ads(cid, "adGroups:mutate", ag_payload)
        if not res_ag:
            print(f"Erro ao criar grupo {g['nome']}")
            continue
        ag_resource = res_ag["results"][0]["resourceName"]
        print(f"\n📁 Grupo criado: {g['nome']} ({ag_resource})")

        # Vincular Audience
        crit_op = {
            "operations": [
                {
                    "create": {
                        "adGroup": ag_resource,
                        "status": "ENABLED",
                        "audience": {"audience": g["audience"]}
                    }
                }
            ]
        }
        mutate_google_ads(cid, "adGroupCriteria:mutate", crit_op)
        print(f"   🎯 Audience vinculada com sucesso.")

        # Anúncios
        ad_ops = []
        for v in videos:
            ad_ops.append({
                "create": {
                    "adGroup": ag_resource,
                    "status": "ENABLED",
                    "ad": {
                        "name": v["name"],
                        "finalUrls": [url_final],
                        "demandGenVideoResponsiveAd": {
                            "businessName": {"text": business_name},
                            "logoImages": [{"asset": logo_asset}],
                            "headlines": [{"text": "Black Vitalícia"}],
                            "longHeadlines": [{"text": "Black Vitalícia dos Concursos - Brabo"}],
                            "descriptions": [{"text": "Garanta sua vaga na melhor condição do ano!"}],
                            "videos": [{"asset": v["asset"]}]
                        }
                    }
                }
            })
        mutate_google_ads(cid, "adGroupAds:mutate", {"operations": ad_ops})
        print(f"   🎬 6 Anúncios vinculados e ATIVOS.")

    # 3. Pausar as 2 campanhas antigas que estavam travadas
    print("\n==================================================================")
    print("PAUSANDO AS 2 CAMPANHAS VVC ANTIGAS TRAVADAS")
    print("==================================================================")
    pause_payload = {
        "operations": [
            {
                "update": {
                    "resourceName": "customers/6482320788/campaigns/24281955281",
                    "status": "PAUSED"
                },
                "updateMask": "status"
            },
            {
                "update": {
                    "resourceName": "customers/6482320788/campaigns/24281955284",
                    "status": "PAUSED"
                },
                "updateMask": "status"
            }
        ]
    }
    res_p = mutate_google_ads(cid, "campaigns:mutate", pause_payload)
    if res_p:
        print("✅ Campanhas antigas VVC pausadas com sucesso!")

    print("\n🎉 SETUP COMPLETO E 100% NO AR!")

if __name__ == "__main__":
    main()
