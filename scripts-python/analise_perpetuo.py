import pandas as pd
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PERPETUO]"

print("=== SCRIPT DE COMPILACAO DE DADOS CORRIGIDO ===")

# 1. Analise do Meta Ads
meta_path = os.path.join(base_path, "meta-ads", "meta-perpetuo.xlsx")
df_meta = pd.read_excel(meta_path)
df_meta_clean = df_meta.dropna(subset=['Nome da campanha', 'Nome do conjunto de anúncios', 'Nome do anúncio'], how='all')

print(f"\nMeta Ads rows: {len(df_meta_clean)}")
print(f"Total Valor usado (BRL): R$ {df_meta_clean['Valor usado (BRL)'].sum():,.2f}")
print(f"Total Cliques (todos): {df_meta_clean['Cliques (todos)'].sum():,.0f}")
print(f"Total Impressões: {df_meta_clean['Impressões'].sum():,.0f}")
print(f"Total Leads no Meta: {df_meta_clean['Leads'].sum():,.0f}")
print(f"Total Compras no Meta (pixel): {df_meta_clean['Compras'].sum():,.0f}")

# Detalhe por campanha
meta_camp = df_meta_clean.groupby('Nome da campanha').agg({
    'Valor usado (BRL)': 'sum',
    'Impressões': 'sum',
    'Cliques (todos)': 'sum',
    'Leads': 'sum',
    'Compras': 'sum'
}).reset_index()
print("\n--- Meta Ads por Campanha ---")
print(meta_camp.to_string())

# Detalhe por anuncio
meta_ad = df_meta_clean.groupby('Nome do anúncio').agg({
    'Valor usado (BRL)': 'sum',
    'Impressões': 'sum',
    'Cliques (todos)': 'sum',
    'Leads': 'sum',
    'Compras': 'sum'
}).reset_index()
print("\n--- Meta Ads por Anúncio ---")
print(meta_ad.to_string())


# 2. Analise de Vendas (Hotmart)
hotmart_path = os.path.join(base_path, "vendas", "hotmart-perpetuo.csv")
df_hotmart = pd.read_csv(hotmart_path, sep=';', encoding='utf-8-sig')
print(f"\nHotmart rows: {len(df_hotmart)}")
print("Status das vendas na Hotmart:")
print(df_hotmart['Status'].value_counts())

# Filtra vendas aprovadas/completas (ex. Aprovado, Completo)
vendas_validas = df_hotmart[df_hotmart['Status'].isin(['Aprovado', 'Completo'])]
print(f"\nTotal Vendas Válidas (Aprovado/Completo): {len(vendas_validas)}")
print(f"Total Receita Bruta (Preço Total Convertido): R$ {vendas_validas['Preço Total Convertido'].sum():,.2f}")
print(f"Total Valor Recebido (Valor que você recebeu convertido): R$ {vendas_validas['Valor que você recebeu convertido'].sum():,.2f}")
print(f"Total Faturamento Líquido (Faturamento líquido): R$ {vendas_validas['Faturamento líquido'].sum():,.2f}")

print("\n--- Detalhe das Vendas Válidas ---")
cols_venda = ['Data de Venda', 'Status', 'Preço Total Convertido', 'Valor que você recebeu convertido', 'Faturamento líquido', 'Origem da venda', 'Origem', 'Cupom', 'Email']
cols_venda = [c for c in cols_venda if c in vendas_validas.columns]
print(vendas_validas[cols_venda].to_string())


# 3. Active Campaign
ac_dir = os.path.join(base_path, "active-campaign")
ac_files = [f for f in os.listdir(ac_dir) if f.endswith('.csv')]
for fname in ac_files:
    f = os.path.join(ac_dir, fname)
    print(f"\nActive Campaign File: {fname}")
    try:
        # Vamos tentar ler de forma genérica detectando separador ou usando engine python
        df_ac = pd.read_csv(f, sep=None, engine='python', encoding='utf-8')
        print(f"Total Leads no AC: {len(df_ac)}")
        print(f"Colunas: {df_ac.columns.tolist()[:10]} ...")
        
        # Agregações úteis
        if '*Utm_source' in df_ac.columns:
            print("Distribuição por UTM Source:")
            print(df_ac['*Utm_source'].value_counts().head(5))
        if '*Utm_campaign' in df_ac.columns:
            print("Distribuição por UTM Campaign:")
            print(df_ac['*Utm_campaign'].value_counts().head(5))
        if '*Utm_content' in df_ac.columns:
            print("Distribuição por UTM Content:")
            print(df_ac['*Utm_content'].value_counts().head(5))
    except Exception as e:
        print(f"Erro ao ler {fname}: {e}")
