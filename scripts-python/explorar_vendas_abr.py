#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exploração dos dados de vendas Hotmart e TMB para PBB-ABR-26."""
import pandas as pd
import numpy as np
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

# ─────────────────────────── HOTMART ───────────────────────────────────────
hm = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv", sep=";")
tipo_col = next((c for c in hm.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
if tipo_col:
    hm = hm[hm[tipo_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
hm["valor"] = hm["Faturamento bruto (sem impostos)"].apply(br2f)
hm["liquido"] = hm["Faturamento líquido"].apply(br2f) if "Faturamento líquido" in hm.columns else hm["valor"]
hm["data"] = pd.to_datetime(hm["Data da transação"], dayfirst=True, errors="coerce")

print("=" * 60)
print("HOTMART PBB-ABR-26")
print("=" * 60)
print(f"Total transações: {len(hm)}")
print(f"Faturamento bruto: R$ {hm['valor'].sum():,.2f}")
print(f"Faturamento líquido: R$ {hm['liquido'].sum():,.2f}")
print(f"Ticket médio bruto: R$ {hm['valor'].mean():,.2f}")
print(f"Ticket médio líquido: R$ {hm['liquido'].mean():,.2f}")
print()

print("-- STATUS --")
print(hm["Status da transação"].value_counts().to_string())

print()
print("-- MÉTODO DE PAGAMENTO --")
mp = hm.groupby("Método de pagamento").agg(
    qtd=("valor","count"), fat=("valor","sum"), ticket_medio=("valor","mean")
).sort_values("fat", ascending=False)
print(mp.to_string())

print()
print("-- PARCELAS (cartão) --")
parc = hm[hm["Método de pagamento"].astype(str).str.lower().str.contains("cart", na=False)]
print(parc["Quantidade total de parcelas"].value_counts().sort_index().to_string())

print()
print("-- NOME DO PREÇO (oferta) --")
of = hm.groupby("Nome deste preço").agg(
    qtd=("valor","count"), fat=("valor","sum"), ticket=("valor","mean")
).sort_values("fat", ascending=False)
print(of.to_string())

print()
print("-- TIPO DE COBRANÇA --")
print(hm["Tipo de cobrança"].value_counts().to_string())

print()
print("-- TOP 12 ESTADOS --")
est = hm.groupby("Estado / Província").agg(
    qtd=("valor","count"), fat=("valor","sum")
).sort_values("qtd", ascending=False).head(12)
print(est.to_string())

print()
print("-- TOP 10 CIDADES --")
cid = hm.groupby("Cidade").agg(
    qtd=("valor","count"), fat=("valor","sum")
).sort_values("qtd", ascending=False).head(10)
print(cid.to_string())

print()
print("-- CANAL --")
print(hm["Canal usado para venda"].value_counts().to_string())

print()
print("-- VENDAS POR DIA --")
if hm["data"].notna().sum() > 0:
    dv = hm.groupby(hm["data"].dt.date).agg(vendas=("valor","count"), fat=("valor","sum"))
    print(dv.to_string())

print()
print("-- CÓDIGO SRC (UTM source) --")
print(hm["Código SRC"].value_counts().head(15).to_string())

print()
print("-- AFILIADO --")
print(hm["Nome do(a) Afiliado(a)"].value_counts().head(10).to_string())

print()
print("-- TAXA PROCESSAMENTO MÉDIA por método --")
hm["taxa_proc"] = hm["Taxa de processamento"].apply(br2f)
tproc = hm.groupby("Método de pagamento")["taxa_proc"].agg(["mean","sum"])
print(tproc.to_string())

print()
print("-- FATURAMENTO BRUTO vs LIQUIDO (diferença = taxas) --")
hm["taxas"] = hm["valor"] - hm["liquido"]
print(f"  Total taxas: R$ {hm['taxas'].sum():,.2f}")
print(f"  Pct médio: {hm['taxas'].sum()/hm['valor'].sum()*100:.2f}%")

# ─────────────────────────── TMB ───────────────────────────────────────────
print()
print("=" * 60)
print("TMB PBB-ABR-26")
print("=" * 60)

tmb = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv", sep=";", encoding="latin-1")
accepted = {"vigente", "efetivado"}
status_col = next((c for c in tmb.columns if "situa" in c.lower()), None)
if status_col:
    mask = tmb[status_col].astype(str).str.strip().str.lower().isin(accepted)
    tmb = tmb[mask].copy()
tmb["valor"] = tmb["Ticket do pedido"].astype(str).apply(br2f)
tmb["data_criacao"] = pd.to_datetime(tmb["Criado em"], dayfirst=True, errors="coerce")
tmb["data_efetivado"] = pd.to_datetime(tmb["Data Efetivado"], dayfirst=True, errors="coerce")

print(f"Total boletos vigentes: {len(tmb)}")
print(f"Faturamento: R$ {tmb['valor'].sum():,.2f}")
print(f"Ticket médio: R$ {tmb['valor'].mean():,.2f}")
print()

print("-- SITUAÇÃO ORIGINAL (antes do filtro) --")
tmb_raw = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv", sep=";", encoding="latin-1")
if status_col: print(tmb_raw[status_col].value_counts().to_string())

print()
print("-- FORMA DE PAGAMENTO --")
print(tmb["Forma de Pagamento"].value_counts().to_string())

print()
print("-- NOME DA OFERTA --")
of_tmb = tmb.groupby("Nome da Oferta").agg(
    qtd=("valor","count"), fat=("valor","sum"), ticket=("valor","mean")
).sort_values("fat", ascending=False)
print(of_tmb.to_string())

print()
print("-- TOP ESTADOS --")
est_tmb = tmb.groupby("Estado").agg(
    qtd=("valor","count"), fat=("valor","sum")
).sort_values("qtd", ascending=False).head(12)
print(est_tmb.to_string())

print()
print("-- TOP CIDADES --")
cid_tmb = tmb.groupby("Cidade").agg(
    qtd=("valor","count"), fat=("valor","sum")
).sort_values("qtd", ascending=False).head(10)
print(cid_tmb.to_string())

print()
print("-- VENDAS POR DIA (criação) --")
if tmb["data_criacao"].notna().sum() > 0:
    dv_tmb = tmb.groupby(tmb["data_criacao"].dt.date).agg(
        vendas=("valor","count"), fat=("valor","sum")
    )
    print(dv_tmb.to_string())

print()
print("-- UTM SOURCE --")
print(tmb["utm_source"].value_counts().head(15).to_string())

print()
print("-- TIPO DO PEDIDO --")
print(tmb["Tipo do pedido"].value_counts().to_string())

print()
print("-- STATUS PEDIDO --")
print(tmb["Status Pedido"].value_counts().to_string())

print()
print("-- STATUS CANCELAMENTO (vigentes) --")
print(tmb["Status Cancelamento"].value_counts().to_string())
