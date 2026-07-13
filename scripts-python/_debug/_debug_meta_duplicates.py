import pandas as pd
import re

ma_a = pd.read_csv('analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv')

# Extrair código do anúncio
pattern = re.compile(r'AD\d+')
def extrair_cod(nome):
    m = pattern.search(str(nome).upper())
    return m.group(0) if m else None

ma_a['cod'] = ma_a['Nome do anúncio'].apply(extrair_cod)

# Contar quantas linhas existem por anúncio, por dia, por conjunto
agrup = ma_a.groupby(['cod', 'Dia', 'Nome do conjunto de anúncios']).size().reset_index(name='n_linhas')

print('Linhas por anúncio/dia/conjunto (top 10):')
print(agrup.head(10).to_string(index=False))

# Mostrar para AD054, AD100, AD071
for ad_code in ['AD054', 'AD100', 'AD071']:
    sub = agrup[agrup['cod'] == ad_code]
    print(f'\n{ad_code}: {len(sub)} linhas únicas (dia/conjunto)')
    print(sub.head(10).to_string(index=False))

# Contar quantos conjuntos diferentes por anúncio
for ad_code in ['AD054', 'AD100', 'AD071']:
    conjuntos = ma_a[ma_a['cod'] == ad_code]['Nome do conjunto de anúncios'].nunique()
    print(f'{ad_code}: {conjuntos} conjuntos diferentes')
