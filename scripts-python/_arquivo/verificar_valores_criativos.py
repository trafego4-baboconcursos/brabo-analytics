#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICACAO DETALHADA: Valores de Vendas por Criativo
Buscando discrepâncias
"""

import pandas as pd

print("=" * 120)
print("VERIFICACAO: VALORES DE VENDAS POR CRIATIVO")
print("=" * 120)

# ===== CARREGAR DADOS =====
df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', 
                      sep=',', encoding='utf-8', quoting=1, low_memory=False)
df_crm['email_norm'] = df_crm['Email'].astype(str).str.strip().str.lower()

# Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)
df_hotmart['plataforma'] = 'Hotmart'

# TMB
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado']
df_tmb['email_norm'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)
df_tmb['plataforma'] = 'TMB'

# Combinar vendas
df_vendas = pd.concat([
    df_hotmart[['email_norm', 'valor_num', 'plataforma']],
    df_tmb[['email_norm', 'valor_num', 'plataforma']]
], ignore_index=True)

# Merge com CRM
df_merged = df_vendas.merge(
    df_crm[['email_norm', '*Utm_content', '*Utm_campaign', '*Utm_source']],
    on='email_norm',
    how='left'
)

# Apenas com UTM
df_vendas_utm = df_merged[df_merged['*Utm_content'].notna()].copy()

# Top 5 criativos - análise detalhada
print("\nTOP 5 CRIATIVOS - ANALISE DETALHADA:")
print("-" * 120)

top_criativos = df_vendas_utm.groupby('*Utm_content')['valor_num'].sum().nlargest(5)

for criativo, valor_total in top_criativos.items():
    vendas_criativo = df_vendas_utm[df_vendas_utm['*Utm_content'] == criativo]
    
    num_vendas = len(vendas_criativo)
    valor_soma = vendas_criativo['valor_num'].sum()
    valor_media = vendas_criativo['valor_num'].mean()
    valor_min = vendas_criativo['valor_num'].min()
    valor_max = vendas_criativo['valor_num'].max()
    
    print(f"\nCriativo: {criativo}")
    print(f"  Número de vendas: {num_vendas}")
    print(f"  Valor total: R$ {valor_soma:,.2f}")
    print(f"  Valor médio: R$ {valor_media:,.2f}")
    print(f"  Valor mín: R$ {valor_min:,.2f}")
    print(f"  Valor máx: R$ {valor_max:,.2f}")
    print(f"  Plataformas: {vendas_criativo['plataforma'].unique().tolist()}")
    
    # Detalhes por plataforma
    for plat in vendas_criativo['plataforma'].unique():
        plat_data = vendas_criativo[vendas_criativo['plataforma'] == plat]
        print(f"    - {plat}: {len(plat_data)} vendas = R$ {plat_data['valor_num'].sum():,.2f}")
    
    # Verificar se tem algum valor 0
    zeros = vendas_criativo[vendas_criativo['valor_num'] == 0]
    if len(zeros) > 0:
        print(f"  ⚠️  {len(zeros)} vendas com valor ZERO!")

print("\n" + "=" * 120)

# ===== COMPARAR COM TOTAIS =====
print("\nTOTAL GERAL - VALIDACAO:")
print("-" * 120)

print(f"Total Hotmart original: {df_hotmart['valor_num'].sum():,.2f}")
print(f"Total TMB original: {df_tmb['valor_num'].sum():,.2f}")
print(f"Total (original): {df_hotmart['valor_num'].sum() + df_tmb['valor_num'].sum():,.2f}")

print(f"\nTotal Vendas (com UTM): {df_vendas_utm['valor_num'].sum():,.2f}")
print(f"Total Vendas (sem UTM): {df_merged[df_merged['*Utm_content'].isna()]['valor_num'].sum():,.2f}")
print(f"Total (merged): {df_merged['valor_num'].sum():,.2f}")

# ===== VERIFICAR DISCREPANCIAS =====
print("\n" + "=" * 120)
print("DISCREPANCIAS:")
print("-" * 120)

# Verificar se há emails duplicados
merged_dupes = df_merged[df_merged.duplicated(subset=['email_norm'], keep=False)]
if len(merged_dupes) > 0:
    print(f"⚠️  {len(merged_dupes)} vendas com emails duplicados!")
    print(merged_dupes[['email_norm', 'valor_num', '*Utm_content', 'plataforma']].head(20))

print("\n" + "=" * 120)
