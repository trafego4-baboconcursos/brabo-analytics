#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar leitura exata dos valores
"""

import pandas as pd
import numpy as np

print("\n" + "="*100)
print("🔍 VERIFICAÇÃO EXATA DE LEITURA")
print("="*100)

# Método 1: Leitura padrão
df1 = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
soma1 = df1['Valor de compra sem impostos'].sum()

print(f"\n✓ Método 1 (leitura padrão):")
print(f"  Soma: {soma1}")
print(f"  Tipo: {type(soma1).__name__}")
print(f"  Primeiros 5 valores: {df1['Valor de compra sem impostos'].head().tolist()}")

# Método 2: Decimal
df2 = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';', decimal=',')
soma2 = df2['Valor de compra sem impostos'].sum()

print(f"\n✓ Método 2 (decimal=','):")
print(f"  Soma: {soma2}")
print(f"  Primeiros 5 valores: {df2['Valor de compra sem impostos'].head().tolist()}")

# Método 3: Forçar string e converter
df3 = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';', dtype={'Valor de compra sem impostos': str})
print(f"\n✓ Método 3 (força string):")
print(f"  Primeiros 5 valores como string: {df3['Valor de compra sem impostos'].head().tolist()}")

# Converter e somar
valores_str = df3['Valor de compra sem impostos'].astype(str).str.strip()
print(f"  Após strip: {valores_str.head().tolist()}")

# Tentar diferentes conversões
soma3a = pd.to_numeric(valores_str, errors='coerce').sum()
print(f"  Conversão direta: {soma3a}")

soma3b = pd.to_numeric(valores_str.str.replace('.', '').str.replace(',', '.'), errors='coerce').sum()
print(f"  Removendo ponto e convertendo vírgula: {soma3b}")

print(f"\n\n📊 COMPARAÇÃO:")
print(f"  Soma Método 1: R$ {soma1:,.2f}")
print(f"  Soma Método 2: R$ {soma2:,.2f}")
print(f"  Soma 3a: R$ {soma3a:,.2f}")
print(f"  Soma 3b: R$ {soma3b:,.2f}")

# Verificar se há NaN
print(f"\n\n❓ Verificar NaN:")
print(f"  Valores NaN em df1: {df1['Valor de compra sem impostos'].isna().sum()}")
print(f"  Valores infinitos: {np.isinf(df1['Valor de compra sem impostos']).sum()}")

# Calcular manualmente com os primeiros 50
print(f"\n\n📝 Soma manual dos primeiros 50:")
primeiros_50 = df1['Valor de compra sem impostos'].head(50).sum()
print(f"  Primeiros 50: R$ {primeiros_50:,.2f}")

# Média × quantidade
print(f"\n\n🧮 Verificação com média:")
media = df1['Valor de compra sem impostos'].mean()
total = len(df1)
print(f"  Média: R$ {media:,.2f}")
print(f"  Total de registros: {total}")
print(f"  Média × Total: R$ {media * total:,.2f}")

print("\n" + "="*100 + "\n")
