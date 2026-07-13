#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigar estrutura de dados de vendas - Hotmart e TMB
"""

import pandas as pd
import numpy as np

print("\n" + "="*100)
print("📊 INVESTIGAÇÃO COMPLETA DE VENDAS")
print("="*100)

# Hotmart
print("\n📥 HOTMART (Cartão de Crédito)")
print("-" * 100)
try:
    df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Total de registros: {len(df_hotmart)}")
    
    # Converter valor
    valor_col = df_hotmart['Valor de compra sem impostos']
    valor_col_str = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
    df_hotmart['valor_numerico'] = pd.to_numeric(valor_col_str, errors='coerce')
    
    valor_total = df_hotmart['valor_numerico'].sum()
    print(f"✓ Valor total: R$ {valor_total:,.2f}")
    
    # Contar emails
    emails_hotmart = df_hotmart['Email do(a) Comprador(a)'].nunique()
    print(f"✓ Emails únicos: {emails_hotmart}")
    
    # Verificar status
    print(f"\nStatus de transações:")
    status_counts = df_hotmart['Status da transação'].value_counts()
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    # Amostra de dados
    print(f"\nPrimeira transação:")
    print(f"  Email: {df_hotmart['Email do(a) Comprador(a)'].iloc[0]}")
    print(f"  Valor: {df_hotmart['Valor de compra sem impostos'].iloc[0]}")
    print(f"  Produto: {df_hotmart['Produto'].iloc[0] if 'Produto' in df_hotmart.columns else 'N/A'}")
    
except Exception as e:
    print(f"✗ Erro: {e}")

# TMB
print("\n\n📥 TMB (Boletos)")
print("-" * 100)
try:
    # Tentar leitura normal
    df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8')
    print(f"✓ Total de registros: {len(df_tmb)}")
    print(f"✓ Colunas: {list(df_tmb.columns)}")
except Exception as e1:
    print(f"✗ Erro leitura normal: {e1}")
    
    # Tentar com diferentes encodings
    encodings = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-16']
    for enc in encodings:
        try:
            df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding=enc)
            print(f"✓ Lido com encoding: {enc}")
            print(f"  Total de registros: {len(df_tmb)}")
            print(f"  Colunas: {list(df_tmb.columns)}")
            
            # Tentar identificar coluna de valor
            valor_cols = [col for col in df_tmb.columns if any(x in col.lower() for x in ['valor', 'preço', 'total', 'amount'])]
            print(f"  Colunas com valores: {valor_cols}")
            
            break
        except Exception as e2:
            continue
    else:
        print("✗ Não foi possível ler o arquivo TMB com nenhum encoding")

print("\n" + "="*100 + "\n")
