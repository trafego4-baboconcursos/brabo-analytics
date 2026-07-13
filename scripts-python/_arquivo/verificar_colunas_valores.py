#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd

df_h = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
print('Colunas de valores Hotmart:')
colunas_valor = [c for c in df_h.columns if 'valor' in c.lower() or 'faturamento' in c.lower() or 'bruto' in c.lower()]
print('\n'.join(f'  - {c}' for c in colunas_valor))

print(f'\n\nPrimeira venda (exemplo):')
print(f"  Faturamento bruto (sem impostos): R$ {df_h.iloc[0]['Faturamento bruto (sem impostos)']}")
print(f"  Valor de compra sem impostos: R$ {df_h.iloc[0]['Valor de compra sem impostos']}")
print(f"  Faturamento líquido: R$ {df_h.iloc[0]['Faturamento líquido']}")
print(f"  Valor de compra com impostos: R$ {df_h.iloc[0]['Valor de compra com impostos']}")

# Calcular soma com diferentes colunas
valor_bruto_sem_impostos = pd.to_numeric(df_h['Faturamento bruto (sem impostos)'], errors='coerce').sum()
valor_compra_sem_impostos = pd.to_numeric(df_h['Valor de compra sem impostos'], errors='coerce').sum()
valor_liquido = pd.to_numeric(df_h['Faturamento líquido'], errors='coerce').sum()
valor_compra_com_impostos = pd.to_numeric(df_h['Valor de compra com impostos'], errors='coerce').sum()

print(f'\n\nTOTAIS Hotmart (388 vendas):')
print(f"  Faturamento bruto (sem impostos): R$ {valor_bruto_sem_impostos:,.2f}")
print(f"  Valor de compra sem impostos: R$ {valor_compra_sem_impostos:,.2f}")
print(f"  Valor de compra com impostos: R$ {valor_compra_com_impostos:,.2f}")
print(f"  Faturamento líquido: R$ {valor_liquido:,.2f}")
