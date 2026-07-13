import pandas as pd
import re

ma_a = pd.read_csv('analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv')

pattern = re.compile(r'AD\d+')
def extrair_cod(nome):
    m = pattern.search(str(nome).upper())
    return m.group(0) if m else None

ma_a['cod'] = ma_a['Nome do anúncio'].apply(extrair_cod)
ma_a['inv'] = ma_a['Valor usado (BRL)'].replace('-', 0).apply(lambda x: float(str(x).replace('R$','').replace('.','').replace(',','.')) if str(x).strip() else 0)

# Escolha o anúncio para detalhar
ad_code = 'AD054'

sub = ma_a[ma_a['cod'] == ad_code]
dias = sub['Dia'].unique()
print(f'Investimento diário por conjunto para {ad_code}:')
for dia in sorted(dias):
    sub_dia = sub[sub['Dia'] == dia]
    soma = sub_dia['inv'].sum()
    print(f'{dia}: soma dos conjuntos = R$ {soma:,.2f}')
    print(sub_dia[['Nome do conjunto de anúncios','inv']].to_string(index=False))
    print('-'*40)
