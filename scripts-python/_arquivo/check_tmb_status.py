#!/usr/bin/env python3
import pandas as pd

df_t = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
sit_cols = [c for c in df_t.columns if 'itua' in c.lower()]

print('Status disponíveis no TMB:')
print(df_t[sit_cols[0]].value_counts())

print('\nValores por status:')
for status in df_t[sit_cols[0]].unique():
    filtered = df_t[df_t[sit_cols[0]] == status]
    filtered['valor'] = pd.to_numeric(filtered['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
    print(f'{status}: {len(filtered)} vendas = R$ {filtered["valor"].sum():,.2f}')

print('\nTodos os registros (sem filtro):')
df_t['valor'] = pd.to_numeric(df_t['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
print(f'Total: {len(df_t)} vendas = R$ {df_t["valor"].sum():,.2f}')
