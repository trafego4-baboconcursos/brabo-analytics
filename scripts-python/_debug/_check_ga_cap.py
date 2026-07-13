import pandas as pd
from pathlib import Path
BASE = Path(".")

def br_count(v):
    s = str(v).replace(".","").replace(",",".").strip()
    try: return float(s)
    except: return 0.0

def br2f(v):
    s = str(v).replace("R$","").replace(".","").replace(",",".").strip()
    try: return float(s)
    except: return 0.0

# Google FEV
ga_f = pd.read_csv(BASE / "analises/[PBB-FEV-26]/google ads/Performance da campanha-pbb-fev-26.csv", skiprows=2)
for col in ["Cliques","Impr.","Conversoes"]:
    c = next((x for x in ga_f.columns if col.lower() in x.lower()), None)
    if c: ga_f[c] = ga_f[c].apply(br_count)
if "Custo" in ga_f.columns: ga_f["Custo"] = ga_f["Custo"].apply(br2f)
cap_f = ga_f["Campanha"].astype(str).str.lower().str.contains("capta", na=False)
conv_col_f = next((c for c in ga_f.columns if "convers" in c.lower()), None)
print("=== FEV Google captacao ===")
print(ga_f[cap_f][["Campanha","Custo", conv_col_f]].to_string())
tot_custo_f = ga_f[cap_f]["Custo"].sum()
tot_conv_f  = ga_f[cap_f][conv_col_f].sum() if conv_col_f else 0
print(f"TOTAL cap FEV: Custo={tot_custo_f:.2f} | Conv={tot_conv_f:.0f} | CPA={tot_custo_f/tot_conv_f:.2f}" if tot_conv_f else f"TOTAL cap FEV: Custo={tot_custo_f:.2f} | Conv=0")
print(f"TOTAL all FEV: Custo={ga_f['Custo'].sum():.2f} | ncamp={len(ga_f)} | ncamp_cap={cap_f.sum()}")
print()

# Google ABR
ga_a = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Google Ads/Performance da campanha-pbb-abr-26.csv", skiprows=2)
for col in ["Cliques","Impr.","Conversoes"]:
    c = next((x for x in ga_a.columns if col.lower() in x.lower()), None)
    if c: ga_a[c] = ga_a[c].apply(br_count)
if "Custo" in ga_a.columns: ga_a["Custo"] = ga_a["Custo"].apply(br2f)
cap_a = ga_a["Campanha"].astype(str).str.lower().str.contains("capta", na=False)
conv_col_a = next((c for c in ga_a.columns if "convers" in c.lower()), None)
print("=== ABR Google captacao ===")
print(ga_a[cap_a][["Campanha","Custo", conv_col_a]].sort_values("Custo",ascending=False).to_string())
tot_custo_a = ga_a[cap_a]["Custo"].sum()
tot_conv_a  = ga_a[cap_a][conv_col_a].sum() if conv_col_a else 0
print(f"TOTAL cap ABR: Custo={tot_custo_a:.2f} | Conv={tot_conv_a:.0f} | CPA={tot_custo_a/tot_conv_a:.2f}" if tot_conv_a else f"TOTAL cap ABR: Custo={tot_custo_a:.2f} | Conv=0")
print(f"TOTAL all ABR: Custo={ga_a['Custo'].sum():.2f} | ncamp={len(ga_a)} | ncamp_cap={cap_a.sum()}")
print()
print("=== ABR Google NAO captacao ===")
print(ga_a[~cap_a][["Campanha","Custo", conv_col_a]].sort_values("Custo",ascending=False).to_string())
