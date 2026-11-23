import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from check_retry_group_01 import query_google_ads, mutate_google_ads

def main():
    cid = "6482320788"
    
    # 1. Dedicated Unshared Budget
    budget_payload = {
        "operations": [{
            "create": {
                "name": "Orçamento Teste VVC BV-26 Dedicado",
                "amountMicros": 10000000, # R$ 10
                "deliveryMethod": "STANDARD",
                "explicitlyShared": False
            }
        }]
    }
    b_res = mutate_google_ads(cid, "campaignBudgets:mutate", budget_payload)
    print("Orçamento criado:", b_res)
    
    if not b_res or "results" not in b_res:
        return
    budget_resource = b_res["results"][0]["resourceName"]
    
    # 2. VVC Campaign
    campaign_payload = {
        "operations": [{
            "create": {
                "name": "[GA][teste][vvc][aquecimento][BV-26][25.09.26]",
                "status": "PAUSED",
                "advertisingChannelType": "VIDEO",
                "campaignBudget": budget_resource,
                "targetCpv": {},
                "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
            }
        }]
    }
    c_res = mutate_google_ads(cid, "campaigns:mutate", campaign_payload)
    print("Campanha VVC criada:", c_res)

if __name__ == "__main__":
    main()
