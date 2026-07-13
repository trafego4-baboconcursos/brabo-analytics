import pandas as pd
from sqlalchemy import text
from etl.db import get_engine
from frontend.database_reader import read_vendas

engine = get_engine()
code = 'PBB-JUN-26'
vendas = read_vendas(code)
buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()

with engine.connect() as conn:
    df_leads = pd.read_sql(
        text("SELECT utm_content, email FROM leads WHERE lancamento_codigo = 'PBB-JUN-26' AND (utm_source ILIKE '%google%' OR utm_source ILIKE '%youtube%')"),
        conn
    )
    df_leads["is_buyer"] = df_leads["email"].isin(buyers)
    
    summary = df_leads.groupby("utm_content").agg(
        leads=("email", "count"),
        vendas=("is_buyer", "sum")
    ).reset_index()
    
    summary = summary[summary["vendas"] > 0].sort_values("vendas", ascending=False)
    
    for _, r in summary.iterrows():
        print(f"UTM: {r['utm_content']:<60} | Leads: {r['leads']:<5} | Vendas: {r['vendas']}")
