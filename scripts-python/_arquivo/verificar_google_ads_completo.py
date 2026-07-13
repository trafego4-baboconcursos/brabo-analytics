import pandas as pd

print("\n" + "=" * 100)
print("🔍 VERIFICAÇÃO DO ARQUIVO GOOGLE ADS")
print("=" * 100)

# Carregar CSV
df = pd.read_csv(r'analises/[PBB-ABR-26]/Google Ads/Performance dos anúncios-pbb-abr-26.csv', sep=',', encoding='utf-8')

print(f"\n📊 INFORMAÇÕES GERAIS:")
print(f"   Total de linhas: {len(df):,}")
print(f"   Total de colunas: {len(df.columns)}")

print(f"\n📋 COLUNAS DISPONÍVEIS:")
for i, col in enumerate(df.columns, 1):
    print(f"   {i:2d}. {col}")

# Verificar coluna de custo/investimento
custo_cols = [col for col in df.columns if any(word in col.lower() for word in ['custo', 'cost', 'gasto', 'spend', 'investimento'])]
print(f"\n💰 COLUNAS DE CUSTO/INVESTIMENTO:")
for col in custo_cols:
    valores_nao_nulos = df[col].notna().sum()
    soma_total = pd.to_numeric(df[col], errors='coerce').sum()
    print(f"   • {col}")
    print(f"     Valores preenchidos: {valores_nao_nulos:,}")
    print(f"     Total: R$ {soma_total:,.2f}")

# Verificar tipos de campanha
if 'Tipo de campanha' in df.columns:
    print(f"\n📌 TIPOS DE CAMPANHA:")
    tipos = df['Tipo de campanha'].value_counts()
    for tipo, count in tipos.items():
        print(f"   {tipo:30} → {count:6,} linhas")

# Verificar rede de campanha
rede_cols = [col for col in df.columns if 'rede' in col.lower() or 'network' in col.lower()]
if rede_cols:
    print(f"\n🌐 REDES DE CAMPANHA:")
    for col in rede_cols:
        print(f"\n   Coluna: {col}")
        valores = df[col].value_counts()
        for valor, count in valores.head(10).items():
            print(f"      {valor:30} → {count:6,} linhas")

# Procurar por YouTube especificamente
print(f"\n🎥 PROCURANDO MENÇÕES AO YOUTUBE:")
youtube_cols = []
for col in df.columns:
    if df[col].dtype == 'object':
        youtube_count = df[col].astype(str).str.contains('youtube|yt|video|vídeo', case=False, na=False).sum()
        if youtube_count > 0:
            youtube_cols.append((col, youtube_count))

if youtube_cols:
    print(f"   ✓ Encontradas menções ao YouTube:")
    for col, count in youtube_cols:
        print(f"      • {col}: {count} linhas")
else:
    print(f"   ❌ Nenhuma menção ao YouTube encontrada")

# Verificar nome dos anúncios
if 'Anúncio' in df.columns or 'Nome do anúncio' in df.columns:
    nome_col = 'Anúncio' if 'Anúncio' in df.columns else 'Nome do anúncio'
    print(f"\n📋 PRIMEIROS 20 NOMES DE ANÚNCIOS:")
    for idx, nome in enumerate(df[nome_col].head(20), 1):
        print(f"   {idx:2d}. {str(nome)[:80]}")
    
    # Procurar AD093
    ad093_count = df[df[nome_col].astype(str).str.contains('093', na=False)]
    print(f"\n🔍 ANÚNCIOS CONTENDO '093': {len(ad093_count)}")
    
    if len(ad093_count) > 0:
        print(f"\n   Detalhes:")
        for idx, row in ad093_count.head(10).iterrows():
            custo_col = custo_cols[0] if custo_cols else None
            custo = pd.to_numeric(row[custo_col], errors='coerce') if custo_col else 0
            print(f"      - {row[nome_col][:70]}")
            if custo_col:
                print(f"        Custo: R$ {custo:,.2f}")

print("\n" + "=" * 100)
