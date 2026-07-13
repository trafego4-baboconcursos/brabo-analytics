#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparar dados do Excel com dados do CRM
"""

import pandas as pd
import glob

print("\n" + "="*100)
print("COMPARACAO DE DADOS - EXCEL vs CRM")
print("="*100)

# Carregar dados do Excel
xlsx_files = glob.glob(r'C:\Users\trafe\OneDrive\Desktop\workspace-mmm\*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0]

df_bm_raw = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')
df_ga_raw = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA', skiprows=2)

print("\n*** DADOS EXTRAIDOS DO EXCEL (Raw) ***")

print(f"\nFacebook Ads (EXTRACAO-BM):")
print(f"  Registros: {len(df_bm_raw)}")
leads_bm = df_bm_raw['Leads'].sum()
invest_bm = df_bm_raw['Amount Spent'].sum()
print(f"  Leads: {leads_bm:,.0f}")
print(f"  Investimento: R$ {invest_bm:,.2f}")

print(f"\nGoogle Ads (EXTRACAO-GA):")
print(f"  Registros: {len(df_ga_raw)}")

invest_ga = 0
if 'Custo' in df_ga_raw.columns:
    invest_ga = pd.to_numeric(df_ga_raw['Custo'].astype(str).str.replace(',', '.'), errors='coerce').sum()
    print(f"  Investimento: R$ {invest_ga:,.2f}")

# TOTAL
total_invest_excel = invest_bm + invest_ga
total_leads_excel = leads_bm

print(f"\n*** TOTAIS EXCEL ***")
print(f"  Investimento Total: R$ {total_invest_excel:,.2f}")
print(f"  Leads Total: {total_leads_excel:,.0f}")

# CRM
print(f"\n*** DADOS DO CRM ***")

df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', sep=';', encoding='utf-8')
print(f"\nCRM Leads: {len(df_crm):,}")

df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
print(f"Hotmart Vendas: {len(df_hotmart)}")

df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
if 'Status' in df_tmb.columns:
    df_tmb = df_tmb[df_tmb['Status'] == 'Efetivado']

total_vendas_crm = len(df_hotmart) + len(df_tmb)

print(f"Vendas TMB (Efetivado): {len(df_tmb)}")
print(f"Total Vendas CRM: {total_vendas_crm}")

# Comparacao
print(f"\n" + "="*100)
print("COMPARACAO RESUMIDA")
print("="*100)

print(f"\n{'Metrica':<30} | {'EXCEL':<25} | {'CRM':<25}")
print("-" * 82)
print(f"{'Leads Gerados':<30} | {total_leads_excel:>23,.0f} | {len(df_crm):>23,}")
print(f"{'Diferenca (%)':<30} | {((total_leads_excel/len(df_crm)-1)*100):>21,.1f}% | -")
print(f"{'Investimento (FB+GA)':<30} | R$ {total_invest_excel:>19,.2f} | N/A")
print(f"{'CPL Medio':<30} | R$ {total_invest_excel/total_leads_excel:>20,.2f} | N/A")
print(f"{'Vendas':<30} | 385 (Excel) | {total_vendas_crm}")

print(f"\n" + "="*100 + "\n")
