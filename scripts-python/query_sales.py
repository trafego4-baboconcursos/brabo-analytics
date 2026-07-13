import pandas as pd
from etl.db import get_engine
from frontend.database_reader import _users_engine, read_vendas

engine = get_engine()

# Obter compradores
vendas = read_vendas('PBB-JUN-26', _users_engine)
buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()
print("Total Buyers:", len(buyers))

# Obter leads
df_leads = pd.read_sql("SELECT utm_content, email FROM leads WHERE lancamento_codigo = 'PBB-JUN-26'", engine)
print("Total Leads:", len(df_leads))

# Cruzar
df_leads['is_buyer'] = df_leads['email'].isin(buyers)
vendas_por_content = df_leads[df_leads['is_buyer']].groupby('utm_content').size()
print("Vendas por UTM Content:")
print(vendas_por_content.sort_values(ascending=False).head(20))
