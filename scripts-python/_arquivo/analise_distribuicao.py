#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisar distribuição de valores
"""

import pandas as pd

print("\n" + "="*100)
print("📊 DISTRIBUIÇÃO DE VALORES")
print("="*100)

df = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')

# Os valores já são float (confirmado)
valores = df['Valor de compra sem impostos']

print(f"\n📋 Valores ÚNICOS:")
unicos = valores.unique()
print(f"Total de valores únicos: {len(unicos)}")
print(f"\nOs 10 primeiros valores únicos:")
for i, val in enumerate(sorted(unicos)[:10]):
    count = (valores == val).sum()
    print(f"  {val}: aparece {count}x")

print(f"\nOs 10 últimos (maiores) valores únicos:")
for val in sorted(unicos)[-10:]:
    count = (valores == val).sum()
    print(f"  {val}: aparece {count}x")

# Verificar se há erro na leitura do CSV
print(f"\n\n🔍 Amostra de valores maiores:")
maiores = df.nlargest(10, 'Valor de compra sem impostos')[['Email do(a) Comprador(a)', 'Valor de compra sem impostos', 'Produto']]
print(maiores.to_string())

# Verificar se a formatação está sendo lida corretamente
print(f"\n\n💾 Revisar estrutura do CSV:")
print(f"Primeira linha bruta do CSV (primeiras 5 colunas):")
with open(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i < 2:
            # Mostrar primeiras 200 caracteres
            print(f"  Linha {i}: {line[:200]}...")
        else:
            break

print("\n" + "="*100 + "\n")
