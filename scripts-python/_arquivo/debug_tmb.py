#!/usr/bin/env python3
import pandas as pd

print("=" * 80)

df_t = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
print('Colunas com Status/Situação:', [c for c in df_t.columns if ('itua' in c.lower() or 'tatus' in c.lower())])
print('Total de linhas:', len(df_t))

sit_cols = [c for c in df_t.columns if 'itua' in c.lower() or 'Situa' in c]
if sit_cols:
    print(f'\nFiltrando por coluna: "{sit_cols[0]}"')
    print(f'Valores únicos nesta coluna: {df_t[sit_cols[0]].unique().tolist()}')
    
    filtered = df_t[df_t[sit_cols[0]] == 'Efetivado']
    print(f'Linhas após filtro: {len(filtered)}')

# Converter TMB sem filtro
df_t['valor'] = pd.to_numeric(df_t['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
print(f'\nTotal TMB (SEM FILTRO): {df_t["valor"].sum():,.2f}')

# Com filtro
if sit_cols:
    filtered = df_t[df_t[sit_cols[0]] == 'Efetivado']
    print(f'Total TMB (COM FILTRO Efetivado): {filtered["valor"].sum():,.2f}')
