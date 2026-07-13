#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICACAO: Total de Vendas vs Total Rastreado por Criativo
"""

import pandas as pd

print("=" * 100)
print("VERIFICACAO: TOTAIS DE VENDAS")
print("=" * 100)

# ===== DADOS ORIGINAIS =====
print("\n1. TOTAIS ORIGINAIS (sem filtro por criativo):")
print("-" * 100)

df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

total_hotmart = len(df_hotmart)
valor_hotmart = df_hotmart['valor_num'].sum()

total_tmb = len(df_tmb)
valor_tmb = df_tmb['valor_num'].sum()

total_vendas = total_hotmart + total_tmb
valor_total = valor_hotmart + valor_tmb

print(f"   Hotmart: {total_hotmart:,} vendas = R$ {valor_hotmart:,.2f}")
print(f"   TMB: {total_tmb:,} vendas = R$ {valor_tmb:,.2f}")
print(f"   TOTAL: {total_vendas:,} vendas = R$ {valor_total:,.2f}")

# ===== VENDAS COM UTM =====
print("\n2. VENDAS RASTREADAS (com UTM):")
print("-" * 100)

df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', 
                      sep=',', encoding='utf-8', quoting=1, low_memory=False)

df_crm['email_norm'] = df_crm['Email'].astype(str).str.strip().str.lower()

df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['plataforma'] = 'Hotmart'

df_tmb['email_norm'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['plataforma'] = 'TMB'

df_vendas = pd.concat([
    df_hotmart[['email_norm', 'valor_num', 'plataforma']],
    df_tmb[['email_norm', 'valor_num', 'plataforma']]
], ignore_index=True)

df_merged = df_vendas.merge(
    df_crm[['email_norm', '*Utm_content', '*Utm_campaign', '*Utm_source']],
    on='email_norm',
    how='left'
)

vendas_com_utm = df_merged[df_merged['*Utm_content'].notna()]
vendas_sem_utm = df_merged[df_merged['*Utm_content'].isna()]

print(f"   Vendas COM UTM: {len(vendas_com_utm):,}")
print(f"   Valor COM UTM: R$ {vendas_com_utm['valor_num'].sum():,.2f}")
print(f"   Valor MEDIO: R$ {vendas_com_utm['valor_num'].mean():,.2f}")

print(f"\n   Vendas SEM UTM: {len(vendas_sem_utm):,}")
print(f"   Valor SEM UTM: R$ {vendas_sem_utm['valor_num'].sum():,.2f}")
print(f"   Valor MEDIO: R$ {vendas_sem_utm['valor_num'].mean():,.2f}")

# ===== COMPARACAO =====
print("\n3. COMPARACAO:")
print("-" * 100)

com_utm_total = len(vendas_com_utm)
com_utm_valor = vendas_com_utm['valor_num'].sum()
sem_utm_total = len(vendas_sem_utm)
sem_utm_valor = vendas_sem_utm['valor_num'].sum()

print(f"   Com UTM: {com_utm_total:,} vendas = R$ {com_utm_valor:,.2f}")
print(f"   Sem UTM: {sem_utm_total:,} vendas = R$ {sem_utm_valor:,.2f}")
print(f"   TOTAL: {com_utm_total + sem_utm_total:,} vendas = R$ {com_utm_valor + sem_utm_valor:,.2f}")

# Verificar discrepancia
print(f"\n   ✓ Vendas reconciliadas: {com_utm_total + sem_utm_total:,} (esperado: {total_vendas:,})")
print(f"   ✓ Valor reconciliado: R$ {com_utm_valor + sem_utm_valor:,.2f} (esperado: R$ {valor_total:,.2f})")

# ===== AGRUPAMENTO POR CRIATIVO =====
print("\n4. AGRUPAMENTO POR CRIATIVO (apenas COM UTM):")
print("-" * 100)

criativos = vendas_com_utm.groupby('*Utm_content').agg({
    'valor_num': ['count', 'sum', 'mean']
}).reset_index()

criativos.columns = ['Criativo', 'Vendas', 'Valor_Total', 'Ticket_Medio']
criativos = criativos.sort_values('Vendas', ascending=False)

print(f"\n   Total de Criativos: {len(criativos)}")
print(f"   Total de Vendas (com criativo): {criativos['Vendas'].sum():,.0f}")
print(f"   Total de Valor (com criativo): R$ {criativos['Valor_Total'].sum():,.2f}")
print(f"\n   Diferenca entre 'Com UTM' e 'Agrupado por Criativo':")
print(f"      Vendas: {com_utm_total:,} vs {criativos['Vendas'].sum():,.0f} = {com_utm_total - criativos['Vendas'].sum():,}")
print(f"      Valor: R$ {com_utm_valor:,.2f} vs R$ {criativos['Valor_Total'].sum():,.2f}")

# ===== VERIFICAR NULOS =====
print("\n5. VERIFICACAO DE NULOS/VAZIOS:")
print("-" * 100)

vazios = vendas_com_utm[vendas_com_utm['*Utm_content'].isna() | (vendas_com_utm['*Utm_content'] == '')]
if len(vazios) > 0:
    print(f"   ⚠️ Criativos vazios ou nulos: {len(vazios)} vendas = R$ {vazios['valor_num'].sum():,.2f}")
else:
    print(f"   ✓ Nenhum criativo vazio/nulo")

# ===== TOP 5 =====
print("\n6. TOP 5 CRIATIVOS:")
print("-" * 100)
for idx, row in criativos.head(5).iterrows():
    print(f"   {idx+1}. {row['Criativo']}: {row['Vendas']:.0f} vendas = R$ {row['Valor_Total']:,.2f}")

print("\n" + "=" * 100)
