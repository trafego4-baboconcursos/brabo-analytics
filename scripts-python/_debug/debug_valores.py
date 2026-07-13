import pandas as pd, re, os, glob

def limpar_numero(value):
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    text = str(value).strip()
    if ";" in text: text = text.split(";", 1)[0]
    if "," in text and "." in text: text = text.replace(".", "").replace(",", ".")
    elif "," in text: text = text.replace(",", ".")
    text = re.sub(r"[^\d\-.]", "", text)
    try: return float(text)
    except: return 0.0

hm_fev = pd.read_csv(r"analises\[PBB-FEV-26]\Vendas\hotmart-pbb-fev-26.csv", sep=";", encoding="utf-8")
hm_fev["v"] = hm_fev["Faturamento bruto (sem impostos)"].apply(limpar_numero)
tipo_col = next((c for c in hm_fev.columns if "Tipo" in c and "cobran" in c.lower()), None)
print(f"Coluna tipo cobranca FEV-26: {tipo_col!r}")
if tipo_col:
    for tipo, grp in hm_fev.groupby(tipo_col):
        print(f"  {tipo[:50]}: {len(grp)} linhas  media={grp.v.mean():.2f}  total={grp.v.sum():,.2f}")
    ri_fev = hm_fev[hm_fev[tipo_col] == "Recuperador Inteligente"]
    print(f"RI no FEV-26: {len(ri_fev)} linhas  total={ri_fev.v.sum():,.2f}")
print(f"Min: {h['valor'].min():.2f}")
print(f"Max: {h['valor'].max():.2f}")
print(f"\nDistribuição:")
print(h['valor'].describe())
print(f"\nPrimeiros 10 valores:")
print(h[['Email do(a) Comprador(a)', 'Faturamento bruto (sem impostos)', 'valor']].head(10).to_string())
