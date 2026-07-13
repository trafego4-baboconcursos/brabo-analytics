"""
ETL: Active Campaign Campaigns → Supabase (tabela: ac_campaigns)

Busca as estatísticas de campanhas (envios, aberturas, cliques) via API
da ActiveCampaign e as vincula a um lançamento baseado na nomenclatura da campanha.

Uso:
  python etl/etl_ac_campaigns.py --api
  python etl/etl_ac_campaigns.py --api --launch-code PBB-FEV-26
"""
import os
import sys
import argparse
import re
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine

load_dotenv()

TABLE = "ac_campaigns"

def extract_launch_code(campaign_name: str) -> str | None:
    if pd.isna(campaign_name) or not campaign_name:
        return None
    match = re.search(r'(PBB|PES|PI)-\w{3}-\d{2}', str(campaign_name), re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None

def _ac_headers() -> dict:
    return {"Api-Token": os.environ["AC_API_KEY"]}

def _ac_get(path: str, **params) -> dict:
    base_url = os.environ["AC_API_URL"].rstrip("/")
    if "/api/3" not in base_url:
        base_url += "/api/3"
    url = base_url + "/" + path
    r = requests.get(url, headers=_ac_headers(), params=params)
    r.raise_for_status()
    return r.json()

def load_campaigns_from_api(launch_code: str | None = None) -> pd.DataFrame:
    """Busca todas as campanhas via API e extrai suas métricas principais."""
    campaigns, offset = [], 0
    print("Buscando campanhas na ActiveCampaign...")
    while True:
        data = _ac_get(
            "campaigns",
            limit=100,
            offset=offset
        )
        batch = data.get("campaigns", [])
        if not batch:
            break
        campaigns.extend(batch)
        total = int(data.get("meta", {}).get("total", 0))
        offset += len(batch)
        if offset >= total:
            break

    if not campaigns:
        return pd.DataFrame()

    records = []
    for c in campaigns:
        cid = str(c.get("id"))
        name = c.get("name", "")
        code = extract_launch_code(name)
        
        # ActiveCampaign API v3 returns metric counts natively in the campaign object
        send_amt = int(c.get("send_amt") or 0)
        opens = int(c.get("opens") or 0)
        unique_opens = int(c.get("uniqueopens") or 0)
        linkclicks = int(c.get("linkclicks") or 0)
        unsubscribes = int(c.get("unsubscribes") or 0)
        bounces = int(c.get("bounces") or 0)
        
        records.append({
            "id": cid,
            "nome_campanha": name,
            "lancamento_codigo": code,
            "data_envio": c.get("sdate") or c.get("cdate"),
            "envios": send_amt,
            "aberturas": opens,
            "aberturas_unicas": unique_opens,
            "cliques": linkclicks,
            "descadastros": unsubscribes,
            "bounces": bounces,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    df = pd.DataFrame(records)
    return df

def upsert(df: pd.DataFrame):
    if df.empty:
        print("  Nenhuma campanha para gravar.")
        return
    engine = get_engine()
    
    # Criar a tabela se não existir
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id VARCHAR PRIMARY KEY,
                nome_campanha VARCHAR,
                lancamento_codigo VARCHAR,
                data_envio TIMESTAMP,
                envios INT,
                aberturas INT,
                aberturas_unicas INT,
                cliques INT,
                descadastros INT,
                bounces INT,
                updated_at TIMESTAMP
            )
        """))
    
    ids = tuple(df["id"].astype(str).tolist())
    with engine.begin() as conn:
        if ids:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE id = ANY(:ids)"),
                {"ids": list(ids)},
            )
    
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"  OK: {len(df)} campanhas gravadas em '{TABLE}'.")

def main():
    parser = argparse.ArgumentParser(description="ETL Active Campaign Campaigns - Supabase")
    parser.add_argument("--api", action="store_true", help="Busca via API (requer credenciais no .env)", required=True)
    parser.add_argument("--launch-code", metavar="CODE", help="Filtra a carga para um lancamento especifico")
    args = parser.parse_args()

    print(f"[AC Campaigns] {TABLE} (API)")
    df = load_campaigns_from_api(args.launch_code)
    upsert(df)

if __name__ == "__main__":
    main()
