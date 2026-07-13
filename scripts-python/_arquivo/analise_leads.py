import pandas as pd

csv_path = r'c:\Users\trafe\Desktop\workspace-mmm\analises\active-campaing\Active-Campaing---Anunciante-Felipe-Graton-leads-6-de-jan-de-2026-22-de-jan-de-2026.csv'

# Ler CSV
df = pd.read_csv(csv_path, dtype={'*Utm_source': 'str', '*Utm_medium': 'str', '*Utm_campaign': 'str'})

print("\n" + "="*90)
print("ANÁLISE CRÍTICA: LEADS vs CAMPANHAS (CRUZ COM META ADS & GOOGLE ADS)")
print("="*90)

# Total
total = len(df)
print(f"\n[1] TOTAL DE LEADS CAPTURADOS: {total}")

# Sem rastreio (sem utm)
sem_rastreio = df[df['*Utm_source'].isna() | (df['*Utm_source'] == '')].shape[0]
com_rastreio = total - sem_rastreio
print(f"\n[2] LEADS COM RASTREIO: {com_rastreio} ({com_rastreio/total*100:.1f}%)")
print(f"    LEADS SEM RASTREIO: {sem_rastreio} ({sem_rastreio/total*100:.1f}%) ⚠️")

# Por utm_source
print(f"\n[3] POR PLATAFORMA (utm_source):")
utm_source = df['*Utm_source'].value_counts()
for src, count in utm_source.items():
    pct = (count / total) * 100
    print(f"    {str(src):15s} → {count:6d} ({pct:5.1f}%)")

# Por utm_medium - DETALHADO
print(f"\n[4] POR TIPO DE ANÚNCIO (utm_medium) - TOP 20:")
utm_medium = df['*Utm_medium'].value_counts().head(20)
for med, count in utm_medium.items():
    pct = (count / total) * 100
    print(f"    {str(med):40s} → {count:6d} ({pct:5.1f}%)")

# Facebook vs YouTube
fb_leads = df[df['*Utm_source'] == 'fb'].shape[0]
yt_leads = df[df['*Utm_source'] == 'yt'].shape[0]

print(f"\n[5] FACEBOOK vs YOUTUBE:")
print(f"    Facebook: {fb_leads} leads ({fb_leads/com_rastreio*100:.1f}% do rastreado)")
print(f"    YouTube:  {yt_leads} leads ({yt_leads/com_rastreio*100:.1f}% do rastreado)")

# Breakdown Facebook
print(f"\n[6] FACEBOOK BREAKDOWN (utm_medium):")
fb_df = df[df['*Utm_source'] == 'fb']
fb_medium = fb_df['*Utm_medium'].value_counts()
for med, count in fb_medium.items():
    pct = (count / fb_leads) * 100
    print(f"    {str(med):40s} → {count:5d} ({pct:5.1f}%)")

# Breakdown YouTube
print(f"\n[7] YOUTUBE BREAKDOWN (utm_medium):")
yt_df = df[df['*Utm_source'] == 'yt']
yt_medium = yt_df['*Utm_medium'].value_counts()
for med, count in yt_medium.items():
    pct = (count / yt_leads) * 100
    print(f"    {str(med):40s} → {count:5d} ({pct:5.1f}%)")

# Qualidade: Disengaged vs OK
print(f"\n[8] QUALIDADE DOS LEADS (Tags):")
disengaged = df[df['Tags'].str.contains('Disengaged', na=False)].shape[0]
limpeza_total = df[df['Tags'].str.contains('LIMPEZA TOTAL', na=False)].shape[0]
limpeza = df[df['Tags'].str.contains('LIMPEZA', na=False) & ~df['Tags'].str.contains('LIMPEZA TOTAL', na=False)].shape[0]
ok = total - disengaged - limpeza_total - limpeza

print(f"    Disengaged:      {disengaged:6d} ({disengaged/total*100:5.1f}%)")
print(f"    [LIMPEZA TOTAL]: {limpeza_total:6d} ({limpeza_total/total*100:5.1f}%)")
print(f"    [LIMPEZA]:       {limpeza:6d} ({limpeza/total*100:5.1f}%)")
print(f"    OK/Válido:       {ok:6d} ({ok/total*100:5.1f}%)")

# Leads válidos por plataforma
print(f"\n[9] LEADS VÁLIDOS (OK, não Disengaged) POR PLATAFORMA:")
ok_df = df[~df['Tags'].str.contains('Disengaged|LIMPEZA', na=False)]
ok_fb = ok_df[ok_df['*Utm_source'] == 'fb'].shape[0]
ok_yt = ok_df[ok_df['*Utm_source'] == 'yt'].shape[0]
ok_sem = ok_df[ok_df['*Utm_source'].isna() | (ok_df['*Utm_source'] == '')].shape[0]
print(f"    Facebook: {ok_fb} leads ({ok_fb/ok_df.shape[0]*100:.1f}% dos válidos)")
print(f"    YouTube:  {ok_yt} leads ({ok_yt/ok_df.shape[0]*100:.1f}% dos válidos)")
print(f"    Sem rastreio: {ok_sem} leads ({ok_sem/ok_df.shape[0]*100:.1f}% dos válidos)")

# Confronto com Meta Ads (9.246 conversões reportadas)
print(f"\n[10] CONFRONTO COM META ADS (9.246 conversões reportadas):")
print(f"     Leads brutos: {total}")
print(f"     Leads válidos: {ok_df.shape[0]}")
print(f"     Diferença vs Meta: {9246 - ok_df.shape[0]} ({abs(9246 - ok_df.shape[0])/9246*100:.1f}%)")

# CPL teórico
print(f"\n[11] CPL TEÓRICO:")
gasto_meta = 58224  # Valor total reportado Meta + Google
cpl_bruto = gasto_meta / total
cpl_valido = gasto_meta / ok_df.shape[0]
print(f"     CPL (todos): R$ {cpl_bruto:.2f}")
print(f"     CPL (válidos): R$ {cpl_valido:.2f}")
print(f"     Meta Ads reportou: R$ 6,30 (Captação)")

print("\n" + "="*90)
