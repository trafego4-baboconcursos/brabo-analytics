#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparar dados calculados vs planilha do usuário
"""

import pandas as pd
from pathlib import Path
import csv

print("=" * 100)
print("🔍 COMPARAÇÃO: SCRIPTS vs PLANILHA DO USUÁRIO")
print("=" * 100)

# Dados da planilha do usuário
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
    'AD117': {'vendas': 2, 'valor': 299.80},
    'Não Atribuído': {'vendas': 155, 'valor': 176683.81}
}

total_vendas_planilha = sum(d['vendas'] for d in planilha.values())
total_valor_planilha = sum(d['valor'] for d in planilha.values())
vendas_rastreadas_planilha = sum(d['vendas'] for k, d in planilha.items() if k != 'Não Atribuído')
valor_rastreado_planilha = sum(d['valor'] for k, d in planilha.items() if k != 'Não Atribuído')

print(f"\n📋 TOTAIS DA PLANILHA:")
print(f"   Vendas rastreadas: {vendas_rastreadas_planilha}")
print(f"   Vendas não atribuídas: {planilha['Não Atribuído']['vendas']}")
print(f"   TOTAL: {total_vendas_planilha} vendas = R$ {total_valor_planilha:,.2f}")

# ========== CARREGAR DADOS REAIS ==========
print(f"\n📦 CARREGANDO DADOS CRM...")

# Leads
def encontrar_csv_leads_abr():
    base = Path(r'analises/[PBB-ABR-26]')
    candidatos = []
    for pasta in [base / 'Active Campaign', base / 'active-campaing', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-abr-26' in f.name.lower() or 'lead' in f.name.lower())
    if not candidatos:
        raise FileNotFoundError('Arquivo de leads PBB-ABR-26 não encontrado')
    return max(candidatos, key=lambda f: f.stat().st_mtime)

leads_file = encontrar_csv_leads_abr()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()
df_leads_criativo = df_leads[df_leads['*Utm_content'].notna()].copy()
df_leads_criativo['criativo'] = df_leads_criativo['*Utm_content'].astype(str).str.strip().str.upper()

# Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce').fillna(0)

# TMB
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
col_situacao = [c for c in df_tmb.columns if 'Situa' in c][0] if any('Situa' in c for c in df_tmb.columns) else None
if col_situacao:
    df_tmb = df_tmb[df_tmb[col_situacao] == 'Vigente']
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce').fillna(0)

print(f"   Hotmart: {len(df_hotmart)} vendas = R$ {df_hotmart['valor_num'].sum():,.2f}")
print(f"   TMB: {len(df_tmb)} vendas = R$ {df_tmb['valor_num'].sum():,.2f}")
print(f"   TOTAL CRM: {len(df_hotmart) + len(df_tmb)} vendas = R$ {(df_hotmart['valor_num'].sum() + df_tmb['valor_num'].sum()):,.2f}")

# ========== ANÁLISE POR CRIATIVO ==========
print(f"\n🎯 ANÁLISE POR CRIATIVO (comparação):")

# Criar dicionário de vendas por criativo
emails_com_utm = set(df_leads_criativo['Email'].unique())
vendas_rastreadas_h = df_hotmart[df_hotmart['email'].isin(emails_com_utm)]
vendas_rastreadas_t = df_tmb[df_tmb['email'].isin(emails_com_utm)]

# Para cada criativo na planilha, calcular vendas
print(f"\n{'Criativo':<15} {'Planilha':>10} {'Script':>10} {'Diferença':>10}")
print("-" * 50)

for criativo_name in sorted(planilha.keys()):
    if criativo_name == 'Não Atribuído':
        continue
    
    vendas_planilha = planilha[criativo_name]['vendas']
    
    # Calcular vendas do script para este criativo
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name.upper()]['Email'].unique()
    vendas_h = len(vendas_rastreadas_h[vendas_rastreadas_h['email'].isin(emails_criativo)])
    vendas_t = len(vendas_rastreadas_t[vendas_rastreadas_t['email'].isin(emails_criativo)])
    vendas_script = vendas_h + vendas_t
    
    diferenca = vendas_script - vendas_planilha
    simbolo = "✓" if diferenca == 0 else "⚠️"
    print(f"{simbolo} {criativo_name:<12} {vendas_planilha:>10} {vendas_script:>10} {diferenca:>+10}")

print("-" * 50)

# Vendas não atribuídas
vendas_nao_rastreadas_h = df_hotmart[~df_hotmart['email'].isin(emails_com_utm)]
vendas_nao_rastreadas_t = df_tmb[~df_tmb['email'].isin(emails_com_utm)]
total_nao_rastreadas = len(vendas_nao_rastreadas_h) + len(vendas_nao_rastreadas_t)

print(f"Não Atribuído    {planilha['Não Atribuído']['vendas']:>10} {total_nao_rastreadas:>10} {total_nao_rastreadas - planilha['Não Atribuído']['vendas']:>+10}")

# ========== VERIFICAR CRIATIVOS EXTRAS NO SCRIPT ==========
print(f"\n🔍 CRIATIVOS COM VENDAS NO SCRIPT (todos):")

criativo_stats = df_leads_criativo.groupby('criativo').agg({'Email': 'count'}).rename(columns={'Email': 'leads'}).reset_index()

def contar_vendas(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    vendas_h = len(vendas_rastreadas_h[vendas_rastreadas_h['email'].isin(emails_criativo)])
    vendas_t = len(vendas_rastreadas_t[vendas_rastreadas_t['email'].isin(emails_criativo)])
    return vendas_h + vendas_t

criativo_stats['vendas'] = criativo_stats['criativo'].apply(contar_vendas)
criativo_stats = criativo_stats[criativo_stats['vendas'] > 0].sort_values('vendas', ascending=False)

print(f"\n{'Criativo':<30} {'Vendas':>10} {'Na Planilha':>15}")
print("-" * 60)

criativos_planilha_upper = [k.upper() for k in planilha.keys() if k != 'Não Atribuído']

for idx, row in criativo_stats.iterrows():
    criativo = row['criativo']
    vendas = int(row['vendas'])
    na_planilha = "✓ Sim" if criativo in criativos_planilha_upper else "❌ NÃO"
    print(f"{criativo:<30} {vendas:>10} {na_planilha:>15}")

print("\n" + "=" * 100)
print(f"📊 RESUMO:")
print(f"   Planilha: {total_vendas_planilha} vendas ({vendas_rastreadas_planilha} rastreadas + {planilha['Não Atribuído']['vendas']} não atribuídas)")
print(f"   Script:   {len(vendas_rastreadas_h) + len(vendas_rastreadas_t) + total_nao_rastreadas} vendas ({len(vendas_rastreadas_h) + len(vendas_rastreadas_t)} rastreadas + {total_nao_rastreadas} não atribuídas)")
print(f"   Diferença: {(len(vendas_rastreadas_h) + len(vendas_rastreadas_t)) - vendas_rastreadas_planilha} vendas rastreadas a mais no script")
print("=" * 100)
