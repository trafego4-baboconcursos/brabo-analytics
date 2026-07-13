#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de ROAS por Criativo (Ad)
Leads > Criativo > Vendas > Investimento
"""

import pandas as pd
import numpy as np

print("\n" + "="*100)
print("📊 ANÁLISE POR CRIATIVO - LEADS, VENDAS E ROAS")
print("="*100)

# Leads
df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')
print(f"\n✓ Leads: {len(df_leads)}")

# Vendas
df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', sep=';')
df_tmb_vendas = df_tmb[df_tmb['Status'] == 'Efetivado'].copy()

# Normalizar emails
df_leads['email_norm'] = df_leads['Email'].astype(str).str.lower().str.strip()
df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
df_hotmart = df_hotmart[df_hotmart['email_norm'].str.contains('@', na=False)]
df_tmb_vendas['email_norm'] = df_tmb_vendas['Cliente Email'].astype(str).str.lower().str.strip()

# Vendas por email
vendas_hotmart_por_email = df_hotmart[['email_norm']].copy()
vendas_hotmart_por_email['valor'] = pd.to_numeric(df_hotmart['Valor de compra sem impostos'], errors='coerce')
vendas_hotmart_por_email['fonte'] = 'Hotmart'

vendas_tmb_por_email = df_tmb_vendas[['email_norm']].copy()
vendas_tmb_por_email['valor'] = pd.to_numeric(df_tmb_vendas['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')
vendas_tmb_por_email['fonte'] = 'TMB'

vendas_por_email = pd.concat([vendas_hotmart_por_email, vendas_tmb_por_email], ignore_index=True)

print(f"✓ Hotmart: {len(df_hotmart)}")
print(f"✓ TMB: {len(df_tmb_vendas)}")
print(f"✓ Total vendas: {len(vendas_por_email)}")

# Cruzar: leads + vendas
df_leads['tem_venda'] = df_leads['email_norm'].isin(vendas_por_email['email_norm'].unique())
df_leads_com_venda = df_leads[df_leads['tem_venda']].copy()

# Merge com vendas para pegar valor
df_leads_com_venda = df_leads_com_venda.merge(
    vendas_por_email.groupby('email_norm').agg({'valor': 'sum', 'fonte': 'first'}).reset_index(),
    on='email_norm',
    how='left'
)

print(f"✓ Leads com venda: {len(df_leads_com_venda)}")

# Análise por Criativo (Utm_content)
print(f"\n📊 ANÁLISE POR CRIATIVO:")
criativo_col = '*Utm_content'

# Agrupar leads por criativo
leads_por_criativo = df_leads.groupby(criativo_col).size().reset_index(name='leads_total')
print(f"  Criativos únicos: {len(leads_por_criativo)}")

# Vendas por criativo
vendas_por_criativo = df_leads_com_venda.groupby(criativo_col).agg({
    'valor': ['sum', 'count'],
    'email_norm': 'count'
}).reset_index()
vendas_por_criativo.columns = [criativo_col, 'valor_total', 'vendas', 'pessoas']

# Merge
analise_criativo = leads_por_criativo.merge(vendas_por_criativo, on=criativo_col, how='left')
analise_criativo['vendas'] = analise_criativo['vendas'].fillna(0).astype(int)
analise_criativo['valor_total'] = analise_criativo['valor_total'].fillna(0)
analise_criativo['taxa_conversao'] = (analise_criativo['vendas'] / analise_criativo['leads_total'] * 100).round(2)

# Ordenar por vendas
analise_criativo = analise_criativo.sort_values('vendas', ascending=False)

print(f"\n\n🏆 TOP 15 CRIATIVOS POR VENDAS:")
print("\nCriativo | Leads | Vendas | Taxa Conv | Valor Total")
print("-" * 90)
for idx, row in analise_criativo.head(15).iterrows():
    criativo = str(row[criativo_col])[:60]  # Truncar se necessário
    leads = int(row['leads_total'])
    vendas = int(row['vendas'])
    taxa = row['taxa_conversao']
    valor = row['valor_total']
    print(f"{criativo:<60} | {leads:>5} | {vendas:>6} | {taxa:>5.2f}% | R$ {valor:>10,.2f}")

print(f"\n\n" + "="*100 + "\n")
