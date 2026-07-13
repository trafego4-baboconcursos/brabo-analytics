#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE COMPARATIVA DETALHADA
Referencial (Excel) vs Real (CRM)
Objetivo: Identificar gaps e sincronizar dados
"""

import pandas as pd
import glob
from datetime import datetime

print("=" * 100)
print("ANALISE COMPARATIVA: EXCEL (Referencial) vs CRM (Real)")
print("=" * 100)

# ===== REFERENCIAL (EXCEL) =====
xlsx_files = glob.glob(r'*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0]

df_bm = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')
df_ga = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA')

# Facebook
leads_fb = df_bm['Leads'].sum()
invest_fb = df_bm['Amount Spent'].sum()
cpl_fb = invest_fb / leads_fb

# Google
leads_ga = df_ga['Conversions'].sum()
invest_ga = float(df_ga['Cost (Spend)'].sum())
cpl_ga = invest_ga / leads_ga

total_leads_excel = leads_fb + leads_ga
total_invest_excel = invest_fb + invest_ga
cpl_total_excel = total_invest_excel / total_leads_excel

print("\n1. REFERENCIAL (EXCEL/PLANILHA):")
print("-" * 100)
print(f"   Facebook Ads:")
print(f"      Leads: {leads_fb:>15,.0f}")
print(f"      Investimento: R$ {invest_fb:>16,.2f}")
print(f"      CPL: R$ {cpl_fb:>22,.2f}")
print(f"\n   Google Ads:")
print(f"      Conversions: {leads_ga:>12,.0f}")
print(f"      Investimento: R$ {invest_ga:>16,.2f}")
print(f"      CPL: R$ {cpl_ga:>22,.2f}")
print(f"\n   TOTAL REFERENCIAL:")
print(f"      Leads: {total_leads_excel:>15,.0f}")
print(f"      Investimento: R$ {total_invest_excel:>16,.2f}")
print(f"      CPL Medio: R$ {cpl_total_excel:>18,.2f}")

# ===== REAL (CRM) =====
df_crm = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', 
                      sep=',', encoding='utf-8', quoting=1, low_memory=False)

# Vendas
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
# Valores já estão em reais, sem conversão necessária
df_hotmart['valor_num'] = df_hotmart['Faturamento bruto (sem impostos)']

df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
# Valores já estão em reais, sem conversão necessária
df_tmb['valor_num'] = df_tmb['Ticket do pedido']

total_leads_crm = len(df_crm)
total_vendas = len(df_hotmart) + len(df_tmb)
total_valor_vendas = df_hotmart['valor_num'].sum() + df_tmb['valor_num'].sum()
taxa_conversao = (total_vendas / total_leads_crm) * 100 if total_leads_crm > 0 else 0
ticket_medio = total_valor_vendas / total_vendas if total_vendas > 0 else 0

# Estimar investimento pelo ROAS (assumindo ROAS = Revenue / Investment)
# Se temos 571 vendas e R$ total_valor_vendas, e queremos ROAS similar ao mercado...
# Vamos usar: Revenue = Investment * ROAS
# ROAS típico de captação é 2-5x
# Se usarmos a planilha como referencial: CPL é R$ 3,48, então por cada lead gasto R$ 3,48
# Com 81.261 leads, seria R$ 282.627,28 de investimento

investimento_estimado_crm = total_leads_crm * cpl_total_excel

print("\n2. REAL (CRM/FOLDERS):")
print("-" * 100)
print(f"   Dados de Leads (Active Campaign):")
print(f"      Leads: {total_leads_crm:>15,.0f}")
print(f"      Investimento (Referencial: CPL x Leads): R$ {investimento_estimado_crm:>8,.2f}")
print(f"      CPL Esperado: R$ {cpl_total_excel:>22,.2f}")
print(f"\n   Dados de Vendas:")
print(f"      Hotmart: {len(df_hotmart):>18,} vendas (R$ {df_hotmart['valor_num'].sum():,.2f})")
print(f"      TMB: {len(df_tmb):>23,} vendas (R$ {df_tmb['valor_num'].sum():,.2f})")
print(f"      TOTAL VENDAS: {total_vendas:>14,}")
print(f"      Valor Total: R$ {total_valor_vendas:>19,.2f}")
print(f"      Ticket Medio: R$ {ticket_medio:>20,.2f}")
print(f"      Taxa de Conversao: {taxa_conversao:>15,.2f}%")

# ===== COMPARACAO E GAPS =====
gap_leads = total_leads_excel - total_leads_crm
gap_leads_pct = (gap_leads / total_leads_excel) * 100
gap_investimento = total_invest_excel - investimento_estimado_crm
gap_investimento_pct = (gap_investimento / total_invest_excel) * 100

print("\n3. ANALISE DE GAPS:")
print("-" * 100)
print(f"   Leads:")
print(f"      Referencial (Excel): {total_leads_excel:>14,.0f}")
print(f"      Real (CRM): {total_leads_crm:>29,.0f}")
print(f"      GAP: {gap_leads:>41,.0f} leads ({gap_leads_pct:>5.1f}%)")
print(f"\n   Investimento:")
print(f"      Referencial (Excel): R$ {total_invest_excel:>16,.2f}")
print(f"      Esperado (CRM): R$ {investimento_estimado_crm:>19,.2f}")
print(f"      GAP: R$ {gap_investimento:>32,.2f} ({gap_investimento_pct:>5.1f}%)")
print(f"\n   ROI/ROAS:")
print(f"      Investimento por Venda (CRM): R$ {investimento_estimado_crm/total_vendas:,.2f}")
print(f"      Valor por Venda: R$ {ticket_medio:,.2f}")
print(f"      ROAS Estimado: {ticket_medio / (investimento_estimado_crm/total_vendas):>2.1f}x")

print("\n4. RECOMENDACOES:")
print("-" * 100)
print(f"""
   1. LEADS FALTANDO NO CRM: {gap_leads:,.0f} ({gap_leads_pct:.1f}%)
      - Validar integracao do Active Campaign com FB/GA
      - Verificar se leads estao sendo filtrados/deletados
      - Revisar regras de duplicacao

   2. INVESTIGAR ORIGEM DOS LEADS:
      - Facebook: {leads_fb:>15,.0f} (no Excel)
      - Google: {leads_ga:>16,.0f} (no Excel)
      - CRM: {total_leads_crm:>17,.0f} (real)
      - Cada fonte deveria ter registro proporcional no CRM

   3. VENDAS vs LEADS:
      - Leads CRM: {total_leads_crm:>17,.0f}
      - Vendas: {total_vendas:>32,.0f}
      - Taxa: {taxa_conversao:>33.2f}%
      - Objetivo: Aumentar para 1-2% (hoje em {taxa_conversao:.2f}%)

   4. PROXIMO PASSO:
      - Comparar leads CRM por utm_source com dados do Excel
      - Identificar qual plataforma tem maior gap
      - Verificar logs de importacao do Active Campaign

""")

print("=" * 100)
print(f"Analise gerada em: {datetime.now().strftime('%d/%m/%Y as %H:%M:%S')}")
print("=" * 100)
