import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from check_retry_group_01 import query_google_ads, mutate_google_ads

# Mapping of creative names to the 3 video assets (16:9, 9:16, 1:1)
CRIATIVOS_MAP = {
    "AD-TR08": {
        "name": "AD-TR08 - Discursão BV - BV-26",
        "videos": [
            "customers/6482320788/assets/424294921364", # 16:9
            "customers/6482320788/assets/424589027945", # 9:16
            "customers/6482320788/assets/424589014982", # 1:1
        ]
    },
    "AD-TR10": {
        "name": "AD-TR10 - Discursão BV - BV-26",
        "videos": [
            "customers/6482320788/assets/424294801655", # 16:9
            "customers/6482320788/assets/424774655625", # 9:16
            "customers/6482320788/assets/424589039657", # 1:1
        ]
    },
    "AD-TR11": {
        "name": "AD-TR11 - Discursão BV p aluno - BV-26",
        "videos": [
            "customers/6482320788/assets/424396558774", # 16:9
            "customers/6482320788/assets/424690590598", # 9:16
            "customers/6482320788/assets/424589040548", # 1:1
        ]
    },
    "AD-TR13": {
        "name": "AD-TR13 - Discursão BV - BV-26",
        "videos": [
            "customers/6482320788/assets/424394291746", # 16:9
            "customers/6482320788/assets/424774667556", # 9:16
            "customers/6482320788/assets/424690595464", # 1:1
        ]
    },
    "ADC-TR25": {
        "name": "ADC-TR25 - Felipe Ivan e Mateus - BV-26",
        "videos": [
            "customers/6482320788/assets/424293019268", # 16:9
            "customers/6482320788/assets/424589095562", # 9:16
            "customers/6482320788/assets/424774701591", # 1:1
        ]
    },
    "ADC-TR26": {
        "name": "ADC-TR26 - Felipe Ivan e Mateus - BV-26",
        "videos": [
            "customers/6482320788/assets/424394466457", # 16:9
            "customers/6482320788/assets/424690611781", # 9:16
            "customers/6482320788/assets/424690612156", # 1:1
        ]
    }
}

def main():
    cid = "6482320788"
    campaign_id = 24281955284
    
    # 1. Fetch current ads in campaign 24281955284
    q = f"""
    SELECT
        ad_group.id,
        ad_group.name,
        ad_group_ad.ad.id,
        ad_group_ad.ad.name,
        ad_group_ad.ad.type,
        ad_group_ad.ad.video_responsive_ad.videos,
        ad_group_ad.ad.video_responsive_ad.headlines,
        ad_group_ad.ad.video_responsive_ad.long_headlines,
        ad_group_ad.ad.video_responsive_ad.descriptions,
        ad_group_ad.ad.video_responsive_ad.call_to_actions,
        ad_group_ad.ad.final_urls,
        ad_group_ad.status
    FROM ad_group_ad
    WHERE campaign.id = {campaign_id} AND ad_group_ad.status != 'REMOVED'
    """
    ads = query_google_ads(cid, q)
    print(f"Total de anúncios atuais: {len(ads)}")
    
    # Let's remove the single-video ads and create the new ones with all 3 videos attached
    # First, let's group by adGroup
    groups_dict = {}
    remove_ops = []
    
    for item in ads:
        ag_id = item['adGroup']['id']
        ad_id = item['adGroupAd']['ad']['id']
        groups_dict[ag_id] = item['adGroup']['name']
        remove_ops.append({
            "remove": f"customers/{cid}/adGroupAds/{ag_id}~{ad_id}"
        })
        
    print(f"Preparando remoção de {len(remove_ops)} anúncios com apenas 1 formato...")
    res_rem = mutate_google_ads(cid, "adGroupAds:mutate", {"operations": remove_ops})
    print(f"Remoção concluída: {res_rem is not None}")
    
    # Now create the 6 multi-format videoResponsiveAds in each group
    create_ops = []
    url_final = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1b/"
    
    for ag_id, ag_name in groups_dict.items():
        for code, c_info in CRIATIVOS_MAP.items():
            v_list = [{"asset": v_asset} for v_asset in c_info["videos"]]
            create_ops.append({
                "create": {
                    "adGroup": f"customers/{cid}/adGroups/{ag_id}",
                    "status": "ENABLED",
                    "ad": {
                        "name": f"{c_info['name']} (Multi-Formato)",
                        "finalUrls": [url_final],
                        "videoResponsiveAd": {
                            "headlines": [{"text": "Black Vitalícia"}],
                            "longHeadlines": [{"text": "Black Vitalícia dos Concursos - Brabo"}],
                            "descriptions": [{"text": "Garanta sua vaga na melhor condição do ano!"}],
                            "callToActions": [{"text": "Saiba mais"}],
                            "videos": v_list
                        }
                    }
                }
            })
            
    print(f"Criando {len(create_ops)} novos anúncios multi-formato (16:9 + 9:16 + 1:1)...")
    res_create = mutate_google_ads(cid, "adGroupAds:mutate", {"operations": create_ops})
    print(f"Criação concluída: {res_create is not None}")

if __name__ == "__main__":
    main()
