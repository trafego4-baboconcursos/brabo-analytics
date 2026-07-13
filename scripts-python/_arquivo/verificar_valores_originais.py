#!/usr/bin/env python3
import pandas as pd

df_h = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
print('HOTMART - VALORES ORIGINAIS (como estão no CSV):')
print(df_h[['Email do(a) Comprador(a)', 'Faturamento bruto (sem impostos)']].head(10))
print(f'\nTipo de dado: {df_h["Faturamento bruto (sem impostos)"].dtype}')
print(f'Valor total SEM conversão: {df_h["Faturamento bruto (sem impostos)"].sum()}')

# Tentar diferentes conversões
print('\n\nTENTATIVA 1: Sem conversão (assumindo já está em float):')
print(f'Total: {df_h["Faturamento bruto (sem impostos)"].sum()}')

print('\n\nTENTATIVA 2: Dividir por 100 (se estão em centavos):')
print(f'Total: {df_h["Faturamento bruto (sem impostos)"].sum() / 100}')

print('\n\nTENTATIVA 3: Dividir por 1000:')
print(f'Total: {df_h["Faturamento bruto (sem impostos)"].sum() / 1000}')

print('\n\nTENTATIVA 4: Dividir por 10000:')
print(f'Total: {df_h["Faturamento bruto (sem impostos)"].sum() / 10000}')

df_t = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
print('\n\nTMB - VALORES ORIGINAIS:')
print(df_t[['E-mail do Cliente', 'Ticket do pedido']].head(10))
print(f'\nTipo de dado: {df_t["Ticket do pedido"].dtype}')
print(f'Valor total SEM conversão: {df_t["Ticket do pedido"].sum()}')

print('\n\nTMB - TENTATIVA 2: Dividir por 100:')
print(f'Total: {df_t["Ticket do pedido"].sum() / 100}')

print('\n\nTMB - TENTATIVA 3: Dividir por 1000:')
print(f'Total: {df_t["Ticket do pedido"].sum() / 1000}')
