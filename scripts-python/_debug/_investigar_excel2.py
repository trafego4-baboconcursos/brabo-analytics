import pandas as pd
import re, os

base = r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm'
xl_path = os.path.join(base, 'Anúncios [PBB-ABR-26] (7).xlsx')
xl = pd.ExcelFile(xl_path)

def get_ad(name):
    m = re.match(r'(AD\d+)', str(name))
    return m.group(1) if m else None

# === 1. EXTRACAO-GA (dados brutos Google Ads) ===
ga_raw = xl.parse('EXTRACAO-GA')
ga_raw['AD'] = ga_raw['Ad Name'].apply(get_ad)
ga_agg = ga_raw.groupby('AD').agg(
    inv_ga=('Cost (Spend)', 'sum'),
    leads_ga=('Conversions', 'sum'),
).reset_index()

print("=== EXTRACAO-GA totais ===")
print(f"Total investimento: {ga_agg['inv_ga'].sum():.2f}")
print(f"Total leads/conversoes: {ga_agg['leads_ga'].sum():.0f}")

# Datas no EXTRACAO-GA
print(f"Date range GA: {ga_raw['Day'].min()} -> {ga_raw['Day'].max()}")
print(f"Linhas raw: {len(ga_raw)}")

# === 2. Anúncios YT (planilha - aba específica YT) ===
yt_raw = xl.parse('Anúncios YT PBB-ABR-26', header=1)
# Remove primeira linha (que é o cabeçalho original "Anúncio, Miniatura...")
# Real header is row 1 (index 1 when header=1 reads row index 1 as header)
# Actually with header=1 it should skip row 0 and use row 1 as header
print("\n=== Anúncios YT (planilha) colunas raw ===")
print(yt_raw.columns.tolist())
print(yt_raw.head(3).to_string())

# === 3. Anúncios YT via aba consolidada PBB-ABR-26 ===
cons_raw = xl.parse('Anúncios PBB-ABR-26', header=1)
print("\n=== Anúncios PBB-ABR-26 (aba consolidada) colunas ===")
print(cons_raw.columns.tolist())
print(cons_raw.head(3).to_string())
