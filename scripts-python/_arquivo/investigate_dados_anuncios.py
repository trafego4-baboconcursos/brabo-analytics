#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigar dados de Meta Ads para obter investimento por criativo
"""

import pandas as pd

print("\n" + "="*100)
print("📊 INVESTIGAÇÃO - META ADS DATA")
print("="*100)

try:
    df_meta = pd.read_csv(r'analises/[PBB-FEV-26]/meta ads/ma-campanhas-pbb-fev-26.csv', encoding='utf-8')
    print(f"\n✓ Meta Ads - Campanhas: {len(df_meta)} registros")
    print(f"\nColunas:")
    for i, col in enumerate(df_meta.columns):
        print(f"  {i+1}. {col}")
    
    print(f"\nPrimeiras 5 linhas (primeiras 5 colunas):")
    print(df_meta.iloc[:5, :5].to_string())
    
except Exception as e:
    print(f"✗ Erro: {e}")

# Tentar ler Google Ads
print(f"\n\n" + "="*100)
print("📊 INVESTIGAÇÃO - GOOGLE ADS DATA")
print("="*100)

try:
    # Tentar diferentes nomes de arquivo
    import os
    google_ads_path = r'analises/[PBB-FEV-26]/google ads/'
    files = os.listdir(google_ads_path)
    print(f"\nArquivos em google ads/:")
    for f in files:
        print(f"  - {f}")
    
    # Ler o primeiro que encontrar
    for f in files:
        if f.endswith('.csv'):
            filepath = os.path.join(google_ads_path, f)
            try:
                df_ga = pd.read_csv(filepath, encoding='utf-8', skiprows=2)
                print(f"\n✓ Lido: {f}")
                print(f"  Registros: {len(df_ga)}")
                print(f"  Colunas principais: {list(df_ga.columns[:10])}")
                break
            except:
                continue
except Exception as e:
    print(f"✗ Erro: {e}")

print(f"\n" + "="*100 + "\n")
