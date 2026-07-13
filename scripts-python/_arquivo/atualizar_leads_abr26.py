#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script completo para regenerar todas as análises com dados do novo arquivo de leads
PBB-ABR-26 - Atualização 12/05/2026 14h
"""

import pandas as pd
import glob
from datetime import datetime
from pathlib import Path

# ===== CARREGAMENTO DE DADOS =====

# Novo arquivo de leads
novo_leads_path = r'analises/[PBB-ABR-26]/Active Campaign/PBB-ABR-14h-12-05-26.csv'
df_all_leads = pd.read_csv(novo_leads_path, sep=',', encoding='utf-8', low_memory=False)

# Filtrar apenas PBB-ABR-26
df_leads = df_all_leads[df_all_leads['*Utm_campaign'] == 'pbb-abr-26'].copy()
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()

print(f"✓ Total de leads no arquivo: {len(df_all_leads)}")
print(f"✓ Leads PBB-ABR-26: {len(df_leads)}")

# Vendas
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Status'] == 'Efetivado'] if 'Status' in df_tmb.columns else df_tmb

# Normalizar emails de vendas
if 'email' in df_hotmart.columns:
    df_hotmart['email'] = df_hotmart['email'].str.strip().str.lower()
if 'email' in df_tmb.columns:
    df_tmb['email'] = df_tmb['email'].str.strip().str.lower()

print(f"✓ Hotmart vendas: {len(df_hotmart)}")
print(f"✓ TMB vendas: {len(df_tmb)}")
print(f"✓ Total vendas: {len(df_hotmart) + len(df_tmb)}")

# ===== ANÁLISE POR FONTE E CRIATIVO =====

print(f"\n=== ANÁLISE DE DADOS ===\n")

# Por fonte
leads_source = df_leads['*Utm_source'].value_counts()
print("LEADS POR FONTE:")
for source, count in leads_source.items():
    pct = (count/len(df_leads))*100
    print(f"  {source}: {count:,} ({pct:.1f}%)")

# Por criativo (utm_content)
leads_criativo = df_leads['*Utm_content'].value_counts()
print(f"\nTOP 15 CRIATIVOS:")
for i, (criativo, count) in enumerate(leads_criativo.head(15).items(), 1):
    pct = (count/len(df_leads))*100
    print(f"  {i:2d}. {criativo}: {count:,} leads ({pct:.1f}%)")

# ===== ATUALIZAR ARQUIVO DE LEADS PADRÃO =====

print(f"\n✓ Atualizando arquivo de leads padrão...")
output_crm_path = Path(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv')
df_leads.to_csv(output_crm_path, index=False, encoding='utf-8', sep=',')
print(f"  Arquivo atualizado: {output_crm_path}")

# ===== ATUALIZAR METADADOS =====

print(f"\n✓ Resumo de dados:")
print(f"  Total leads: {len(df_leads):,}")
print(f"  Total vendas: {len(df_hotmart) + len(df_tmb):,}")
print(f"  Taxa conversão: {((len(df_hotmart) + len(df_tmb))/len(df_leads)*100):.2f}%")
print(f"  Leads por fonte: FB={leads_source.get('fb', 0):,}, YT={leads_source.get('yt', 0):,}")

print(f"\n✓ Dados prontos para regenerar análises!")
print(f"  Próximo passo: execute os scripts de análise")
