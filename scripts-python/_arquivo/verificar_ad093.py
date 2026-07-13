import pandas as pd

print("\n" + "=" * 100)
print("🔍 VERIFICAÇÃO AD093 - Meta Ads CSV")
print("=" * 100)

# Carregar CSV
df = pd.read_csv(r'analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv', sep=',', encoding='utf-8')

# Extrair código do criativo
df['criativo'] = df['Nome do anúncio'].astype(str).apply(lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper())

# Converter valores
df['valor'] = pd.to_numeric(df['Valor usado (BRL)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Filtrar AD093
ad093 = df[df['criativo'] == 'AD093']

print(f"\n📊 TOTAL DE LINHAS COM AD093: {len(ad093)}")
print(f"💰 INVESTIMENTO TOTAL: R$ {ad093['valor'].sum():,.2f}")

if len(ad093) > 0:
    print(f"\n📋 DETALHES POR LINHA:")
    print("-" * 100)
    for idx, row in ad093.iterrows():
        print(f"   Nome completo: {row['Nome do anúncio'][:70]}")
        print(f"   Valor: R$ {row['valor']:,.2f}")
        print(f"   Leads: {row.get('Leads', 'N/A')}")
        print("-" * 100)
    
    # Verificar se existem outras variações
    print(f"\n🔍 BUSCANDO VARIAÇÕES DE 'AD093' (case-insensitive):")
    todos_nomes = df['Nome do anúncio'].astype(str).str.upper()
    variações = df[todos_nomes.str.contains('AD093', na=False)]
    print(f"   Total de linhas contendo 'AD093': {len(variações)}")
    
    if len(variações) > len(ad093):
        print(f"\n⚠️ ATENÇÃO: Existem {len(variações) - len(ad093)} linhas adicionais que contêm 'AD093' mas não começam com 'AD093 - '")
        print(f"\n📋 TODAS AS VARIAÇÕES:")
        for idx, row in variações.iterrows():
            print(f"   - {row['Nome do anúncio'][:80]}: R$ {pd.to_numeric(row['Valor usado (BRL)'], errors='coerce') or 0:,.2f}")
        
        print(f"\n💰 INVESTIMENTO TOTAL (TODAS VARIAÇÕES): R$ {variações['valor'].sum():,.2f}")
else:
    print("\n❌ NENHUMA LINHA ENCONTRADA COM CÓDIGO 'AD093'")
    print("\n🔍 Verificando se existe algum nome de anúncio contendo '093':")
    contains_093 = df[df['Nome do anúncio'].astype(str).str.contains('093', na=False)]
    if len(contains_093) > 0:
        print(f"\n✓ Encontradas {len(contains_093)} linhas contendo '093':")
        for idx, row in contains_093.head(20).iterrows():
            print(f"   - {row['Nome do anúncio'][:80]}: R$ {pd.to_numeric(row['Valor usado (BRL)'], errors='coerce') or 0:,.2f}")

print("\n" + "=" * 100)
