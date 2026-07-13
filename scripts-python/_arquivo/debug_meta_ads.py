#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd

df = pd.read_csv(r'analises/[PBB-ABR-26]/Meta Ads/pbb-abr-26-meta-ads.csv', sep=',', encoding='utf-8')

print("Colunas do CSV:")
print(df.columns.tolist())

print("\n\nPrimeiras 20 linhas da coluna 'Valor usado (BRL)':")
print(df[['Nome do anúncio', 'Valor usado (BRL)']].head(20))

print(f"\n\nTipo de dado: {df['Valor usado (BRL)'].dtype}")
print(f"\nValores únicos (primeiros 30):")
print(df['Valor usado (BRL)'].unique()[:30])

print(f"\n\nValores não vazios:")
valores_nao_vazios = df[df['Valor usado (BRL)'].notna() & (df['Valor usado (BRL)'] != '')]
print(f"Total de linhas com valor: {len(valores_nao_vazios)}")
if len(valores_nao_vazios) > 0:
    print("\nPrimeiras 10 linhas com valor:")
    print(valores_nao_vazios[['Nome do anúncio', 'Valor usado (BRL)', 'Leads']].head(10))
