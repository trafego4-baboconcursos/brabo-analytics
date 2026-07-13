import pandas as pd
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PERPETUO]"

# Carrega vendas Hotmart
hotmart_path = os.path.join(base_path, "vendas", "hotmart-perpetuo.csv")
df_hotmart = pd.read_csv(hotmart_path, sep=';', encoding='utf-8-sig')
df_vendas = df_hotmart[df_hotmart['Status'].isin(['Aprovado', 'Completo'])].copy()

# Carrega Active Campaign
ac_dir = os.path.join(base_path, "active-campaign")
ac_files = [f for f in os.listdir(ac_dir) if f.endswith('.csv')]

ac_leads_list = []
for fname in ac_files:
    f = os.path.join(ac_dir, fname)
    df_ac = pd.read_csv(f, sep=None, engine='python', encoding='utf-8')
    df_ac['origem_arquivo'] = fname
    ac_leads_list.append(df_ac)

df_ac_all = pd.concat(ac_leads_list, ignore_index=True)

# Normaliza emails para o cruzamento
df_vendas['Email'] = df_vendas['Email'].str.strip().str.lower()
df_ac_all['Email'] = df_ac_all['Email'].str.strip().str.lower()

# Realiza o merge (cruzamento)
df_cruzado = pd.merge(df_vendas, df_ac_all, on='Email', how='left')

print("=== CRUZAMENTO DE VENDAS HOTMART COM ACTIVE CAMPAIGN ===")
print(f"Total de vendas válidas na Hotmart: {len(df_vendas)}")
print(f"Total de vendas com lead encontrado no AC: {df_cruzado['ID'].notna().sum()}")
print(f"Vendas sem lead correspondente no AC: {df_cruzado['ID'].isna().sum()}")

# Lista as vendas com seus respectivos leads e UTMs encontrados
cols_mostrar = ['Data de Venda', 'Email', 'Preço Total Convertido', 'Faturamento líquido', 'origem_arquivo', '*Utm_campaign', '*Utm_source', '*Utm_medium', '*Utm_content', 'Tags']
cols_existentes = [c for c in cols_mostrar if c in df_cruzado.columns]
print("\n--- Lista de Vendas e UTMs Atribuidos ---")
print(df_cruzado[cols_existentes].to_string())

# Agrega por UTM Campaign
print("\n--- Receita (Faturamento Líquido) por Campanha (do AC) ---")
camp_recv = df_cruzado.groupby('*Utm_campaign', dropna=False).agg(
    vendas=('Email', 'count'),
    faturamento_liquido=('Faturamento líquido', 'sum'),
    receita_bruta=('Preço Total Convertido', 'sum')
).reset_index()
print(camp_recv.to_string())

# Agrega por UTM Content (anúncio)
print("\n--- Receita (Faturamento Líquido) por Anúncio (do AC) ---")
ad_recv = df_cruzado.groupby('*Utm_content', dropna=False).agg(
    vendas=('Email', 'count'),
    faturamento_liquido=('Faturamento líquido', 'sum'),
    receita_bruta=('Preço Total Convertido', 'sum')
).reset_index()
print(ad_recv.to_string())
