#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar dados de Google Ads no Excel
"""

import pandas as pd
import glob

xlsx_files = glob.glob(r'*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0] if xlsx_files else None

if not xlsx_path:
    print("ERRO: Arquivo Excel nao encontrado")
else:
    print(f"OK - Arquivo: {xlsx_path}\n")
    
    # Google Ads - Tentar diferentes formas de leitura
    try:
        # Primeiro tenta sem skiprows para ver headers
        df_ga = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA')
        print(f"Google Ads (EXTRACAO-GA):")
        print(f"  Linhas: {len(df_ga)}")
        print(f"  Colunas: {list(df_ga.columns)}")
        print(f"  Primeiras linhas:")
        print(df_ga.head(2))
        
    except Exception as e:
        print(f"ERRO ao ler Google Ads: {e}")
    
    # Facebook (para comparar)
    try:
        df_fb = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')
        print(f"\nFacebook Ads (EXTRACAO-BM):")
        print(f"  Linhas: {len(df_fb)}")
        print(f"  Colunas: {list(df_fb.columns)[:10]}")
        
        if 'Amount Spent' in df_fb.columns:
            total_spent = df_fb['Amount Spent'].sum()
            print(f"  Investimento total: R$ {total_spent:,.2f}")
        
        if 'Leads' in df_fb.columns:
            total_leads = df_fb['Leads'].sum()
            print(f"  Leads total: {total_leads:,}")
            
    except Exception as e:
        print(f"ERRO ao ler Facebook: {e}")
