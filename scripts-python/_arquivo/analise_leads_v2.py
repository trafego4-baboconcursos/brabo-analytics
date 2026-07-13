import pandas as pd

csv_path = r'c:\Users\trafe\Desktop\workspace-mmm\analises\active-campaing\Active-Campaing---Anunciante-Felipe-Graton-leads-6-de-jan-de-2026-22-de-jan-de-2026-V2.csv'

# Ler CSV
df = pd.read_csv(csv_path)

print("\n" + "="*100)
print("ANÁLISE CRÍTICA: LEADS vs CAMPANHAS (CONFRONTO COM META ADS & GOOGLE ADS)")
print("="*100)

# Colunas com asterisco
utm_cols = [col for col in df.columns if col.startswith('*Utm')]
print(f"\nColunas UTM encontradas: {utm_cols}")

# Total
total = len(df)
print(f"\n[1] TOTAL DE LEADS: {total}")

# Analisar utm_source
utm_src_col = '*Utm_source'
utm_src_values = df[utm_src_col].fillna('').value_counts()
print(f"\n[2] POR PLATAFORMA (utm_source):")
for src, count in utm_src_values.items():
    src_display = src if src != '' else '(vazio)'
    pct = (count / total) * 100
    print(f"    {src_display:15s} → {count:6d} leads ({pct:5.1f}%)")

# Analisar utm_medium
utm_med_col = '*Utm_medium'
utm_med_values = df[utm_med_col].fillna('').value_counts()
print(f"\n[3] POR TIPO DE ANÚNCIO (utm_medium) - TOP 20:")
for i, (med, count) in enumerate(utm_med_values.head(20).items()):
    med_display = med if med != '' else '(vazio)'
    pct = (count / total) * 100
    print(f"    {med_display:45s} → {count:5d} ({pct:5.1f}%)")

# Analisar utm_campaign
utm_camp_col = '*Utm_campaign'
utm_camp_values = df[utm_camp_col].fillna('').value_counts()
print(f"\n[4] POR CAMPANHA (utm_campaign):")
for camp, count in utm_camp_values.items():
    camp_display = camp if camp != '' else '(vazio)'
    pct = (count / total) * 100
    print(f"    {camp_display:40s} → {count:6d} ({pct:5.1f}%)")

# Qualidade: por Tag
print(f"\n[5] QUALIDADE (Tags):")
disengaged = df[df['Tags'].str.contains('Disengaged', na=False)].shape[0]
limpeza_total = df[df['Tags'].str.contains('LIMPEZA TOTAL', na=False)].shape[0]
limpeza = df[df['Tags'].str.contains('LIMPEZA', na=False) & ~df['Tags'].str.contains('LIMPEZA TOTAL', na=False)].shape[0]
ok = total - disengaged - limpeza_total - limpeza

print(f"    Disengaged:      {disengaged:6d} ({disengaged/total*100:5.1f}%)")
print(f"    [LIMPEZA TOTAL]: {limpeza_total:6d} ({limpeza_total/total*100:5.1f}%)")
print(f"    [LIMPEZA]:       {limpeza:6d} ({limpeza/total*100:5.1f}%)")
print(f"    OK/Válido:       {ok:6d} ({ok/total*100:5.1f}%)")

# Facebook vs YouTube
print(f"\n[6] FACEBOOK vs YOUTUBE (baseado em utm_source):")
fb_df = df[df[utm_src_col] == 'fb']
yt_df = df[df[utm_src_col] == 'yt']
fb_count = len(fb_df)
yt_count = len(yt_df)
print(f"    Facebook: {fb_count:6d} leads ({fb_count/total*100:5.1f}%)")
print(f"    YouTube:  {yt_count:6d} leads ({yt_count/total*100:5.1f}%)")

# Top mediums por plataforma
print(f"\n[7] TOP MEDIUMS FACEBOOK:")
fb_mediums = fb_df[utm_med_col].value_counts().head(10)
for med, count in fb_mediums.items():
    pct = (count / fb_count) * 100
    print(f"    {str(med):45s} → {count:5d} ({pct:5.1f}%)")

print(f"\n[8] TOP MEDIUMS YOUTUBE:")
yt_mediums = yt_df[utm_med_col].value_counts().head(10)
for med, count in yt_mediums.items():
    pct = (count / yt_count) * 100
    print(f"    {str(med):45s} → {count:5d} ({pct:5.1f}%)")

# Confronto com Meta Ads (9.246 conversões)
print(f"\n[9] CONFRONTO COM META ADS (9.246 conversões reportadas):")
ok_df = df[~df['Tags'].str.contains('Disengaged|LIMPEZA', na=False)]
ok_count = len(ok_df)
print(f"    Leads brutos: {total:6d}")
print(f"    Leads OK: {ok_count:6d}")
print(f"    Diferença vs Meta (9.246): {abs(9246 - ok_count):6d} ({abs(9246-ok_count)/9246*100:5.1f}%)")

# CPL teórico
print(f"\n[10] CPL TEÓRICO:")
gasto = 58224
cpl_bruto = gasto / total
cpl_valido = gasto / ok_count if ok_count > 0 else 0
print(f"    CPL (todos): R$ {cpl_bruto:.2f}")
print(f"    CPL (válidos): R$ {cpl_valido:.2f}")
print(f"    Meta Ads reportou: R$ 6,30 (fundo) / R$ 0,027 (topo)")

print("\n" + "="*100)
