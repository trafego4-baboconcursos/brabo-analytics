import pandas as pd
import os

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PERPETUO]"
meta_path = os.path.join(base_path, "meta-ads", "meta-perpetuo.xlsx")
df_meta = pd.read_excel(meta_path)
df_meta_clean = df_meta.dropna(subset=['Nome da campanha', 'Nome do conjunto de anúncios', 'Nome do anúncio'], how='all')

print("=== TOTAIS ATUALIZADOS DO META ADS ===")
print(f"Total Valor usado (BRL): R$ {df_meta_clean['Valor usado (BRL)'].sum():,.2f}")
print(f"Total Cliques (todos): {df_meta_clean['Cliques (todos)'].sum():,.0f}")
print(f"Total Impressões: {df_meta_clean['Impressões'].sum():,.0f}")
print(f"Total Leads no Meta (pixel): {df_meta_clean['Leads'].sum():,.0f}")
print(f"Total Compras no Meta (pixel): {df_meta_clean['Compras'].sum():,.0f}")

print("\n--- Meta por Campanha ---")
meta_camp = df_meta_clean.groupby('Nome da campanha').agg({
    'Valor usado (BRL)': 'sum',
    'Impressões': 'sum',
    'Cliques (todos)': 'sum',
    'Leads': 'sum',
    'Compras': 'sum'
}).reset_index()
print(meta_camp.to_string())
