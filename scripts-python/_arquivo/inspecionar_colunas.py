#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

print("=" * 100)
print("INSPEÇÃO DE COLUNAS - Hotmart e TMB")
print("=" * 100)

# Hotmart
print("\n1. HOTMART - Colunas disponíveis:")
print("-" * 100)
try:
    df = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8', quoting=1, low_memory=False, nrows=0)
    for i, col in enumerate(df.columns):
        print(f"{i:2d}. {col}")
except Exception as e:
    print(f"Erro: {e}")

# TMB
print("\n2. TMB - Colunas disponíveis:")
print("-" * 100)
try:
    df = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8', quoting=1, low_memory=False, nrows=0)
    for i, col in enumerate(df.columns):
        print(f"{i:2d}. {col}")
except Exception as e:
    print(f"Erro: {e}")

print("\n" + "=" * 100)
