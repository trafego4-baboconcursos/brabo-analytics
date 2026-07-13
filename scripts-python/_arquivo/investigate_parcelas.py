#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigar estrutura de parcelas nos dados de vendas
"""

import pandas as pd
import numpy as np

print("\n" + "="*100)
print("📊 INVESTIGAÇÃO DE PARCELAS")
print("="*100)

# Hotmart
print("\n📥 HOTMART - Análise de Parcelas")
print("-" * 100)

df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
print(f"Total de registros: {len(df_hotmart)}")

# Ver colunas relacionadas a parcelamento
parcel_cols = [col for col in df_hotmart.columns if 'parcel' in col.lower() or 'cobr' in col.lower()]
print(f"\nColunas de parcelamento:")
for col in parcel_cols:
    print(f"  - {col}")

# Verificar se há coluna de parcela
print(f"\nColunas principais:")
for i, col in enumerate(df_hotmart.columns[:15]):
    print(f"  {i+1}. {col}")

# Converter valor
valor_col = df_hotmart['Valor de compra sem impostos']
valor_col_str = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
df_hotmart['valor_numerico'] = pd.to_numeric(valor_col_str, errors='coerce')

# Verificar parcelas
parcel_col = 'Quantidade total de parcelas'
cobr_col = 'Quantidade de cobranças'

print(f"\n\nAnálise de parcelas:")
print(f"  {parcel_col}:")
print(df_hotmart[parcel_col].value_counts().head(10))

print(f"\n  {cobr_col}:")
print(df_hotmart[cobr_col].value_counts().head(10))

# Amostra de dados
print(f"\n\nAmostra de 5 transações:")
print(df_hotmart[['Email do(a) Comprador(a)', 'Valor de compra sem impostos', 'Quantidade total de parcelas', 'Quantidade de cobranças', 'Status da transação']].head(5))

# Calcular valor total SEM dividir por parcelas (cada linha é uma cobrança, não uma venda)
print(f"\n\n💰 CÁLCULO DE VALOR:")
valor_total_raw = df_hotmart['valor_numerico'].sum()
print(f"  Soma BRUTA (cada registro): R$ {valor_total_raw:,.2f}")

# Tentar identificar se é preciso agrupar por cliente/email
emails_unicos = df_hotmart['Email do(a) Comprador(a)'].nunique()
print(f"  Emails únicos: {emails_unicos}")
print(f"  Registros: {len(df_hotmart)}")
print(f"  Proporção: {len(df_hotmart) / emails_unicos:.2f} registros por email")

# Agrupar por email para ver quantas parcelas por cliente
print(f"\n\nDistribuição de registros por cliente:")
por_email = df_hotmart.groupby('Email do(a) Comprador(a)').size()
print(por_email.value_counts().head(10))

# TMB
print(f"\n\n📥 TMB - Análise de Parcelas")
print("-" * 100)

df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', sep=';')
print(f"Total de registros: {len(df_tmb)}")

# Filtrar status
df_tmb_efetvizado = df_tmb[df_tmb['Status'] == 'Efetivado']
print(f"Efetivado: {len(df_tmb_efetvizado)}")

# Converter valor
df_tmb['valor_numerico'] = pd.to_numeric(df_tmb['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')

# Converter valor corretamente
df_tmb_efetvizado['valor_numerico'] = pd.to_numeric(df_tmb_efetvizado['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')
valor_total_tmb = df_tmb_efetvizado['valor_numerico'].sum()
print(f"  Valor total: R$ {valor_total_tmb:,.2f}")

# Verificar emails únicos
emails_tmb = df_tmb_efetvizado['Cliente Email'].nunique()
print(f"  Emails únicos: {emails_tmb}")
print(f"  Registros Efetivado: {len(df_tmb_efetvizado)}")

print(f"\n" + "="*100 + "\n")
