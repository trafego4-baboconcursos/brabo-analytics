#!/usr/bin/env python3
import pandas as pd

df_h = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_h['valor'] = pd.to_numeric(df_h['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')

print('HOTMART:')
print(f'  Total: {df_h["valor"].sum():,.2f}')
print(f'  Máximo: {df_h["valor"].max():,.2f}')
print(f'  Mínimo: {df_h["valor"].min():,.2f}')
print(f'  Média: {df_h["valor"].mean():,.2f}')

df_t = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
# Encontrar coluna com 'itua' (Situação com encoding)
sit_cols = [c for c in df_t.columns if 'itua' in c.lower() or 'Situa' in c]
if sit_cols:
    df_t = df_t[df_t[sit_cols[0]] == 'Efetivado']
df_t['valor'] = pd.to_numeric(df_t['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')

print('\nTMB:')
print(f'  Total: {df_t["valor"].sum():,.2f}')
print(f'  Máximo: {df_t["valor"].max():,.2f}')
print(f'  Mínimo: {df_t["valor"].min():,.2f}')
print(f'  Média: {df_t["valor"].mean():,.2f}')

print(f'\nTOTAL GERAL: {df_h["valor"].sum() + df_t["valor"].sum():,.2f}')
