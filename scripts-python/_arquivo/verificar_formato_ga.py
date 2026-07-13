#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar formato de valores do Google Ads
"""

import pandas as pd
import glob

xlsx_files = glob.glob(r'*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0]

df_ga = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA')

print("Verificando coluna Cost (Spend):")
print(f"  Tipo: {df_ga['Cost (Spend)'].dtype}")
print(f"  Min: {df_ga['Cost (Spend)'].min()}")
print(f"  Max: {df_ga['Cost (Spend)'].max()}")
print(f"  Media: {df_ga['Cost (Spend)'].mean():.2f}")
print(f"  Total: {df_ga['Cost (Spend)'].sum():.2f}")

print("\nPrimeiras 15 valores:")
for i, val in enumerate(df_ga['Cost (Spend)'].head(15).tolist(), 1):
    print(f"  {i:2d}. {val}")

print("\nDividindo por 100 (se em centavos):")
print(f"  Total /100: {df_ga['Cost (Spend)'].sum() / 100:.2f}")

print("\nDividindo por 1000:")
print(f"  Total /1000: {df_ga['Cost (Spend)'].sum() / 1000:.2f}")
