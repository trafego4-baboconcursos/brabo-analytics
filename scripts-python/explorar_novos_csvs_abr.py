# -*- coding: utf-8 -*-
"""Explorar os novos CSVs de vendas PBB-ABR-26."""
import pandas as pd

def br2f(x):
    if pd.isna(x): return 0.0
    s = str(x).strip().replace("R$","").strip()
    s = s.replace(".","").replace(",",".")
    try: return float(s)
    except: return 0.0

print("=" * 60)
print("HOTMART — hotmart pbb-abr-26.csv")
print("=" * 60)

hpath = r"analises\[PBB-ABR-26]\Vendas\hotmart pbb-abr-26.csv"
hdf = pd.read_csv(hpath, sep=";", encoding="utf-8")
print(f"Total rows: {len(hdf)}")
print(f"Colunas ({len(hdf.columns)}):")
for c in hdf.columns:
    print(f"  {c!r}")

print("\nStatus da transação:")
print(hdf["Status da transação"].value_counts().to_dict())

# Tipo de cobrança / RI check
tipo_cols = [c for c in hdf.columns if any(k in c.lower() for k in ["tipo", "cobran", "modalidade", "recuper"])]
print(f"\nColunas tipo/cobrança: {tipo_cols}")
for c in tipo_cols:
    print(f"  {c}: {hdf[c].value_counts().to_dict()}")

# Pagamento
pag_cols = [c for c in hdf.columns if any(k in c.lower() for k in ["pagamento", "pix", "cartao", "cartão", "forma"])]
print(f"\nColunas pagamento: {pag_cols}")
for c in pag_cols[:4]:
    print(f"  {c}: {hdf[c].value_counts().to_dict()}")

# Faturamento
print("\nFaturamento bruto (sem impostos):")
hdf["_bruto"] = hdf["Faturamento bruto (sem impostos)"].apply(br2f)
print(f"  Sum: R$ {hdf['_bruto'].sum():,.2f}")
print(f"  Ticket médio: R$ {hdf['_bruto'].mean():,.2f}")

print("\nFaturamento líquido do(a) Produtor(a):")
hdf["_liq"] = hdf["Faturamento líquido do(a) Produtor(a)"].apply(br2f)
print(f"  Sum: R$ {hdf['_liq'].sum():,.2f}")

# Data
date_cols = [c for c in hdf.columns if "data" in c.lower() or "date" in c.lower()]
print(f"\nColunas de data: {date_cols}")
if date_cols:
    col = date_cols[0]
    hdf["_dt"] = pd.to_datetime(hdf[col], dayfirst=True, errors="coerce")
    print(hdf["_dt"].dt.date.value_counts().sort_index().head(20).to_dict())

# Parcelamento
parc_cols = [c for c in hdf.columns if "parcel" in c.lower() or "insta" in c.lower()]
print(f"\nColunas parcelamento: {parc_cols}")
for c in parc_cols[:3]:
    print(f"  {c}: {hdf[c].value_counts().head(10).to_dict()}")

# Afiliado
afil_cols = [c for c in hdf.columns if "afili" in c.lower()]
print(f"\nColunas afiliado: {afil_cols}")
for c in afil_cols[:3]:
    print(f"  {c}: {hdf[c].value_counts().head(10).to_dict()}")

# Estado
geo_cols = [c for c in hdf.columns if any(k in c.lower() for k in ["estado", "cidade", "uf", "estado"])]
print(f"\nColunas geo: {geo_cols}")
for c in geo_cols[:3]:
    print(f"  {c}: {hdf[c].value_counts().head(8).to_dict()}")

print()
print("=" * 60)
print("TMB — tmb pbb-abr-26.csv")
print("=" * 60)

tpath = r"analises\[PBB-ABR-26]\Vendas\tmb pbb-abr-26.csv"
tdf = pd.read_csv(tpath, sep=";", encoding="utf-8")
print(f"Total rows: {len(tdf)}")
print(f"Colunas ({len(tdf.columns)}):")
for c in tdf.columns:
    print(f"  {c!r}")

print("\nStatus Pedido:")
status_col = [c for c in tdf.columns if "status" in c.lower()][0]
print(tdf[status_col].value_counts().to_dict())

# Filtrar vigentes/efetivados
mask = tdf[status_col].str.lower().isin(["vigente", "efetivado"])
tdf_ok = tdf[mask]
print(f"\nVigente/Efetivado: {len(tdf_ok)} rows")

# Valor
val_cols = [c for c in tdf.columns if any(k in c.lower() for k in ["valor", "total", "preco", "preço"])]
print(f"\nColunas valor: {val_cols}")
for c in val_cols[:4]:
    tdf["_v"] = tdf[c].apply(br2f)
    ok_sum = tdf_ok[c].apply(br2f).sum()
    print(f"  {c}: total={tdf['_v'].sum():,.2f} | vigentes={ok_sum:,.2f}")

# Data
date_cols = [c for c in tdf.columns if "data" in c.lower() or "date" in c.lower()]
print(f"\nColunas data: {date_cols}")
if date_cols:
    col = date_cols[0]
    tdf["_dt"] = pd.to_datetime(tdf[col], dayfirst=True, errors="coerce")
    print(tdf_ok["_dt"].dt.date.value_counts().sort_index().head(20).to_dict())

# Oferta
oferta_cols = [c for c in tdf.columns if any(k in c.lower() for k in ["oferta", "plano", "produto", "nome"])]
print(f"\nColunas oferta/produto: {oferta_cols}")
for c in oferta_cols[:4]:
    print(f"  {c}: {tdf_ok[c].value_counts().head(6).to_dict()}")

# UTM
utm_cols = [c for c in tdf.columns if "utm" in c.lower()]
print(f"\nColunas UTM: {utm_cols}")
for c in utm_cols[:5]:
    print(f"  {c}: {tdf_ok[c].value_counts().head(6).to_dict()}")

# Geo
geo_cols = [c for c in tdf.columns if any(k in c.lower() for k in ["estado", "cidade", "uf"])]
print(f"\nColunas geo: {geo_cols}")
for c in geo_cols[:3]:
    print(f"  {c}: {tdf_ok[c].value_counts().head(8).to_dict()}")
