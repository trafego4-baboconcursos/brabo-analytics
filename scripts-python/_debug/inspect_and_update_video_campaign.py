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
    campaign_id = 24281955284
    
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
    
    res = query_google_ads(cid, q)
    print(f"Total de anúncios encontrados na campanha {campaign_id}: {len(res)}")
    for item in res:
        ag = item['adGroup']
        ad = item['adGroupAd']['ad']
        v_resp = ad.get('videoResponsiveAd', {})
        videos = v_resp.get('videos', [])
        print(f"Grupo: {ag['name']} (ID: {ag['id']}) | Anúncio: {ad.get('name')} (ID: {ad['id']}) | Vídeos atuais: {len(videos)}")
        for v in videos:
            print(f"   - Video Asset: {v.get('asset')}")

if __name__ == "__main__":
    main()
