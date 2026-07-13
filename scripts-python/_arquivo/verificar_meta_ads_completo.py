#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificação completa do arquivo Meta Ads atualizado
"""
import pandas as pd

print("=" * 100)
print("🔍 VERIFICAÇÃO DO ARQUIVO META ADS ATUALIZADO")
print("=" * 100)

# Tentar ambos os arquivos
arquivos = [
    r'analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv',
    r'analises/[PBB-ABR-26]/Meta Ads/pbb-abr-26-meta-ads.csv'
]

for arquivo in arquivos:
    try:
        print(f"\n📁 Arquivo: {arquivo.split('/')[-1]}")
        print("-" * 100)
        
        df = pd.read_csv(arquivo, sep=',', encoding='utf-8')
        
        print(f"   Total de linhas: {len(df):,}")
        print(f"   Total de colunas: {len(df.columns)}")
        
        # Verificar coluna de valores
        if 'Valor usado (BRL)' in df.columns:
            print(f"\n   ✓ Coluna 'Valor usado (BRL)' encontrada")
            
            # Converter valores
            df['valor_gasto'] = pd.to_numeric(
                df['Valor usado (BRL)'].astype(str).str.replace(',', '.'),
                errors='coerce'
            ).fillna(0)
            
            linhas_com_valor = df[df['valor_gasto'] > 0]
            total_investimento = df['valor_gasto'].sum()
            
            print(f"   • Linhas com valor preenchido: {len(linhas_com_valor):,}")
            print(f"   • Linhas sem valor: {len(df) - len(linhas_com_valor):,}")
            print(f"   • INVESTIMENTO TOTAL: R$ {total_investimento:,.2f}")
            
            if len(linhas_com_valor) > 0:
                print(f"\n   📊 Primeiras 10 linhas com investimento:")
                print(linhas_com_valor[['Nome do anúncio', 'Valor usado (BRL)', 'Leads']].head(10).to_string(index=False))
                
                # Agrupar por anúncio
                print(f"\n   📈 Top 10 anúncios por investimento:")
                df['codigo_ad'] = df['Nome do anúncio'].astype(str).str.strip().apply(
                    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
                )
                
                por_anuncio = df.groupby('codigo_ad').agg({
                    'valor_gasto': 'sum',
                    'Leads': lambda x: pd.to_numeric(x, errors='coerce').sum()
                }).reset_index()
                
                por_anuncio = por_anuncio[por_anuncio['valor_gasto'] > 0].sort_values('valor_gasto', ascending=False)
                
                for idx, row in por_anuncio.head(10).iterrows():
                    print(f"      {row['codigo_ad']}: R$ {row['valor_gasto']:,.2f} | {int(row['Leads'])} leads")
                
                print(f"\n   ✅ ARQUIVO VÁLIDO - Contém dados de investimento!")
                
        else:
            print(f"   ❌ Coluna 'Valor usado (BRL)' NÃO encontrada")
            print(f"   Colunas disponíveis: {', '.join(df.columns[:10])}...")
        
        # Verificar outras métricas importantes
        print(f"\n   📋 Outras métricas:")
        metricas = ['Leads', 'Alcance', 'Impressões', 'Cliques (todos)', 'Cliques no link']
        for metrica in metricas:
            if metrica in df.columns:
                valores = pd.to_numeric(df[metrica], errors='coerce')
                total = valores.sum()
                print(f"      • {metrica}: {total:,.0f}")
        
    except FileNotFoundError:
        print(f"   ❌ Arquivo não encontrado")
    except Exception as e:
        print(f"   ❌ Erro ao processar: {e}")

print("\n" + "=" * 100)
