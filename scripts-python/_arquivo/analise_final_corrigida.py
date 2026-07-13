#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise FINAL CORRIGIDA - Valores corretos
"""

import pandas as pd

print("\n" + "="*100)
print("📊 ANÁLISE FINAL CORRIGIDA - VALORES REAIS")
print("="*100)

# Leads
df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')
print(f"\n✓ Leads: {len(df_leads):,}")

# Hotmart - CORREÇÃO: usar valores como estão (não remover ponto!)
df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
# Os valores já estão como float correto!
hotmart_soma = df_hotmart['Valor de compra sem impostos'].sum()
hotmart_count = len(df_hotmart)
print(f"✓ Hotmart: {hotmart_count} transações | R$ {hotmart_soma:,.2f}")

# TMB - CORREÇÃO: ler normalmente
df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', sep=';')
df_tmb_efetvizado = df_tmb[df_tmb['Status'] == 'Efetivado'].copy()
# Converter ticket com vírgula para ponto
tmb_soma = pd.to_numeric(df_tmb_efetvizado['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce').sum()
tmb_count = len(df_tmb_efetvizado)
print(f"✓ TMB: {tmb_count} transações | R$ {tmb_soma:,.2f}")

# Total
total_soma = hotmart_soma + tmb_soma
total_count = hotmart_count + tmb_count
print(f"\n📊 TOTAL: {total_count} transações | R$ {total_soma:,.2f}")

# Cruzar com leads
df_leads['email_normalizado'] = df_leads['Email'].astype(str).str.lower().str.strip()

df_hotmart['email_normalizado'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
df_hotmart = df_hotmart[df_hotmart['email_normalizado'].str.contains('@', na=False)]

df_tmb_efetvizado['email_normalizado'] = df_tmb_efetvizado['Cliente Email'].astype(str).str.lower().str.strip()

# Emails com venda
emails_vendas_hotmart = set(df_hotmart['email_normalizado'].unique())
emails_vendas_tmb = set(df_tmb_efetvizado['email_normalizado'].unique())
emails_com_venda = emails_vendas_hotmart.union(emails_vendas_tmb)

# Análise
df_leads['tem_venda'] = df_leads['email_normalizado'].isin(emails_com_venda)

vendas_pessoas = df_leads['tem_venda'].sum()
taxa_conversao = (vendas_pessoas / len(df_leads) * 100) if len(df_leads) > 0 else 0
ticket_medio = total_soma / total_count if total_count > 0 else 0

print(f"\n🔗 VINCULAÇÃO COM LEADS:")
print(f"  Leads totais: {len(df_leads):,}")
print(f"  Pessoas com venda: {vendas_pessoas}")
print(f"  Taxa de conversão: {taxa_conversao:.2f}%")
print(f"  Ticket médio: R$ {ticket_medio:,.2f}")

# Por campanha
leads_hotmart = df_leads[df_leads['email_normalizado'].isin(emails_vendas_hotmart)].copy()
leads_tmb = df_leads[df_leads['email_normalizado'].isin(emails_vendas_tmb)].copy()

print(f"\n📈 POR CAMPANHA:")
print(f"\n  HOTMART:")
hotmart_com_utm = leads_hotmart.dropna(subset=['*Utm_campaign'])
for camp in sorted(hotmart_com_utm['*Utm_campaign'].unique()):
    count = len(hotmart_com_utm[hotmart_com_utm['*Utm_campaign'] == camp])
    print(f"    {camp}: {count} vendas")

print(f"\n  TMB:")
tmb_com_utm = leads_tmb.dropna(subset=['*Utm_campaign'])
for camp in sorted(tmb_com_utm['*Utm_campaign'].unique()):
    count = len(tmb_com_utm[tmb_com_utm['*Utm_campaign'] == camp])
    print(f"    {camp}: {count} vendas")

print(f"\n" + "="*100 + "\n")
