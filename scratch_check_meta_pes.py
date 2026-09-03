import os
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.environ.get('META_ACCESS_TOKEN')
act = 'act_1407542209639031'

# 1. Campaigns
r_camp = requests.get(f'https://graph.facebook.com/v22.0/{act}/campaigns', params={
    'access_token': token,
    'fields': 'id,name,status,effective_status',
    'limit': 50
}).json()
print("CAMPAIGNS:")
for c in r_camp.get('data', []):
    if 'PES-SET-26' in c.get('name', ''):
        print(f"  {c['id']} | {c['name']} | {c['effective_status']}")

# 2. Adsets
r_adsets = requests.get(f'https://graph.facebook.com/v22.0/{act}/adsets', params={
    'access_token': token,
    'fields': 'id,name,campaign_id,status,effective_status,daily_budget,start_time,end_time',
    'limit': 50
}).json()
print("\nADSETS:")
target_adset_ids = []
for a in r_adsets.get('data', []):
    if a.get('campaign_id') in ['120247379013450014', '120247379014650014'] or 'PES-SET-26' in a.get('name', ''):
        target_adset_ids.append(a['id'])
        print(f"  {a['id']} | Camp: {a['campaign_id']} | {a['name']} | Budget: {a.get('daily_budget')} | Start: {a.get('start_time')} | End: {a.get('end_time')}")

# 3. Ads
r_ads = requests.get(f'https://graph.facebook.com/v22.0/{act}/ads', params={
    'access_token': token,
    'fields': 'id,name,adset_id,status,effective_status,creative{id,name}',
    'limit': 100
}).json()
print("\nADS:")
for ad in r_ads.get('data', []):
    if ad.get('adset_id') in target_adset_ids:
        print(f"  {ad['id']} | AdSet: {ad['adset_id']} | {ad['name']} | {ad['status']}")

# 4. Check available videos in library matching AD10 or PES-SET-26
r_vids = requests.get(f'https://graph.facebook.com/v22.0/{act}/advideos', params={
    'access_token': token,
    'fields': 'id,title,description,created_time',
    'limit': 100
}).json()
print("\nVIDEOS IN LIBRARY (Matching AD1 or PES-SET):")
for v in r_vids.get('data', []):
    title = v.get('title') or v.get('description') or ''
    if 'PES-SET' in title or 'AD1' in title or 'PQ' in title:
        print(f"  {v['id']} | {title} | {v.get('created_time')}")
