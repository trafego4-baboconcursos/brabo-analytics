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

def criar_campanha_instream(dry_run: bool = True):
    cid = "6482320788"
    print(f"=== CRIANDO CAMPANHA DE VÍDEO IN-STREAM PULÁVEL (CPV PURO) NA CONTA {cid} (Dry Run: {dry_run}) ===")

    # 1. Orçamento
    budget_name = f"[BUDGET] In-stream Alunos BV-26 - {os.urandom(3).hex()}"
    budget_payload = {
        "validateOnly": dry_run,
        "operations": [
            {
                "create": {
                    "name": budget_name,
                    "amountMicros": 377000000, # R$ 377,00/dia
                    "deliveryMethod": "STANDARD",
                    "explicitlyShared": False
                }
            }
        ]
    }
    res_b = mutate_google_ads(cid, "campaignBudgets:mutate", budget_payload)
    if not res_b and not dry_run:
        print("Falha ao criar orçamento.")
        return
    budget_resource = res_b["results"][0]["resourceName"] if not dry_run else "customers/6482320788/campaignBudgets/mock"
    print(f"✅ Orçamento preparado: {budget_resource}")

    # 2. Campanha
    camp_name = "[GA][trio][mateus][engajamento][aquecimento][alunos-instream][BV-26][25.09.26]"
    camp_payload = {
        "validateOnly": dry_run,
        "operations": [
            {
                "create": {
                    "name": camp_name,
                    "status": "PAUSED",
                    "advertisingChannelType": "VIDEO",
                    "manualCpv": {},
                    "campaignBudget": budget_resource,
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
    if not dry_run:
        res_c = mutate_google_ads(cid, "campaigns:mutate", camp_payload)
        if not res_c:
            print("Falha ao criar campanha.")
            return
        camp_resource = res_c["results"][0]["resourceName"]
        camp_id = camp_resource.split("/")[-1]
        print(f"✅ Campanha criada: {camp_resource} (ID: {camp_id})")
    else:
        camp_resource = "customers/6482320788/campaigns/mock"
        camp_id = "mock"
        print(f"✅ [Dry-Run] Campanha validada: {camp_name}")

    # 3. Grupos de Anúncios (In-stream Pulável)
    grupos_config = [
        {
            "nome": "00 - Alunos INSS Engajados - BV-26",
            "cpv": 200000, # R$ 0,20
            "target_ul": "customers/6482320788/userLists/9475941829", # A00
            "exclusoes": [
                "customers/6482320788/userLists/9475907428", # Cadastrados BV-26
                "customers/6482320788/userLists/9475494077", # Compradores Black 25
                "customers/6482320788/userLists/9475583498", # Compradores PES-SET-26
            ]
        },
        {
            "nome": "01 - Alunos INSS Ativos - BV-26",
            "cpv": 200000, # R$ 0,20
            "target_ul": "customers/6482320788/userLists/9476764542", # A01
            "exclusoes": [
                "customers/6482320788/userLists/9475941829", # A00
                "customers/6482320788/userLists/9475907428",
                "customers/6482320788/userLists/9475494077",
                "customers/6482320788/userLists/9475583498",
            ]
        },
        {
            "nome": "02 - Alunos INSS Inativos - BV-26",
            "cpv": 200000, # R$ 0,20
            "target_ul": "customers/6482320788/userLists/9476008837", # A02
            "exclusoes": [
                "customers/6482320788/userLists/9475941829", # A00
                "customers/6482320788/userLists/9476764542", # A01
                "customers/6482320788/userLists/9475907428",
                "customers/6482320788/userLists/9475494077",
                "customers/6482320788/userLists/9475583498",
            ]
        }
    ]

    videos = [
        {"name": "AD-TR08 - Discursão BV - BV-26", "asset": "customers/6482320788/assets/424294921364"},
        {"name": "AD-TR10 - Discursão BV - BV-26", "asset": "customers/6482320788/assets/424294801655"},
        {"name": "AD-TR11 - Discursão BV p aluno - BV-26", "asset": "customers/6482320788/assets/424396558774"},
        {"name": "AD-TR13 - Discursão BV - BV-26", "asset": "customers/6482320788/assets/424394291746"},
        {"name": "ADC-TR25 - Felipe Ivan e Mateus - BV-26", "asset": "customers/6482320788/assets/424293019268"},
        {"name": "ADC-TR26 - Felipe Ivan e Mateus - BV-26", "asset": "customers/6482320788/assets/424394466457"}
    ]
    url_final = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1b/"

    if not dry_run:
        for g in grupos_config:
            # Cria grupo
            ag_payload = {
                "operations": [
                    {
                        "create": {
                            "name": g["nome"],
                            "status": "PAUSED",
                            "campaign": camp_resource,
                            "type": "VIDEO_TRUE_VIEW_IN_STREAM",
                            "cpvBidMicros": g["cpv"]
                        }
                    }
                ]
            }
            res_ag = mutate_google_ads(cid, "adGroups:mutate", ag_payload)
            if not res_ag:
                print(f"Erro ao criar grupo {g['nome']}")
                continue
            ag_resource = res_ag["results"][0]["resourceName"]
            print(f"\n📁 Grupo criado: {g['nome']} ({ag_resource})")

            # Segmentação positiva
            crit_ops = [
                {
                    "create": {
                        "adGroup": ag_resource,
                        "status": "ENABLED",
                        "userList": {"userList": g["target_ul"]}
                    }
                }
            ]
            # Exclusões
            for exc in g["exclusoes"]:
                crit_ops.append({
                    "create": {
                        "adGroup": ag_resource,
                        "status": "ENABLED",
                        "negative": True,
                        "userList": {"userList": exc}
                    }
                })
            mutate_google_ads(cid, "adGroupCriteria:mutate", {"operations": crit_ops})
            print(f"   🎯 Públicos e exclusões vinculados.")

            # Anúncios em Vídeo
            ad_ops = []
            for v in videos:
                ad_ops.append({
                    "create": {
                        "adGroup": ag_resource,
                        "status": "ENABLED",
                        "ad": {
                            "name": v["name"],
                            "finalUrls": [url_final],
                            "videoResponsiveAd": {
                                "videos": [{"asset": v["asset"]}],
                                "descriptions": [{"text": "Black Vitalícia - Brabo Concursos"}],
                                "callToActions": [{"text": "Saiba mais"}]
                            }
                        }
                    }
                })
            mutate_google_ads(cid, "adGroupAds:mutate", {"operations": ad_ops})
            print(f"   🎬 6 Anúncios em vídeo vinculados.")

    print("\n🎉 Execução concluída!")

if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    criar_campanha_instream(dry_run=dry_run)
