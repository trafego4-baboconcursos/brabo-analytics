import pandas as pd
import re

def br2f(s):
    if pd.isna(s): return 0
    s = str(s).strip()
    s = s.replace('R$', '').replace('.', '').replace(',', '.').strip()
    try: return float(s)
    except: return 0

# Carregar dados
ma_a = pd.read_csv('analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv')
crm_a = pd.read_csv('analises/[PBB-ABR-26]/Active Campaign/PBB-ABR-14h-12-05-26.csv')
hm_a = pd.read_csv('analises/[PBB-ABR-26]/Vendas/hotmart pbb-abr-26.csv', sep=';')
tmb_a = pd.read_csv('analises/[PBB-ABR-26]/Vendas/tmb pbb-abr-26.csv', sep=';')

# Normalizar emails
crm_a['email_n'] = crm_a.iloc[:, 0].astype(str).str.lower().str.strip()
hm_a['email_n'] = hm_a.iloc[:, 0].astype(str).str.lower().str.strip()
tmb_a['email_n'] = tmb_a.iloc[:, 0].astype(str).str.lower().str.strip()

comp_emails_a = set(hm_a['email_n']) | set(tmb_a['email_n'])

# Simular EXATAMENTE o que inv_sem_venda faz
cap_ma_a = ma_a[ma_a['Nome da campanha'].str.lower().str.contains('captacao|captação', na=False)]

def extrair_cod(nome):
    m = re.search(r'\b(AD\d+)\b', str(nome).upper())
    return m.group(1) if m else None

cap_ma_a = cap_ma_a.copy()
cap_ma_a['cod'] = cap_ma_a['Nome do anúncio'].apply(extrair_cod)

# Agrupar por anúncio e somar investimento
grp = cap_ma_a.groupby('Nome do anúncio')['Valor usado (BRL)'].apply(lambda s: s.apply(br2f).sum()).reset_index()
grp.columns = ['ad', 'inv']
grp['cod'] = grp['ad'].apply(extrair_cod)

# Simular vendas_por_criativo
utm_col = next((c for c in crm_a.columns if 'utm_content' in c.lower()), None)
compradores = crm_a[crm_a['email_n'].isin(comp_emails_a)]
vendas_crit_a = compradores[utm_col].astype(str).str.upper().value_counts().to_dict() if utm_col else {}

print('Vendas por UTM registradas (top 20):')
for cod, count in sorted(vendas_crit_a.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f'  {cod}: {count} vendas')

# Identificar perdedores (0 vendas no dict)
perdedores = grp[grp['cod'].apply(lambda c: vendas_crit_a.get(c, 0) == 0 if c else True)]
perdedores = perdedores[perdedores['inv'] > 500].sort_values('inv', ascending=False)

print(f'\n=== ANÚNCIOS SEM VENDAS RASTREADAS (inv > R$500) ===')
print(f'Total: {len(perdedores)} anúncios')
print(f'\nTop 10:')
for idx, row in perdedores.head(10).iterrows():
    print(f'{row["cod"]}: R$ {row["inv"]:,.2f} - {row["ad"][:60]}')

total_waste = perdedores['inv'].sum()
inv_cap_total = cap_ma_a['Valor usado (BRL)'].apply(br2f).sum()
print(f'\nTotal desperdiçado: R$ {total_waste:,.2f}')
print(f'Total captação Meta ABR: R$ {inv_cap_total:,.2f}')
print(f'Percentual: {total_waste/inv_cap_total*100:.1f}%')

# Agora verificar se esses 3 anúncios estão nessa lista
print(f'\n=== VERIFICANDO OS 3 ANÚNCIOS ===')
for ad_code in ['AD054', 'AD100', 'AD071']:
    matching = grp[grp['cod'] == ad_code]
    if not matching.empty:
        inv = matching['inv'].sum()
        vendas = vendas_crit_a.get(ad_code, 0)
        print(f'{ad_code}: R$ {inv:,.2f} | Vendas: {vendas}')
    else:
        print(f'{ad_code}: NÃO ENCONTRADO')
