import pandas as pd

# Carregar CSV pulando as 2 primeiras linhas (cabeçalho do Google Ads)
df = pd.read_csv(
    r'analises/[PBB-ABR-26]/Google Ads/Performance dos anúncios-pbb-abr-26.csv',
    sep=',',
    encoding='utf-8',
    skiprows=2
)

print(f"\n>>> Total de anuncios no arquivo: {len(df):,}")

# Procurar AD093
ad093 = df[df['Nome do anúncio'].astype(str).str.contains('AD093', case=False, na=False)]

print(f">>> Linhas com AD093: {len(ad093)}")

if len(ad093) > 0:
    # Converter custo (formato brasileiro com vírgula)
    ad093_copy = ad093.copy()
    ad093_copy['custo_num'] = pd.to_numeric(
        ad093_copy['Custo'].astype(str).str.replace('.', '').str.replace(',', '.'),
        errors='coerce'
    ).fillna(0)
    
    total_ad093 = ad093_copy['custo_num'].sum()
    
    print(f"\n>>> INVESTIMENTO TOTAL AD093 NO YOUTUBE: R$ {total_ad093:,.2f}")
    
    # Conversões
    if 'Conversões' in ad093_copy.columns:
        ad093_copy['conv_num'] = pd.to_numeric(
            ad093_copy['Conversões'].astype(str).str.replace('.', '').str.replace(',', '.'),
            errors='coerce'
        ).fillna(0)
        total_conv = ad093_copy['conv_num'].sum()
        print(f">>> CONVERSOES TOTAL AD093: {total_conv:.0f}")
    
    # Cliques
    if 'Cliques' in ad093_copy.columns:
        ad093_copy['cliques_num'] = pd.to_numeric(
            ad093_copy['Cliques'].astype(str).str.replace('.', '').str.replace(',', '.'),
            errors='coerce'
        ).fillna(0)
        total_cliques = ad093_copy['cliques_num'].sum()
        print(f">>> CLIQUES TOTAL AD093: {total_cliques:.0f}")

# Total geral do arquivo
df['custo_num'] = pd.to_numeric(
    df['Custo'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

print(f"\n>>> INVESTIMENTO TOTAL YOUTUBE (todos anuncios): R$ {df['custo_num'].sum():,.2f}")
print(f">>> Percentual AD093: {(total_ad093 / df['custo_num'].sum() * 100):.2f}%")
