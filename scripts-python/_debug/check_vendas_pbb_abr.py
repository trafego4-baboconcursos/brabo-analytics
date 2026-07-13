import pandas as pd, re

HM_FILE = r"analises\[PBB-ABR-26]\Vendas\hotmart-pbb-abr-26.csv"
TMB_FILE = r"analises\[PBB-ABR-26]\Vendas\tmb-pbb-abr-26.csv"

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

# ---------- HOTMART ----------
hm = pd.read_csv(HM_FILE, sep=";", encoding="utf-8")
hm["email_n"] = hm["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
hm["v"] = hm["Faturamento bruto (sem impostos)"].apply(limpar_numero)

print("=== HOTMART - Status da transacao ===")
for st, grp in hm.groupby("Status da transação"):
    print(f"  {st}: {len(grp):,} linhas  R$ {grp['v'].sum():,.2f}")

print()
print("=== HOTMART - Tipo de cobranca ===")
for st, grp in hm.groupby("Tipo de cobrança"):
    print(f"  {st[:50]}: {len(grp):,} linhas  {grp['email_n'].nunique()} únicos  R$ {grp['v'].sum():,.2f}")

print()
ri = hm[hm["Tipo de cobrança"] == "Recuperador Inteligente"]
par = hm[hm["Tipo de cobrança"].str.startswith("Parcelado")]
av = hm[hm["Tipo de cobrança"] == "Apenas à vista"]
print(f"Recuperador Inteligente - emails que também estão em Parcelado: {len(set(ri.email_n) & set(par.email_n))}")
print(f"Recuperador Inteligente - emails que também estão em À Vista: {len(set(ri.email_n) & set(av.email_n))}")
print(f"Recuperador Inteligente - emails exclusivos (não aparecem em outro tipo): {len(set(ri.email_n) - set(par.email_n) - set(av.email_n))}")

print()
print(f"HM - emails unicos (todos os tipos): {hm['email_n'].nunique()}")
print(f"HM - emails com mais de 1 linha: {(hm['email_n'].value_counts() > 1).sum()}")

# ---------- TMB ----------
try:
    tmb = pd.read_csv(TMB_FILE, sep=";", encoding="utf-8")
except:
    tmb = pd.read_csv(TMB_FILE, sep=";", encoding="latin-1")
tmb["v"] = tmb["Ticket do pedido"].apply(limpar_numero)
tmb["email_n"] = tmb["E-mail do Cliente"].astype(str).str.lower().str.strip()

print()
print("=== TMB - Status Pedido ===")
for st, grp in tmb.groupby("Status Pedido"):
    print(f"  {st}: {len(grp):,}  R$ {grp['v'].sum():,.2f}")

# ---------- RESUMO FINAL ----------
hm_ap = hm[hm["Status da transação"] == "Aprovado"]
hm_co = hm[hm["Status da transação"] == "Completo"]
hm_valido = hm[hm["Status da transação"].isin(["Aprovado", "Completo"])]
hm_sem_ri = hm_valido[hm_valido["Tipo de cobrança"] != "Recuperador Inteligente"]
tmb_ok = tmb[tmb["Status Pedido"] == "Em Dia"]

print()
print("=== RESUMO FINAL ===")
print(f"Hotmart ALL (sem filtro):           {len(hm):,} linhas   R$ {hm['v'].sum():,.2f}")
print(f"  Aprovado:                         {len(hm_ap):,} linhas   R$ {hm_ap['v'].sum():,.2f}")
print(f"  Completo:                         {len(hm_co):,} linhas   R$ {hm_co['v'].sum():,.2f}")
print(f"Hotmart sem Recuperador Inteligente:{len(hm_sem_ri):,} linhas   R$ {hm_sem_ri['v'].sum():,.2f}")
print(f"TMB Em Dia:                         {len(tmb_ok):,} linhas   R$ {tmb_ok['v'].sum():,.2f}")
print()
print(f"CENARIO A - HM ALL + TMB Em Dia:    {len(hm)+len(tmb_ok):,}  R$ {hm['v'].sum()+tmb_ok['v'].sum():,.2f}")
print(f"CENARIO B - HM sem RI + TMB Em Dia: {len(hm_sem_ri)+len(tmb_ok):,}  R$ {hm_sem_ri['v'].sum()+tmb_ok['v'].sum():,.2f}")
print(f"CENARIO C - HM Aprovado + TMB:      {len(hm_ap)+len(tmb_ok):,}  R$ {hm_ap['v'].sum()+tmb_ok['v'].sum():,.2f}")
