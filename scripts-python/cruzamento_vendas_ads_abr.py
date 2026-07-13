#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRUZAMENTO VENDAS × ADS — PBB-ABR-26
Cruza: investimento Meta+Google por anúncio × vendas atribuídas via CRM (email match)
Output: ranking de anúncios por ROAS, CPA, conversão
"""

import pandas as pd
import numpy as np
import re
import csv
from pathlib import Path

BASE = Path('analises') / '[PBB-ABR-26]'

# ─────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────
def extrair_codigo_ad(nome):
    """Extrai código base do anúncio (ex: 'AD092 - Dois...' → 'AD092')"""
    txt = str(nome).strip()
    if ' - ' in txt:
        codigo = txt.split(' - ')[0].strip().upper()
    else:
        codigo = txt.strip().upper()
    # Valida padrão AD + números
    if re.match(r'^AD\d{2,3}$', codigo):
        return codigo
    return None

def limpar_brl(valor):
    """Converte string monetária BRL para float (ex: '8.085,67' → 8085.67)"""
    if pd.isna(valor) or valor in ('--', '', None):
        return 0.0
    txt = str(valor).strip()
    # Remove símbolo R$ se houver
    txt = txt.replace('R$', '').strip()
    # Formato 1.234,56 ou 1234,56
    if ',' in txt and '.' in txt:
        txt = txt.replace('.', '').replace(',', '.')
    elif ',' in txt:
        txt = txt.replace(',', '.')
    try:
        return float(txt)
    except:
        return 0.0

def encontrar_csv_leads():
    base = BASE
    candidatos = []
    for pasta in [base / 'Active Campaign', base / 'active-campaing', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-abr' in f.name.lower())
    if not candidatos:
        raise FileNotFoundError('Arquivo de leads não encontrado')
    return max(candidatos, key=lambda f: f.stat().st_mtime)

# ─────────────────────────────────────────
print("=" * 80)
print("🎯 CRUZAMENTO VENDAS × ADS — PBB-ABR-26")
print("=" * 80)

# ─────────────────────────────────────────
# 1. LEADS CRM (com UTM)
# ─────────────────────────────────────────
print("\n[1/5] Carregando CRM leads...")
leads_file = encontrar_csv_leads()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_leads['email'] = df_leads['Email'].astype(str).str.strip().str.lower()
df_leads['utm_content'] = df_leads['*Utm_content'].astype(str).str.strip()
df_leads['ad_code'] = df_leads['utm_content'].apply(lambda x: extrair_codigo_ad(str(x).split(' - ')[0]) if pd.notna(x) and str(x) != 'nan' else None)
df_leads_com_ad = df_leads[df_leads['ad_code'].notna()].copy()

total_leads = len(df_leads)
leads_com_utm = len(df_leads_com_ad)
print(f"   Total leads: {total_leads:,}")
print(f"   Leads com UTM (ad code válido): {leads_com_utm:,} ({leads_com_utm/total_leads*100:.1f}%)")
print(f"   Ads únicos no CRM: {df_leads_com_ad['ad_code'].nunique()}")

# ─────────────────────────────────────────
# 2. VENDAS (Hotmart + TMB, sem RI)
# ─────────────────────────────────────────
print("\n[2/5] Carregando vendas...")
df_hotmart = pd.read_csv(BASE / 'Vendas' / 'hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
_tipo_col = next((c for c in df_hotmart.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
if _tipo_col:
    df_hotmart = df_hotmart[df_hotmart[_tipo_col].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
df_hotmart['valor'] = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce').fillna(0)
df_hotmart['plataforma'] = 'Hotmart'

df_tmb = pd.read_csv(BASE / 'Vendas' / 'tmb-pbb-abr-26.csv', sep=';', encoding='latin-1')
col_sit = next((c for c in df_tmb.columns if 'situa' in c.lower()), None)
if col_sit:
    df_tmb = df_tmb[df_tmb[col_sit].astype(str).str.strip().str.lower() == 'vigente'].copy()
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor'] = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce').fillna(0)
df_tmb['plataforma'] = 'TMB'

# Unifica compradores
df_vendas = pd.concat([
    df_hotmart[['email', 'valor', 'plataforma']],
    df_tmb[['email', 'valor', 'plataforma']]
], ignore_index=True)

print(f"   Hotmart: {len(df_hotmart):,} vendas | R$ {df_hotmart['valor'].sum():,.2f}")
print(f"   TMB:     {len(df_tmb):,} vendas | R$ {df_tmb['valor'].sum():,.2f}")
print(f"   TOTAL:   {len(df_vendas):,} vendas | R$ {df_vendas['valor'].sum():,.2f}")

# ─────────────────────────────────────────
# 3. ATRIBUIÇÃO: email comprador → ad_code via CRM
# ─────────────────────────────────────────
print("\n[3/5] Cruzando compradores × UTM do CRM...")

# Para cada comprador, pega o ad_code do seu lead no CRM
email_to_ad = (
    df_leads_com_ad.sort_values('ad_code')  # determinístico se múltiplos
    .drop_duplicates('email', keep='last')
    .set_index('email')['ad_code']
)

df_vendas['ad_code'] = df_vendas['email'].map(email_to_ad)
vendas_rastreadas = df_vendas[df_vendas['ad_code'].notna()]
vendas_nao_rastreadas = df_vendas[df_vendas['ad_code'].isna()]

print(f"   Rastreadas (com ad_code): {len(vendas_rastreadas):,} | R$ {vendas_rastreadas['valor'].sum():,.2f}")
print(f"   Não rastreadas:           {len(vendas_nao_rastreadas):,} | R$ {vendas_nao_rastreadas['valor'].sum():,.2f}")

# Agregação por ad_code
vendas_por_ad = vendas_rastreadas.groupby('ad_code').agg(
    vendas=('email', 'count'),
    receita=('valor', 'sum'),
    ticket_medio=('valor', 'mean')
).reset_index()

# Leads por ad_code
leads_por_ad = df_leads_com_ad.groupby('ad_code').agg(
    leads=('email', 'count')
).reset_index()

# ─────────────────────────────────────────
# 4. INVESTIMENTO: Meta Ads + Google Ads por ad_code
# ─────────────────────────────────────────
print("\n[4/5] Carregando investimento por anúncio...")

# Meta Ads
meta = pd.read_csv(BASE / 'Meta Ads' / 'MA-Campanhas-Completas-PBB-ABR-26.csv', encoding='utf-8', low_memory=False)
meta['ad_code'] = meta['Nome do anúncio'].apply(extrair_codigo_ad)
meta['investimento'] = meta['Valor usado (BRL)'].apply(limpar_brl)
meta_por_ad = meta[meta['ad_code'].notna()].groupby('ad_code')['investimento'].sum().reset_index()
meta_por_ad.columns = ['ad_code', 'invest_meta']

# Google Ads
p_gads = BASE / 'Google Ads' / 'Performance dos an\u00FAncios-pbb-abr-26.csv'
gads = pd.read_csv(p_gads, encoding='utf-8', skiprows=2)
gads['ad_code'] = gads['Nome do anúncio'].apply(extrair_codigo_ad)
gads['investimento'] = gads['Custo'].apply(limpar_brl)
gads_por_ad = gads[gads['ad_code'].notna()].groupby('ad_code')['investimento'].sum().reset_index()
gads_por_ad.columns = ['ad_code', 'invest_google']

print(f"   Meta Ads: R$ {meta_por_ad['invest_meta'].sum():,.2f} | {meta_por_ad['ad_code'].nunique()} ads")
print(f"   Google Ads: R$ {gads_por_ad['invest_google'].sum():,.2f} | {gads_por_ad['ad_code'].nunique()} ads")

# ─────────────────────────────────────────
# 5. CONSOLIDAÇÃO FINAL
# ─────────────────────────────────────────
print("\n[5/5] Consolidando ranking...")

# Todos os ad_codes conhecidos
todos_ads = set(df_leads_com_ad['ad_code'].unique()) | set(vendas_por_ad['ad_code'].unique()) | \
            set(meta_por_ad['ad_code'].unique()) | set(gads_por_ad['ad_code'].unique())

df_rank = pd.DataFrame({'ad_code': sorted(todos_ads)})
df_rank = df_rank.merge(leads_por_ad, on='ad_code', how='left')
df_rank = df_rank.merge(vendas_por_ad[['ad_code', 'vendas', 'receita', 'ticket_medio']], on='ad_code', how='left')
df_rank = df_rank.merge(meta_por_ad, on='ad_code', how='left')
df_rank = df_rank.merge(gads_por_ad, on='ad_code', how='left')

df_rank['leads']        = df_rank['leads'].fillna(0).astype(int)
df_rank['vendas']       = df_rank['vendas'].fillna(0).astype(int)
df_rank['receita']      = df_rank['receita'].fillna(0)
df_rank['ticket_medio'] = df_rank['ticket_medio'].fillna(0)
df_rank['invest_meta']  = df_rank['invest_meta'].fillna(0)
df_rank['invest_google']= df_rank['invest_google'].fillna(0)
df_rank['investimento'] = df_rank['invest_meta'] + df_rank['invest_google']

# Métricas derivadas
df_rank['taxa_conv']    = np.where(df_rank['leads'] > 0, df_rank['vendas'] / df_rank['leads'] * 100, 0)
df_rank['roas']         = np.where(df_rank['investimento'] > 0, df_rank['receita'] / df_rank['investimento'], np.nan)
df_rank['cpa']          = np.where(df_rank['vendas'] > 0, df_rank['investimento'] / df_rank['vendas'], np.nan)
df_rank['vpl']          = np.where(df_rank['leads'] > 0, df_rank['receita'] / df_rank['leads'], 0)  # valor por lead

# Só ads com pelo menos 1 venda ou investimento
df_rank = df_rank[(df_rank['vendas'] > 0) | (df_rank['investimento'] > 0)].copy()
df_rank = df_rank.sort_values(['receita', 'vendas'], ascending=False).reset_index(drop=True)

# ─────────────────────────────────────────
# OUTPUT PRINCIPAL: Ranking por receita atribuída
# ─────────────────────────────────────────
print()
print("=" * 80)
print("📊 RANKING COMPLETO — PBB-ABR-26 (por receita atribuída)")
print("=" * 80)
print(f"\n{'#':>3} {'Ad':>6} {'Leads':>7} {'Vendas':>7} {'Conv%':>6} {'Receita':>14} {'Ticket':>10} {'Invest.':>12} {'ROAS':>6} {'CPA':>10}")
print("-" * 95)

for i, row in df_rank.iterrows():
    roas_str = f"{row['roas']:.2f}x" if not np.isnan(row['roas']) else "  n/a"
    cpa_str  = f"R${row['cpa']:,.0f}" if not np.isnan(row['cpa']) else "   n/a"
    invest_str = f"R${row['investimento']:>9,.2f}" if row['investimento'] > 0 else "         -"
    print(f"{i+1:>3} {row['ad_code']:>6}  {row['leads']:>6,}  {row['vendas']:>6,}  {row['taxa_conv']:>5.2f}%  R${row['receita']:>11,.2f}  R${row['ticket_medio']:>7,.0f}  {invest_str}  {roas_str:>6}  {cpa_str:>10}")

print("-" * 95)
total_invest = df_rank['investimento'].sum()
total_rec = df_rank['receita'].sum()
total_v = df_rank['vendas'].sum()
total_l = df_rank['leads'].sum()
roas_geral = total_rec / total_invest if total_invest > 0 else 0
print(f"{'TOTAL':>10}  {total_l:>6,}  {total_v:>6,}  {total_v/total_l*100:>5.2f}%  R${total_rec:>11,.2f}  {'':>10}  R${total_invest:>9,.2f}  {roas_geral:.2f}x")

# ─────────────────────────────────────────
# OUTPUT 2: Top 10 por ROAS (só ads com investimento)
# ─────────────────────────────────────────
df_com_invest = df_rank[(df_rank['investimento'] > 0) & (df_rank['vendas'] > 0)].copy()
df_top_roas = df_com_invest.sort_values('roas', ascending=False).head(10)

print()
print("=" * 80)
print("🏆 TOP 10 POR ROAS")
print("=" * 80)
print(f"\n{'#':>3} {'Ad':>6} {'Vendas':>7} {'Receita':>14} {'Investimento':>13} {'ROAS':>7} {'CPA':>10} {'Conv%':>7}")
print("-" * 75)
for i, (_, row) in enumerate(df_top_roas.iterrows(), 1):
    roas_str = f"{row['roas']:.2f}x"
    cpa_str  = f"R${row['cpa']:,.0f}"
    print(f"{i:>3} {row['ad_code']:>6}  {row['vendas']:>6,}  R${row['receita']:>11,.2f}  R${row['investimento']:>10,.2f}  {roas_str:>7}  {cpa_str:>10}  {row['taxa_conv']:>6.2f}%")

# ─────────────────────────────────────────
# OUTPUT 3: Ads com vendas MAS sem investimento rastreado
# ─────────────────────────────────────────
df_sem_invest = df_rank[(df_rank['investimento'] == 0) & (df_rank['vendas'] > 0)].copy()
if len(df_sem_invest) > 0:
    print()
    print("=" * 80)
    print("⚠️  ADS COM VENDAS SEM INVESTIMENTO RASTREADO (orgânico/direto?)")
    print("=" * 80)
    print(f"\n{'Ad':>6} {'Leads':>7} {'Vendas':>7} {'Receita':>14} {'Conv%':>7}")
    print("-" * 50)
    for _, row in df_sem_invest.iterrows():
        print(f"{row['ad_code']:>6}  {row['leads']:>6,}  {row['vendas']:>6,}  R${row['receita']:>11,.2f}  {row['taxa_conv']:>6.2f}%")

# ─────────────────────────────────────────
# OUTPUT 4: Ads com investimento MAS sem vendas atribuídas
# ─────────────────────────────────────────
df_sem_venda = df_rank[(df_rank['investimento'] > 0) & (df_rank['vendas'] == 0)].sort_values('investimento', ascending=False)
if len(df_sem_venda) > 0:
    print()
    print("=" * 80)
    print("💸 ADS COM INVESTIMENTO MAS SEM VENDAS ATRIBUÍDAS")
    print("=" * 80)
    print(f"\n{'Ad':>6} {'Leads':>7} {'Investimento':>13}")
    print("-" * 35)
    for _, row in df_sem_venda.iterrows():
        print(f"{row['ad_code']:>6}  {row['leads']:>6,}  R${row['investimento']:>10,.2f}")

# ─────────────────────────────────────────
# SUMÁRIO GERAL
# ─────────────────────────────────────────
print()
print("=" * 80)
print("📋 SUMÁRIO")
print("=" * 80)
print(f"   Total ads analisados:       {len(df_rank)}")
print(f"   Ads com vendas:             {(df_rank['vendas']>0).sum()}")
print(f"   Ads com investimento:       {(df_rank['investimento']>0).sum()}")
print(f"   Ads com vendas + invest:    {((df_rank['vendas']>0) & (df_rank['investimento']>0)).sum()}")
print()
print(f"   Receita total atribuída:    R$ {total_rec:,.2f}")
print(f"   Receita não atribuída:      R$ {vendas_nao_rastreadas['valor'].sum():,.2f}")
print(f"   Receita TOTAL lançamento:   R$ {df_vendas['valor'].sum():,.2f}")
print()
print(f"   Investimento total:         R$ {total_invest:,.2f}")
print(f"   ROAS geral (rastreado):     {roas_geral:.2f}x")
print(f"   CPA médio (rastreado):      R$ {total_invest/total_v:,.0f}" if total_v > 0 else "")
print()
print("✅ CONCLUÍDO")
