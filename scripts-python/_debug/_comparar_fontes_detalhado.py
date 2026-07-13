import pandas as pd
import os

base = r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm'
xl_path = os.path.join(base, 'Anúncios [PBB-ABR-26] (7).xlsx')
xl = pd.ExcelFile(xl_path)

# === EXTRACAO-GA: agregar por anúncio ===
print("=== EXTRACAO-GA: soma de Conversions por AD ===")
ga_raw = xl.parse('EXTRACAO-GA')
# Extract AD code from Ad Name
import re
def get_ad(name):
    m = re.match(r'(AD\d+)', str(name))
    return m.group(1) if m else str(name)

ga_raw['AD'] = ga_raw['Ad Name'].apply(get_ad)
ga_agg = ga_raw.groupby('AD').agg(
    cost=('Cost (Spend)', 'sum'),
    conversions=('Conversions', 'sum'),
).reset_index().sort_values('cost', ascending=False)
print(ga_agg.to_string())
print(f"\nTotal conversions (GA raw): {ga_agg['conversions'].sum():.0f}")
print(f"Total cost (GA raw): {ga_agg['cost'].sum():.2f}")

# === Anúncios YT: ler a aba da planilha ===
print("\n\n=== ANÚNCIOS YT PBB-ABR-26 (planilha do usuário) ===")
yt_xl = xl.parse('Anúncios YT PBB-ABR-26')
# Header is on row 1 (index)
yt_xl.columns = yt_xl.iloc[0].tolist()
yt_xl = yt_xl.iloc[1:].reset_index(drop=True)
yt_xl.columns = ['Anuncio', 'Miniatura', 'Investimento', 'Leads', 'CPL', 'Vendas', 'CustoVenda', 'ROAS']
yt_xl = yt_xl[yt_xl['Anuncio'].notna()]
yt_xl['AD'] = yt_xl['Anuncio'].apply(lambda x: re.match(r'(AD\d+)', str(x)).group(1) if re.match(r'(AD\d+)', str(x)) else x)
print(yt_xl[['AD', 'Investimento', 'Leads', 'Vendas', 'ROAS']].to_string())
print(f"\nTotal leads (planilha YT): {yt_xl['Leads'].sum()}")
print(f"Total vendas (planilha YT): {yt_xl['Vendas'].sum()}")

# === Nossa ANALISE_YOUTUBE CSV ===
print("\n\n=== NOSSO ANALISE_YOUTUBE CSV ===")
our_csv = pd.read_csv(os.path.join(base, 'analises', '[PBB-ABR-26]', 'ANALISE_YOUTUBE_[PBB-ABR-26].csv'), encoding='utf-8-sig')
our_csv['AD'] = our_csv['criativo'].apply(lambda x: re.match(r'(AD\d+)', str(x)).group(1) if re.match(r'(AD\d+)', str(x)) else x)
print(our_csv[['AD', 'investimento', 'leads', 'vendas', 'roas']].to_string())
print(f"\nTotal leads (nosso CSV): {our_csv['leads'].sum()}")
print(f"Total vendas (nosso CSV): {our_csv['vendas'].sum()}")

# === COMPARAÇÃO DIRETA ===
print("\n\n=== COMPARAÇÃO: GA_RAW vs YT_PLANILHA vs NOSSO_CSV ===")
print(f"{'AD':<8} {'GA_raw_conv':>12} {'YT_sheet_leads':>14} {'YT_sheet_vnd':>13} {'CSV_leads':>10} {'CSV_vnd':>8}")
print("-" * 70)
all_ads = sorted(set(ga_agg['AD'].tolist() + yt_xl['AD'].tolist() + our_csv['AD'].tolist()))
for ad in all_ads:
    gc = ga_agg[ga_agg['AD']==ad]['conversions'].sum()
    yl = yt_xl[yt_xl['AD']==ad]['Leads'].values
    yv = yt_xl[yt_xl['AD']==ad]['Vendas'].values
    cl = our_csv[our_csv['AD']==ad]['leads'].values
    cv = our_csv[our_csv['AD']==ad]['vendas'].values
    gc_s = f"{gc:.0f}" if gc > 0 else "---"
    yl_s = str(yl[0]) if len(yl)>0 and str(yl[0]) != 'nan' else "---"
    yv_s = str(yv[0]) if len(yv)>0 and str(yv[0]) != 'nan' else "---"
    cl_s = str(cl[0]) if len(cl)>0 else "---"
    cv_s = str(cv[0]) if len(cv)>0 else "---"
    print(f"{ad:<8} {gc_s:>12} {yl_s:>14} {yv_s:>13} {cl_s:>10} {cv_s:>8}")
