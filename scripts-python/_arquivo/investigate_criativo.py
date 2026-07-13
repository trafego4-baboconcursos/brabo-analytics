#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de ROAS por Criativo
Cruzar: Leads > Criativo > Vendas > Investimento
"""

import pandas as pd
import numpy as np

print("\n" + "="*100)
print("📊 INVESTIGAÇÃO - DADOS PARA ANÁLISE POR CRIATIVO")
print("="*100)

# Leads
df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')
print(f"\n✓ Leads: {len(df_leads)} registros")
print(f"  Colunas disponíveis:")
for col in df_leads.columns[:20]:
    print(f"    - {col}")

# Verificar colunas que identificam criativo
utm_cols = [col for col in df_leads.columns if 'utm' in col.lower()]
print(f"\n  Colunas UTM: {utm_cols}")

# Amostra
print(f"\n  Amostra de um lead:")
print(df_leads[utm_cols].iloc[0].to_string())

# Google Ads
print(f"\n\n✓ Google Ads:")
try:
    df_ga = pd.read_csv(r'analises/[PBB-FEV-26]/google ads/pbb-fev-26-google-ads-gclid-campaigns.csv', encoding='utf-8', skiprows=2)
    print(f"  Registros: {len(df_ga)}")
    print(f"  Colunas principais: {list(df_ga.columns[:10])}")
    if 'Cliques' in df_ga.columns:
        print(f"  Cliques totais: {df_ga['Cliques'].sum()}")
    if 'Custo' in df_ga.columns:
        print(f"  Custo total: {df_ga['Custo'].sum()}")
except Exception as e:
    print(f"  Erro: {e}")

# Meta Ads
print(f"\n\n✓ Meta Ads:")
try:
    df_meta = pd.read_csv(r'analises/[PBB-FEV-26]/meta ads/pbb-fev-26-meta-ads.csv', encoding='utf-8', skiprows=2)
    print(f"  Registros: {len(df_meta)}")
    print(f"  Colunas principais: {list(df_meta.columns[:10])}")
except Exception as e:
    print(f"  Erro: {e}")

# Vendas
print(f"\n\n✓ Vendas (Hotmart + TMB):")
df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', sep=';')
print(f"  Hotmart: {len(df_hotmart)}")
print(f"  TMB: {len(df_tmb)}")

print(f"\n" + "="*100 + "\n")
