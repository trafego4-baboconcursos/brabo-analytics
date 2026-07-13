#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VALIDAÇÃO TOTAL DOS DADOS BRUTOS - SEM CONVERSÕES
"""

import pandas as pd

print("=" * 100)
print("🔍 VALIDAÇÃO DOS DADOS BRUTOS - PBB-ABR-26")
print("=" * 100)

# ========== HOTMART ==========
print("\n📦 HOTMART:")
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
print(f"Total de linhas: {len(df_hotmart)}")
print(f"\nColunas disponíveis:")
print(df_hotmart.columns.tolist())

print(f"\n🔢 Primeiros 10 valores da coluna 'Faturamento bruto (sem impostos)':")
for i, val in enumerate(df_hotmart['Faturamento bruto (sem impostos)'].head(10)):
    print(f"   {i+1}. {repr(val)} (tipo: {type(val).__name__})")

# Testar conversão direta
df_hotmart['valor_convertido'] = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce')
soma_hotmart = df_hotmart['valor_convertido'].sum()
print(f"\n💰 SOMA TOTAL HOTMART: R$ {soma_hotmart:,.2f}")
print(f"   Média por venda: R$ {soma_hotmart/len(df_hotmart):,.2f}")
print(f"   Valores nulos: {df_hotmart['valor_convertido'].isna().sum()}")

# ========== TMB ==========
print("\n" + "=" * 100)
print("📦 TMB:")
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
print(f"Total de linhas: {len(df_tmb)}")

print(f"\nColunas disponíveis:")
print(df_tmb.columns.tolist())

col_situacao = [c for c in df_tmb.columns if 'Situa' in c][0] if any('Situa' in c for c in df_tmb.columns) else None
if col_situacao:
    print(f"\n📊 Situações (coluna: {repr(col_situacao)}):")
    print(df_tmb[col_situacao].value_counts())
    df_tmb_efetivado = df_tmb[df_tmb[col_situacao] == 'Vigente']
    print(f"\n✅ Apenas 'Vigente': {len(df_tmb_efetivado)} vendas")
else:
    df_tmb_efetivado = df_tmb
    print("⚠️ Coluna 'Situação' não encontrada, usando todas as linhas")

print(f"\n🔢 Primeiros 10 valores da coluna 'Ticket do pedido':")
for i, val in enumerate(df_tmb['Ticket do pedido'].head(10)):
    print(f"   {i+1}. {repr(val)} (tipo: {type(val).__name__})")

# Testar conversão direta
df_tmb_efetivado['valor_convertido'] = pd.to_numeric(df_tmb_efetivado['Ticket do pedido'], errors='coerce')
soma_tmb = df_tmb_efetivado['valor_convertido'].sum()
print(f"\n💰 SOMA TOTAL TMB (Efetivado): R$ {soma_tmb:,.2f}")
print(f"   Média por venda: R$ {soma_tmb/len(df_tmb_efetivado):,.2f}")
print(f"   Valores nulos: {df_tmb_efetivado['valor_convertido'].isna().sum()}")

# ========== RESUMO FINAL ==========
print("\n" + "=" * 100)
print("📊 RESUMO CONSOLIDADO:")
print("=" * 100)
print(f"Hotmart:  {len(df_hotmart):>4} vendas = R$ {soma_hotmart:>15,.2f}")
print(f"TMB:      {len(df_tmb_efetivado):>4} vendas = R$ {soma_tmb:>15,.2f}")
print(f"{'-'*100}")
print(f"TOTAL:    {len(df_hotmart) + len(df_tmb_efetivado):>4} vendas = R$ {soma_hotmart + soma_tmb:>15,.2f}")
print("=" * 100)
