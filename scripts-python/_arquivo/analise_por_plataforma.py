#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE POR PLATAFORMA
Comparando leads no CRM por utm_source com referencial do Excel
"""

import pandas as pd
import glob

print("=" * 100)
print("ANALISE POR PLATAFORMA: Comparando CRM com Referencial")
print("=" * 100)

# ===== REFERENCIAL (EXCEL) =====
xlsx_files = glob.glob(r'*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0]

df_bm = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')
df_ga = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA')

referencial_fb = df_bm['Leads'].sum()
referencial_ga = df_ga['Conversions'].sum()

print(f"\n1. REFERENCIAL (EXCEL/PLANILHA):")
print("-" * 100)
print(f"   Facebook Ads: {referencial_fb:>15,.0f} leads")
print(f"   Google Ads: {referencial_ga:>17,.0f} leads")
print(f"   TOTAL: {referencial_fb + referencial_ga:>24,.0f} leads")

# ===== REAL (CRM) - Analisando utm_source =====
df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', 
                      sep=',', encoding='utf-8', quoting=1, low_memory=False)

print(f"\n2. REAL (CRM/ACTIVE CAMPAIGN):")
print("-" * 100)
print(f"\n   Total de Leads: {len(df_crm):>12,.0f}")
print(f"\n   Breakdown por utm_source:")

# Colunas que podem conter a origem
utm_cols = [col for col in df_crm.columns if 'utm' in col.lower() or 'source' in col.lower()]
print(f"\n   Colunas encontradas: {utm_cols}")

if '*Utm_source' in df_crm.columns:
    utm_breakdown = df_crm['*Utm_source'].value_counts()
    for source, count in utm_breakdown.items():
        pct = (count / len(df_crm)) * 100
        print(f"      {source}: {count:>12,.0f} ({pct:>5.1f}%)")
else:
    print("      Coluna '*Utm_source' nao encontrada")
    print("      Colunas disponiveis que contem 'utm':")
    for col in utm_cols:
        print(f"         - {col}")
        if df_crm[col].notna().sum() > 0:
            breakdown = df_crm[col].value_counts().head(5)
            for val, count in breakdown.items():
                pct = (count / len(df_crm)) * 100
                print(f"            {val}: {count:>10,.0f} ({pct:>5.1f}%)")

# ===== COMPARACAO POR PLATAFORMA =====
print(f"\n3. COMPARACAO POR PLATAFORMA:")
print("-" * 100)

if '*Utm_source' in df_crm.columns:
    crm_fb = len(df_crm[df_crm['*Utm_source'].str.lower().str.contains('facebook|meta|fb', na=False)])
    crm_ga = len(df_crm[df_crm['*Utm_source'].str.lower().str.contains('google', na=False)])
    crm_outros = len(df_crm) - crm_fb - crm_ga
    
    print(f"\n   Facebook/Meta:")
    print(f"      Referencial (Excel): {referencial_fb:>12,.0f}")
    print(f"      Real (CRM): {crm_fb:>26,.0f}")
    print(f"      GAP: {referencial_fb - crm_fb:>28,.0f} ({((referencial_fb - crm_fb)/referencial_fb)*100:>5.1f}%)")
    
    print(f"\n   Google Ads:")
    print(f"      Referencial (Excel): {referencial_ga:>12,.0f}")
    print(f"      Real (CRM): {crm_ga:>26,.0f}")
    print(f"      GAP: {referencial_ga - crm_ga:>28,.0f} ({((referencial_ga - crm_ga)/referencial_ga)*100:>5.1f}%)")
    
    print(f"\n   Outros/Sem origen:")
    print(f"      Real (CRM): {crm_outros:>26,.0f}")

print("\n" + "=" * 100)
print("FIM DA ANALISE")
print("=" * 100)
