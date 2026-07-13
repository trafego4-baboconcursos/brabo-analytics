#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisa novo arquivo de leads e compara com vendas
"""

import pandas as pd
import glob
from pathlib import Path

# Carregar novo arquivo de leads
novo_leads_path = r'analises/[PBB-ABR-26]/Active Campaign/PBB-ABR-14h-12-05-26.csv'
df_leads = pd.read_csv(novo_leads_path, sep=',', encoding='utf-8')

print(f"✓ Total de leads: {len(df_leads)}")
print(f"\n✓ Colunas UTM disponíveis:")
utm_cols = [col for col in df_leads.columns if 'utm' in col.lower() or 'rastreio' in col.lower()]
for col in utm_cols:
    print(f"  - {col}")

print(f"\n✓ UTM_CAMPAIGN: {df_leads['*Utm_campaign'].unique()}")
print(f"\n✓ UTM_SOURCE (plataformas): {df_leads['*Utm_source'].unique()}")
print(f"\n✓ UTM_MEDIUM (tipos campanha): {df_leads['*Utm_medium'].nunique()} tipos únicos")
print(f"\n✓ UTM_CONTENT (criativos): {df_leads['*Utm_content'].nunique()} criativos únicos")

# Contar leads por fonte
print(f"\n=== LEADS POR FONTE ===")
leads_source = df_leads['*Utm_source'].value_counts()
for source, count in leads_source.items():
    print(f"  {source}: {count}")

# Contar leads por criativo
print(f"\n=== TOP 10 CRIATIVOS ===")
top_criativos = df_leads['*Utm_content'].value_counts().head(10)
for criativo, count in top_criativos.items():
    print(f"  {criativo}: {count} leads")

# Dados de vendas
print(f"\n=== VENDAS DISPONIVEIS ===")
hotmart_path = r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv'
tmb_path = r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv'

df_hotmart = pd.read_csv(hotmart_path, sep=';', encoding='utf-8')
df_tmb = pd.read_csv(tmb_path, sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Status'] == 'Efetivado']

print(f"  Hotmart: {len(df_hotmart)} vendas")
print(f"  TMB: {len(df_tmb)} vendas")
print(f"  Total: {len(df_hotmart) + len(df_tmb)} vendas")
