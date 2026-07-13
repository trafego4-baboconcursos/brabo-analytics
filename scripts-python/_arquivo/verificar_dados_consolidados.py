#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar dados consolidados da comparacao
"""

import pandas as pd
import glob

xlsx_files = glob.glob(r'*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0]

df_bm = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')
df_ga = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA')

print("=" * 80)
print("DADOS DO EXCEL - COMPARACAO")
print("=" * 80)

print("\nFACEBOOK ADS:")
leads_fb = df_bm['Leads'].sum()
invest_fb = df_bm['Amount Spent'].sum()
print(f"  Leads: {leads_fb:,.0f}")
print(f"  Investimento: R$ {invest_fb:,.2f}")
print(f"  CPL: R$ {invest_fb/leads_fb:,.2f}")

print("\nGOOGLE ADS:")
leads_ga = df_ga['Conversions'].sum() if 'Conversions' in df_ga.columns else 0
invest_ga = float(df_ga['Cost (Spend)'].sum()) if 'Cost (Spend)' in df_ga.columns else 0
print(f"  Leads (Conversions): {leads_ga:,.0f}")
print(f"  Investimento: R$ {invest_ga:,.2f}")
print(f"  CPL: R$ {invest_ga/leads_ga:,.2f}" if leads_ga > 0 else "  CPL: N/A")

print("\nTOTAL CONSOLIDADO:")
total_leads = leads_fb + leads_ga
total_invest = invest_fb + invest_ga
print(f"  Leads: {total_leads:,.0f}")
print(f"  Investimento: R$ {total_invest:,.2f}")
print(f"  CPL: R$ {total_invest/total_leads:,.2f}")

print("\nCRM:")
df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', sep=',', encoding='utf-8', quoting=1, low_memory=False)
print(f"  Leads CRM: {len(df_crm):,}")

print("\nDISCREPANCIA:")
pct_diff = ((total_leads / len(df_crm)) - 1) * 100
print(f"  Excel tem {pct_diff:.0f}% MAIS leads que CRM")
print(f"  Diferenca: {total_leads - len(df_crm):,.0f} leads nao rastreados")

print("\n" + "=" * 80)
