# -*- coding: utf-8 -*-
"""Exploração focada dos novos CSVs — corrigindo erros do primeiro script."""
import pandas as pd

# ── HOTMART ────────────────────────────────────────────────────────────────────
hpath = r"analises\[PBB-ABR-26]\Vendas\hotmart pbb-abr-26.csv"
hdf = pd.read_csv(hpath, sep=";", encoding="utf-8")

print("HOTMART — primeiros valores de Faturamento bruto:")
print(hdf["Faturamento bruto (sem impostos)"].head(10).tolist())
print()
print("HOTMART — primeiros valores de Faturamento líquido do(a) Produtor(a):")
print(hdf["Faturamento líquido do(a) Produtor(a)"].head(10).tolist())
print()

# Descobrir o formato real da coluna
col_bruto = "Faturamento bruto (sem impostos)"
col_liq   = "Faturamento líquido do(a) Produtor(a)"
col_liqt  = "Faturamento líquido"

print(f"dtype bruto: {hdf[col_bruto].dtype}")
print(f"Sample bruto: {hdf[col_bruto].dropna().head(5).tolist()}")
print(f"dtype liq prod: {hdf[col_liq].dtype}")
print(f"Sample liq prod: {hdf[col_liq].dropna().head(5).tolist()}")
print(f"Sample liq total: {hdf[col_liqt].dropna().head(5).tolist()}")

# Tipo de cobrança breakdown
print("\nTipo de cobrança:")
print(hdf["Tipo de cobrança"].value_counts().to_dict())

# Filtrar SEM Recuperador Inteligente
hdf_sem_ri = hdf[hdf["Tipo de cobrança"] != "Recuperador Inteligente"]
print(f"\nSem RI: {len(hdf_sem_ri)} rows")

# Se as colunas são numéricas:
if hdf[col_bruto].dtype in ["float64", "int64"]:
    print(f"Bruto (sem RI): R$ {hdf_sem_ri[col_bruto].sum():,.2f}")
    print(f"Liq prod (sem RI): R$ {hdf_sem_ri[col_liq].sum():,.2f}")
    print(f"Ticket médio bruto: R$ {hdf_sem_ri[col_bruto].mean():,.2f}")
else:
    # tentar converter
    def br2f(x):
        if pd.isna(x): return 0.0
        s = str(x).strip().replace("R$","").strip()
        s = s.replace(".","").replace(",",".")
        try: return float(s)
        except: return 0.0

    hdf_sem_ri = hdf_sem_ri.copy()
    hdf_sem_ri["_bruto"] = hdf_sem_ri[col_bruto].apply(br2f)
    hdf_sem_ri["_liq"]   = hdf_sem_ri[col_liq].apply(br2f)
    print(f"Bruto (sem RI): R$ {hdf_sem_ri['_bruto'].sum():,.2f}")
    print(f"Liq prod (sem RI): R$ {hdf_sem_ri['_liq'].sum():,.2f}")
    print(f"Ticket médio bruto: R$ {hdf_sem_ri['_bruto'].mean():,.2f}")

# Forma de pagamento sem RI
print("\nMétodo de pagamento (sem RI):")
print(hdf_sem_ri["Método de pagamento"].value_counts().to_dict())

# Parcelamento sem RI
print("\nQuantidade total de parcelas (sem RI):")
print(hdf_sem_ri["Quantidade total de parcelas"].value_counts().sort_index().to_dict())

# Estado sem RI
print("\nEstado / Província (sem RI) top 10:")
print(hdf_sem_ri["Estado / Província"].value_counts().head(10).to_dict())

# Cidade sem RI top 10
print("\nCidade (sem RI) top 8:")
print(hdf_sem_ri["Cidade"].value_counts().head(8).to_dict())

# Timeline sem RI
hdf_sem_ri = hdf_sem_ri.copy()
hdf_sem_ri["_dt"] = pd.to_datetime(hdf_sem_ri["Data da transação"], dayfirst=True, errors="coerce")
print("\nTimeline D1 (sem RI):")
print(hdf_sem_ri["_dt"].dt.date.value_counts().sort_index().to_dict())

print("\n")
print("=" * 60)
print("TMB — tmb pbb-abr-26.csv")
print("=" * 60)

tpath = r"analises\[PBB-ABR-26]\Vendas\tmb pbb-abr-26.csv"
# TMB encoding may be latin-1 due to garbled chars in first run
for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
    try:
        tdf = pd.read_csv(tpath, sep=";", encoding=enc)
        # test for garbled
        sample = " ".join(str(c) for c in tdf.columns)
        if "ç" in sample or "ã" in sample or "ê" in sample:
            print(f"TMB encoding: {enc}")
            break
        elif enc == "cp1252":
            print(f"TMB encoding (fallback): {enc}")
    except Exception as e:
        print(f"  {enc} failed: {e}")

print(f"Total rows: {len(tdf)}")
print("Colunas:", list(tdf.columns))

# Status
print("\nStatus Pedido:", tdf["Status Pedido"].value_counts().to_dict())

# Situação
sit_cols = [c for c in tdf.columns if "situa" in c.lower() or "situ" in c.lower()]
print(f"Situação cols: {sit_cols}")
for c in sit_cols:
    print(f"  {c}: {tdf[c].value_counts().to_dict()}")

# Filter: Em Dia (new status name)
tdf_ok = tdf[tdf["Status Pedido"] == "Em Dia"]
print(f"\nEm Dia: {len(tdf_ok)} rows")

# Ticket
print("\nTicket do pedido (primeiros valores):")
print(tdf["Ticket do pedido"].head(10).tolist())
print(f"dtype: {tdf['Ticket do pedido'].dtype}")
if tdf["Ticket do pedido"].dtype in ["float64","int64"]:
    total = tdf_ok["Ticket do pedido"].sum()
    ticket = tdf_ok["Ticket do pedido"].mean()
    print(f"Total: R$ {total:,.2f} | Ticket médio: R$ {ticket:,.2f}")
else:
    def br2f(x):
        if pd.isna(x): return 0.0
        s = str(x).strip().replace("R$","").strip()
        s = s.replace(".","").replace(",",".")
        try: return float(s)
        except: return 0.0
    tdf_ok = tdf_ok.copy()
    tdf_ok["_v"] = tdf_ok["Ticket do pedido"].apply(br2f)
    print(f"Total: R$ {tdf_ok['_v'].sum():,.2f} | Ticket médio: R$ {tdf_ok['_v'].mean():,.2f}")

# Oferta
print("\nNome da Oferta (Em Dia):")
print(tdf_ok["Nome da Oferta"].value_counts().to_dict())

# UTM
utm_cols = [c for c in tdf.columns if "utm" in c.lower()]
print(f"\nUTM cols: {utm_cols}")
for c in utm_cols[:4]:
    vals = tdf_ok[c].value_counts().head(6).to_dict()
    none_count = tdf_ok[c].isna().sum() + (tdf_ok[c] == "(none)").sum()
    print(f"  {c}: {vals} | sem UTM: {none_count}")

# Forma de pagamento
print("\nForma de Pagamento (Em Dia):")
print(tdf_ok["Forma de Pagamento"].value_counts().to_dict())

# Timeline
tdf_ok = tdf_ok.copy()
tdf_ok["_dt"] = pd.to_datetime(tdf_ok["Criado em"], dayfirst=True, errors="coerce")
print("\nTimeline (Em Dia):")
print(tdf_ok["_dt"].dt.date.value_counts().sort_index().to_dict())

# Geo
print("\nEstado (Em Dia) top 10:")
print(tdf_ok["Estado"].value_counts().head(10).to_dict())
print("\nCidade (Em Dia) top 8:")
print(tdf_ok["Cidade"].value_counts().head(8).to_dict())

# Tipo do pedido
print("\nTipo do pedido (Em Dia):")
print(tdf_ok["Tipo do pedido"].value_counts().to_dict())
