#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPARATIVO_ABR_FEV_2026.html
Relatório detalhado: por que ABR-26 teve menos vendas investindo mais que FEV-26
"""

import pandas as pd
import csv as csvmod
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
OUT  = BASE / "analises" / "COMPARATIVO_ABR_FEV_2026.html"

LOGO    = "../img/logo-brabo-concursos.png"
FAVICON = "../img/favicon-brabo-concursos.png"

print("=" * 70)
print("COMPARATIVO PBB-ABR-26 vs PBB-FEV-26")
print("=" * 70)

# ── helpers ────────────────────────────────────────────────────────────────

def br2f(v):
    """Converte número para float. Suporta BR (1.234,56), standard (1234.56) e misto."""
    if pd.isna(v) or v == "" or v == "--": return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if "," in s and "." in s:
        # BR com milhar: 1.234,56 → remove ponto, troca vírgula
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Somente vírgula decimal: 1234,56 → 1234.56
        s = s.replace(",", ".")
    # Se só tem ponto: já é float padrão (1234.56), deixa como está
    try: return float(s)
    except: return 0.0

def br_count(v):
    """Converte contagens exportadas com milhar BR (65.811 / 8.476,00) em float."""
    if pd.isna(v) or v == "" or v == "--": return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def filtrar_tmb_validas(df):
    """Mantém apenas vendas válidas do TMB para evitar inflar total com cancelados."""
    accepted = {"vigente", "efetivado"}
    status_col = next((c for c in df.columns if "situa" in c.lower()), None)
    if status_col is None:
        status_col = next((c for c in df.columns if c.lower() == "status"), None)
    if status_col is None:
        return df.copy()
    status_norm = df[status_col].astype(str).str.strip().str.lower()
    return df[status_norm.isin(accepted)].copy()

def moeda(v):
    return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def intfmt(v):
    return f"{int(round(v)):,}".replace(",",".")

def pct(v):
    return f"{v:.2f}%".replace(".", ",")

def delta_badge(val, ref, invert=False, fmt="pct"):
    """Retorna HTML com delta colorido."""
    d = (val - ref) / ref * 100 if ref != 0 else 0
    is_good = (d >= 0) if not invert else (d <= 0)
    color = "#28a745" if is_good else "#dc3545"
    arrow = "▲" if d >= 0 else "▼"
    txt = f"{arrow} {abs(d):.1f}%"
    return f'<span style="color:{color};font-size:12px;font-weight:600">{txt}</span>'

def bar(pct_val, color="#667eea", height=8):
    w = min(max(pct_val, 0), 100)
    return f'<div style="height:{height}px;background:{color};border-radius:3px;width:{w:.0f}%;margin-top:4px"></div>'

# ── carregar FEV-26 ─────────────────────────────────────────────────────────

print("\n[1/8] Carregando FEV-26...")

crm_f = pd.read_csv(
    BASE / "analises/[PBB-FEV-26]/active-campaing/PBB-FEV-26-16h-12-05-26.csv",
    sep=",", quoting=csvmod.QUOTE_MINIMAL, low_memory=False
)
crm_f["email_n"] = crm_f["Email"].astype(str).str.lower().str.strip()
utm_f = next((c for c in crm_f.columns if "utm_source" in c.lower()), None)

hm_f_raw = pd.read_csv(BASE / "analises/[PBB-FEV-26]/vendas/hotmart pbb-fev-26.csv", sep=";", encoding="utf-8")
hm_f_raw["email_n"] = hm_f_raw["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
hm_f_raw = hm_f_raw[hm_f_raw["email_n"].str.contains("@", na=False)].copy()
# RI cobrança=1 × parcelas = valor total do contrato
_tipo_col_f = next((c for c in hm_f_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
if _tipo_col_f:
    _par_col_f  = "Quantidade total de parcelas"
    _cob_col_f  = "Quantidade de cobranças"
    _f_norm = hm_f_raw[hm_f_raw[_tipo_col_f].astype(str).str.strip() != "Recuperador Inteligente"].copy()
    _f_norm["valor"] = _f_norm["Faturamento líquido do(a) Produtor(a)"].apply(br2f)
    _f_ri = hm_f_raw[
        (hm_f_raw[_tipo_col_f].astype(str).str.strip() == "Recuperador Inteligente") &
        (pd.to_numeric(hm_f_raw[_cob_col_f], errors="coerce").fillna(0) == 1)
    ].copy()
    _f_ri[_par_col_f] = pd.to_numeric(_f_ri[_par_col_f], errors="coerce").fillna(1)
    _f_ri["valor"] = _f_ri["Faturamento líquido do(a) Produtor(a)"].apply(br2f) * _f_ri[_par_col_f]
    hm_f = pd.concat([_f_norm, _f_ri], ignore_index=True)
    hm_f["email_n"] = hm_f["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
else:
    hm_f = hm_f_raw.copy()
    hm_f["valor"] = hm_f["Faturamento líquido do(a) Produtor(a)"].apply(br2f)

tmb_f_raw = pd.read_csv(BASE / "analises/[PBB-FEV-26]/vendas/tmb pbb-fev-26.csv", sep=";", encoding="utf-8")
tmb_f = tmb_f_raw.copy()
tmb_f["email_n"] = tmb_f["E-mail do Cliente"].astype(str).str.lower().str.strip()
tmb_f["valor"]   = tmb_f["Ticket do pedido"].astype(str).apply(br2f)

ma_f = pd.read_csv(BASE / "analises/[PBB-FEV-26]/meta ads/MA-Campanhas-Completas-PBB-FEV-26.csv")
ma_leads_col_f = next((c for c in ma_f.columns if "lead" in c.lower() and "custo" not in c.lower()), None)
ma_inv_f  = ma_f["Valor usado (BRL)"].apply(br2f).sum()
_cap_f_ma = ma_f["Nome da campanha"].astype(str).str.lower().str.contains("capta", na=False) if "Nome da campanha" in ma_f.columns else pd.Series([True]*len(ma_f), index=ma_f.index)
ma_inv_f_cap   = ma_f[_cap_f_ma]["Valor usado (BRL)"].apply(br2f).sum()
ma_inv_f_other = ma_f[~_cap_f_ma]["Valor usado (BRL)"].apply(br2f).sum()
ma_leads_f = ma_f[ma_leads_col_f].apply(br2f).sum() if ma_leads_col_f else 0
ma_ads_f  = ma_f["Nome do anúncio"].nunique() if "Nome do anúncio" in ma_f.columns else 0

ga_c_f = pd.read_csv(BASE / "analises/[PBB-FEV-26]/google ads/Performance da campanha-pbb-fev-26.csv", skiprows=2)
for col in ["Cliques", "Impr.", "Conversões"]:
  if col in ga_c_f.columns:
    ga_c_f[col] = ga_c_f[col].apply(br_count)
if "Custo" in ga_c_f.columns:
  ga_c_f["Custo"] = ga_c_f["Custo"].apply(br2f)
ga_inv_f   = ga_c_f["Custo"].sum()
_cap_f_ga  = ga_c_f["Campanha"].astype(str).str.lower().str.contains("capta", na=False) if "Campanha" in ga_c_f.columns else pd.Series([True]*len(ga_c_f), index=ga_c_f.index)
ga_inv_f_cap   = ga_c_f[_cap_f_ga]["Custo"].sum()
ga_inv_f_other = ga_c_f[~_cap_f_ga]["Custo"].sum()
ga_clk_f   = ga_c_f["Cliques"].sum()
ga_impr_f  = ga_c_f["Impr."].sum()
ga_conv_f  = ga_c_f["Conversões"].sum()
ga_cpa_f   = ga_inv_f / ga_conv_f if ga_conv_f else 0
ga_cpc_f   = ga_inv_f / ga_clk_f  if ga_clk_f else 0
ga_ctr_f   = ga_clk_f / ga_impr_f * 100 if ga_impr_f else 0
ga_ncamp_f = len(ga_c_f)
_ga_conv_col_f  = next((c for c in ga_c_f.columns if "convers" in c.lower()), None)
ga_conv_cap_f   = ga_c_f[_cap_f_ga][_ga_conv_col_f].sum() if _ga_conv_col_f else 0
ga_cpa_cap_f    = ga_inv_f_cap / ga_conv_cap_f if ga_conv_cap_f else 0
ga_ncamp_cap_f  = int(_cap_f_ga.sum())

# totais FEV
fat_hm_f  = hm_f["valor"].sum()
fat_tmb_f = tmb_f["valor"].sum()
fat_f     = fat_hm_f + fat_tmb_f
nvend_f   = len(hm_f) + len(tmb_f)
ticket_f  = fat_f / nvend_f if nvend_f else 0
inv_f       = ma_inv_f + ga_inv_f
inv_f_cap   = ma_inv_f_cap + ga_inv_f_cap
inv_f_other = ma_inv_f_other + ga_inv_f_other
nleads_f  = len(crm_f)
roas_f    = fat_f / inv_f_cap if inv_f_cap else 0
cpl_f     = inv_f_cap / nleads_f if nleads_f else 0

comp_emails_f = set(hm_f["email_n"]) | set(tmb_f["email_n"])
compradores_crm_f = crm_f[crm_f["email_n"].isin(comp_emails_f)]
txconv_f  = len(compradores_crm_f) / nleads_f * 100 if nleads_f else 0
cpa_venda_f = inv_f_cap / nvend_f if nvend_f else 0

print(f"  FEV: {nleads_f:,} leads | {nvend_f:,} vendas | {moeda(fat_f)} | {moeda(inv_f_cap)} captacao + {moeda(inv_f_other)} outros | ROAS {roas_f:.2f}x")

# ── carregar ABR-26 ─────────────────────────────────────────────────────────

print("[2/8] Carregando ABR-26...")

crm_a = pd.read_csv(
    BASE / "analises/[PBB-ABR-26]/Active Campaign/PBB-ABR-14h-12-05-26.csv",
    sep=",", quoting=csvmod.QUOTE_MINIMAL, low_memory=False
)
crm_a["email_n"] = crm_a["Email"].astype(str).str.lower().str.strip()
utm_a = next((c for c in crm_a.columns if "utm_source" in c.lower()), None)

hm_a = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Vendas/hotmart pbb-abr-26.csv", sep=";")
hm_a["email_n"] = hm_a["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
_tipo_col_a = next((c for c in hm_a.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
_par_col_a = "Quantidade total de parcelas"
_cob_col_a = "Quantidade de cobranças"
_hma_norm = hm_a[hm_a[_tipo_col_a].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
_hma_norm["valor"] = _hma_norm["Faturamento líquido do(a) Produtor(a)"].apply(br2f)
_hma_ri = hm_a[
    (hm_a[_tipo_col_a].astype(str).str.strip() == 'Recuperador Inteligente') &
    (pd.to_numeric(hm_a[_cob_col_a], errors='coerce').fillna(0) == 1)
].copy()
_hma_ri[_par_col_a] = pd.to_numeric(_hma_ri[_par_col_a], errors='coerce').fillna(1)
_hma_ri["valor"] = _hma_ri["Faturamento líquido do(a) Produtor(a)"].apply(br2f) * _hma_ri[_par_col_a]
hm_a = pd.concat([_hma_norm, _hma_ri], ignore_index=True)
hm_a["email_n"] = hm_a["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()

tmb_a = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Vendas/tmb pbb-abr-26.csv", sep=";", encoding="utf-8")
# Inclui todos os rows (oficial conta todos os 170)
email_col_ta = "E-mail do Cliente" if "E-mail do Cliente" in tmb_a.columns else "Cliente Email"
val_col_ta   = "Ticket do pedido"  if "Ticket do pedido"  in tmb_a.columns else "Ticket (R$)"
tmb_a["email_n"] = tmb_a[email_col_ta].astype(str).str.lower().str.strip()
tmb_a["valor"]   = tmb_a[val_col_ta].astype(str).apply(br2f)

ma_a = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Meta Ads/MA-Campanhas-completas-PBB-ABR-26.csv")
ma_leads_col_a = next((c for c in ma_a.columns if "lead" in c.lower() and "custo" not in c.lower()), None)
ma_inv_a  = ma_a["Valor usado (BRL)"].apply(br2f).sum()
_cap_a_ma = ma_a["Nome da campanha"].astype(str).str.lower().str.contains("capta", na=False) if "Nome da campanha" in ma_a.columns else pd.Series([True]*len(ma_a), index=ma_a.index)
ma_inv_a_cap   = ma_a[_cap_a_ma]["Valor usado (BRL)"].apply(br2f).sum()
ma_inv_a_other = ma_a[~_cap_a_ma]["Valor usado (BRL)"].apply(br2f).sum()
ma_leads_a = ma_a[ma_leads_col_a].apply(br2f).sum() if ma_leads_col_a else 0
ma_ads_a  = ma_a["Nome do anúncio"].nunique() if "Nome do anúncio" in ma_a.columns else 0

ga_c_a = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Google Ads/Performance da campanha-pbb-abr-26.csv", skiprows=2)
for col in ["Cliques", "Impr.", "Conversões"]:
  if col in ga_c_a.columns:
    ga_c_a[col] = ga_c_a[col].apply(br_count)
if "Custo" in ga_c_a.columns:
  ga_c_a["Custo"] = ga_c_a["Custo"].apply(br2f)
ga_inv_a   = ga_c_a["Custo"].sum()
_cap_a_ga  = ga_c_a["Campanha"].astype(str).str.lower().str.contains("capta", na=False) if "Campanha" in ga_c_a.columns else pd.Series([True]*len(ga_c_a), index=ga_c_a.index)
ga_inv_a_cap   = ga_c_a[_cap_a_ga]["Custo"].sum()
ga_inv_a_other = ga_c_a[~_cap_a_ga]["Custo"].sum()
ga_clk_a   = ga_c_a["Cliques"].sum()
ga_impr_a  = ga_c_a["Impr."].sum()
ga_conv_a  = ga_c_a["Conversões"].sum()
ga_cpa_a   = ga_inv_a / ga_conv_a if ga_conv_a else 0
ga_cpc_a   = ga_inv_a / ga_clk_a  if ga_clk_a else 0
ga_ctr_a   = ga_clk_a / ga_impr_a * 100 if ga_impr_a else 0
ga_ncamp_a = len(ga_c_a)
_ga_conv_col_a   = next((c for c in ga_c_a.columns if "convers" in c.lower()), None)
ga_conv_cap_a    = ga_c_a[_cap_a_ga][_ga_conv_col_a].sum() if _ga_conv_col_a else 0
ga_cpa_cap_a     = ga_inv_a_cap / ga_conv_cap_a if ga_conv_cap_a else 0
ga_ncamp_cap_a   = int(_cap_a_ga.sum())
ga_noncap_ncamp_a = int((~_cap_a_ga).sum())
ga_noncap_conv_a  = ga_c_a[~_cap_a_ga][_ga_conv_col_a].sum() if _ga_conv_col_a else 0
ga_noncap_cpa_a   = ga_inv_a_other / ga_noncap_conv_a if ga_noncap_conv_a else 0

# totais ABR
fat_hm_a  = hm_a["valor"].sum()
fat_tmb_a = tmb_a["valor"].sum()
fat_a     = fat_hm_a + fat_tmb_a
nvend_a   = len(hm_a) + len(tmb_a)
ticket_a  = fat_a / nvend_a if nvend_a else 0
inv_a       = ma_inv_a + ga_inv_a
inv_a_cap   = ma_inv_a_cap + ga_inv_a_cap
inv_a_other = ma_inv_a_other + ga_inv_a_other
nleads_a  = len(crm_a)
roas_a    = fat_a / inv_a_cap if inv_a_cap else 0
cpl_a     = inv_a_cap / nleads_a if nleads_a else 0

comp_emails_a = set(hm_a["email_n"]) | set(tmb_a["email_n"])
compradores_crm_a = crm_a[crm_a["email_n"].isin(comp_emails_a)]
txconv_a  = len(compradores_crm_a) / nleads_a * 100 if nleads_a else 0
cpa_venda_a = inv_a_cap / nvend_a if nvend_a else 0

print(f"  ABR: {nleads_a:,} leads | {nvend_a:,} vendas | {moeda(fat_a)} | {moeda(inv_a_cap)} captacao + {moeda(inv_a_other)} outros | ROAS {roas_a:.2f}x")

# ── Meta Ads: top 5 anúncios por investimento (cada campanha) ───────────────

print("[3/8] Processando Meta Ads por anúncio...")

import re as _re

def top_ads_meta_full(ma_df, crm_df, hm_df, tmb_df, comp_emails, n=5):
    """Top N Meta ads enriquecido: investimento + leads CRM + vendas + CPL + CPA + total vendido."""
    if "Nome do anúncio" not in ma_df.columns:
        return []

    inv_series = ma_df.groupby("Nome do anúncio")["Valor usado (BRL)"].apply(
        lambda s: s.apply(br2f).sum()
    ).sort_values(ascending=False).head(n)

    leads_col_m = next((c for c in ma_df.columns if c.lower() == "leads"), None)
    leads_plat_by_ad = {}
    if leads_col_m:
        leads_plat_by_ad = ma_df.groupby("Nome do anúncio")[leads_col_m].apply(
            lambda s: s.apply(br2f).sum()
        ).to_dict()

    utm_content_col = next((c for c in crm_df.columns if "utm_content" in c.lower()), None)

    def norm_criativo(v):
        t = str(v).strip()
        return t.split(" - ")[0].strip().upper() if " - " in t else t.strip().upper()

    # Pre-build criativo -> emails map from CRM for speed
    crm_criativo_emails = {}
    if utm_content_col:
        crm_utm = crm_df[crm_df[utm_content_col].notna()].copy()
        crm_utm["_cri"] = crm_utm[utm_content_col].apply(norm_criativo)
        for cri, grp in crm_utm.groupby("_cri"):
            crm_criativo_emails[cri] = set(grp["email_n"].unique())

    result = []
    for ad_name, inv in inv_series.items():
        m = _re.search(r'\b(AD\d+)\b', str(ad_name).upper())
        ad_code = m.group(1) if m else None

        crm_leads = 0
        vendas    = 0
        total_vendido = 0.0
        leads_plat = leads_plat_by_ad.get(ad_name, 0)

        if ad_code and ad_code in crm_criativo_emails:
            emails_cri = crm_criativo_emails[ad_code]
            crm_leads  = len(emails_cri)
            buyers_cri = emails_cri & comp_emails
            v_hm  = hm_df[hm_df["email_n"].isin(buyers_cri)]
            v_tmb = tmb_df[tmb_df["email_n"].isin(buyers_cri)]
            vendas = len(v_hm) + len(v_tmb)
            total_vendido = v_hm["valor"].sum() + v_tmb["valor"].sum()

        result.append({
            "name":          ad_name,
            "inv":           inv,
            "leads_plat":    leads_plat,
            "leads_crm":     crm_leads,
            "vendas":        vendas,
            "total_vendido": total_vendido,
            "cpl":           inv / leads_plat if leads_plat > 0 else 0,
            "cpa":           inv / vendas     if vendas     > 0 else 0,
        })
    return result

top_ma_f = top_ads_meta_full(ma_f, crm_f, hm_f, tmb_f, comp_emails_f)
top_ma_a = top_ads_meta_full(ma_a, crm_a, hm_a, tmb_a, comp_emails_a)

# ── Qualidade do lead por plataforma ────────────────────────────────────────

print("[4/8] Calculando qualidade de lead por plataforma...")

def txconv_por_plataforma(crm, comp_emails, utm_col):
    if not utm_col: return {}
    result = {}
    for prefix, label in [("fb-","Facebook"), ("yt-","YouTube")]:
        sub = crm[crm[utm_col].astype(str).str.startswith(prefix)]
        comp = sub[sub["email_n"].isin(comp_emails)]
        result[label] = {
            "leads": len(sub),
            "compradores": len(comp),
            "tx": len(comp)/len(sub)*100 if len(sub) else 0
        }
    return result

plat_f = txconv_por_plataforma(crm_f, comp_emails_f, utm_f)
plat_a = txconv_por_plataforma(crm_a, comp_emails_a, utm_a)

# ── Budget desperdiçado ABR (anúncios Meta com inv > 0 e 0 vendas) ──────────

print("[5/8] Calculando budget desperdiçado ABR-26...")

# Mapear vendas por utm_content (criativo) no CRM
def vendas_por_criativo(crm, comp_emails, utm_col):
    utm_content = next((c for c in crm.columns if "utm_content" in c.lower()), None)
    if not utm_content: return {}
    compradores = crm[crm["email_n"].isin(comp_emails)]
    return compradores[utm_content].astype(str).str.upper().value_counts().to_dict()

vendas_crit_a = vendas_por_criativo(crm_a, comp_emails_a, utm_a)

# Anúncios Meta ABR: investimento por código de anúncio (apenas campanhas de captação)
def inv_sem_venda(ma_df, vendas_dict):
    if "Nome do anúncio" not in ma_df.columns: return [], 0
    # Filtrar apenas campanhas de captação
    if "Nome da campanha" in ma_df.columns:
        ma_df = ma_df[ma_df["Nome da campanha"].str.lower().str.contains("captação|captacao", na=False)]
    grp = ma_df.groupby("Nome do anúncio")["Valor usado (BRL)"].apply(
        lambda s: s.apply(br2f).sum()
    ).reset_index()
    grp.columns = ["ad", "inv"]
    # extrair código (ex: AD050)
    import re
    def extrair_cod(nome):
        m = re.search(r'\b(AD\d+)\b', str(nome).upper())
        return m.group(1) if m else None
    grp["cod"] = grp["ad"].apply(extrair_cod)
    perdedores = grp[grp["cod"].apply(lambda c: vendas_dict.get(c, 0) == 0 if c else True)]
    perdedores = perdedores[perdedores["inv"] > 500].sort_values("inv", ascending=False)
    return perdedores[["ad","inv"]].values.tolist(), perdedores["inv"].sum()

waste_list_a, waste_total_a = inv_sem_venda(ma_a, vendas_crit_a)

# ── Cruzamento de criativos (overlap ABR x FEV) ─────────────────────────────

print("[6/8] Analisando overlap de criativos...")

import re
def extrair_codigos(ma_df):
    if "Nome do anúncio" not in ma_df.columns: return set()
    cods = set()
    for nome in ma_df["Nome do anúncio"].dropna().unique():
        m = re.search(r'\b(AD\d+)\b', str(nome).upper())
        if m: cods.add(m.group(1))
    return cods

cods_f = extrair_codigos(ma_f)
cods_a = extrair_codigos(ma_a)
overlap = cods_f & cods_a
excl_f  = cods_f - cods_a
excl_a  = cods_a - cods_f

# ── Top utm_source dos compradores ──────────────────────────────────────────

print("[7/8] Top UTM sources dos compradores...")

def top_utm(crm, comp_emails, utm_col, n=8):
    if not utm_col: return []
    compradores = crm[crm["email_n"].isin(comp_emails)]
    return list(compradores[utm_col].value_counts().head(n).items())

top_utm_f = top_utm(crm_f, comp_emails_f, utm_f)
top_utm_a = top_utm(crm_a, comp_emails_a, utm_a)

# Cores (definidas aqui para uso nas funções auxiliares abaixo)
FEV_COLOR = "#667eea"
ABR_COLOR = "#f5576c"

# ── Typeform: carregar e cruzar ──────────────────────────────────────────────

print("[7.5/8] Comparativo Typeform...")

tf_a_df = pd.read_csv(BASE / "analises/[PBB-ABR-26]/Typeform/typeform-pesquisa-pbb-abr-26.csv", low_memory=False)
tf_a_df["email_n"] = tf_a_df["Digite o seu e-mail."].astype(str).str.lower().str.strip()

tf_f_df = pd.read_csv(BASE / "analises/[PBB-FEV-26]/typeform/typeform-pbb-fev-26.csv", low_memory=False)
tf_f_df["email_n"] = tf_f_df["Digite o seu e-mail."].astype(str).str.lower().str.strip()

# Cruzamentos TF × vendas × CRM
tf_a_e_venda = set(tf_a_df["email_n"]) & comp_emails_a
tf_f_e_venda = set(tf_f_df["email_n"]) & comp_emails_f
tf_a_e_crm   = set(tf_a_df["email_n"]) & set(crm_a["email_n"])
tf_f_e_crm   = set(tf_f_df["email_n"]) & set(crm_f["email_n"])

fat_tf_a = (hm_a[hm_a["email_n"].isin(tf_a_e_venda)]["valor"].sum() +
            tmb_a[tmb_a["email_n"].isin(tf_a_e_venda)]["valor"].sum())
fat_tf_f = (hm_f[hm_f["email_n"].isin(tf_f_e_venda)]["valor"].sum() +
            tmb_f[tmb_f["email_n"].isin(tf_f_e_venda)]["valor"].sum())

tx_tf_venda_a = len(tf_a_e_venda) / len(tf_a_df) * 100
tx_tf_venda_f = len(tf_f_e_venda) / len(tf_f_df) * 100
tx_tf_crm_a   = len(tf_a_e_crm)   / len(tf_a_df) * 100
tx_tf_crm_f   = len(tf_f_e_crm)   / len(tf_f_df) * 100

overlap_tf = set(tf_a_df["email_n"]) & set(tf_f_df["email_n"])

def _pct_col(df, col, val):
    if col not in df.columns: return 0.0
    return df[col].value_counts(normalize=True).get(val, 0) * 100

def _pct_notnull(df, col):
    if col not in df.columns: return 0.0
    return df[col].notna().sum() / len(df) * 100

def _count_seg_email(df, col, val, email_set):
    """Count TF respondents in a demographic segment whose email is in email_set."""
    if col not in df.columns: return 0
    sub = df[df[col] == val]
    return len(set(sub["email_n"]) & email_set)

def demo_row_full(label, val_f, val_a, leads_f, leads_a, vendas_f, vendas_a, invert=False):
    d = val_a - val_f
    color = ("#28a745" if (d >= 0) != invert else "#dc3545")
    sign  = "+" if d >= 0 else ""
    return (
        f"<tr><td>{label}</td>"
        f"<td style='text-align:right'><strong>{val_f:.1f}%</strong></td>"
        f"<td style='text-align:right'>{leads_f:,}</td>"
        f"<td style='text-align:right'>{'—' if vendas_f == 0 else vendas_f}</td>"
        f"<td style='text-align:right'><strong>{val_a:.1f}%</strong></td>"
        f"<td style='text-align:right'>{leads_a:,}</td>"
        f"<td style='text-align:right'>{'—' if vendas_a == 0 else vendas_a}</td>"
        f"<td style='text-align:right;color:{color};font-weight:600'>{sign}{d:.1f}pp</td></tr>"
    )

def demo_row(label, val_f, val_a, invert=False):
    d = val_a - val_f
    color = ("#28a745" if (d >= 0) != invert else "#dc3545")
    sign  = "+" if d >= 0 else ""
    b_f = bar(val_f, FEV_COLOR)
    b_a = bar(val_a, ABR_COLOR)
    return (
        f"<tr><td>{label}</td>"
        f"<td style='text-align:right'><strong>{val_f:.1f}%</strong>{b_f}</td>"
        f"<td style='text-align:right'><strong>{val_a:.1f}%</strong>{b_a}</td>"
        f"<td style='text-align:right;color:{color};font-weight:600'>{sign}{d:.1f}pp</td></tr>"
    )

# Métricas demográficas
_C_GEN   = "Qual é o seu gênero?"
_C_IDADE = "Qual a sua idade?"
_C_NIVEL = "Em relação aos estudos para concursos públicos, você se considera?"
_C_SITUA = "Qual a sua situação profissional atualmente?"
_C_MORA  = "Com quem você mora atualmente?"
_C_FILHOS= "Quantos filhos você tem?"

def _demo_full(col, val, invert=False):
    return demo_row_full(
        val,
        _pct_col(tf_f_df, col, val), _pct_col(tf_a_df, col, val),
        _count_seg_email(tf_f_df, col, val, tf_f_e_crm),
        _count_seg_email(tf_a_df, col, val, tf_a_e_crm),
        _count_seg_email(tf_f_df, col, val, tf_f_e_venda),
        _count_seg_email(tf_a_df, col, val, tf_a_e_venda),
        invert=invert,
    )

genero_rows = "".join(_demo_full(_C_GEN, v)   for v in ["Feminino", "Masculino"])

idade_rows  = "".join(_demo_full(_C_IDADE, v) for v in
    ["18 a 22 anos","23 a 27 anos","28 a 32 anos","33 a 37 anos","38 a 45 anos"])

nivel_rows  = "".join(_demo_full(_C_NIVEL, v) for v in
    ["Estou do zero","Sou Iniciante","Sou Intermediário(a)","Sou Avançado(a)"])

situa_rows  = "".join(_demo_full(_C_SITUA, v) for v in
    ["Desempregado(a)","Funcionário(a) de empresa privada","Autônomo(a)","Funcionário(a) público"])

mora_rows   = "".join(_demo_full(_C_MORA, v) for v in
    ["Com meus pais","Esposo(a) ou companheiro(a) e filhos","Esposo(a) ou companheiro(a)","Sozinho","Eu e meus filhos apenas"])

filhos_rows = "".join(_demo_full(_C_FILHOS, v) for v in ["Nenhum","Um","Dois","Três ou mais"])

graton_f_sim = _pct_col(tf_f_df,"Você já assistiu a algum vídeo ou Aula do Felipe Graton?",1)
graton_a_sim = _pct_col(tf_a_df,"Você já assistiu a algum vídeo ou Aula do Felipe Graton?",1)

# Obstáculos
obst_col_a = "Medo de não sair o concurso este ano"
obst_col_f = "Medo de não sair o concurso em 2025"
obstaculos_comp = [
    ("Não sei estudar do jeito certo",
     "Não sei estudar do jeito certo (falta de técnicas de estudos)",
     "Não sei estudar do jeito certo (falta de técnicas de estudos)"),
    ("Não sei montar cronograma",
     "Não sei montar um cronograma de estudos",
     "Não sei montar um cronograma de estudos"),
    ("Procrastinação",
     "Procrastinação (não conseguir estudar)",
     "Procrastinação (não conseguir estudar)"),
    ("Sem dinheiro para curso",
     "Não tenho dinheiro para investir em um curso",
     "Não tenho dinheiro para investir em um curso"),
    ("Medo de estudar e não passar",
     "Medo de estudar muito e não conseguir passar",
     "Medo de estudar muito e não conseguir passar"),
    ("Medo de esquecer na prova",
     "Medo de esquecer tudo no dia da prova",
     "Medo de esquecer tudo no dia da prova"),
    ("Pouco tempo disponível",
     "Pouco tempo disponível pra me dedicar aos estudos",
     "Pouco tempo disponível pra me dedicar aos estudos"),
    ("Há muito tempo sem estudar",
     "Estou há muito tempo sem estudar",
     "Estou há muito tempo sem estudar"),
    ("Medo de não sair o concurso",
     obst_col_f, obst_col_a),
]
obst_rows = ""
for label, col_f, col_a in obstaculos_comp:
    vf = _pct_notnull(tf_f_df, col_f)
    va = _pct_notnull(tf_a_df, col_a)
    invert = (label == "Sem dinheiro para curso")
    obst_rows += demo_row(label, vf, va, invert=invert)

# Top estados comparado
def top_estados_rows(tf_f, tf_a, n=8):
    e_f = tf_f["De qual estado você é?"].value_counts().head(n)
    e_a = tf_a["De qual estado você é?"].value_counts().head(n)
    estados = list(dict.fromkeys(list(e_f.index) + list(e_a.index)))[:n]
    rows = ""
    for e in estados:
        nf = e_f.get(e, 0)
        na = e_a.get(e, 0)
        pf = nf / len(tf_f) * 100
        pa = na / len(tf_a) * 100
        d = pa - pf
        color = "#28a745" if d >= 0 else "#dc3545"
        sign  = "+" if d >= 0 else ""
        rows += (f"<tr><td><strong>{e}</strong></td>"
                 f"<td style='text-align:right'>{nf:,} ({pf:.1f}%)</td>"
                 f"<td style='text-align:right'>{na:,} ({pa:.1f}%)</td>"
                 f"<td style='text-align:right;color:{color}'>{sign}{d:.1f}pp</td></tr>")
    return rows

estados_tf_rows = top_estados_rows(tf_f_df, tf_a_df)

print(f"  TF ABR: {len(tf_a_df):,} | TF→CRM {tx_tf_crm_a:.1f}% | TF→Venda {tx_tf_venda_a:.2f}% | Fat TF {moeda(fat_tf_a)}")
print(f"  TF FEV: {len(tf_f_df):,} | TF→CRM {tx_tf_crm_f:.1f}% | TF→Venda {tx_tf_venda_f:.2f}% | Fat TF {moeda(fat_tf_f)}")

print("[8/8] Gerando HTML...")

# ── BUILD HTML ──────────────────────────────────────────────────────────────

def scorecard_row(label, val_fev, val_abr, fmt="str", invert=False):
    """Linha da tabela scorecard."""
    d = ""
    try:
        vf = float(str(val_fev).replace("R$ ","").replace(".","").replace(",",".").replace("%","").replace("x",""))
        va = float(str(val_abr).replace("R$ ","").replace(".","").replace(",",".").replace("%","").replace("x",""))
        d = delta_badge(va, vf, invert=invert)
    except: pass
    return (
        f"<tr><td style='font-weight:600'>{label}</td>"
        f"<td style='text-align:right'>{val_fev}</td>"
        f"<td style='text-align:right'>{val_abr} {d}</td></tr>"
    )

def plat_rows(plat_dict_f, plat_dict_a):
    rows = ""
    for plat in ["Facebook", "YouTube"]:
        f = plat_dict_f.get(plat, {"leads":0,"compradores":0,"tx":0})
        a = plat_dict_a.get(plat, {"leads":0,"compradores":0,"tx":0})
        d_leads = delta_badge(a["leads"], f["leads"])
        d_tx    = delta_badge(a["tx"], f["tx"])
        rows += (
            f"<tr><td>{plat}</td>"
            f"<td style='text-align:right'>{intfmt(f['leads'])}</td>"
            f"<td style='text-align:right'>{intfmt(f['compradores'])}</td>"
            f"<td style='text-align:right'>{pct(f['tx'])}</td>"
            f"<td style='text-align:right'>{intfmt(a['leads'])} {d_leads}</td>"
            f"<td style='text-align:right'>{intfmt(a['compradores'])}</td>"
            f"<td style='text-align:right'>{pct(a['tx'])} {d_tx}</td></tr>"
        )
    return rows

def utm_rows_side(top_f, top_a):
    max_len = max(len(top_f), len(top_a))
    rows = ""
    for i in range(max_len):
        sf, nf = top_f[i] if i < len(top_f) else ("—", 0)
        sa, na = top_a[i] if i < len(top_a) else ("—", 0)
        plat_f_color = "#ff0000" if str(sf).startswith("yt") else "#1877f2"
        plat_a_color = "#ff0000" if str(sa).startswith("yt") else "#1877f2"
        badge_f = f'<span style="background:{plat_f_color};color:white;padding:1px 5px;border-radius:8px;font-size:10px">{"YT" if str(sf).startswith("yt") else "FB"}</span>'
        badge_a = f'<span style="background:{plat_a_color};color:white;padding:1px 5px;border-radius:8px;font-size:10px">{"YT" if str(sa).startswith("yt") else "FB"}</span>'
        rows += (
            f"<tr>"
            f"<td>{badge_f} <small>{sf}</small></td>"
            f"<td style='text-align:right'><strong>{nf}</strong></td>"
            f"<td style='text-align:right;border-left:2px solid #eee'>{badge_a} <small>{sa}</small></td>"
            f"<td style='text-align:right'><strong>{na}</strong></td>"
            f"</tr>"
        )
    return rows

# Top anúncios Meta
def top_ads_rows(top_f, top_a):
    max_len = max(len(top_f), len(top_a))
    rows = ""
    for i in range(max_len):
        nf, vf = top_f[i] if i < len(top_f) else ("—", 0)
        na, va = top_a[i] if i < len(top_a) else ("—", 0)
        rows += (
            f"<tr>"
            f"<td><small>{nf[:45]}{'…' if len(str(nf))>45 else ''}</small></td>"
            f"<td style='text-align:right'>{moeda(vf)}</td>"
            f"<td style='text-align:right;border-left:2px solid #eee'><small>{na[:45]}{'…' if len(str(na))>45 else ''}</small></td>"
            f"<td style='text-align:right'>{moeda(va)}</td>"
            f"</tr>"
        )
    return rows

def render_top_ads_full(top_data, th_class):
    """Renderiza tabela detalhada de top anúncios: inv, leads, vendas, CPL, CPA, total vendido."""
    rows = ""
    for d in top_data:
        nm = d["name"]
        short = nm[:48] + "…" if len(nm) > 48 else nm
        cpl_str  = moeda(d["cpl"])  if d["cpl"]  > 0 else "—"
        cpa_str  = moeda(d["cpa"])  if d["cpa"]  > 0 else "—"
        fat_str  = moeda(d["total_vendido"]) if d["total_vendido"] > 0 else "—"
        rows += (
            f"<tr>"
            f"<td><small>{short}</small></td>"
            f"<td style='text-align:right'>{moeda(d['inv'])}</td>"
            f"<td style='text-align:right'>{intfmt(d['leads_plat'])}</td>"
            f"<td style='text-align:right'>{d['vendas'] if d['vendas'] > 0 else '—'}</td>"
            f"<td style='text-align:right'>{cpl_str}</td>"
            f"<td style='text-align:right'>{cpa_str}</td>"
            f"<td style='text-align:right'>{fat_str}</td>"
            f"</tr>"
        )
    return f"""<table style="width:100%">
<tr>
  <th class="{th_class}">Anúncio</th>
  <th class="{th_class}" style="text-align:right">Investimento</th>
  <th class="{th_class}" style="text-align:right">Leads</th>
  <th class="{th_class}" style="text-align:right">Vendas</th>
  <th class="{th_class}" style="text-align:right">CPL</th>
  <th class="{th_class}" style="text-align:right">Custo/Venda</th>
  <th class="{th_class}" style="text-align:right">Total Vendido</th>
</tr>
{rows}
</table>"""

# Budget desperdiçado
waste_rows = ""
for ad_nome, ad_inv in waste_list_a[:12]:
    waste_rows += f"<tr><td><small>{str(ad_nome)[:55]}</small></td><td style='text-align:right;color:#dc3545'><strong>{moeda(ad_inv)}</strong></td><td style='text-align:center'>0</td></tr>"

# Campanhas GA top 5 por custo
def ga_top5(df):
    return df.nlargest(5, "Custo")[["Campanha","Custo","Conversões","Cliques"]].values.tolist()

ga_top_f = ga_top5(ga_c_f)
ga_top_a = ga_top5(ga_c_a)

def ga_camp_rows(rows):
    html = ""
    for r in rows:
        nome = str(r[0])[:60]
        custo = moeda(r[1])
        conv  = intfmt(r[2])
        cpa_c = moeda(r[1]/r[2]) if r[2] > 0 else "—"
        html += f"<tr><td><small>{nome}</small></td><td style='text-align:right'>{custo}</td><td style='text-align:right'>{conv}</td><td style='text-align:right'>{cpa_c}</td></tr>"
    return html

# Leitura sintética de Google Ads após saneamento dos números
tipo_ga_f = "Google com maior volume de conversões e CPA mais eficiente"
tipo_ga_a = "Google mais fragmentado, com CTR melhor mas eficiência final inferior"

# Funil
funil_fev = [
    ("Leads capturados", nleads_f, 100),
    ("Com UTM rastreado", crm_f[utm_f].notna().sum() if utm_f else nleads_f,
     crm_f[utm_f].notna().sum()/nleads_f*100 if utm_f else 100),
    ("Vinculados a venda", len(compradores_crm_f), txconv_f),
    ("Vendas realizadas", nvend_f, nvend_f/nleads_f*100),
]
funil_abr = [
    ("Leads capturados", nleads_a, 100),
    ("Com UTM rastreado", crm_a[utm_a].notna().sum() if utm_a else nleads_a,
     crm_a[utm_a].notna().sum()/nleads_a*100 if utm_a else 100),
    ("Vinculados a venda", len(compradores_crm_a), txconv_a),
    ("Vendas realizadas", nvend_a, nvend_a/nleads_a*100),
]

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparativo ABR-26 vs FEV-26 | Brabo Concursos</title>
<link rel="icon" type="image/png" href="{FAVICON}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);color:#333;line-height:1.5}}
.container{{max-width:1300px;margin:20px auto;background:white;box-shadow:0 20px 60px rgba(0,0,0,.4);overflow:hidden;border-radius:10px}}
.header{{background:white;padding:36px 40px;display:flex;align-items:center;gap:24px;border-bottom:3px solid #eee}}
.header img{{max-width:110px;height:auto}}
.header h1{{font-size:26px;color:#1a1a2e;margin-bottom:6px}}
.header p{{font-size:13px;color:#666}}
.content{{padding:40px}}
h2{{margin:32px 0 14px;color:#1a1a2e;border-bottom:3px solid #1a1a2e;padding-bottom:8px;font-size:20px}}
h3{{margin:18px 0 8px;color:#444;font-size:15px}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}}
table th{{padding:10px 12px;text-align:left;font-weight:600}}
table td{{padding:9px 12px;border-bottom:1px solid #eee;vertical-align:middle}}
table tr:hover{{background:#fafafa}}
.th-fev{{background:{FEV_COLOR};color:white}}
.th-abr{{background:{ABR_COLOR};color:white}}
.th-dark{{background:#1a1a2e;color:white}}
.paradox{{background:linear-gradient(135deg,#1a1a2e 0%,#0f3460 100%);color:white;padding:28px 36px;border-radius:10px;margin:20px 0;display:flex;align-items:center;gap:20px;flex-wrap:wrap}}
.paradox .block{{flex:1;min-width:160px;text-align:center;padding:16px;border-radius:8px}}
.paradox .block.fev{{background:rgba(102,126,234,.3);border:2px solid {FEV_COLOR}}}
.paradox .block.abr{{background:rgba(245,87,108,.3);border:2px solid {ABR_COLOR}}}
.paradox .block .label{{font-size:11px;text-transform:uppercase;opacity:.8;margin-bottom:4px}}
.paradox .block .num{{font-size:22px;font-weight:700}}
.paradox .arrow{{font-size:32px;opacity:.6}}
.metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}}
.mbox{{padding:16px;border-radius:8px;border-left:4px solid #1a1a2e}}
.mbox.fev{{border-color:{FEV_COLOR};background:rgba(102,126,234,.06)}}
.mbox.abr{{border-color:{ABR_COLOR};background:rgba(245,87,108,.06)}}
.mbox .label{{font-size:11px;color:#666;text-transform:uppercase;margin-bottom:3px}}
.mbox .val{{font-size:20px;font-weight:700;color:#1a1a2e}}
.mbox .sub{{font-size:11px;color:#888;margin-top:2px}}
.cause{{border-left:4px solid;padding:14px 18px;margin:10px 0;border-radius:0 6px 6px 0}}
.cause.red{{border-color:#dc3545;background:#fff5f5}}
.cause.orange{{border-color:#fd7e14;background:#fff8f0}}
.cause.yellow{{border-color:#ffc107;background:#fffdf0}}
.cause.blue{{border-color:#4285f4;background:#f0f4ff}}
.cause.purple{{border-color:#764ba2;background:#f8f0ff}}
.action-box{{background:#f0fff4;border-left:4px solid #28a745;padding:14px 18px;margin:10px 0;border-radius:0 6px 6px 0}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}
.badge.fev{{background:{FEV_COLOR};color:white}}
.badge.abr{{background:{ABR_COLOR};color:white}}
.badge.warn{{background:#ffc107;color:#333}}
.badge.ok{{background:#28a745;color:white}}
.funil-wrap{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:16px 0}}
.funil-step{{padding:12px 16px;border-radius:6px;margin:4px 0;display:flex;justify-content:space-between;align-items:center}}
.section-intro{{background:#f8f9fa;border-radius:6px;padding:14px;font-size:13px;color:#555;margin-bottom:16px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.footer{{background:#f8f9fa;padding:24px;text-align:center;font-size:12px;color:#666;border-top:1px solid #eee;margin-top:40px}}
@media(max-width:800px){{.two-col,.funil-wrap{{grid-template-columns:1fr}}.paradox{{flex-direction:column}}}}
</style>
</head>
<body>
<div class="container">

<!-- HEADER -->
<div class="header">
  <a href="#"><img src="{LOGO}" alt="Brabo Concursos"></a>
  <div>
    <h1>📊 Comparativo de Campanhas — PBB 2026</h1>
    <p>Por que ABR-26 vendeu <strong>menos</strong> investindo <strong>mais</strong> que FEV-26? Análise detalhada com diagnóstico e plano de ação.</p>
    <p style="margin-top:4px;color:#999">Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Dados: Active Campaign, Hotmart, TMB, Meta Ads, Google Ads</p>
  </div>
</div>

<div class="content">

<!-- O PARADOXO -->
<h2>⚡ O Paradoxo</h2>
<div class="paradox">
  <div class="block fev">
    <div class="label">FEV-26</div>
    <div class="num">{moeda(inv_f)}</div>
    <div class="label" style="margin-top:6px">Investido</div>
    <div class="num" style="font-size:28px;margin-top:10px">{intfmt(nvend_f)}</div>
    <div class="label">vendas</div>
    <div class="num" style="font-size:18px;margin-top:8px">{moeda(fat_f)}</div>
    <div class="label">faturamento</div>
  </div>
  <div class="arrow">→</div>
  <div style="flex:1.5;text-align:center;color:white;padding:16px">
    <div style="font-size:13px;opacity:.7;margin-bottom:8px">DIFERENÇA ABR vs FEV</div>
    <div style="font-size:36px;font-weight:700;color:#ffc107">+{(inv_a-inv_f)/inv_f*100:.0f}%</div>
    <div style="font-size:13px;margin-bottom:12px;opacity:.8">mais investimento</div>
    <div style="font-size:36px;font-weight:700;color:#ff6b6b">{(nvend_a-nvend_f)/nvend_f*100:.0f}%</div>
    <div style="font-size:13px;opacity:.8">menos vendas</div>
    <div style="font-size:12px;margin-top:16px;opacity:.6">+{(nleads_a-nleads_f)/nleads_f*100:.0f}% mais leads, {(fat_a-fat_f)/fat_f*100:.0f}% menos faturamento</div>
  </div>
  <div class="arrow">←</div>
  <div class="block abr">
    <div class="label">ABR-26</div>
    <div class="num">{moeda(inv_a)}</div>
    <div class="label" style="margin-top:6px">Investido</div>
    <div class="num" style="font-size:28px;margin-top:10px">{intfmt(nvend_a)}</div>
    <div class="label">vendas</div>
    <div class="num" style="font-size:18px;margin-top:8px">{moeda(fat_a)}</div>
    <div class="label">faturamento</div>
  </div>
</div>

<!-- SCORECARD -->
<h2>📋 Scorecard Comparativo</h2>
<div class="section-intro">Todos os indicadores principais lado a lado. A seta indica a direção do ABR-26 em relação ao FEV-26.</div>
<table>
<tr>
  <th class="th-dark">Indicador</th>
  <th class="th-fev" style="text-align:right">🟣 FEV-26</th>
  <th class="th-abr" style="text-align:right">🔴 ABR-26</th>
</tr>
{scorecard_row("Investimento Total", moeda(inv_f), moeda(inv_a), invert=True)}
{scorecard_row("↳ Captação (Meta+Google)", moeda(inv_f_cap), moeda(inv_a_cap), invert=True)}
{scorecard_row("↳ Alcance/Engaj/Aulas", moeda(inv_f_other), moeda(inv_a_other))}
{scorecard_row("↳ Meta Ads (total)", moeda(ma_inv_f), moeda(ma_inv_a), invert=True)}
{scorecard_row("↳ Google Ads (total)", moeda(ga_inv_f), moeda(ga_inv_a), invert=True)}
{scorecard_row("Leads no CRM", intfmt(nleads_f), intfmt(nleads_a))}
{scorecard_row("CPL — captação", moeda(cpl_f), moeda(cpl_a), invert=True)}
{scorecard_row("Vendas Totais", intfmt(nvend_f), intfmt(nvend_a))}
{scorecard_row("↳ Hotmart", intfmt(len(hm_f)), intfmt(len(hm_a)))}
{scorecard_row("↳ TMB (Boleto)", intfmt(len(tmb_f)), intfmt(len(tmb_a)))}
{scorecard_row("Faturamento Total", moeda(fat_f), moeda(fat_a))}
{scorecard_row("Ticket Médio", moeda(ticket_f), moeda(ticket_a))}
{scorecard_row("ROAS (s/ captação)", f"{roas_f:.2f}x", f"{roas_a:.2f}x")}
{scorecard_row("Taxa Conv. CRM→Venda", pct(txconv_f), pct(txconv_a))}
{scorecard_row("CPA por Venda (captação)", moeda(cpa_venda_f), moeda(cpa_venda_a), invert=True)}
{scorecard_row("N° Campanhas Google", str(ga_ncamp_f), str(ga_ncamp_a), invert=True)}
{scorecard_row("Conversões Google", intfmt(ga_conv_f), intfmt(ga_conv_a))}
{scorecard_row("CPC Google Ads", moeda(ga_cpc_f), moeda(ga_cpc_a), invert=True)}
{scorecard_row("CTR Google Ads", pct(ga_ctr_f), pct(ga_ctr_a))}
</table>

<!-- FUNIL COMPARADO -->
<h2>🔽 Funil de Conversão Comparado</h2>
<div class="section-intro">O funil revela onde cada campanha perdeu eficiência. O número que mais importa: a <strong>taxa CRM → Venda</strong>.</div>
<div class="funil-wrap">
  <div>
    <div style="text-align:center;margin-bottom:10px"><span class="badge fev" style="font-size:14px;padding:4px 16px">FEV-26</span></div>
    {"".join(
        f'<div class="funil-step" style="background:rgba(102,126,234,{0.08+i*0.07});margin-bottom:2px">'
        f'<span style="font-weight:600;font-size:13px">{funil_fev[i][0]}</span>'
        f'<span style="font-size:18px;font-weight:700;color:{FEV_COLOR}">{intfmt(funil_fev[i][1])}'
        f'<span style="font-size:11px;color:#888;margin-left:6px">{funil_fev[i][2]:.2f}%</span></span>'
        f'</div>'
        for i in range(len(funil_fev))
    )}
  </div>
  <div>
    <div style="text-align:center;margin-bottom:10px"><span class="badge abr" style="font-size:14px;padding:4px 16px">ABR-26</span></div>
    {"".join(
        f'<div class="funil-step" style="background:rgba(245,87,108,{0.06+i*0.06});margin-bottom:2px">'
        f'<span style="font-weight:600;font-size:13px">{funil_abr[i][0]}</span>'
        f'<span style="font-size:18px;font-weight:700;color:{ABR_COLOR}">{intfmt(funil_abr[i][1])}'
        f'<span style="font-size:11px;color:#888;margin-left:6px">{funil_abr[i][2]:.2f}%</span></span>'
        f'</div>'
        for i in range(len(funil_abr))
    )}
  </div>
</div>
<div class="cause red" style="margin-top:8px">
  <strong>⚠️ Taxa de conversão CRM→Venda: FEV {pct(txconv_f)} → ABR {pct(txconv_a)}</strong> — queda de <strong>{(txconv_a-txconv_f)/txconv_f*100:.0f}%</strong>.
  ABR captou <strong>{intfmt(nleads_a-nleads_f)} leads a mais</strong>, mas converteu proporcionalmente muito menos. O problema não foi o volume — foi a qualidade ou o processo de venda.
</div>

<!-- QUALIDADE DO LEAD POR PLATAFORMA -->
<h2>🎯 Qualidade do Lead por Plataforma</h2>
<div class="section-intro">Taxa de conversão (lead → comprador) segmentada por plataforma de origem. Revela qual canal trouxe leads de maior intenção de compra.</div>
<table>
<tr>
  <th class="th-dark">Plataforma</th>
  <th class="th-fev" style="text-align:right">Leads FEV</th>
  <th class="th-fev" style="text-align:right">Compradores</th>
  <th class="th-fev" style="text-align:right">Taxa FEV</th>
  <th class="th-abr" style="text-align:right">Leads ABR</th>
  <th class="th-abr" style="text-align:right">Compradores</th>
  <th class="th-abr" style="text-align:right">Taxa ABR</th>
</tr>
{plat_rows(plat_f, plat_a)}
</table>

<!-- META ADS -->
<h2>📱 Meta Ads — Comparativo</h2>
<div class="metric-grid">
  <div class="mbox fev"><div class="label">Investimento FEV</div><div class="val">{moeda(ma_inv_f)}</div><div class="sub">{intfmt(ma_ads_f)} anúncios únicos</div></div>
  <div class="mbox fev"><div class="label">Leads Meta FEV</div><div class="val">{intfmt(ma_leads_f)}</div><div class="sub">CPL Meta {moeda(ma_inv_f/ma_leads_f if ma_leads_f else 0)}</div></div>
  <div class="mbox abr"><div class="label">Investimento ABR</div><div class="val">{moeda(ma_inv_a)}</div><div class="sub">{intfmt(ma_ads_a)} anúncios únicos {delta_badge(ma_ads_a, ma_ads_f, invert=True)}</div></div>
  <div class="mbox abr"><div class="label">Leads Meta ABR</div><div class="val">{intfmt(ma_leads_a)}</div><div class="sub">CPL Meta {moeda(ma_inv_a/ma_leads_a if ma_leads_a else 0)} {delta_badge(ma_inv_a/ma_leads_a if ma_leads_a else 0, ma_inv_f/ma_leads_f if ma_leads_f else 1, invert=True)}</div></div>
</div>

<h3>Top 5 Anúncios por Investimento — FEV-26</h3>
{render_top_ads_full(top_ma_f, "th-fev")}

<h3>Top 5 Anúncios por Investimento — ABR-26</h3>
{render_top_ads_full(top_ma_a, "th-abr")}

<h3>Overlap de Criativos</h3>
<div class="metric-grid">
  <div class="mbox fev"><div class="label">Exclusivos FEV</div><div class="val">{len(excl_f)}</div><div class="sub">códigos ADXXX só no FEV</div></div>
  <div class="mbox" style="border-color:#1a1a2e"><div class="label">Em Comum</div><div class="val">{len(overlap)}</div><div class="sub">mesmo código ADXXX em FEV e ABR</div></div>
  <div class="mbox abr"><div class="label">Exclusivos ABR</div><div class="val">{len(excl_a)}</div><div class="sub">códigos ADXXX novos no ABR</div></div>
</div>
<div class="cause blue">
  <strong>📌 Critério de validação:</strong> consideramos "criativo validado" quando o <strong>código ADXXX</strong> aparece nos dois lançamentos.
  Neste recorte, <strong>{len(overlap)} códigos ADXXX foram reutilizados</strong> do FEV no ABR ({', '.join(sorted(overlap)[:10])}{'...' if len(overlap)>10 else ''}).
  Já os códigos presentes apenas em ABR ({len(excl_a)}) são tratados como <strong>criativos novos</strong> neste comparativo.
</div>

<!-- GOOGLE ADS -->
<h2>🔍 Google Ads — Comparativo Estratégico</h2>
<div class="section-intro">
  <strong>Esta é a maior divergência entre as campanhas.</strong>
  O Google em FEV fechou com <strong>mais conversões e CPA melhor</strong>.
  O ABR trouxe <strong>mais cliques, CTR maior e mais campanhas</strong>, mas monetizou pior, o que sugere fragmentação e desalinhamento de objetivo entre campanhas.
</div>

<div class="metric-grid">
  <div class="mbox fev"><div class="label">Investimento GA FEV</div><div class="val">{moeda(ga_inv_f)}</div></div>
  <div class="mbox fev"><div class="label">Conversões GA FEV</div><div class="val">{intfmt(ga_conv_f)}</div><div class="sub">CPA {moeda(ga_cpa_f)}</div></div>
  <div class="mbox fev"><div class="label">CPC FEV</div><div class="val">{moeda(ga_cpc_f)}</div><div class="sub">CTR {pct(ga_ctr_f)}</div></div>
  <div class="mbox fev"><div class="label">Campanhas FEV</div><div class="val">{ga_ncamp_f}</div><div class="sub">campanhas ativas</div></div>
  <div class="mbox abr"><div class="label">Investimento GA ABR</div><div class="val">{moeda(ga_inv_a)}</div></div>
  <div class="mbox abr"><div class="label">Conversões GA ABR</div><div class="val">{intfmt(ga_conv_a)}</div><div class="sub">CPA {moeda(ga_cpa_a)} {delta_badge(ga_cpa_a, ga_cpa_f, invert=True)}</div></div>
  <div class="mbox abr"><div class="label">CPC ABR</div><div class="val">{moeda(ga_cpc_a)}</div><div class="sub">CTR {pct(ga_ctr_a)} {delta_badge(ga_ctr_a, ga_ctr_f)}</div></div>
  <div class="mbox abr"><div class="label">Campanhas ABR</div><div class="val">{ga_ncamp_a}</div><div class="sub">{delta_badge(ga_ncamp_a, ga_ncamp_f, invert=True)} vs FEV</div></div>
</div>

<div class="two-col">
  <div>
    <h3>Top 5 Campanhas GA — FEV-26</h3>
    <table>
    <tr><th class="th-fev">Campanha</th><th class="th-fev" style="text-align:right">Custo</th><th class="th-fev" style="text-align:right">Conv.</th><th class="th-fev" style="text-align:right">CPA</th></tr>
    {ga_camp_rows(ga_top_f)}
    </table>
  </div>
  <div>
    <h3>Top 5 Campanhas GA — ABR-26</h3>
    <table>
    <tr><th class="th-abr">Campanha</th><th class="th-abr" style="text-align:right">Custo</th><th class="th-abr" style="text-align:right">Conv.</th><th class="th-abr" style="text-align:right">CPA</th></tr>
    {ga_camp_rows(ga_top_a)}
    </table>
  </div>
</div>

<div class="cause orange">
  <strong>⚠️ O ganho de tráfego no ABR não virou eficiência de conversão</strong>.
  O ABR registrou CPC de <strong>{moeda(ga_cpc_a)}</strong> contra <strong>{moeda(ga_cpc_f)}</strong> no FEV e CTR superior,
  mas ainda assim fechou com <strong>menos conversões</strong> e <strong>CPA pior</strong>.
  A leitura correta aqui não é "clique mais caro" isoladamente, e sim <strong>mix de campanhas mais disperso e menos eficiente para o objetivo final</strong>.
</div>

<!-- BUDGET DESPERDIÇADO -->
<h2>🚨 Budget Desperdiçado — ABR-26</h2>
<div class="section-intro">Anúncios de <strong>campanhas de captação</strong> no ABR-26 que consumiram investimento significativo e <strong>não geraram nenhuma venda rastreável</strong> no CRM. Campanhas de engajamento, alcance e aulas foram excluídas desta análise pois seu objetivo não é conversão direta.</div>
{'<table><tr><th class="th-abr">Anúncio</th><th class="th-abr" style="text-align:right">Investimento</th><th class="th-abr" style="text-align:center">Vendas</th></tr>' + waste_rows + f'<tr style="background:#fff5f5;font-weight:700"><td>TOTAL NÃO RASTREADO</td><td style="text-align:right;color:#dc3545">{moeda(waste_total_a)}</td><td style="text-align:center">0</td></tr></table>' if waste_rows else '<p style="color:#666">Dados insuficientes para análise de criativos sem retorno.</p>'}

<div class="cause red">
  <strong>🔴 {moeda(waste_total_a)} investidos sem retorno rastreável</strong> — representa {waste_total_a/inv_a*100:.1f}% do investimento total do ABR.
  Parte pode ter gerado leads não atribuídos (sem UTM), mas o impacto na taxa de conversão geral é real.
</div>

<!-- UTM DOS COMPRADORES -->
<h2>📡 Origem dos Compradores (UTM Source)</h2>
<div class="section-intro">UTM sources com maior concentração de compradores em cada campanha — revela quais canais/criativos geraram vendas de fato.</div>
<table>
<tr>
  <th class="th-fev">Origem FEV-26</th>
  <th class="th-fev" style="text-align:right">Compradores</th>
  <th class="th-abr" style="border-left:2px solid white">Origem ABR-26</th>
  <th class="th-abr" style="text-align:right">Compradores</th>
</tr>
{utm_rows_side(top_utm_f, top_utm_a)}
</table>

<!-- TYPEFORM COMPARATIVO -->
<h2>📋 Comparativo Typeform: O Mesmo Público, Resultados Opostos</h2>
<div class="section-intro">
  <strong>Esta é uma das análises mais reveladoras deste relatório.</strong>
  Ambas as campanhas usaram a mesma pesquisa Typeform para capturar leads quentes. O perfil demográfico é
  <em>praticamente idêntico</em> entre ABR e FEV. No entanto, a taxa de conversão Typeform→Venda foi
  <strong>2,25× maior no FEV</strong>. Isso exclui "qualidade de audiência" como causa do baixo desempenho do ABR
  e aponta para problemas de <strong>execução, estratégia de mídia e processo de venda</strong>.
</div>

<h3>📊 Funil Typeform Comparado</h3>
<div class="funil-wrap">
  <div>
    <div style="text-align:center;margin-bottom:10px"><span class="badge fev" style="font-size:14px;padding:4px 16px">FEV-26</span></div>
    <div class="funil-step" style="background:rgba(102,126,234,.08)">
      <span style="font-weight:600;font-size:13px">Respostas Typeform</span>
      <span style="font-size:20px;font-weight:700;color:{FEV_COLOR}">{len(tf_f_df):,}
        <span style="font-size:11px;color:#888;margin-left:6px">100%</span></span>
    </div>
    <div class="funil-step" style="background:rgba(102,126,234,.14)">
      <span style="font-weight:600;font-size:13px">TF → Lead CRM</span>
      <span style="font-size:20px;font-weight:700;color:{FEV_COLOR}">{len(tf_f_e_crm):,}
        <span style="font-size:11px;color:#888;margin-left:6px">{tx_tf_crm_f:.1f}%</span></span>
    </div>
    <div class="funil-step" style="background:rgba(102,126,234,.20)">
      <span style="font-weight:600;font-size:13px">TF → Compra</span>
      <span style="font-size:20px;font-weight:700;color:{FEV_COLOR}">{len(tf_f_e_venda):,}
        <span style="font-size:11px;color:#888;margin-left:6px">{tx_tf_venda_f:.2f}%</span></span>
    </div>
    <div class="funil-step" style="background:rgba(102,126,234,.28)">
      <span style="font-weight:600;font-size:13px">Receita via TF</span>
      <span style="font-size:16px;font-weight:700;color:{FEV_COLOR}">{moeda(fat_tf_f)}
        <span style="font-size:11px;color:#888;margin-left:6px">{fat_tf_f/fat_f*100:.1f}% do total</span></span>
    </div>
  </div>
  <div>
    <div style="text-align:center;margin-bottom:10px"><span class="badge abr" style="font-size:14px;padding:4px 16px">ABR-26</span></div>
    <div class="funil-step" style="background:rgba(245,87,108,.06)">
      <span style="font-weight:600;font-size:13px">Respostas Typeform</span>
      <span style="font-size:20px;font-weight:700;color:{ABR_COLOR}">{len(tf_a_df):,}
        <span style="font-size:11px;color:#888;margin-left:6px">100%</span></span>
    </div>
    <div class="funil-step" style="background:rgba(245,87,108,.10)">
      <span style="font-weight:600;font-size:13px">TF → Lead CRM</span>
      <span style="font-size:20px;font-weight:700;color:{ABR_COLOR}">{len(tf_a_e_crm):,}
        <span style="font-size:11px;color:#888;margin-left:6px">{tx_tf_crm_a:.1f}%</span></span>
    </div>
    <div class="funil-step" style="background:rgba(245,87,108,.16)">
      <span style="font-weight:600;font-size:13px">TF → Compra</span>
      <span style="font-size:20px;font-weight:700;color:{ABR_COLOR}">{len(tf_a_e_venda):,}
        <span style="font-size:11px;color:#888;margin-left:6px">{tx_tf_venda_a:.2f}%</span></span>
    </div>
    <div class="funil-step" style="background:rgba(245,87,108,.22)">
      <span style="font-weight:600;font-size:13px">Receita via TF</span>
      <span style="font-size:16px;font-weight:700;color:{ABR_COLOR}">{moeda(fat_tf_a)}
        <span style="font-size:11px;color:#888;margin-left:6px">{fat_tf_a/fat_a*100:.1f}% do total</span></span>
    </div>
  </div>
</div>

<div class="metric-grid" style="margin-top:16px">
  <div class="mbox" style="border-color:#1a1a2e;background:#f0f4ff">
    <div class="label">Respondentes TF</div>
    <div class="val">{len(tf_f_df):,} <span style="font-size:13px;color:#888">FEV</span> vs {len(tf_a_df):,} <span style="font-size:13px;color:#888">ABR</span></div>
    <div class="sub">+{(len(tf_f_df)-len(tf_a_df))/len(tf_a_df)*100:.1f}% mais respostas no FEV</div>
  </div>
  <div class="mbox fev">
    <div class="label">Taxa TF→Venda FEV</div>
    <div class="val">{tx_tf_venda_f:.2f}%</div>
    <div class="sub">{len(tf_f_e_venda)} compradores de {len(tf_f_df):,} respondentes</div>
  </div>
  <div class="mbox abr">
    <div class="label">Taxa TF→Venda ABR</div>
    <div class="val">{tx_tf_venda_a:.2f}%</div>
    <div class="sub">{len(tf_a_e_venda)} compradores de {len(tf_a_df):,} respondentes {delta_badge(tx_tf_venda_a, tx_tf_venda_f)}</div>
  </div>
  <div class="mbox" style="border-color:#764ba2;background:#f8f0ff">
    <div class="label">Multiplicador FEV vs ABR</div>
    <div class="val" style="color:#764ba2">{tx_tf_venda_f/tx_tf_venda_a:.2f}×</div>
    <div class="sub">FEV converteu {tx_tf_venda_f/tx_tf_venda_a:.2f}× mais leads TF em vendas</div>
  </div>
  <div class="mbox fev">
    <div class="label">Receita via TF — FEV</div>
    <div class="val">{moeda(fat_tf_f)}</div>
    <div class="sub">{fat_tf_f/fat_f*100:.1f}% do faturamento total</div>
  </div>
  <div class="mbox abr">
    <div class="label">Receita via TF — ABR</div>
    <div class="val">{moeda(fat_tf_a)}</div>
    <div class="sub">{fat_tf_a/fat_a*100:.1f}% do faturamento total {delta_badge(fat_tf_a, fat_tf_f)}</div>
  </div>
</div>

<div class="cause purple" style="margin-top:12px">
  <strong>🔑 Insight Central: {len(overlap_tf):,} pessoas responderam as duas pesquisas</strong> (participaram do ABR e do FEV).
  O TF não é uma base nova a cada lançamento — parte do público já estava morno/quente do ciclo anterior.
  Isso reforça a importância de nurturing entre campanhas para converter quem ficou para trás.
</div>

<h3>👥 Perfil Demográfico Comparado (FEV vs ABR)</h3>
<div class="section-intro">A semelhança de perfil entre as campanhas confirma que a diferença de conversão <strong>não é demográfica</strong> — é de execução. Leads e vendas são dos respondentes Typeform (email-match CRM/Hotmart).</div>

<h4>Gênero</h4>
<table style="width:100%">
  <tr>
    <th class="th-dark" rowspan="2">Gênero</th>
    <th class="th-fev" colspan="3" style="text-align:center">FEV-26</th>
    <th class="th-abr" colspan="3" style="text-align:center">ABR-26</th>
    <th class="th-dark" rowspan="2" style="text-align:right">Δ</th>
  </tr>
  <tr>
    <th class="th-fev" style="text-align:right">%</th><th class="th-fev" style="text-align:right">Leads</th><th class="th-fev" style="text-align:right">Vendas</th>
    <th class="th-abr" style="text-align:right">%</th><th class="th-abr" style="text-align:right">Leads</th><th class="th-abr" style="text-align:right">Vendas</th>
  </tr>
  {genero_rows}
</table>

<h4>Faixa Etária</h4>
<table style="width:100%">
  <tr>
    <th class="th-dark" rowspan="2">Faixa</th>
    <th class="th-fev" colspan="3" style="text-align:center">FEV-26</th>
    <th class="th-abr" colspan="3" style="text-align:center">ABR-26</th>
    <th class="th-dark" rowspan="2" style="text-align:right">Δ</th>
  </tr>
  <tr>
    <th class="th-fev" style="text-align:right">%</th><th class="th-fev" style="text-align:right">Leads</th><th class="th-fev" style="text-align:right">Vendas</th>
    <th class="th-abr" style="text-align:right">%</th><th class="th-abr" style="text-align:right">Leads</th><th class="th-abr" style="text-align:right">Vendas</th>
  </tr>
  {idade_rows}
</table>

<h4>Situação Profissional</h4>
<table style="width:100%">
  <tr>
    <th class="th-dark" rowspan="2">Situação</th>
    <th class="th-fev" colspan="3" style="text-align:center">FEV-26</th>
    <th class="th-abr" colspan="3" style="text-align:center">ABR-26</th>
    <th class="th-dark" rowspan="2" style="text-align:right">Δ</th>
  </tr>
  <tr>
    <th class="th-fev" style="text-align:right">%</th><th class="th-fev" style="text-align:right">Leads</th><th class="th-fev" style="text-align:right">Vendas</th>
    <th class="th-abr" style="text-align:right">%</th><th class="th-abr" style="text-align:right">Leads</th><th class="th-abr" style="text-align:right">Vendas</th>
  </tr>
  {situa_rows}
</table>

<h4>Nível nos Estudos</h4>
<table style="width:100%">
  <tr>
    <th class="th-dark" rowspan="2">Nível</th>
    <th class="th-fev" colspan="3" style="text-align:center">FEV-26</th>
    <th class="th-abr" colspan="3" style="text-align:center">ABR-26</th>
    <th class="th-dark" rowspan="2" style="text-align:right">Δ</th>
  </tr>
  <tr>
    <th class="th-fev" style="text-align:right">%</th><th class="th-fev" style="text-align:right">Leads</th><th class="th-fev" style="text-align:right">Vendas</th>
    <th class="th-abr" style="text-align:right">%</th><th class="th-abr" style="text-align:right">Leads</th><th class="th-abr" style="text-align:right">Vendas</th>
  </tr>
  {nivel_rows}
</table>

<div class="cause blue">
  <strong>📌 Perfil Quase Idêntico:</strong>
  ~59% feminino, ~41% masculino nas duas campanhas.
  Mesmo split de nível: {_pct_col(tf_f_df,'Em relação aos estudos para concursos públicos, você se considera?','Estou do zero'):.0f}% do zero FEV vs {_pct_col(tf_a_df,'Em relação aos estudos para concursos públicos, você se considera?','Estou do zero'):.0f}% ABR.
  A principal diferença de faixa etária é que o ABR tinha mais jovens 18–22 anos
  ({_pct_col(tf_a_df,'Qual a sua idade?','18 a 22 anos'):.1f}% vs {_pct_col(tf_f_df,'Qual a sua idade?','18 a 22 anos'):.1f}% no FEV) —
  faixa com maior barreira financeira. Isso pode ter contribuído marginalmente para a menor conversão do ABR,
  mas não explica o gap de {tx_tf_venda_f/tx_tf_venda_a:.2f}× sozinho.
</div>

<h3>🏠 Composição Familiar (Fator de Urgência)</h3>

<h4>Com quem mora</h4>
<table style="width:100%">
  <tr>
    <th class="th-dark" rowspan="2">Com quem mora</th>
    <th class="th-fev" colspan="3" style="text-align:center">FEV-26</th>
    <th class="th-abr" colspan="3" style="text-align:center">ABR-26</th>
    <th class="th-dark" rowspan="2" style="text-align:right">Δ</th>
  </tr>
  <tr>
    <th class="th-fev" style="text-align:right">%</th><th class="th-fev" style="text-align:right">Leads</th><th class="th-fev" style="text-align:right">Vendas</th>
    <th class="th-abr" style="text-align:right">%</th><th class="th-abr" style="text-align:right">Leads</th><th class="th-abr" style="text-align:right">Vendas</th>
  </tr>
  {mora_rows}
</table>

<h4>Filhos</h4>
<table style="width:100%">
  <tr>
    <th class="th-dark" rowspan="2">Filhos</th>
    <th class="th-fev" colspan="3" style="text-align:center">FEV-26</th>
    <th class="th-abr" colspan="3" style="text-align:center">ABR-26</th>
    <th class="th-dark" rowspan="2" style="text-align:right">Δ</th>
  </tr>
  <tr>
    <th class="th-fev" style="text-align:right">%</th><th class="th-fev" style="text-align:right">Leads</th><th class="th-fev" style="text-align:right">Vendas</th>
    <th class="th-abr" style="text-align:right">%</th><th class="th-abr" style="text-align:right">Leads</th><th class="th-abr" style="text-align:right">Vendas</th>
  </tr>
  {filhos_rows}
</table>
<div class="cause blue">
  <strong>📌 FEV tem mais respondentes com família constituída:</strong>
  {_pct_col(tf_f_df,'Com quem você mora atualmente?','Esposo(a) ou companheiro(a) e filhos'):.1f}%
  vs {_pct_col(tf_a_df,'Com quem você mora atualmente?','Esposo(a) ou companheiro(a) e filhos'):.1f}% no ABR moram com esposo(a) e filhos.
  FEV também tem mais respondentes com 2+ filhos ({_pct_col(tf_f_df,'Quantos filhos você tem?','Dois'):.1f}% + {_pct_col(tf_f_df,'Quantos filhos você tem?','Três ou mais'):.1f}%
  vs {_pct_col(tf_a_df,'Quantos filhos você tem?','Dois'):.1f}% + {_pct_col(tf_a_df,'Quantos filhos você tem?','Três ou mais'):.1f}% ABR).
  Responsabilidade familiar aumenta senso de urgência e propensão de compra — possível fator de melhoria no FEV.
</div>

<h3>🚧 Obstáculos Declarados Comparados</h3>
<table>
  <tr>
    <th class="th-dark">Obstáculo</th>
    <th class="th-fev" style="text-align:right">FEV %</th>
    <th class="th-abr" style="text-align:right">ABR %</th>
    <th class="th-dark" style="text-align:right">Δ (ABR−FEV)</th>
  </tr>
  {obst_rows}
</table>
<div class="two-col">
  <div class="cause blue">
    <strong>📌 FEV tem mais dor metodológica:</strong><br>
    "Não sei estudar do jeito certo" {_pct_notnull(tf_f_df,'Não sei estudar do jeito certo (falta de técnicas de estudos)'):.1f}% FEV
    vs {_pct_notnull(tf_a_df,'Não sei estudar do jeito certo (falta de técnicas de estudos)'):.1f}% ABR (+{_pct_notnull(tf_f_df,'Não sei estudar do jeito certo (falta de técnicas de estudos)')-_pct_notnull(tf_a_df,'Não sei estudar do jeito certo (falta de técnicas de estudos)'):.1f}pp).
    "Não sei montar cronograma" {_pct_notnull(tf_f_df,'Não sei montar um cronograma de estudos'):.1f}% FEV vs {_pct_notnull(tf_a_df,'Não sei montar um cronograma de estudos'):.1f}% ABR.
    Quem sente essas dores entende o valor do produto e converte mais.
  </div>
  <div class="cause orange">
    <strong>⚠️ ABR tem mais barreira financeira:</strong><br>
    "Sem dinheiro para curso" {_pct_notnull(tf_a_df,'Não tenho dinheiro para investir em um curso'):.1f}% ABR
    vs {_pct_notnull(tf_f_df,'Não tenho dinheiro para investir em um curso'):.1f}% FEV (+{_pct_notnull(tf_a_df,'Não tenho dinheiro para investir em um curso')-_pct_notnull(tf_f_df,'Não tenho dinheiro para investir em um curso'):.1f}pp).
    Combined com mais jovens 18–22 (renda mais baixa), parte da menor conversão do ABR pode ter origem em
    barreira financeira real — não resolvida por nurturing ou condições de pagamento melhores.
  </div>
</div>

<h3>🎥 Consciência de Marca — Felipe Graton</h3>
<table>
  <tr><th class="th-dark">Já assistiu Graton?</th><th class="th-fev" style="text-align:right">FEV</th><th class="th-abr" style="text-align:right">ABR</th><th class="th-dark" style="text-align:right">Δ</th></tr>
  {demo_row("Sim (já conhecia)", graton_f_sim, graton_a_sim)}
  {demo_row("Não (novo seguidor)", 100-graton_f_sim, 100-graton_a_sim, invert=True)}
</table>
<div class="cause blue">
  <strong>📌 Brand awareness praticamente igual</strong> ({graton_f_sim:.1f}% FEV vs {graton_a_sim:.1f}% ABR já conheciam o Graton).
  A diferença de conversão portanto <em>não vem de reconhecimento de marca</em> — confirma que o problema está na
  qualidade dos leads capturados fora da pesquisa, no mix de canais e no processo de venda pós-captação.
</div>

<h3>🗺️ Distribuição Geográfica Comparada</h3>
<table>
  <tr><th class="th-dark">Estado</th><th class="th-fev" style="text-align:right">FEV (n | %)</th><th class="th-abr" style="text-align:right">ABR (n | %)</th><th class="th-dark" style="text-align:right">Δ</th></tr>
  {estados_tf_rows}
</table>
<div class="cause blue">
  <strong>📌 FEV cresceu em SP (+{_pct_col(tf_f_df,'De qual estado você é?','São Paulo')-_pct_col(tf_a_df,'De qual estado você é?','São Paulo'):.1f}pp), RJ (+{_pct_col(tf_f_df,'De qual estado você é?','Rio de Janeiro')-_pct_col(tf_a_df,'De qual estado você é?','Rio de Janeiro'):.1f}pp) e CE</strong> — estados com maior renda per capita e menor barreira de compra.
  ABR tinha mais presença no Nordeste (PA, BA) — maior desafio de conversão por renda e acesso a parcelamento.
  Para o próximo lançamento: ajustar lances geográficos para priorizar SP, RJ, RS, PR e DF.
</div>

<!-- 5 CAUSAS RAIZ -->
<h2>🔬 Diagnóstico: 5 Causas Raiz</h2>

<div class="cause red">
  <strong>🔴 CAUSA 1 — Colapso da taxa de conversão em captação: {pct(txconv_f)} → {pct(txconv_a)} (-{abs((txconv_a-txconv_f)/txconv_f*100):.0f}%)</strong><br><br>
  Esta é a causa fundamental. O ABR capturou <strong>{intfmt(nleads_a-nleads_f)} leads a mais</strong> mas converteu muito menos — e isso se concentra nos leads de captação, que respondem por virtualmente 100% dos leads com UTM rastreado.
  As hipóteses: (a) piora na qualidade/intenção do lead captado (mais jovens 18–22, mais barreira financeira);
  (b) a estratégia de mídia de captação gerou mais volume de topo sem sustentar avanço proporcional até a venda;
  (c) o processo comercial/sequência de e-mails pode não ter acompanhado o volume extra.
  <br><strong>Evidência (captação):</strong> FEV taxa {pct(txconv_f)} | ABR taxa {pct(txconv_a)} com {intfmt(nleads_a)} leads — gap de {abs((txconv_a-txconv_f)/txconv_f*100):.0f}% na eficiência de conversão.
</div>

<div class="cause orange">
  <strong>🟠 CAUSA 2 — Google Ads captação mais fragmentado e menos eficiente no ABR</strong><br><br>
  Nas campanhas de captação, o FEV fechou com <strong>{intfmt(ga_conv_cap_f)} conversões</strong> e CPA de <strong>{moeda(ga_cpa_cap_f)}</strong>, enquanto o ABR ficou em <strong>{intfmt(ga_conv_cap_a)} conversões</strong> e CPA de <strong>{moeda(ga_cpa_cap_a)}</strong>.
  O ABR rodou <strong>{ga_ncamp_cap_a} campanhas de captação</strong> no Google contra apenas <strong>{ga_ncamp_cap_f} no FEV</strong> — fragmentação excessiva que divide o orçamento e prejudica a aprendizagem dos algoritmos.
  <br><strong>Evidência (captação):</strong> CPA {moeda(ga_cpa_cap_a)} vs {moeda(ga_cpa_cap_f)} | CTR {pct(ga_ctr_a)} vs {pct(ga_ctr_f)} | {ga_ncamp_cap_a} campanhas captação ABR vs {ga_ncamp_cap_f} FEV.
</div>

<div class="cause yellow">
  <strong>🟡 CAUSA 3 — Budget de captação desperdiçado em anúncios sem retorno ({moeda(waste_total_a)})</strong><br><br>
  Múltiplos anúncios de campanhas de captação Meta Ads no ABR consumiram investimento relevante sem produzir vendas rastreáveis no CRM.
  {f"{waste_list_a[0][0].split(' - ')[0] if waste_list_a else 'N/A'} ({moeda(waste_list_a[0][1]) if waste_list_a else ''}), {waste_list_a[1][0].split(' - ')[0] if len(waste_list_a)>1 else ''} ({moeda(waste_list_a[1][1]) if len(waste_list_a)>1 else ''}), {waste_list_a[2][0].split(' - ')[0] if len(waste_list_a)>2 else ''} ({moeda(waste_list_a[2][1]) if len(waste_list_a)>2 else ''})"} — sozinhos somam ~{moeda(sum(x[1] for x in waste_list_a[:3]))} com 0 vendas confirmadas.
  Isso aumenta o CPA efetivo de venda e distorce a percepção de eficiência do canal de captação.
  <br><strong>Evidência:</strong> {moeda(waste_total_a)} = {waste_total_a/inv_a_cap*100:.1f}% do investimento de captação sem retorno rastreado.
</div>

<div class="cause blue">
  <strong>🔵 CAUSA 4 — Budget alocado em campanhas não-captação no Google ({moeda(ga_inv_a_other)})</strong><br><br>
  O ABR rodou <strong>{ga_noncap_ncamp_a} campanhas não-captação</strong> no Google Ads (pré-qualificação, tráfego/aulas, alcance/lembrete) que gastaram <strong>{moeda(ga_inv_a_other)}</strong> com apenas <strong>{intfmt(ga_noncap_conv_a)} conversões</strong> — CPA médio de <strong>{moeda(ga_noncap_cpa_a)}</strong> contra {moeda(ga_cpa_cap_a)} nas campanhas de captação.
  Esse investimento não gera leads qualificados diretamente e distorce os números de eficiência do Google.
  No FEV, praticamente todo o budget Google foi concentrado em captação, o que explica parte da eficiência superior.
  <br><strong>Evidência:</strong> {ga_noncap_ncamp_a} campanhas não-captação = {moeda(ga_inv_a_other)} ({ga_inv_a_other/ga_inv_a*100:.1f}% do budget Google ABR) com retorno desprezível em leads.
</div>

<div class="cause purple">
  <strong>🟣 CAUSA 5 — Variação no ticket médio e mix de produto</strong><br><br>
  O ticket médio do ABR foi <strong>{moeda(ticket_a)}</strong> vs <strong>{moeda(ticket_f)}</strong> no FEV — {"aumento" if ticket_a >= ticket_f else "queda"} de {abs((ticket_a-ticket_f)/ticket_f*100):.1f}%.
  Esse efeito de ticket foi secundário: o principal impacto no faturamento veio da queda no volume de vendas.
  Ainda assim, a variação de ticket pode indicar diferença no mix de oferta (parcelamento, preço praticado ou proporção de meios de pagamento).
  <br><strong>Evidência:</strong> Hotmart FEV ticket R${fat_hm_f/len(hm_f):,.2f} vs ABR R${fat_hm_a/len(hm_a):,.2f} | TMB FEV R${fat_tmb_f/len(tmb_f):,.2f} vs ABR R${fat_tmb_a/len(tmb_a):,.2f}.
</div>

<!-- PLANO DE AÇÃO -->
<h2>🚀 Plano de Ação — Próximo Lançamento</h2>

<div class="action-box">
  <strong>✅ 1. Concentrar budget Google exclusivamente em captação</strong><br>
  Eliminar campanhas de pré-qualificação, tráfego/aulas e alcance/lembrete do Google Ads durante a fase de captação.
  No ABR, essas {ga_noncap_ncamp_a} campanhas não-captação desperdiçaram {moeda(ga_inv_a_other)} com CPA médio de {moeda(ga_noncap_cpa_a)}.
  Meta operacional: 100% do budget Google em captação, CPA abaixo de {moeda(ga_cpa_cap_f)}.
</div>

<div class="action-box">
  <strong>✅ 2. Reduzir fragmentação: máximo 20 campanhas de captação no Google</strong><br>
  Reduzir de {ga_ncamp_cap_a} para no máximo 20 campanhas de captação com grupos de anúncios bem definidos (quente/específico/frio).
  No FEV foram {ga_ncamp_cap_f} campanhas de captação com CPA {moeda(ga_cpa_cap_f)} — esse é o benchmark para o próximo lançamento.
  Consolidar versões deletadas e variantes similares para concentrar orçamento nos melhores públicos.
</div>

<div class="action-box">
  <strong>✅ 3. Pausar anúncios sem venda após R$3.000 investidos</strong><br>
  Estabelecer regra de pausa automática: qualquer anúncio com &gt;R$3.000 investido e 0 vendas confirmadas no CRM
  deve ser pausado e avaliado. Isso evitaria a perda de ~{moeda(waste_total_a)} identificada no ABR.
</div>

<div class="action-box">
  <strong>✅ 4. Monitorar taxa de conversão CRM→Venda em tempo real</strong><br>
  Criar dashboard semanal durante o lançamento comparando a taxa de conversão com o benchmark do FEV ({pct(txconv_f)}).
  Se cair abaixo de 0,8%, acionar revisão imediata de: sequência de e-mails, qualidade do lead e mix de canais.
</div>

<div class="action-box">
  <strong>✅ 5. Renovar criativos: reduzir overlap com campanha anterior</strong><br>
  {len(overlap)} criativos foram compartilhados entre FEV e ABR. Para o próximo lançamento, desenvolver pelo menos
  70% de criativos novos para evitar fadiga de audiência — principalmente nos públicos quentes (remarketing).
</div>

<div class="action-box">
  <strong>✅ 6. Segmentar Google por objetivo: captação vs aquecimento</strong><br>
  Se quiser manter campanhas de branding (Demand Gen), separá-las em <strong>budget isolado (máx 20%)</strong>
  e não contabilizá-las no CPA de captação. Assim a performance de captação fica clara e o CPA não é distorcido.
</div>

<div class="action-box">
  <strong>✅ 7. Revisão de copy e sequência de nurturing pós-lead</strong><br>
  Com {intfmt(nleads_a)} leads no CRM e taxa de conversão de apenas {pct(txconv_a)}, há {intfmt(nleads_a - nvend_a)}
  potenciais compradores que não converteram. Uma sequência de reativação pós-lançamento pode recuperar parte desse valor.
</div>

<div class="action-box">
  <strong>✅ 8. Usar a dor metodológica como principal ângulo de copy (sinal forte do Typeform)</strong><br>
  O FEV tinha mais respondentes com "Não sei estudar do jeito certo" (+{_pct_notnull(tf_f_df,'Não sei estudar do jeito certo (falta de técnicas de estudos)')-_pct_notnull(tf_a_df,'Não sei estudar do jeito certo (falta de técnicas de estudos)'):.1f}pp) e "Não sei montar cronograma" (+{_pct_notnull(tf_f_df,'Não sei montar um cronograma de estudos')-_pct_notnull(tf_a_df,'Não sei montar um cronograma de estudos'):.1f}pp), dores que o produto resolve diretamente.
  Copy e criativos que abordam <em>método, cronograma e estrutura</em> ressoam mais com compradores — priorizar esses ângulos.
</div>

<div class="action-box">
  <strong>✅ 9. Segmentação geográfica mais agressiva em SP, RJ, RS e DF</strong><br>
  FEV cresceu +{_pct_col(tf_f_df,'De qual estado você é?','São Paulo')-_pct_col(tf_a_df,'De qual estado você é?','São Paulo'):.1f}pp em SP e +{_pct_col(tf_f_df,'De qual estado você é?','Rio de Janeiro')-_pct_col(tf_a_df,'De qual estado você é?','Rio de Janeiro'):.1f}pp em RJ. Estados com renda maior = menor barreira financeira = maior conversão.
  Aumentar lances geográficos nesses estados e criar variações de copy específicas para SP/RJ.
</div>

<div class="action-box">
  <strong>✅ 10. Criar oferta de acesso para o segmento jovem 18–22 anos</strong><br>
  ABR tinha {_pct_col(tf_a_df,'Qual a sua idade?','18 a 22 anos'):.1f}% de jovens 18–22 vs {_pct_col(tf_f_df,'Qual a sua idade?','18 a 22 anos'):.1f}% no FEV — faixa com barreira financeira real.
  Uma opção de menor entrada, parcelamento estendido ou trial pode converter esse segmento que responde a pesquisa mas não compra.
</div>

<div class="action-box">
  <strong>✅ 11. Explorar o segmento com família constituída (Esposo+filhos)</strong><br>
  FEV teve {_pct_col(tf_f_df,'Com quem você mora atualmente?','Esposo(a) ou companheiro(a) e filhos'):.1f}% vs {_pct_col(tf_a_df,'Com quem você mora atualmente?','Esposo(a) ou companheiro(a) e filhos'):.1f}% ABR de respondentes casados com filhos — maior senso de urgência e responsabilidade.
  Criativos que abordam "estabilidade para a família", "concurso para dar uma vida melhor para os filhos" podem amplificar a conversão nesse segmento.
</div>

<!-- FONTES -->
<h2>📁 Fontes de Dados</h2>
<table>
<tr><th class="th-dark">Fonte</th><th class="th-dark">FEV-26</th><th class="th-dark">ABR-26</th></tr>
<tr><td>CRM (Active Campaign)</td><td>{intfmt(nleads_f)} leads</td><td>{intfmt(nleads_a)} leads</td></tr>
<tr><td>Hotmart</td><td>{len(hm_f)} vendas | {moeda(fat_hm_f)}</td><td>{len(hm_a)} vendas | {moeda(fat_hm_a)}</td></tr>
<tr><td>TMB</td><td>{len(tmb_f)} vendas | {moeda(fat_tmb_f)}</td><td>{len(tmb_a)} vendas | {moeda(fat_tmb_a)}</td></tr>
<tr><td>Meta Ads</td><td>{len(ma_f):,} linhas | {moeda(ma_inv_f)}</td><td>{len(ma_a):,} linhas | {moeda(ma_inv_a)}</td></tr>
<tr><td>Google Ads Campanhas</td><td>{ga_ncamp_f} campanhas | {moeda(ga_inv_f)}</td><td>{ga_ncamp_a} campanhas | {moeda(ga_inv_a)}</td></tr>
<tr><td>Typeform</td><td>{len(tf_f_df):,} respostas | TF→Venda {tx_tf_venda_f:.2f}%</td><td>{len(tf_a_df):,} respostas | TF→Venda {tx_tf_venda_a:.2f}%</td></tr>
</table>

</div><!-- /content -->

<div class="footer">
  <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos — Análise Interna</p>
  <p style="margin-top:6px">
    <a href="index.html" style="color:#1a1a2e;font-weight:600">← Índice central</a>
    &nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="[PBB-FEV-26]/INDEX_[PBB-FEV-26].html" style="color:{FEV_COLOR};font-weight:600">← Ver FEV-26</a>
    &nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="[PBB-ABR-26]/INDEX_[PBB-ABR-26].html" style="color:{ABR_COLOR};font-weight:600">Ver ABR-26 →</a>
  </p>
</div>

</div><!-- /container -->
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

import os
print(f"\nArquivo gerado: {OUT}")
print(f"Tamanho: {os.path.getsize(OUT)//1024} KB")
print("=" * 70)
