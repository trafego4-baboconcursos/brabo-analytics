#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE POR PLATAFORMA - CORRIGIDA
Contando YouTube como Google Ads
"""

import pandas as pd
import glob
import re

print("=" * 100)
print("ANALISE POR PLATAFORMA - CORRIGIDA (YouTube = Google Ads)")
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
print(f"   Google Ads (incl. YouTube): {referencial_ga:>5,.0f} leads")
print(f"   TOTAL: {referencial_fb + referencial_ga:>24,.0f} leads")

# ===== REAL (CRM) =====
df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', 
                      sep=',', encoding='utf-8', quoting=1, low_memory=False)

print(f"\n2. REAL (CRM/ACTIVE CAMPAIGN):")
print("-" * 100)
print(f"   Total de Leads: {len(df_crm):>12,.0f}")

# Contando por plataforma
crm_fb = len(df_crm[df_crm['*Utm_source'].str.lower().str.contains('facebook|meta|fb', na=False)])
crm_yt = len(df_crm[df_crm['*Utm_source'].str.lower().str.contains('youtube|yt-', na=False)])
crm_ga = len(df_crm[df_crm['*Utm_source'].str.lower().str.contains('google', na=False)])
crm_google_total = crm_yt + crm_ga  # YouTube + Google Ads
crm_sem_origem = len(df_crm[df_crm['*Utm_source'].isna() | (df_crm['*Utm_source'] == '')])
crm_outros = len(df_crm) - crm_fb - crm_google_total - crm_sem_origem

print(f"   Facebook/Meta: {crm_fb:>15,.0f} leads")
print(f"   Google Ads: {crm_ga:>17,.0f} leads")
print(f"   YouTube: {crm_yt:>20,.0f} leads")
print(f"   Google Total (GA + YT): {crm_google_total:>8,.0f} leads")
print(f"   Outros: {crm_outros:>23,.0f} leads")
print(f"   SEM ORIGEM (utm_source vazio): {crm_sem_origem:>5,.0f} leads ⚠️")

# ===== COMPARACAO POR PLATAFORMA =====
print(f"\n3. COMPARACAO POR PLATAFORMA:")
print("-" * 100)

gap_fb = referencial_fb - crm_fb
gap_fb_pct = (gap_fb / referencial_fb) * 100

gap_ga = referencial_ga - crm_google_total
gap_ga_pct = (gap_ga / referencial_ga) * 100

print(f"\n   Facebook/Meta:")
print(f"      Referencial (Excel): {referencial_fb:>12,.0f}")
print(f"      Real (CRM): {crm_fb:>26,.0f}")
if gap_fb > 0:
    print(f"      GAP: {gap_fb:>28,.0f} leads faltando ({gap_fb_pct:>5.1f}%)")
else:
    print(f"      EXTRA: {abs(gap_fb):>24,.0f} leads acima da meta ({abs(gap_fb_pct):>5.1f}%)")

print(f"\n   Google Ads (Facebook Ads + YouTube):")
print(f"      Referencial (Excel): {referencial_ga:>12,.0f}")
print(f"      Real (CRM) - GA: {crm_ga:>15,.0f}")
print(f"      Real (CRM) - YT: {crm_yt:>15,.0f}")
print(f"      Real (CRM) - TOTAL: {crm_google_total:>11,.0f}")
if gap_ga > 0:
    print(f"      GAP: {gap_ga:>28,.0f} leads faltando ({gap_ga_pct:>5.1f}%)")
else:
    print(f"      EXTRA: {abs(gap_ga):>24,.0f} leads acima da meta ({abs(gap_ga_pct):>5.1f}%)")

# ===== RESUMO FINAL =====
total_rastreado = crm_fb + crm_google_total
total_esperado = referencial_fb + referencial_ga

print(f"\n4. RESUMO FINAL:")
print("-" * 100)
print(f"   Total Esperado (Excel): {total_esperado:>17,.0f} leads")
print(f"   Total Rastreado (CRM): {total_rastreado:>18,.0f} leads")
print(f"   Sem Origem: {crm_sem_origem:>28,.0f} leads ({(crm_sem_origem/len(df_crm))*100:>5.1f}%)")
print(f"   Outros: {crm_outros:>32,.0f} leads ({(crm_outros/len(df_crm))*100:>5.1f}%)")
print(f"   ────────────────────────────────────────────────────────────")
print(f"   Total CRM: {len(df_crm):>32,.0f} leads")

gap_total = total_esperado - total_rastreado
gap_total_pct = (gap_total / total_esperado) * 100

print(f"\n   GAP TOTAL (Esperado - Rastreado): {gap_total:>12,.0f} ({gap_total_pct:>5.1f}%)")

print(f"\n5. PROBLEMAS IDENTIFICADOS:")
print("-" * 100)
if crm_sem_origem > 0:
    print(f"   ⚠️  {crm_sem_origem:,} leads ({(crm_sem_origem/len(df_crm))*100:.1f}%) sem utm_source preenchido")
    print(f"       → ACAO: Validar origem desses leads (podem ser diretos, organic, etc)")

if gap_ga > 0:
    print(f"\n   ⚠️  {gap_ga:,} leads de Google Ads faltando no CRM ({gap_ga_pct:.1f}%)")
    print(f"       → ACAO: Verificar integracao GA com Active Campaign")
    
if gap_fb < 0:
    print(f"\n   ✅ Facebook tem {abs(gap_fb):,} leads ACIMA da meta")
    print(f"       → Possivelmente contabilizacao duplicada ou leads organicos rastreados como FB")

print("\n" + "=" * 100)
