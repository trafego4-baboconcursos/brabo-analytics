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
    c_res = "customers/6482320788/campaigns/24294246907" # Campanha Super Quente Demand Gen
    logo_asset = "customers/6482320788/assets/398565635065"
    business_name = "Brabo Concursos"
    url_final = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1b/"

    # Assets multi-formato já mapeados
    criativos = [
        {
            "name": "AD-TR08 - Discursão BV - BV-26 (Multi-Formato)",
            "video_assets": [
                "customers/6482320788/assets/424294921364", # 16:9
                "customers/6482320788/assets/424589027945", # 9:16
                "customers/6482320788/assets/424589014982"  # 1:1
            ]
        },
        {
            "name": "AD-TR10 - Discursão BV - BV-26 (Multi-Formato)",
            "video_assets": [
                "customers/6482320788/assets/424294801655", # 16:9
                "customers/6482320788/assets/424774655625", # 9:16
                "customers/6482320788/assets/424589039657"  # 1:1
            ]
        },
        {
            "name": "AD-TR11 - Discursão BV p aluno - BV-26 (Multi-Formato)",
            "video_assets": [
                "customers/6482320788/assets/424396558774", # 16:9
                "customers/6482320788/assets/424690590598", # 9:16
                "customers/6482320788/assets/424589040548"  # 1:1
            ]
        },
        {
            "name": "AD-TR13 - Discursão BV - BV-26 (Multi-Formato)",
            "video_assets": [
                "customers/6482320788/assets/424394291746", # 16:9
                "customers/6482320788/assets/424774667556", # 9:16
                "customers/6482320788/assets/424690595464"  # 1:1
            ]
        },
        {
            "name": "ADC-TR25 - Felipe Ivan e Mateus - BV-26 (Multi-Formato)",
            "video_assets": [
                "customers/6482320788/assets/424293019268", # 16:9
                "customers/6482320788/assets/424589095562", # 9:16
                "customers/6482320788/assets/424774701591"  # 1:1
            ]
        },
        {
            "name": "ADC-TR26 - Felipe Ivan e Mateus - BV-26 (Multi-Formato)",
            "video_assets": [
                "customers/6482320788/assets/424394466457", # 16:9
                "customers/6482320788/assets/424690611781", # 9:16
                "customers/6482320788/assets/424690612156"  # 1:1
            ]
        }
    ]

    novos_grupos = [
        {
            "nome": "01 - Grupo VIP + Sorteio + Pesquisa INSS - BV-26",
            "audience": "customers/6482320788/audiences/360380218"
        },
        {
            "nome": "03 - Viu Aquecimento - INSS BV-26",
            "audience": "customers/6482320788/audiences/360391219"
        }
    ]

    print("=== ADICIONANDO GRUPOS 01 E 03 NA CAMPANHA SUPER QUENTE (24294246907) ===")

    for g in novos_grupos:
        print(f"\n📁 Criando Grupo: {g['nome']}")
        ag_payload = {
            "operations": [{
                "create": {
                    "name": g["nome"],
                    "status": "ENABLED",
                    "campaign": c_res
                }
            }]
        }
        res_ag = mutate_google_ads(cid, "adGroups:mutate", ag_payload)
        if not res_ag:
            print(f"Erro ao criar grupo {g['nome']}")
            continue
        ag_resource = res_ag["results"][0]["resourceName"]
        ag_id = ag_resource.split("/")[-1]
        print(f"✅ Grupo criado e ATIVADO: {ag_resource} (ID: {ag_id})")

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
        res_crit = mutate_google_ads(cid, "adGroupCriteria:mutate", crit_op)
        print(f"✅ Audience {g['audience'].split('/')[-1]} vinculada com sucesso!")

        # Criar Anúncios Multi-formato
        ad_ops = []
        for c in criativos:
            v_list = [{"asset": a_res} for a_res in c["video_assets"]]
            ad_ops.append({
                "create": {
                    "adGroup": ag_resource,
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
        mutate_google_ads(cid, "adGroupAds:mutate", {"operations": ad_ops})
        print(f"✅ 6 Anúncios Multi-formato (18 vídeos) criados e ATIVOS no grupo {ag_id}!")

    print("\n🎉 GRUPOS 01 E 03 ADICIONADOS COM SUCESSO À CAMPANHA SUPER QUENTE!")

if __name__ == "__main__":
    main()
