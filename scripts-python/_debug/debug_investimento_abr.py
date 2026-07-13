#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path

BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")

def br2f(v):
    if pd.isna(v) or v == "" or v == "--": return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

# Meta ABR
ma = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv", encoding="utf-8")
ma["inv"] = ma["Valor usado (BRL)"].apply(br2f)
is_cap_ma = ma["Nome da campanha"].astype(str).str.lower().str.contains("capta", na=False) if "Nome da campanha" in ma.columns else pd.Series([True]*len(ma))
print("=== META ADS ABR ===")
print(f"  Total Meta:      R$ {ma['inv'].sum():,.2f}")
print(f"  Meta captacao:   R$ {ma[is_cap_ma]['inv'].sum():,.2f}")
print(f"  Meta outros:     R$ {ma[~is_cap_ma]['inv'].sum():,.2f}")

# Google ABR
ga = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Google Ads/Performance da campanha-pbb-abr-26.csv", skiprows=2, encoding="utf-8")
ga["Custo"] = ga["Custo"].apply(br2f)
ga["prefixo"] = ga["Campanha"].astype(str).str[:4]
is_cap_ga = ga["Campanha"].astype(str).str.lower().str.contains("capta", na=False) if "Campanha" in ga.columns else pd.Series([True]*len(ga))
ga_other = ga[~is_cap_ga]

print("\n=== GOOGLE ADS ABR ===")
print(f"  Total Google:    R$ {ga['Custo'].sum():,.2f}")
print(f"  Google captacao: R$ {ga[is_cap_ga]['Custo'].sum():,.2f}")
print(f"  Google outros:   R$ {ga_other['Custo'].sum():,.2f}")
print("\n  Custo por prefixo:")
for pfx, custo in ga.groupby("prefixo")["Custo"].sum().sort_values(ascending=False).items():
    print(f"    {pfx}: R$ {custo:,.2f}")

print("\n  Campanhas [MA] no Google Ads CSV:")
ma_in_ga = ga[ga["Campanha"].astype(str).str.startswith("[MA]")]
if len(ma_in_ga):
    for _, row in ma_in_ga.iterrows():
        print(f"    {row['Campanha'][:60]}  -> R$ {row['Custo']:,.2f}")
else:
    print("    (nenhuma)")

total_inv = ma["inv"].sum() + ga["Custo"].sum()
total_cap = ma[is_cap_ma]["inv"].sum() + ga[is_cap_ga]["Custo"].sum()
total_other = ma[~is_cap_ma]["inv"].sum() + ga[~is_cap_ga]["Custo"].sum()
print(f"\n=== TOTAIS COMBINADOS ABR ===")
print(f"  Investimento total:         R$ {total_inv:,.2f}")
print(f"  Captacao (Meta+Google):     R$ {total_cap:,.2f}")
print(f"  Outros  (Meta+Google):      R$ {total_other:,.2f}")
print(f"  cap + outros = R$ {(total_cap+total_other):,.2f} (deve = total)")
