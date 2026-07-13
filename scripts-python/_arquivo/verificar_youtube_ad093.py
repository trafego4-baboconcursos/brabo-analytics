import pandas as pd

print("\n" + "=" * 100)
print("VERIFICACAO AD093 NO ARQUIVO YOUTUBE (Google Ads)")
print("=" * 100)

# Carregar CSV pulando as 2 primeiras linhas (cabeçalho do Google Ads)
df = pd.read_csv(
    r'analises/[PBB-ABR-26]/Google Ads/Performance dos anúncios-pbb-abr-26.csv',
    sep=',',
    encoding='utf-8',
    skiprows=2
)

print(f"\n📊 Total de linhas: {len(df):,}")

# Verificar colunas
print(f"\n📋 Colunas de interesse:")
print(f"   • Nome do anúncio: {'✓' if 'Nome do anúncio' in df.columns else '✗'}")
print(f"   • Custo: {'✓' if 'Custo' in df.columns else '✗'}")
print(f"   • Cliques: {'✓' if 'Cliques' in df.columns else '✗'}")
print(f"   • Conversões: {'✓' if 'Conversões' in df.columns else '✗'}")

# Procurar AD093
if 'Nome do anúncio' in df.columns:
    ad093 = df[df['Nome do anúncio'].astype(str).str.contains('AD093', case=False, na=False)]
    
    print(f"\n🔍 ANÚNCIOS COM 'AD093': {len(ad093)}")
    
    if len(ad093) > 0:
        # Converter custo (formato brasileiro com vírgula)
        df['custo_num'] = pd.to_numeric(
            df['Custo'].astype(str).str.replace('.', '').str.replace(',', '.'),
            errors='coerce'
        ).fillna(0)
        
        ad093['custo_num'] = pd.to_numeric(
            ad093['Custo'].astype(str).str.replace('.', '').str.replace(',', '.'),
            errors='coerce'
        ).fillna(0)
        
        print(f"\n💰 INVESTIMENTO TOTAL AD093: R$ {ad093['custo_num'].sum():,.2f}")
        
        print(f"\n📋 DETALHES POR LINHA:")
        print("-" * 100)
        for idx, row in ad093.iterrows():
            print(f"   Nome completo: {row['Nome do anúncio']}")
            print(f"   Custo: R$ {row['custo_num']:,.2f}")
            print(f"   Cliques: {row.get('Cliques', 'N/A')}")
            print(f"   Conversões: {row.get('Conversões', 'N/A')}")
            
            # Extrair utm_source do template de acompanhamento
            if 'Modelo de acompanhamento' in df.columns:
                template = str(row.get('Modelo de acompanhamento', ''))
                if 'utm_source=' in template:
                    import re
                    match = re.search(r'utm_source=([^&]+)', template)
                    if match:
                        print(f"   UTM_source: {match.group(1)}")
            
            print("-" * 100)
        
        # Agrupar por campanha
        if 'Campanha' in df.columns:
            print(f"\n📊 DISTRIBUIÇÃO POR CAMPANHA:")
            for campanha in ad093['Campanha'].unique():
                linhas_campanha = ad093[ad093['Campanha'] == campanha]
                custo_campanha = linhas_campanha['custo_num'].sum()
                print(f"   {campanha}")
                print(f"      Custo: R$ {custo_campanha:,.2f}")
                print(f"      Linhas: {len(linhas_campanha)}")
    else:
        print(f"\n❌ Nenhum anúncio AD093 encontrado")
        
        # Listar alguns anúncios para referência
        print(f"\n📋 PRIMEIROS 20 ANÚNCIOS NO ARQUIVO:")
        for idx, nome in enumerate(df['Nome do anúncio'].head(20), 1):
            print(f"   {idx:2d}. {nome}")

# Estatísticas gerais do arquivo
print(f"\n📊 ESTATÍSTICAS GERAIS DO ARQUIVO:")
if 'Custo' in df.columns:
    df['custo_num'] = pd.to_numeric(
        df['Custo'].astype(str).str.replace('.', '').str.replace(',', '.'),
        errors='coerce'
    ).fillna(0)
    
    print(f"   💰 Investimento total (todos anúncios): R$ {df['custo_num'].sum():,.2f}")
    
    # Top 10 anúncios por custo
    top_anuncios = df.nlargest(10, 'custo_num')
    print(f"\n   🏆 TOP 10 ANÚNCIOS POR INVESTIMENTO:")
    for idx, row in top_anuncios.iterrows():
        nome = row['Nome do anúncio']
        # Extrair código do anúncio (AD093, AD084, etc.)
        codigo = nome.split(' - ')[0] if ' - ' in nome else nome[:10]
        print(f"      {codigo:15} → R$ {row['custo_num']:8,.2f}")

print("\n" + "=" * 100)
