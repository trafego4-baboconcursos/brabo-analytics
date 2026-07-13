import pandas as pd
import os

base = r'c:\Users\trafe\OneDrive\Desktop\workspace-mmm'
xl_path = os.path.join(base, 'Anúncios [PBB-ABR-26] (7).xlsx')
xl = pd.ExcelFile(xl_path)

# Ler todas as abas relevantes
for aba in xl.sheet_names:
    df = xl.parse(aba)
    print(f"\n{'='*60}")
    print(f"ABA: {aba}")
    print(f"Forma: {df.shape}")
    print(f"Colunas: {df.columns.tolist()}")
    print(df.head(5).to_string())
    print()
