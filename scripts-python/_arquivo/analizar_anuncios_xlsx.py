#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisar estrutura do arquivo Anúncios [PBB-ABR-26] (7).xlsx
"""

import pandas as pd
import openpyxl

xlsx_path = r'Anúncios [PBB-ABR-26] (7).xlsx'

print("\n" + "="*100)
print("ANALISE DO ARQUIVO EXCEL: Anuncios [PBB-ABR-26] (7).xlsx")
print("="*100)

try:
    # Ver abas
    xls = pd.ExcelFile(xlsx_path)
    print(f"\nAbas encontradas: {xls.sheet_names}")
    
    # Ler cada aba
    for sheet_name in xls.sheet_names:
        print(f"\n\n{'='*100}")
        print(f"ABA: {sheet_name}")
        print('='*100)
        
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        print(f"\nDimensões: {len(df)} linhas × {len(df.columns)} colunas")
        print(f"\nColunas:")
        for i, col in enumerate(df.columns):
            print(f"  {i+1}. {col}")
        
        print(f"\nPrimeiras 5 linhas:")
        print(df.head().to_string())
        
        print(f"\nTipos de dados:")
        print(df.dtypes)
        
        print(f"\nResumo de valores (primeiras 3 colunas):")
        print(df.iloc[:, :3].describe())

except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

print(f"\n" + "="*100 + "\n")
