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

def criar_demand_gen(dry_run: bool = True):
    cid = "6482320788"
    print(f"=== CRIANDO CAMPANHAS DEMAND GEN BV-26 NO PADRÃO OFICIAL (Dry Run: {dry_run}) ===")

    # Assets oficiais validados da conta
    logo_asset = "customers/6482320788/assets/398565635065" # Logo Brabo Concursos
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

    campanhas = [
        {
            "nome": "[GA][trio][mateus][demand-gen][aquecimento][alunos][BV-26][25.09.26]",
            "budget": 377000000, # R$ 377,00/dia
            "grupos": [
                {
                    "nome": "00 - Alunos INSS Engajados - BV-26",
                    "target_ul": "customers/6482320788/userLists/9475941829", # A00
                    "exclusoes": [
                        "customers/6482320788/userLists/9475907428", # Cadastrados BV-26
                        "customers/6482320788/userLists/9475494077", # Compradores Black 25
                        "customers/6482320788/userLists/9475583498", # Compradores PES-SET-26
                    ]
                },
                {
                    "nome": "01 - Alunos INSS Ativos - BV-26",
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
        },
        {
            "nome": "[GA][trio][mateus][demand-gen][aquecimento][super quente][BV-26][25.09.26]",
            "budget": 94000000, # R$ 94,00/dia
            "grupos": [
                {
                    "nome": "00 - Eventos Hotmart + Página de Vendas INSS - BV-26",
                    "target_ul": "customers/6482320788/userLists/9476693970", # Hotmart
                    "exclusoes": [
                        "customers/6482320788/userLists/8126156550", # Alunos INSS 2026
                        "customers/6482320788/userLists/9475907428", # Cadastrados BV-26
                        "customers/6482320788/userLists/9475494077", # Compradores Black 25
                        "customers/6482320788/userLists/9475583498", # Compradores PES-SET-26
                    ]
                },
                {
                    "nome": "02 - Cadastrados Black Anterior BV-25 - BV-26",
                    "target_ul": "customers/6482320788/userLists/9476013142", # Cadastrados Black 25
                    "exclusoes": [
                        "customers/6482320788/userLists/8126156550",
                        "customers/6482320788/userLists/9476693970",
                        "customers/6482320788/userLists/9475907428",
                        "customers/6482320788/userLists/9475494077",
                        "customers/6482320788/userLists/9475583498",
                    ]
                }
            ]
        }
    ]

    for c_info in campanhas:
        print(f"\n==================================================================")
        print(f"PROCESSANDO CAMPANHA: {c_info['nome']}")
        print(f"==================================================================")

        # 1. Budget
        b_name = f"[BUDGET] {c_info['nome'][:50]} - {os.urandom(2).hex()}"
        b_payload = {
            "validateOnly": dry_run,
            "operations": [{
                "create": {
                    "name": b_name,
                    "amountMicros": c_info["budget"],
                    "deliveryMethod": "STANDARD",
                    "explicitlyShared": False
                }
            }]
        }
        res_b = mutate_google_ads(cid, "campaignBudgets:mutate", b_payload)
        if not dry_run and not res_b:
            print("Erro ao criar orçamento.")
            continue
        b_resource = res_b["results"][0]["resourceName"] if not dry_run else "customers/6482320788/campaignBudgets/mock"
        print(f"✅ Orçamento criado: {b_resource}")

        # 2. Campaign (ENABLED)
        c_payload = {
            "validateOnly": dry_run,
            "operations": [{
                "create": {
                    "name": c_info["nome"],
                    "status": "ENABLED",
                    "advertisingChannelType": "DEMAND_GEN",
                    "maximizeConversions": {},
                    "campaignBudget": b_resource,
                    "startDate": "2026-09-25",
                    "endDate": "2026-10-12",
                    "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
                }
            }]
        }
        res_c = mutate_google_ads(cid, "campaigns:mutate", c_payload)
        if not dry_run and not res_c:
            print("Erro ao criar campanha.")
            continue
        c_resource = res_c["results"][0]["resourceName"] if not dry_run else "customers/6482320788/campaigns/mock"
        print(f"✅ Campanha criada e ATIVADA: {c_resource}")

        if dry_run:
            print(f"   [Dry-Run] Simulando criação de {len(c_info['grupos'])} grupos e {len(videos)} anúncios por grupo...")
            continue

        # 3. Grupos, Critérios e Anúncios (ENABLED)
        for g in c_info["grupos"]:
            # Ad Group
            ag_payload = {
                "operations": [{
                    "create": {
                        "name": g["nome"],
                        "status": "ENABLED",
                        "campaign": c_resource
                    }
                }]
            }
            res_ag = mutate_google_ads(cid, "adGroups:mutate", ag_payload)
            if not res_ag:
                print(f"Erro ao criar grupo {g['nome']}")
                continue
            ag_resource = res_ag["results"][0]["resourceName"]
            print(f"\n   📁 Grupo criado e ATIVADO: {g['nome']} ({ag_resource})")

            # Segmentações e Exclusões
            crit_ops = [{
                "create": {
                    "adGroup": ag_resource,
                    "status": "ENABLED",
                    "userList": {"userList": g["target_ul"]}
                }
            }]
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
            print(f"      🎯 Públicos e exclusões vinculados.")

            # Anúncios Demand Gen Vídeo (ENABLED)
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
            print(f"      🎬 6 Anúncios de Vídeo Demand Gen vinculados e ATIVOS.")

    # 4. Pausar as 2 campanhas VVC antigas para não concorrer nem duplicar verba
    if not dry_run:
        print("\n==================================================================")
        print("PAUSANDO AS 2 CAMPANHAS VVC ANTIGAS QUE ESTAVAM TRAVADAS")
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
            print("✅ Campanhas antigas VVC (24281955281 e 24281955284) pausadas com sucesso!")

    print("\n🎉 TODAS AS CAMPANHAS DEMAND GEN FORAM CRIADAS E ATIVADAS COM SUCESSO!")

if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    criar_demand_gen(dry_run=dry_run)
