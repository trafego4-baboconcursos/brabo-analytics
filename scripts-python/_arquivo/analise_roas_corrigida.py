#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise CORRIGIDA de ROAS - Todas as vendas (Hotmart + TMB)
"""

import pandas as pd
import numpy as np
from datetime import datetime

print("\n" + "="*100)
print("📊 ANÁLISE ROAS - LEADS x TODAS AS VENDAS (Hotmart + TMB)")
print("="*100)

# Carregar dados
print("\n📥 Carregando dados...")
df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')
print(f"✓ Leads: {len(df_leads)} registros")

# Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
valor_col = df_hotmart['Valor de compra sem impostos']
valor_col_str = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
df_hotmart['valor_numerico'] = pd.to_numeric(valor_col_str, errors='coerce')
df_hotmart['email_normalizado'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
df_hotmart = df_hotmart[df_hotmart['email_normalizado'].str.contains('@', na=False)]
print(f"✓ Hotmart: {len(df_hotmart)} registros | Total: R$ {df_hotmart['valor_numerico'].sum():,.2f}")

# TMB
df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', sep=';')
# Converter valor TMB (usar ponto como separador decimal)
df_tmb['valor_numerico'] = pd.to_numeric(df_tmb['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')
# Filtrar apenas vendas efetivadas
df_tmb_vendas = df_tmb[df_tmb['Status'] == 'Efetivado'].copy()
df_tmb_vendas['email_normalizado'] = df_tmb_vendas['Cliente Email'].astype(str).str.lower().str.strip()
print(f"✓ TMB: {len(df_tmb_vendas)} registros | Total: R$ {df_tmb_vendas['valor_numerico'].sum():,.2f}")

# Combinar vendas
print(f"\n📊 TOTAL DE VENDAS:")
total_hotmart = df_hotmart['valor_numerico'].sum()
total_tmb = df_tmb_vendas['valor_numerico'].sum()
total_vendas_valor = total_hotmart + total_tmb
print(f"  Hotmart (Crédito): R$ {total_hotmart:,.2f} ({len(df_hotmart)} transações)")
print(f"  TMB (Boleto):      R$ {total_tmb:,.2f} ({len(df_tmb_vendas)} transações)")
print(f"  TOTAL GERAL:       R$ {total_vendas_valor:,.2f} ({len(df_hotmart) + len(df_tmb_vendas)} transações)")

# Combinar emails de vendedores
emails_vendas_hotmart = set(df_hotmart['email_normalizado'].unique())
emails_vendas_tmb = set(df_tmb_vendas['email_normalizado'].unique())
emails_com_venda = emails_vendas_hotmart.union(emails_vendas_tmb)

print(f"\n🔗 VINCULAÇÃO COM LEADS:")
df_leads['email_normalizado'] = df_leads['Email'].astype(str).str.lower().str.strip()
df_leads['tem_venda'] = df_leads['email_normalizado'].isin(emails_com_venda)

vendas_vinculadas = df_leads['tem_venda'].sum()
taxa_conversao = (vendas_vinculadas / len(df_leads) * 100) if len(df_leads) > 0 else 0

print(f"  Total de leads: {len(df_leads):,}")
print(f"  Leads com venda: {vendas_vinculadas}")
print(f"  Taxa de conversão: {taxa_conversao:.2f}%")

# Cruzar informações detalhadas
print(f"\n💼 CRUZAMENTO DE DADOS:")

# Hotmart
leads_hotmart = df_leads[df_leads['email_normalizado'].isin(emails_vendas_hotmart)].copy()
hotmart_com_utm = leads_hotmart.dropna(subset=['*Utm_campaign'])
print(f"  Hotmart com UTM vinculado: {len(hotmart_com_utm)} / {len(leads_hotmart)}")

# TMB
leads_tmb = df_leads[df_leads['email_normalizado'].isin(emails_vendas_tmb)].copy()
tmb_com_utm = leads_tmb.dropna(subset=['*Utm_campaign'])
print(f"  TMB com UTM vinculado: {len(tmb_com_utm)} / {len(leads_tmb)}")

# Vendas sem UTM mapeado
leads_vendas_sem_utm = vendas_vinculadas - len(hotmart_com_utm) - len(tmb_com_utm)
print(f"  Vendas SEM UTM mapeado: {leads_vendas_sem_utm}")

# Análise por campanha (apenas com UTM)
print(f"\n📈 ANÁLISE POR CAMPANHA (apenas com UTM mapeado):")

# Hotmart por campanha
if len(hotmart_com_utm) > 0:
    print(f"\n  HOTMART (Crédito):")
    for campanha in sorted(hotmart_com_utm['*Utm_campaign'].unique()):
        if pd.isna(campanha):
            continue
        leads_campaign = len(hotmart_com_utm[hotmart_com_utm['*Utm_campaign'] == campanha])
        print(f"    {campanha}: {leads_campaign} vendas")

# TMB por campanha
if len(tmb_com_utm) > 0:
    print(f"\n  TMB (Boleto):")
    for campanha in sorted(tmb_com_utm['*Utm_campaign'].unique()):
        if pd.isna(campanha):
            continue
        leads_campaign = len(tmb_com_utm[tmb_com_utm['*Utm_campaign'] == campanha])
        print(f"    {campanha}: {leads_campaign} vendas")

# Resumo final
print(f"\n" + "="*100)
print(f"📊 RESUMO FINAL:")
print(f"  Valor Total em Vendas: R$ {total_vendas_valor:,.2f}")
print(f"  Ticket Médio Geral: R$ {total_vendas_valor / (len(df_hotmart) + len(df_tmb_vendas)):,.2f}")
print(f"  Vendas Vinculadas a Leads: {vendas_vinculadas}")
print(f"  Vendas com UTM Mapeado: {len(hotmart_com_utm) + len(tmb_com_utm)}")
print(f"  Vendas SEM UTM: {leads_vendas_sem_utm}")
print("="*100 + "\n")
