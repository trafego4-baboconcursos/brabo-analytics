import requests, os
from dotenv import load_dotenv
load_dotenv(r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm\.env')
token = os.environ['META_ACCESS_TOKEN']
url = 'https://graph.facebook.com/v22.0/act_1407542209639031/insights'
params = {
    'access_token': token,
    'fields': 'campaign_name,impressions,clicks,spend,actions',
    'level': 'campaign',
    'breakdowns': 'age,gender',
    'time_range': '{"since":"2026-05-01","until":"2026-06-22"}',
    'time_increment': 1,
    'limit': 50
}
r = requests.get(url, params=params)
if r.status_code != 200:
    print(r.text)
else:
    print("SUCCESS")
