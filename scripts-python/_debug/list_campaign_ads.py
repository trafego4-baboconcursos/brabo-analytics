import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from verify_all_demand_gen import query_google_ads

def main():
    cid = "6482320788"
    q = """
    SELECT 
        campaign.id, 
        campaign.name, 
        campaign.status, 
        campaign.advertising_channel_type
    FROM campaign 
    WHERE campaign.status != 'REMOVED'
    ORDER BY campaign.id DESC
    LIMIT 15
    """
    results = query_google_ads(cid, q)
    print("=== TOP 15 CAMPANHAS RECENTES ===")
    for r in results:
        c = r['campaign']
        ch = c.get('advertisingChannelType', '')
        print(f"\nID: {c['id']} | Tipo: {ch} | Status: {c['status']} | Nome: {c['name']}")
        
        # list ads in this campaign
        q_ad = f"""
        SELECT 
            ad_group.id,
            ad_group.name,
            ad_group_ad.ad.id,
            ad_group_ad.ad.name,
            ad_group_ad.ad.type,
            ad_group_ad.status
        FROM ad_group_ad
        WHERE campaign.id = {c['id']} AND ad_group_ad.status != 'REMOVED'
        """
        ads = query_google_ads(cid, q_ad)
        print(f"   Total de Anúncios: {len(ads)}")
        for ad_item in ads:
            ag = ad_item['adGroup']
            ad = ad_item['adGroupAd']
            print(f"   - [{ag['name']}] {ad['ad']['name']} (Tipo: {ad['ad']['type']}, ID: {ad['ad']['id']}) [{ad['status']}]")

if __name__ == "__main__":
    main()
