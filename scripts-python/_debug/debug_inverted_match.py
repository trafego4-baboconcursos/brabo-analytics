import pandas as pd
from sqlalchemy import text
from etl.db import get_engine
import re
from difflib import SequenceMatcher
from frontend.database_reader import read_vendas

engine = get_engine()
code = 'PBB-JUN-26'

def _clean_str(s):
    if not s: return ""
    s = str(s).lower()
    s = re.sub(r'[^a-z0-9]', '', s)
    s = re.sub(r'^\d+', '', s)
    for w in ['todos', 'pbbjun26', 'pbbabr26', 'site', 'lancamentosanteriores', 'pesquisagoogle', 'captura']:
        s = s.replace(w, '')
    return s

def _match_score(utm, api):
    u, a = _clean_str(utm), _clean_str(api)
    if not u or not a: return 0
    if u in a or a in u: return 1.0
    return SequenceMatcher(None, u, a).ratio()

vendas = read_vendas(code)
buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()

with engine.connect() as conn:
    df_leads = pd.read_sql(
        text("SELECT utm_content, email FROM leads WHERE lancamento_codigo = 'PBB-JUN-26' AND (utm_source ILIKE '%google%' OR utm_source ILIKE '%youtube%')"),
        conn
    )
    df_leads["is_buyer"] = df_leads["email"].isin(buyers)
    
    sales_by_content = df_leads[df_leads["is_buyer"]].groupby("utm_content").size().to_dict()

    df_aud = pd.read_sql(
        text("SELECT audience_name, SUM(cost) as cost FROM google_ads_audiences_daily WHERE lancamento_codigo = 'PBB-JUN-26' GROUP BY audience_name ORDER BY cost DESC"),
        conn
    )
    api_audiences = df_aud["audience_name"].tolist()

    # Invert mapping: map each UTM to the best API Audience
    utm_to_api = {}
    for utm, sales in sales_by_content.items():
        best_api = None
        best_score = 0
        for api in api_audiences:
            score = _match_score(utm, api)
            if score > best_score:
                best_score = score
                best_api = api
        
        if best_score > 0.55:
            utm_to_api[utm] = {"api": best_api, "score": best_score, "sales": sales}

    # Now aggregate sales by API Audience
    api_to_sales = {}
    for utm, data in utm_to_api.items():
        api = data["api"]
        api_to_sales[api] = api_to_sales.get(api, 0) + data["sales"]

    # Print results
    print("MAPPING RESULT:")
    for api, sales in api_to_sales.items():
        print(f"API: {api[:60]:<60} -> {sales} sales")
