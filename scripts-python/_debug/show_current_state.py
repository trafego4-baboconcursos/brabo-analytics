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
        campaign.advertising_channel_type,
        campaign_budget.amount_micros
    FROM campaign 
    WHERE campaign.status = 'ENABLED'
    ORDER BY campaign.id DESC
    """
    results = query_google_ads(cid, q)
    print(f"=== TODAS AS CAMPANHAS ATIVAS (ENABLED) NA CONTA {cid} ===\n")
    for r in results:
        c = r['campaign']
        b_micros = int(r.get('campaignBudget', {}).get('amountMicros', 0))
        b_reais = b_micros / 1_000_000
        ch = c.get('advertisingChannelType', '')
        print(f"🎯 [{ch}] {c['name']} (ID: {c['id']}) - R$ {b_reais:.2f}/dia")
        
        # query ad groups
        q_ag = f"""
        SELECT ad_group.id, ad_group.name, ad_group.status
        FROM ad_group
        WHERE campaign.id = {c['id']} AND ad_group.status = 'ENABLED'
        ORDER BY ad_group.name
        """
        ag_res = query_google_ads(cid, q_ag)
        for ag in ag_res:
            ag_id = ag['adGroup']['id']
            ag_name = ag['adGroup']['name']
            
            # query ads
            q_ad = f"""
            SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.status
            FROM ad_group_ad
            WHERE ad_group.id = {ag_id} AND ad_group_ad.status = 'ENABLED'
            ORDER BY ad_group_ad.ad.name
            """
            ads_res = query_google_ads(cid, q_ad)
            print(f"   📁 {ag_name} (ID: {ag_id}) -> {len(ads_res)} anúncios ativos:")
            for ad_item in ads_res:
                ad = ad_item['adGroupAd']['ad']
                print(f"      * {ad.get('name', 'Sem Nome')} (ID: {ad['id']})")
        print("-" * 70)

if __name__ == "__main__":
    main()
