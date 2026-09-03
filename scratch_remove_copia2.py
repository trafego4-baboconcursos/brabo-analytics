import sys, os, requests, time, json
sys.path.insert(0,'src')
from dotenv import load_dotenv
load_dotenv()
token = os.environ["META_ACCESS_TOKEN"]

campaigns = [
    "120246765909300014","120246763410100014","120246676451300014","120246676451180014",
    "120246676450540014","120246676450530014","120246676316240014","120246676315350014",
    "120246676315340014","120246676315330014","120246656561590014","120246656561570014",
    "120246656561560014","120246656561550014",
    "120246596107440014","120246595424530014","120246577242110014","120246576459370014",
    "120246573476320014","120246570918780014","120246253926440014","120246253926340014",
    "120246253926320014","120246253926310014","120246253926300014","120246253925990014",
    "120244280343910014","120244280343810014","120244280343800014","120244280343790014",
    "120244280343760014","120244280343250014",
]

def list_all_ads(camp_id):
    ads = []
    url = f"https://graph.facebook.com/v22.0/{camp_id}/ads"
    params = {"access_token": token, "fields": "id,name", "limit": 200}
    attempts = 0
    while True:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            attempts += 1
            if attempts > 3:
                print("  DESISTINDO", camp_id, r.text[:150])
                break
            print("  retry...", r.text[:100])
            time.sleep(15)
            continue
        attempts = 0
        data = r.json()
        ads.extend(data.get("data", []))
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        url = next_url
        params = {}
        time.sleep(3)
    return ads

todo = []
for camp_id in campaigns:
    print(f"Listando campanha {camp_id}...")
    ads = list_all_ads(camp_id)
    n_copia = sum(1 for a in ads if 'Cópia' in a.get('name',''))
    for ad in ads:
        name = ad.get("name","")
        if "Cópia" in name:
            todo.append((ad["id"], name))
    print(f"  {len(ads)} anuncios, {n_copia} com Copia")
    time.sleep(4)

print(f"\nTOTAL a renomear: {len(todo)}")
with open("scratch_copia_list.json","w", encoding="utf-8") as f:
    json.dump(todo, f, ensure_ascii=False)
