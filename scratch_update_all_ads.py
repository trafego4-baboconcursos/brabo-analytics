import sys, os, requests, json, time
sys.path.insert(0,'src')
from dotenv import load_dotenv
load_dotenv()
token = os.environ["META_ACCESS_TOKEN"]

with open("scratch_new_creative_319.txt") as f: creative_319 = f.read().strip()
with open("scratch_new_creative_320.txt") as f: creative_320 = f.read().strip()

ad319_ids = [
    "120246876936950014","120246876934930014","120246876932970014","120246876931090014",
    "120246876929190014","120246876927020014","120246876599210014",
    "120246876943680014","120246876942200014","120246876940380014","120246876938920014",
    "120246876948130014","120246876946350014",
]
ad320_ids = [
    "120246877276990014","120246877277960014","120246877271580014","120246877273740014",
    "120246877269840014","120246877270530014","120246877234550014",
    "120246877282390014","120246877288060014","120246877285270014","120246877280540014",
    "120246877291320014","120246877289560014",
]

ok = 0
total = len(ad319_ids) + len(ad320_ids)
for ad_id in ad319_ids:
    r = requests.post(f"https://graph.facebook.com/v22.0/{ad_id}", data={
        "access_token": token,
        "creative": json.dumps({"creative_id": creative_319}),
    }, timeout=20)
    success = r.status_code == 200 and r.json().get("success")
    ok += 1 if success else 0
    print("AD319", ad_id, r.status_code, r.text[:100])
    time.sleep(2.5)

for ad_id in ad320_ids:
    r = requests.post(f"https://graph.facebook.com/v22.0/{ad_id}", data={
        "access_token": token,
        "creative": json.dumps({"creative_id": creative_320}),
    }, timeout=20)
    success = r.status_code == 200 and r.json().get("success")
    ok += 1 if success else 0
    print("AD320", ad_id, r.status_code, r.text[:100])
    time.sleep(2.5)

print(f"\n{ok}/{total} atualizados")
