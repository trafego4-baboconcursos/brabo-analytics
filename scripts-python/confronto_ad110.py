import pandas as pd
from pathlib import Path

# META ADS PLATFORM
meta = pd.read_csv("analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-Completas-PBB-ABR-26.csv", encoding="utf-8-sig")
ad_col = [c for c in meta.columns if "ncio" in c and "conjunto" not in c and ".1" not in c][0]

r110 = meta[meta[ad_col].astype(str).str.startswith("AD110", na=False)].copy()
r110["spend"] = pd.to_numeric(r110["Valor usado (BRL)"].astype(str).str.replace(",","."), errors="coerce")
r110["leads_p"] = pd.to_numeric(r110["Leads"].astype(str).str.replace(",","."), errors="coerce")

total_spend = r110["spend"].sum()
total_leads_meta = r110["leads_p"].sum()

print("=== META ADS PLATFORM - AD110 ===")
print(f"Spend total: R$ {total_spend:,.2f}")
print(f"Leads plataforma: {total_leads_meta:.0f}")
if total_leads_meta > 0:
    print(f"CPL plataforma: R$ {total_spend/total_leads_meta:.2f}")
print()
print("Por variante de anuncio:")
for nome, grp in r110.groupby(ad_col):
    s = grp["spend"].sum()
    l = grp["leads_p"].sum()
    cpl = f"R$ {s/l:.2f}" if l > 0 else "n/a"
    print(f"  [{nome}]  Spend: R$ {s:,.2f} | Leads: {l:.0f} | CPL: {cpl}")

# CRM
df = pd.read_csv("analises/[PBB-ABR-26]/Active Campaign/PBB-ABR-14h-12-05-26.csv", sep=",", encoding="utf-8", low_memory=False)
df["Email"] = df["Email"].str.strip().str.lower()
df_c = df[df["*Utm_content"].notna()].copy()

def normalizar(v):
    t = str(v).strip()
    return t.split(" - ")[0].strip().upper() if " - " in t else t.strip().upper()

df_c["criativo"] = df_c["*Utm_content"].astype(str).str.strip().apply(normalizar)
ad110_crm = df_c[df_c["criativo"] == "AD110"]

fb_l = ad110_crm[ad110_crm["*Utm_source"].astype(str).str.startswith("fb-")]
yt_l = ad110_crm[ad110_crm["*Utm_source"].astype(str).str.startswith("yt-")]

print()
print("=== CRM (ActiveCampaign) - AD110 ===")
print(f"Meta/Facebook (fb-*):  {len(fb_l):>6} leads")
for src, cnt in fb_l["*Utm_source"].value_counts().items():
    print(f"      {cnt:>6}  {src}")
print(f"Google/YouTube (yt-*): {len(yt_l):>6} leads")
for src, cnt in yt_l["*Utm_source"].value_counts().items():
    print(f"      {cnt:>6}  {src}")
print(f"TOTAL CRM:             {len(ad110_crm):>6} leads")

print()
print("=== CONFRONTO META: PLATAFORMA vs CRM ===")
print(f"Meta Ads platform:  {total_leads_meta:.0f} leads")
print(f"CRM (fb-* utms):   {len(fb_l)} leads")
if total_leads_meta > 0:
    gap = len(fb_l) - int(total_leads_meta)
    print(f"GAP CRM - Platform: {gap:+d} leads ({gap/total_leads_meta*100:+.1f}%)")

print()
print("=== UTM CONTENT VARIANTS (raw) ===")
for val, cnt in ad110_crm["*Utm_content"].value_counts().items():
    print(f"  {cnt:>6}  {val}")

# Google Ads
gpath = Path("analises/[PBB-ABR-26]/Google Ads")
print()
print("=== GOOGLE ADS FILES ===")
if gpath.exists():
    for f in sorted(gpath.iterdir()):
        print(" ", f.name)
    # Try to find AD110 in Google performance ads CSV
    for f in gpath.iterdir():
        if "nuncio" in f.name.lower() or "ad" in f.name.lower() or "performance" in f.name.lower():
            try:
                g = pd.read_csv(f, encoding="utf-8", skiprows=2)
                ncols = [c for c in g.columns if "ncio" in c and "conjunto" not in c]
                if ncols:
                    nc = ncols[0]
                    g110 = g[g[nc].astype(str).str.startswith("AD110", na=False)]
                    if len(g110) > 0:
                        g110["cost"] = pd.to_numeric(g110["Custo"].astype(str).str.replace(",","."), errors="coerce")
                        print(f"\n  AD110 no Google Ads [{f.name}]: {len(g110)} rows")
                        print(f"  Custo: R$ {g110['cost'].sum():,.2f}")
            except Exception as e:
                pass
else:
    print("  Pasta nao encontrada")
