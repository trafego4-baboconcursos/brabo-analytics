import pandas as pd
import re

def br2f(s):
    if pd.isna(s): return 0
    s = str(s).strip()
    s = s.replace('R$','').replace('.','').replace(',','.').strip()
    try: return float(s)
    except: return 0

ma_a = pd.read_csv('analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv')

# Extrair código do anúncio
pattern = re.compile(r'AD\d+')
def extrair_cod(nome):
    m = pattern.search(str(nome).upper())
    return m.group(0) if m else None

ma_a['cod'] = ma_a['Nome do anúncio'].apply(extrair_cod)
ma_a['inv'] = ma_a['Valor usado (BRL)'].apply(br2f)

# Agrupar por anúncio e dia, somar valor diário
agrupado = ma_a.groupby(['cod', 'Dia'])['inv'].sum().reset_index()

# Calcular total por anúncio
for ad_code in ['AD054', 'AD100', 'AD071']:
    total = agrupado[agrupado['cod'] == ad_code]['inv'].sum()
    print(f'{ad_code}: Investimento total real (soma diária) = R$ {total:,.2f}')

total_cap = agrupado[agrupado['cod'].notnull()]['inv'].sum()
print(f'Total investido em todos anúncios com código (soma diária): R$ {total_cap:,.2f}')
