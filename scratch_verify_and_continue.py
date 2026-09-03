import sys, os, requests, json, time
sys.path.insert(0,'src')
from dotenv import load_dotenv
load_dotenv()
token = os.environ["META_ACCESS_TOKEN"]

with open("scratch_new_creative_319.txt") as f: creative_319 = f.read().strip()
with open("scratch_new_creative_320.txt") as f: creative_320 = f.read().strip()

# checar se os 2 ultimos AD319 ja foram atualizados
for ad_id in ["120246876948130014", "120246876946350014"]:
    r = requests.get(f"https://graph.facebook.com/v22.0/{ad_id}", params={"access_token": token, "fields": "creative"}, timeout=20)
    print(ad_id, "creative atual:", r.json().get("creative",{}).get("id"), "| esperado:", creative_319)
    time.sleep(2)
