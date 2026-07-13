#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparação detalhada: Planilha vs Script (após consolidação)
"""

import pandas as pd
from pathlib import Path
import csv

# Dados da planilha
planilha = {
    'AD113': {'vendas': 53, 'valor': 72117.72},
    'AD092': {'vendas': 53, 'valor': 67014.90},
    'AD050': {'vendas': 55, 'valor': 63091.94},
    'AD110': {'vendas': 43, 'valor': 58413.43},
    'AD037': {'vendas': 22, 'valor': 22124.72},
    'AD084': {'vendas': 24, 'valor': 31561.80},
    'AD093': {'vendas': 24, 'valor': 28888.00},
    'AD109': {'vendas': 21, 'valor': 26195.38},
    'AD058': {'vendas': 16, 'valor': 21249.20},
    'AD112': {'vendas': 7, 'valor': 10942.70},
    'AD098': {'vendas': 6, 'valor': 7183.00},
    'AD059': {'vendas': 5, 'valor': 5228.20},
    'AD048': {'vendas': 4, 'valor': 5078.30},
    'AD040': {'vendas': 1, 'valor': 1798.80},
    'AD090': {'vendas': 2, 'valor': 3441.60},
    'AD117': {'vendas': 2, 'valor': 299.80}
}

print("=" * 100)
print("🔍 COMPARAÇÃO DETALHADA: PLANILHA vs SCRIPT (CONSOLIDADO)")
print("=" * 100)

# ========== CARREGAR DADOS ==========
def encontrar_csv_leads_abr():
    base = Path(r'analises/[PBB-ABR-26]')
    candidatos = []
    for pasta in [base / 'Active Campaign', base / 'active-campaing', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-abr-26' in f.name.lower() or 'lead' in f.name.lower())
    return max(candidatos, key=lambda f: f.stat().st_mtime)

leads_file = encontrar_csv_leads_abr()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()
df_leads_criativo = df_leads[df_leads['*Utm_content'].notna()].copy()
df_leads_criativo['criativo_original'] = df_leads_criativo['*Utm_content'].astype(str).str.strip()
df_leads_criativo['criativo'] = df_leads_criativo['criativo_original'].apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)

df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce').fillna(0)

df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
col_situacao = [c for c in df_tmb.columns if 'Situa' in c][0] if any('Situa' in c for c in df_tmb.columns) else None
if col_situacao:
    df_tmb = df_tmb[df_tmb[col_situacao] == 'Vigente']
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce').fillna(0)

emails_com_utm = set(df_leads_criativo['Email'].unique())
vendas_rastreadas_h = df_hotmart[df_hotmart['email'].isin(emails_com_utm)]
vendas_rastreadas_t = df_tmb[df_tmb['email'].isin(emails_com_utm)]

# ========== COMPARAÇÃO POR CRIATIVO ==========
print(f"\n{'Criativo':<10} {'Vendas':>8} {'Valor Planilha':>18} {'Valor Script':>18} {'Diferença':>15} {'Status':>8}")
print("-" * 100)

total_vendas_planilha = 0
total_valor_planilha = 0
total_valor_script = 0

for criativo_name in sorted(planilha.keys()):
    vendas_planilha = planilha[criativo_name]['vendas']
    valor_planilha = planilha[criativo_name]['valor']
    
    # Calcular do script
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name.upper()]['Email'].unique()
    vendas_h = len(vendas_rastreadas_h[vendas_rastreadas_h['email'].isin(emails_criativo)])
    vendas_t = len(vendas_rastreadas_t[vendas_rastreadas_t['email'].isin(emails_criativo)])
    vendas_script = vendas_h + vendas_t
    
    valor_h = vendas_rastreadas_h[vendas_rastreadas_h['email'].isin(emails_criativo)]['valor_num'].sum()
    valor_t = vendas_rastreadas_t[vendas_rastreadas_t['email'].isin(emails_criativo)]['valor_num'].sum()
    valor_script = valor_h + valor_t
    
    diferenca = valor_script - valor_planilha
    simbolo = "✓" if abs(diferenca) < 100 else "⚠️"
    
    print(f"{criativo_name:<10} {vendas_script:>8} R$ {valor_planilha:>14,.2f} R$ {valor_script:>14,.2f} R$ {diferenca:>12,.2f} {simbolo:>8}")
    
    total_vendas_planilha += vendas_script
    total_valor_planilha += valor_planilha
    total_valor_script += valor_script

print("-" * 100)
print(f"{'TOTAL':<10} {total_vendas_planilha:>8} R$ {total_valor_planilha:>14,.2f} R$ {total_valor_script:>14,.2f} R$ {total_valor_script - total_valor_planilha:>12,.2f}")
print("=" * 100)

# ========== ANÁLISE DA DIFERENÇA ==========
diferenca_total = total_valor_script - total_valor_planilha
print(f"\n📊 ANÁLISE:")
print(f"   Diferença total: R$ {diferenca_total:,.2f}")
print(f"   Percentual: {diferenca_total/total_valor_planilha*100:.2f}%")

if abs(diferenca_total) > 1000:
    print(f"\n⚠️ POSSÍVEL CAUSA:")
    print(f"   A planilha pode estar usando um recorte diferente de vendas (período, status, etc)")
    print(f"   ou há vendas duplicadas/excluídas na planilha que não estão nos CSVs.")
else:
    print(f"\n✅ Os valores estão muito próximos! Diferença aceitável.")

# Verificar vendas não atribuídas
vendas_nao_rastreadas_h = df_hotmart[~df_hotmart['email'].isin(emails_com_utm)]
vendas_nao_rastreadas_t = df_tmb[~df_tmb['email'].isin(emails_com_utm)]
total_nao_rastreadas = len(vendas_nao_rastreadas_h) + len(vendas_nao_rastreadas_t)
valor_nao_rastreado = vendas_nao_rastreadas_h['valor_num'].sum() + vendas_nao_rastreadas_t['valor_num'].sum()

print(f"\n📋 VENDAS NÃO ATRIBUÍDAS:")
print(f"   Planilha: 155 vendas = R$ 176.683,81")
print(f"   Script:   {total_nao_rastreadas} vendas = R$ {valor_nao_rastreado:,.2f}")
print(f"   Diferença: R$ {valor_nao_rastreado - 176683.81:,.2f}")

print(f"\n📊 TOTAL GERAL:")
print(f"   Planilha: {total_vendas_planilha + 155} vendas = R$ {total_valor_planilha + 176683.81:,.2f}")
print(f"   Script:   {total_vendas_planilha + total_nao_rastreadas} vendas = R$ {total_valor_script + valor_nao_rastreado:,.2f}")
print(f"   Diferença: R$ {(total_valor_script + valor_nao_rastreado) - (total_valor_planilha + 176683.81):,.2f}")
print("=" * 100)
