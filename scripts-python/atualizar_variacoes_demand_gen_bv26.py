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

def get_or_create_video_asset(cid: str, yt_id: str, asset_name: str) -> str:
    # 1. Buscar se já existe asset para esse youtube_video_id
    q = f"""
    SELECT
      asset.resource_name,
      asset.id,
      asset.name,
      asset.youtube_video_asset.youtube_video_id
    FROM asset
    WHERE asset.type = 'YOUTUBE_VIDEO' AND asset.youtube_video_asset.youtube_video_id = '{yt_id}'
    """
    res = query_google_ads(cid, q)
    if res:
        asset_res = res[0]["asset"]["resourceName"]
        return asset_res
    
    # 2. Se não existir, criar novo asset
    payload = {
        "operations": [
            {
                "create": {
                    "name": asset_name,
                    "type": "YOUTUBE_VIDEO",
                    "youtubeVideoAsset": {
                        "youtubeVideoId": yt_id
                    }
                }
            }
        ]
    }
    mut = mutate_google_ads(cid, "assets:mutate", payload)
    if mut and "results" in mut and mut["results"]:
        return mut["results"][0]["resourceName"]
    return None

def main():
    cid = "6482320788"
    logo_asset = "customers/6482320788/assets/398565635065"
    business_name = "Brabo Concursos"
    url_final = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1b/"

    print("="*90)
    print("PREPARANDO ASSETS DE TODAS AS VARIAÇÕES (16:9, 9:16 e 1:1)")
    print("="*90)

    criativos_completos = [
        {
            "ad_name": "AD-TR08 - Discursão BV - BV-26 (Multi-Formato)",
            "videos": [
                {"id": "C2MQCvtq_l8", "tipo": "16:9 (Horizontal)"},
                {"id": "oda8Z3MNIGY", "tipo": "9:16 (Story/Shorts)"},
                {"id": "JIzBUwRUalg", "tipo": "1:1 (Feed/Quadrado)"}
            ]
        },
        {
            "ad_name": "AD-TR10 - Discursão BV - BV-26 (Multi-Formato)",
            "videos": [
                {"id": "mAifc1plGXw", "tipo": "16:9 (Horizontal)"},
                {"id": "FbE3eVGE1_E", "tipo": "9:16 (Story/Shorts)"},
                {"id": "7iGNHYlTwXc", "tipo": "1:1 (Feed/Quadrado)"}
            ]
        },
        {
            "ad_name": "AD-TR11 - Discursão BV p aluno - BV-26 (Multi-Formato)",
            "videos": [
                {"id": "WU8iTEyzd0c", "tipo": "16:9 (Horizontal)"},
                {"id": "aVEM2LCsFlE", "tipo": "9:16 (Story/Shorts)"},
                {"id": "i8YjQu5DZmk", "tipo": "1:1 (Feed/Quadrado)"}
            ]
        },
        {
            "ad_name": "AD-TR13 - Discursão BV - BV-26 (Multi-Formato)",
            "videos": [
                {"id": "iuv7LEN4QYk", "tipo": "16:9 (Horizontal)"},
                {"id": "qDwpGdhizsI", "tipo": "9:16 (Story/Shorts)"},
                {"id": "EcZgZ26QxHQ", "tipo": "1:1 (Feed/Quadrado)"}
            ]
        },
        {
            "ad_name": "ADC-TR25 - Felipe Ivan e Mateus - BV-26 (Multi-Formato)",
            "videos": [
                {"id": "VX_AZ0I8jD4", "tipo": "16:9 (Horizontal)"},
                {"id": "o4g0x3GhHjM", "tipo": "9:16 (Story/Shorts)"},
                {"id": "dO23cvIcix4", "tipo": "1:1 (Feed/Quadrado)"}
            ]
        },
        {
            "ad_name": "ADC-TR26 - Felipe Ivan e Mateus - BV-26 (Multi-Formato)",
            "videos": [
                {"id": "hgCon8Qv3xQ", "tipo": "16:9 (Horizontal)"},
                {"id": "hkPLHjmLZOM", "tipo": "9:16 (Story/Shorts)"},
                {"id": "5qIPTgso9KI", "tipo": "1:1 (Feed/Quadrado)"}
            ]
        }
    ]

    # Resolver Asset Resource para cada vídeo
    for c in criativos_completos:
        print(f"\nResolvendo assets para: {c['ad_name']}")
        c["asset_resources"] = []
        for v in c["videos"]:
            asset_res = get_or_create_video_asset(cid, v["id"], f"{c['ad_name']} [{v['tipo']}]")
            print(f"  -> {v['tipo']} (ID: {v['id']}) => {asset_res}")
            if asset_res:
                c["asset_resources"].append(asset_res)

    # 5 Grupos nas 2 campanhas
    ad_groups = [
        "customers/6482320788/adGroups/200956244576", # 00 - Alunos Engajados
        "customers/6482320788/adGroups/203567131827", # 01 - Alunos Ativos
        "customers/6482320788/adGroups/200191341509", # 02 - Alunos Inativos
        "customers/6482320788/adGroups/203567200707", # 00 - Hotmart
        "customers/6482320788/adGroups/204252802287", # 02 - Black 25
    ]

    print("\n" + "="*90)
    print("ATUALIZANDO OS ANÚNCIOS COM AS 3 PROPORÇÕES DE VÍDEO (16:9 + 9:16 + 1:1)")
    print("="*90)

    for ag in ad_groups:
        ag_id = ag.split("/")[-1]
        print(f"\n📁 Processando Grupo: {ag_id}")
        
        # 1. Remover anúncios simples anteriores
        q_existing = f"""
        SELECT
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.resource_name
        FROM ad_group_ad
        WHERE ad_group.id = {ag_id} AND ad_group_ad.status != 'REMOVED'
        """
        existing = query_google_ads(cid, q_existing)
        if existing:
            rem_ops = [{"remove": ex["adGroupAd"]["resourceName"]} for ex in existing]
            mutate_google_ads(cid, "adGroupAds:mutate", {"operations": rem_ops})
            print(f"   🗑️ {len(rem_ops)} anúncios simples antigos removidos para substituição.")

        # 2. Criar os novos 6 anúncios com os 3 vídeos agrupados
        add_ops = []
        for c in criativos_completos:
            video_asset_list = [{"asset": a_res} for a_res in c["asset_resources"]]
            add_ops.append({
                "create": {
                    "adGroup": ag,
                    "status": "ENABLED",
                    "ad": {
                        "name": c["ad_name"],
                        "finalUrls": [url_final],
                        "demandGenVideoResponsiveAd": {
                            "businessName": {"text": business_name},
                            "logoImages": [{"asset": logo_asset}],
                            "headlines": [{"text": "Black Vitalícia"}],
                            "longHeadlines": [{"text": "Black Vitalícia dos Concursos - Brabo"}],
                            "descriptions": [{"text": "Garanta sua vaga na melhor condição do ano!"}],
                            "videos": video_asset_list
                        }
                    }
                }
            })
        
        res = mutate_google_ads(cid, "adGroupAds:mutate", {"operations": add_ops})
        if res and "results" in res:
            print(f"   ✅ 6 anúncios multi-formato (18 vídeos) criados e ATIVOS no grupo {ag_id}!")
        else:
            print(f"   ❌ Erro ao criar anúncios no grupo {ag_id}")

    print("\n🎉 TODAS AS 30 PEÇAS MULTI-FORMATO FORAM ATUALIZADAS COM SUCESSO!")

if __name__ == "__main__":
    main()
