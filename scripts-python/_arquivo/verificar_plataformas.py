import pandas as pd

print("\n" + "=" * 100)
print("🔍 VERIFICAÇÃO DE PLATAFORMAS NO CSV META ADS")
print("=" * 100)

# Carregar CSV
df = pd.read_csv(r'analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv', sep=',', encoding='utf-8')

print(f"\n📊 INFORMAÇÕES GERAIS:")
print(f"   Total de linhas: {len(df)}")
print(f"   Total de colunas: {len(df.columns)}")

print(f"\n📋 COLUNAS DISPONÍVEIS:")
for i, col in enumerate(df.columns, 1):
    print(f"   {i}. {col}")

# Procurar indicadores de plataforma
print(f"\n🔍 PROCURANDO INDICADORES DE PLATAFORMA:")

# Verificar se existe coluna de plataforma
plataforma_cols = [col for col in df.columns if 'plataforma' in col.lower() or 'platform' in col.lower() or 'tipo' in col.lower() or 'rede' in col.lower()]
if plataforma_cols:
    print(f"\n✓ Encontradas colunas relacionadas a plataforma:")
    for col in plataforma_cols:
        print(f"\n   Coluna: {col}")
        print(f"   Valores únicos: {df[col].nunique()}")
        print(f"   Valores:")
        print(df[col].value_counts().head(10))

# Verificar nome das campanhas/anúncios
print(f"\n🔍 ANALISANDO NOMES DOS ANÚNCIOS:")
if 'Nome da campanha' in df.columns:
    print(f"\n   📌 CAMPANHAS ÚNICAS:")
    campanhas = df['Nome da campanha'].value_counts()
    print(f"   Total: {len(campanhas)}")
    print(f"\n   Top 10:")
    for nome, count in campanhas.head(10).items():
        print(f"      {nome}: {count} linhas")

# Verificar se há menção a YouTube nos nomes
nomes_col = 'Nome do anúncio' if 'Nome do anúncio' in df.columns else 'Nome da campanha'
if nomes_col in df.columns:
    youtube_mentions = df[df[nomes_col].astype(str).str.upper().str.contains('YOUTUBE|YT|VIDEO|VÍDEO', na=False)]
    print(f"\n   🎥 LINHAS COM MENÇÃO A YOUTUBE/VIDEO: {len(youtube_mentions)}")
    
    if len(youtube_mentions) > 0:
        print(f"\n   Exemplos:")
        for idx, row in youtube_mentions.head(10).iterrows():
            valor = pd.to_numeric(row.get('Valor usado (BRL)', 0), errors='coerce') or 0
            print(f"      - {row[nomes_col][:80]}: R$ {valor:,.2f}")

# Verificar AD093 especificamente em todas as possíveis variações
print(f"\n🔍 PROCURANDO AD093 (TODAS VARIAÇÕES):")
ad093_all = df[df[nomes_col].astype(str).str.contains('093', na=False)]
print(f"   Total de linhas com '093': {len(ad093_all)}")

if len(ad093_all) > 0:
    # Converter valores
    ad093_all['valor'] = pd.to_numeric(ad093_all['Valor usado (BRL)'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    print(f"\n   Nomes únicos encontrados:")
    for nome in ad093_all[nomes_col].unique():
        linhas_nome = ad093_all[ad093_all[nomes_col] == nome]
        total_valor = linhas_nome['valor'].sum()
        print(f"      - {nome[:80]}")
        print(f"        Total investido: R$ {total_valor:,.2f}")
        print(f"        Linhas: {len(linhas_nome)}")

print("\n" + "=" * 100)
