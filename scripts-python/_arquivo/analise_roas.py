#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de ROAS - Cruzamento de Leads vs Vendas
Verifica quais leads viraram vendas e calcula ROAS por campanha
"""

import pandas as pd
import numpy as np
from datetime import datetime

print("\n" + "="*100)
print("📊 ANÁLISE ROAS - LEADS x VENDAS")
print("="*100)

# Carregar Leads Active Campaign
print("\n📥 Carregando dados...")
try:
    df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')
    print(f"✓ Leads carregado: {len(df_leads)} registros")
    
    # Verificar colunas de email e UTM
    email_col = None
    for col in df_leads.columns:
        if 'email' in col.lower():
            email_col = col
            break
    
    if email_col:
        print(f"  Email column: {email_col}")
        print(f"  Emails únicos: {df_leads[email_col].nunique()}")
    
    # Verificar UTM columns
    utm_cols = [col for col in df_leads.columns if col.startswith('*Utm')]
    print(f"  UTM columns: {utm_cols[:3]}")  # Primeiras 3
    
except Exception as e:
    print(f"✗ Erro ao carregar leads: {e}")
    df_leads = None

# Carregar Vendas Hotmart
print("\n📥 Carregando vendas Hotmart...")
try:
    df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Vendas Hotmart: {len(df_hotmart)} registros")
    
    # Verificar emails
    email_hotmart = df_hotmart['Email do(a) Comprador(a)'].nunique()
    print(f"  Emails únicos: {email_hotmart}")
    
    # Valor total - converter para número
    valor_col = df_hotmart['Valor de compra sem impostos']
    valor_col_clean = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
    try:
        valor_total = pd.to_numeric(valor_col_clean, errors='coerce').sum()
        print(f"  Valor total: R$ {valor_total:,.2f}")
    except:
        print(f"  Valor total: erro ao converter")
    
except Exception as e:
    print(f"✗ Erro ao carregar Hotmart: {e}")
    df_hotmart = None

# Fazer o cruzamento
if df_leads is not None and df_hotmart is not None and email_col:
    print("\n" + "="*100)
    print("🔗 CRUZANDO LEADS COM VENDAS")
    print("="*100)
    
    # Normalizar emails - converter para string e remover NaNs
    df_leads['email_normalizado'] = df_leads[email_col].astype(str).str.lower().str.strip()
    df_hotmart['email_normalizado'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
    
    # Remover emails inválidos
    df_hotmart = df_hotmart[df_hotmart['email_normalizado'] != 'nan']
    df_hotmart = df_hotmart[df_hotmart['email_normalizado'].str.contains('@', na=False)]
    
    # Encontrar vendas
    emails_com_venda = set(df_hotmart['email_normalizado'].unique())
    df_leads['tem_venda'] = df_leads['email_normalizado'].isin(emails_com_venda)
    
    vendas_encontradas = df_leads['tem_venda'].sum()
    print(f"\n✓ Vendas encontradas: {vendas_encontradas} leads viraram clientes")
    print(f"  Taxa de conversão (leads com venda): {vendas_encontradas / len(df_leads) * 100:.2f}%")
    
    # Cruzar informações
    leads_com_venda = df_leads[df_leads['tem_venda']].copy()
    leads_com_venda = leads_com_venda.merge(
        df_hotmart[['email_normalizado', 'Valor de compra sem impostos', 'Data da transação']],
        on='email_normalizado',
        how='left'
    )
    
    # Converter valor para número - pode estar como string ou float
    valor_col = leads_com_venda['Valor de compra sem impostos']
    valor_col_str = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
    leads_com_venda['valor_venda'] = pd.to_numeric(valor_col_str, errors='coerce')
    
    print(f"\n📊 Valor total em vendas: R$ {leads_com_venda['valor_venda'].sum():,.2f}")
    print(f"  Ticket médio: R$ {leads_com_venda['valor_venda'].mean():,.2f}")
    
    # Análise por campanha
    if '*Utm_campaign' in df_leads.columns:
        print("\n" + "="*100)
        print("📈 ANÁLISE POR CAMPANHA")
        print("="*100)
        
        campaign_col = '*Utm_campaign'
        analise_campanha = leads_com_venda.groupby(campaign_col).agg({
            'valor_venda': ['count', 'sum', 'mean']
        }).reset_index()
        
        print("\nCampanhas com vendas:")
        for idx, row in analise_campanha.iterrows():
            campaign = row[(campaign_col, '')]
            vendas = int(row[('valor_venda', 'count')])
            total = row[('valor_venda', 'sum')]
            media = row[('valor_venda', 'mean')]
            print(f"  {campaign}: {vendas} vendas | Total R$ {total:,.2f} | Ticket R$ {media:,.2f}")
    
    # Análise por UTM Source (plataforma)
    if '*Utm_source' in df_leads.columns:
        print("\n" + "="*100)
        print("📱 ANÁLISE POR PLATAFORMA")
        print("="*100)
        
        source_col = '*Utm_source'
        
        # Total de leads por source
        total_leads_source = df_leads.groupby(source_col).size()
        
        # Vendas por source
        vendas_source = leads_com_venda.groupby(source_col).agg({
            'valor_venda': ['count', 'sum', 'mean']
        })
        
        print("\nPerformance por plataforma:")
        for source in df_leads[source_col].unique():
            if pd.isna(source):
                continue
            
            total = total_leads_source.get(source, 0)
            if source in vendas_source.index:
                vendas = int(vendas_source.loc[source, ('valor_venda', 'count')])
                valor = vendas_source.loc[source, ('valor_venda', 'sum')]
                media = vendas_source.loc[source, ('valor_venda', 'mean')]
            else:
                vendas = 0
                valor = 0
                media = 0
            
            conv_rate = (vendas / total * 100) if total > 0 else 0
            print(f"  {source}: {total} leads → {vendas} vendas ({conv_rate:.1f}%) | Valor R$ {valor:,.2f}")

print("\n" + "="*100 + "\n")
