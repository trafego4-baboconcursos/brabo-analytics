import pandas as pd
from pathlib import Path

gpath = Path("analises/[PBB-ABR-26]/Google Ads")
g = pd.read_csv(list(gpath.glob("Performance dos*"))[0], encoding="utf-8", skiprows=2)
nc = [c for c in g.columns if "ncio" in c and "grupo" not in c.lower() and "campanha" not in c.lower() and ".1" not in c and "URL" not in c and "final" not in c.lower()][0]
print("Using col:", nc)

# Check AD110 in nome do anuncio
g110 = g[g[nc].astype(str).str.upper().str.contains("AD110", na=False)]
print("AD110 rows in Google Ads (nome):", len(g110))

# Check parametro personalizado for _adname=ad110
param_col = [c for c in g.columns if "arametro" in c and "sonaliz" in c]
print("Param col:", param_col)
if param_col:
    pc = param_col[0]
    p110 = g[g[pc].astype(str).str.contains("ad110", case=False, na=False)]
    print(f"Rows with _adname=ad110 in parametro: {len(p110)}")
    if len(p110) > 0:
        p110 = p110.copy()
        p110["cost"] = pd.to_numeric(p110["Custo"].astype(str).str.replace(",","."), errors="coerce")
        print(f"Google/YouTube spend for ad110: R$ {p110['cost'].sum():,.2f}")
        print()
        for nm, grp in p110.groupby(nc):
            grp_c = grp.copy()
            grp_c["cost"] = pd.to_numeric(grp_c["Custo"].astype(str).str.replace(",","."), errors="coerce")
            print(f"  [{nm}]  Custo: R$ {grp_c['cost'].sum():,.2f} | Campanha: {grp_c['Campanha'].iloc[0][:60]}")

# Sample of principal campaigns ad names
print()
g_principal = g[g["Campanha"].astype(str).str.contains("principal", case=False, na=False)]
print("Ad names in principal campaigns (top 10):")
print(g_principal[nc].value_counts().head(10).to_string())
