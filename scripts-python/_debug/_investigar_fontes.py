import pandas as pd
import os

base = r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm'

# =============================================
# 1. Google Ads CSV oficial (Performance)
# =============================================
ga_path = os.path.join(base, 'analises', '[PBB-ABR-26]', 'Google Ads', 'Performance dos anúncios-pbb-abr-26.csv')
print("=== GOOGLE ADS CSV ===")
# Read raw first to see structure
with open(ga_path, encoding='utf-8-sig') as f:
    for i, line in enumerate(f):
        if i < 5:
            print(f"  L{i}: {line.rstrip()[:120]}")
        else:
            break

# =============================================
# 2. ANALISE_YOUTUBE CSV (processado)
# =============================================
yt_path = os.path.join(base, 'analises', '[PBB-ABR-26]', 'ANALISE_YOUTUBE_[PBB-ABR-26].csv')
print("\n=== ANALISE_YOUTUBE CSV ===")
yt = pd.read_csv(yt_path, encoding='utf-8-sig')
print(f"Colunas: {yt.columns.tolist()}")
print(f"Linhas: {len(yt)}")
print(yt.head(3).to_string())

# =============================================
# 3. Excel "Anúncios [PBB-ABR-26]"
# =============================================
xl_path = os.path.join(base, 'Anúncios [PBB-ABR-26] (7).xlsx')
print("\n=== EXCEL ANÚNCIOS ===")
xl = pd.ExcelFile(xl_path)
print(f"Abas: {xl.sheet_names}")
