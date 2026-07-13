#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigar estrutura dos dados de vendas
"""

import pandas as pd
import numpy as np

print("\n" + "="*80)
print("INVESTIGANDO ESTRUTURA DE DADOS DE VENDAS")
print("="*80)

# Hotmart
print("\n📊 HOTMART")
print("-" * 80)
try:
    df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Linhas: {len(df_hotmart)}")
    print(f"✓ Colunas: {len(df_hotmart.columns)}")
    print(f"\nPrimeiras 10 colunas:")
    for i, col in enumerate(df_hotmart.columns[:10]):
        print(f"  {i+1}. {col}")
    
    print(f"\nColunas com 'Email':")
    email_cols = [col for col in df_hotmart.columns if 'email' in col.lower()]
    for col in email_cols:
        print(f"  - {col}")
    
    print(f"\nColunas com 'Valor', 'Preço' ou 'Faturamento':")
    valor_cols = [col for col in df_hotmart.columns if any(x in col.lower() for x in ['valor', 'preço', 'faturamento'])]
    for col in valor_cols:
        print(f"  - {col}")
    
    print(f"\nColunas com 'Canal', 'Afiliado' ou 'SRC':")
    canal_cols = [col for col in df_hotmart.columns if any(x in col.lower() for x in ['canal', 'afiliado', 'src', 'sck'])]
    for col in canal_cols:
        print(f"  - {col}")
        
except Exception as e:
    print(f"✗ Erro: {e}")

# TMB
print("\n📊 TMB")
print("-" * 80)
try:
    df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8')
    print(f"✓ Linhas: {len(df_tmb)}")
    print(f"✓ Colunas: {len(df_tmb.columns)}")
    print(f"\nTodas as colunas:")
    for i, col in enumerate(df_tmb.columns):
        print(f"  {i+1}. {col}")
except Exception as e:
    print(f"✗ Erro TMB: {e}")
    
    # Tentar ler com skip
    try:
        df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', skiprows=2)
        print(f"\n✓ Lido com skiprows=2")
        print(f"  Linhas: {len(df_tmb)}")
        print(f"  Colunas: {len(df_tmb.columns)}")
        print(f"  Primeiras colunas: {list(df_tmb.columns[:5])}")
    except Exception as e2:
        print(f"✗ Erro com skiprows: {e2}")

print("\n" + "="*80)
