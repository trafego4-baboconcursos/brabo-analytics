import pandas as pd
import unicodedata
from pathlib import Path
import csv

base = Path(r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm')
ac_dir = base / 'analises' / '[PBB-ABR-26]' / 'Active Campaign'

# Listar todos os arquivos AC
for f in ac_dir.glob('*.csv'):
    size = f.stat().st_size
    print(f"  {f.name} ({size:,} bytes, mtime={f.stat().st_mtime:.0f})")

# Ler arquivo principal
ac_files = sorted(ac_dir.glob('*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)
print(f"\nUsando arquivo mais recente: {ac_files[0].name}")
df = pd.read_csv(ac_files[0], encoding='utf-8', low_memory=False)

print(f"Total de leads no AC: {len(df)}")
print(f"Colunas com UTM: {[c for c in df.columns if 'utm' in c.lower()]}")

# Verificar UTM source
df['utm_source_clean'] = df['*Utm_source'].fillna('').astype(str).str.strip().str.lower()
print(f"\nDistribuição utm_source (top 20):")
print(df['utm_source_clean'].value_counts().head(20))

# Contar leads YT
yt_mask = df['utm_source_clean'].str.startswith('yt-', na=False)
print(f"\nLeads com utm_source yt-: {yt_mask.sum()}")

# Contar leads FB
fb_mask = df['utm_source_clean'].str.startswith('fb-', na=False)
print(f"Leads com utm_source fb-: {fb_mask.sum()}")

# Sem UTM
empty_mask = df['utm_source_clean'].isin(['', 'nan'])
print(f"Leads sem utm_source:    {empty_mask.sum()}")

# Quais utm_source começam com yt-
print(f"\nTipos de yt- utm_source:")
print(df[yt_mask]['utm_source_clean'].value_counts().head(20))

# Verificar datas
date_cols = [c for c in df.columns if 'data' in c.lower() or 'date' in c.lower() or 'creat' in c.lower()]
print(f"\nColunas de data: {date_cols}")
if date_cols:
    for col in date_cols[:2]:
        print(f"  {col}: min={df[col].min()}, max={df[col].max()}")
