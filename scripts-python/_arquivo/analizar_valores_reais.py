#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisar valores reais de Hotmart
"""

import pandas as pd

print("\n" + "="*100)
print("📊 ANÁLISE DE VALORES HOTMART")
print("="*100)

df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')

# Pegar primeiras 20 linhas com colunas importantes
cols_importantes = [
    'Email do(a) Comprador(a)', 
    'Valor de compra sem impostos',
    'Faturamento líquido',
    'Quantidade total de parcelas',
    'Data da transação',
    'Produto'
]

print("\nPrimeiras 20 transações:")
print(df_hotmart[cols_importantes].head(20).to_string())

# Verificar estatísticas
print(f"\n\n💰 ESTATÍSTICAS DE VALORES:")

# Converter para número
valor_col = df_hotmart['Valor de compra sem impostos'].astype(str).str.replace('.', '').str.replace(',', '.')
df_hotmart['valor_num'] = pd.to_numeric(valor_col, errors='coerce')

print(f"  Valor mínimo: R$ {df_hotmart['valor_num'].min():,.2f}")
print(f"  Valor máximo: R$ {df_hotmart['valor_num'].max():,.2f}")
print(f"  Valor médio: R$ {df_hotmart['valor_num'].mean():,.2f}")
print(f"  Valor total: R$ {df_hotmart['valor_num'].sum():,.2f}")

# Por produto
print(f"\n\nPor produto:")
por_produto = df_hotmart.groupby('Produto')['valor_num'].agg(['count', 'sum', 'mean'])
print(por_produto.to_string())

# Distribuição de valores
print(f"\n\nDistribuição de valores:")
print(f"  Valores entre 1.000-2.000: {len(df_hotmart[(df_hotmart['valor_num'] >= 1000) & (df_hotmart['valor_num'] < 2000)])}")
print(f"  Valores entre 2.000-5.000: {len(df_hotmart[(df_hotmart['valor_num'] >= 2000) & (df_hotmart['valor_num'] < 5000)])}")
print(f"  Valores maiores que 5.000: {len(df_hotmart[df_hotmart['valor_num'] >= 5000])}")

# Data
print(f"\n\nData das transações:")
print(f"  Período: {df_hotmart['Data da transação'].min()} a {df_hotmart['Data da transação'].max()}")

# Filtrar apenas fevereiro
df_fev = df_hotmart[df_hotmart['Data da transação'].str.contains('02/2026|2026-02', na=False)]
print(f"  Transações em fevereiro: {len(df_fev)}")
if len(df_fev) > 0:
    fev_total = df_fev['valor_num'].sum()
    print(f"  Valor total em fevereiro: R$ {fev_total:,.2f}")
