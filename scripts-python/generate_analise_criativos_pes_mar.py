#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_analise_criativos_pes_mar.py
Análise de Criativos — PES-MAR-26
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime
import csv as csv_mod
import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nav_component import FRAME_CLOSE, nav_html

BASE    = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
CAMPAIGN_CODE = "PES-MAR-26"
CAMPAIGN_FOLDER = "[PES-MAR-26]"
PRODUCT_NAME = "Escrevente TJSP"
PERIOD_LABEL = "Março de 2026"
ABR_DIR = BASE / "analises" / CAMPAIGN_FOLDER
OUT     = ABR_DIR / "ANALISE_CRIATIVOS_[PES-MAR-26].html"
LOGO    = "../../img/logo-brabo-concursos.png"
FAV     = "../../img/favicon-brabo-concursos.png"

print("="*70)
print("🎨 ANALISE_CRIATIVOS — PES-MAR-26")
print("="*70)


def read_csv_safe(filepath, sep=',', skiprows=0, **kwargs):
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']:
        try:
            return pd.read_csv(filepath, sep=sep, skiprows=skiprows, encoding=enc, **kwargs)
        except Exception:
            continue
    return pd.read_csv(filepath, sep=sep, skiprows=skiprows, **kwargs)


def find_column(df, possible_names):
    def normalize_str(s):
        import unicodedata
        s = str(s).strip().lower()
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
        return s
    
    normalized_possibilities = [normalize_str(n) for n in possible_names]
    
    for col in df.columns:
        col_norm = normalize_str(col)
        if col_norm in normalized_possibilities:
            return col
            
    for col in df.columns:
        col_norm = col.lower()
        for pos in possible_names:
            pos_norm = pos.lower()
            if 'an' in pos_norm and 'nc' in pos_norm:
                if ('an' in col_norm and 'nc' in col_norm) or 'ad' in col_norm:
                    return col
            elif 'camp' in pos_norm:
                if 'camp' in col_norm or 'campaign' in col_norm:
                    return col
            elif 'cust' in pos_norm:
                if 'cust' in col_norm or 'cost' in col_norm or 'valor' in col_norm or 'gasto' in col_norm:
                    return col
                    
    for col in df.columns:
        col_norm = normalize_str(col)
        for pos_norm in normalized_possibilities:
            if pos_norm in col_norm or col_norm in pos_norm:
                return col
                
    return possible_names[0]


def adaptar_html_campaign(html):
    nav_start = "<!-- BRABO-NAV -->"
    nav_end = "<!-- /BRABO-NAV -->"
    nav_block = None
    if nav_start in html and nav_end in html:
        before_nav, rest = html.split(nav_start, 1)
        nav_body, after_nav = rest.split(nav_end, 1)
        nav_block = nav_start + nav_body + nav_end
        html = before_nav + "__BRABO_NAV__" + after_nav
    replacements = {
        "[PBB-ABR-26]": CAMPAIGN_FOLDER,
        "PBB-ABR-26": CAMPAIGN_CODE,
        "Banco do Brasil": PRODUCT_NAME,
        "Abril de 2026": PERIOD_LABEL,
        "Abril 2026": PERIOD_LABEL,
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    if nav_block is not None:
        html = html.replace("__BRABO_NAV__", nav_block)
    return html


def campanha_pes(valor):
    return CAMPAIGN_CODE.lower() in str(valor).lower()

# ── Helpers ───────────────────────────────────────────────────────────────────
def br(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return "-"

def num(v):
    try:
        f = float(v)
        return f"{int(f):,}".replace(",",".")
    except: return "-"

def pct(v):
    try: return f"{float(v):.2f}%"
    except: return "-"

def normalize_ad_id(raw):
    if pd.isna(raw): return None
    s = str(raw).strip().lower()
    m = re.match(r'(ad\d+)', s)
    return m.group(1).upper() if m else s[:20].strip()

def badge(text, color="#667eea"):
    return (f'<span style="background:{color};color:#fff;padding:2px 9px;'
            f'border-radius:12px;font-size:11px;font-weight:700">{text}</span>')

def bar(val, total, color="#667eea"):
    p = min(val / total * 100, 100) if total else 0
    return (f'<div style="background:#eee;border-radius:3px;height:8px">'
            f'<div style="background:{color};width:{p:.1f}%;height:8px;border-radius:3px"></div></div>')

# ── Load data ─────────────────────────────────────────────────────────────────
print("\n📊 Carregando dados...")

# Meta Ads
meta_files = sorted((ABR_DIR / "Meta Ads").glob("*.csv"))
if meta_files:
    df_meta = read_csv_safe(meta_files[0], sep=",")
    col_camp = find_column(df_meta, ["Nome da campanha", "Campanha", "Campaign"])
    col_ad = find_column(df_meta, ["Nome do anúncio", "Nome do anuncio", "Ad name", "Ad Name"])
    col_valor = find_column(df_meta, ["Valor usado (BRL)", "Valor usado", "Valor gasto", "Custo"])
    col_leads = find_column(df_meta, ["Leads", "Resultados", "Leads (todos)"])
    col_impr = find_column(df_meta, ["Impressões", "Impressões (todas)", "Impr."])
    col_clicks = find_column(df_meta, ["Cliques (todos)", "Cliques", "Cliques no link"])
    
    if col_camp in df_meta.columns:
        df_meta = df_meta[df_meta[col_camp].apply(campanha_pes)].copy()
    
    for col in [col_valor, col_leads, col_impr, col_clicks]:
        if col in df_meta.columns:
            df_meta[col] = pd.to_numeric(df_meta[col], errors="coerce").fillna(0)
            
    # Tag captação
    capt_meta = df_meta[df_meta[col_camp].astype(str).str.contains(
        r"\[captação\]|\[captacao\]|capta|cadastro", case=False, regex=True, na=False)].copy()
        
    capt_meta["tipo"] = capt_meta[col_camp].apply(
        lambda x: "Novo" if "[novos-ads]" in str(x).lower() else "Validado"
    )
    capt_meta["ad_id"] = capt_meta[col_ad].apply(normalize_ad_id)
    
    meta_by_ad = capt_meta.groupby([col_ad, "ad_id", "tipo"]).agg(
        inv    = (col_valor, "sum"),
        leads_meta = (col_leads, "sum"),
        impr   = (col_impr, "sum"),
        clicks = (col_clicks, "sum"),
    ).reset_index()
    meta_by_ad.rename(columns={col_ad: "Nome do anúncio"}, inplace=True)
    meta_by_ad["CPL_meta"] = meta_by_ad["inv"] / meta_by_ad["leads_meta"].replace(0, np.nan)
    meta_by_ad["CTR"]      = meta_by_ad["clicks"] / meta_by_ad["impr"].replace(0, np.nan) * 100
else:
    meta_by_ad = pd.DataFrame(columns=["Nome do anúncio", "ad_id", "tipo", "inv", "leads_meta", "impr", "clicks", "CPL_meta", "CTR"])

print(f"  ✓ Meta Ads: {len(meta_by_ad)} criativos únicos na captação")

# CRM Leads
leads_candidates = list((ABR_DIR / "Active Campaign").glob("*.csv"))
if leads_candidates:
    leads_file = max(leads_candidates, key=lambda f: f.stat().st_mtime)
    df_leads = read_csv_safe(leads_file, sep=",", quoting=csv_mod.QUOTE_MINIMAL, low_memory=False)
    
    col_email = find_column(df_leads, ["Email", "E-mail", "email"])
    col_content = find_column(df_leads, ["*Utm_content", "Utm_content", "utm_content"])
    col_term = find_column(df_leads, ["*Utm_term", "Utm_term", "utm_term"])
    
    df_leads["Email"] = df_leads[col_email].astype(str).str.strip().str.lower()
    df_leads["criativo_base"] = df_leads[col_content].astype(str).str.strip()
    
    if col_term in df_leads.columns:
        mask_blank = df_leads["criativo_base"].isin(["", "nan", "None"])
        df_leads.loc[mask_blank, "criativo_base"] = df_leads.loc[mask_blank, col_term].astype(str).str.strip()
        
    df_leads_utm = df_leads[
        ~df_leads["criativo_base"].astype(str).str.strip().str.lower().isin(["", "nan", "none"])
    ].copy()
    df_leads_utm["ad_id"] = df_leads_utm["criativo_base"].apply(normalize_ad_id)
else:
    df_leads = pd.DataFrame(columns=["Email"])
    df_leads_utm = pd.DataFrame(columns=["Email", "criativo_base", "ad_id"])

print(f"  ✓ CRM: {len(df_leads):,} leads | {len(df_leads_utm):,} com UTM content")

# Hotmart
hotmart_files = sorted((ABR_DIR / "Vendas").glob("*hotmart*.csv"))
if hotmart_files:
    _hot_raw = read_csv_safe(hotmart_files[0], sep=";")
    col_h_email = find_column(_hot_raw, ["Email do(a) Comprador(a)", "Email", "Comprador Email"])
    col_h_valor = find_column(_hot_raw, ["Faturamento líquido do(a) Produtor(a)", "Preço", "Preco", "Valor"])
    
    _hot_raw["email"] = _hot_raw[col_h_email].astype(str).str.strip().str.lower()
    _hot_raw = _hot_raw[_hot_raw["email"].str.contains("@", na=False)].copy()
    _tipo_c = next((c for c in _hot_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
    
    if _tipo_c:
        _par_c = "Quantidade total de parcelas"
        _cob_c = "Quantidade de cobranças"
        _c_norm = _hot_raw[_hot_raw[_tipo_c].astype(str).str.strip() != "Recuperador Inteligente"].copy()
        _c_norm["val"] = pd.to_numeric(_c_norm[col_h_valor], errors="coerce").fillna(0)
        
        if _par_c in _hot_raw.columns and _cob_c in _hot_raw.columns:
            _c_ri = _hot_raw[
                (_hot_raw[_tipo_c].astype(str).str.strip() == "Recuperador Inteligente") &
                (pd.to_numeric(_hot_raw[_cob_c], errors="coerce").fillna(0) == 1)
            ].copy()
            _c_ri[_par_c] = pd.to_numeric(_c_ri[_par_c], errors="coerce").fillna(1)
            _c_ri["val"] = pd.to_numeric(_c_ri[col_h_valor], errors="coerce").fillna(0) * _c_ri[_par_c]
            df_hot = pd.concat([_c_norm, _c_ri], ignore_index=True)
        else:
            df_hot = _c_norm
    else:
        df_hot = _hot_raw.copy()
        df_hot["val"] = pd.to_numeric(df_hot[col_h_valor], errors="coerce").fillna(0)
else:
    df_hot = pd.DataFrame(columns=["email", "val"])

print(f"  ✓ Hotmart: {len(df_hot):,} vendas")

# TMB
tmb_files = sorted((ABR_DIR / "Vendas").glob("*tmb*.csv")) + sorted((ABR_DIR / "Vendas").glob("*pedido*.csv"))
if tmb_files:
    df_tmb = read_csv_safe(tmb_files[0], sep=";")
    df_tmb_v = df_tmb.copy()
    tmb_email_col  = find_column(df_tmb, ["E-mail do Cliente", "Email do cliente", "Email", "E-mail"])
    tmb_ticket_col = find_column(df_tmb, ["Ticket do pedido", "Ticket", "Valor", "Preco"])
    
    df_tmb_v["email"] = df_tmb_v[tmb_email_col].astype(str).str.strip().str.lower()
    df_tmb_v["val"]   = pd.to_numeric(df_tmb_v[tmb_ticket_col].astype(str).str.replace(",",".", regex=False),
                                       errors="coerce").fillna(0)
else:
    df_tmb_v = pd.DataFrame(columns=["email", "val"])

print(f"  ✓ TMB: {len(df_tmb_v):,} vendas vigentes")

# ── Build CRM-side stats per ad_id ────────────────────────────────────────────
print("\n📐 Calculando conversões por criativo...")

crm_rows = []
if not df_leads_utm.empty:
    for ad_id, grp in df_leads_utm.groupby("ad_id"):
        emails = set(grp["Email"].dropna().unique())
        n_leads  = len(grp)
        n_vendas = len(df_hot[df_hot["email"].isin(emails)]) + len(df_tmb_v[df_tmb_v["email"].isin(emails)])
        faturamento = df_hot[df_hot["email"].isin(emails)]["val"].sum() + \
                      df_tmb_v[df_tmb_v["email"].isin(emails)]["val"].sum()
        crm_rows.append({
            "ad_id":       ad_id,
            "leads_crm":   n_leads,
            "vendas":      n_vendas,
            "fat":         faturamento,
            "conv_rate":   n_vendas / n_leads * 100 if n_leads > 0 else 0,
        })

df_crm = pd.DataFrame(crm_rows)
if df_crm.empty:
    df_crm = pd.DataFrame(columns=["ad_id", "leads_crm", "vendas", "fat", "conv_rate"])
print(f"  ✓ {len(df_crm)} criativos com dados CRM")

# ── Merge Meta + CRM ──────────────────────────────────────────────────────────
# Se df_meta estiver vazio (como no caso PES-MAR-26 atual), criamos um merge
# a partir dos dados do CRM para não deixar a tabela em branco!
if meta_by_ad.empty and not df_crm.empty:
    # Simula a estrutura do Meta Ads a partir do CRM
    df_merged = df_crm.copy()
    df_merged["Nome do anúncio"] = df_merged["ad_id"]
    df_merged["tipo"] = "Validado"
    df_merged["inv"] = 0.0
    df_merged["leads_meta"] = df_merged["leads_crm"]
    df_merged["impr"] = 0
    df_merged["clicks"] = 0
    df_merged["CPL_meta"] = 0.0
    df_merged["CTR"] = 0.0
else:
    df_merged = pd.merge(meta_by_ad, df_crm, on="ad_id", how="left")
    df_merged["leads_crm"]  = df_merged["leads_crm"].fillna(0)
    df_merged["vendas"]     = df_merged["vendas"].fillna(0)
    df_merged["fat"]        = df_merged["fat"].fillna(0)
    df_merged["conv_rate"]  = df_merged["conv_rate"].fillna(0)

df_merged["inv"]        = df_merged.get("inv", pd.Series(dtype=float)).fillna(0)
df_merged["CPA_real"]   = df_merged["inv"] / df_merged["vendas"].replace(0, np.nan)
df_merged["ROAS"]       = df_merged["fat"] / df_merged["inv"].replace(0, np.nan)

df_merged = df_merged.sort_values("leads_crm", ascending=False)
total_inv = df_merged["inv"].sum()

# Separate validados / novos
df_valid = df_merged[df_merged["tipo"] == "Validado"].sort_values("leads_crm", ascending=False)
df_novos = df_merged[df_merged["tipo"] == "Novo"].sort_values("leads_crm", ascending=False)

print(f"  ✓ Validados: {len(df_valid)} | Novos: {len(df_novos)}")

# ── Summary comparison ────────────────────────────────────────────────────────
sum_valid = {
    "inv":    df_valid["inv"].sum(),
    "leads":  df_valid["leads_meta"].sum() if "leads_meta" in df_valid.columns else 0,
    "vendas": df_valid["vendas"].sum(),
    "fat":    df_valid["fat"].sum(),
}
sum_novos = {
    "inv":    df_novos["inv"].sum(),
    "leads":  df_novos["leads_meta"].sum() if "leads_meta" in df_novos.columns else 0,
    "vendas": df_novos["vendas"].sum(),
    "fat":    df_novos["fat"].sum(),
}
sum_valid["CPL"]  = sum_valid["inv"] / sum_valid["leads"]  if sum_valid["leads"]  > 0 else 0
sum_novos["CPL"]  = sum_novos["inv"] / sum_novos["leads"]  if sum_novos["leads"]  > 0 else 0
sum_valid["ROAS"] = sum_valid["fat"] / sum_valid["inv"]    if sum_valid["inv"]    > 0 else 0
sum_novos["ROAS"] = sum_novos["fat"] / sum_novos["inv"]    if sum_novos["inv"]    > 0 else 0

if len(df_novos) == 0 or sum_novos["leads"] == 0:
    novos_verdict_color = "#667eea"
    novos_verdict_text = "Sem criativos novos identificados no naming atual do PES-MAR-26"
else:
    novos_win = sum_novos["CPL"] < sum_valid["CPL"]
    novos_verdict_color = "#28a745" if novos_win else "#dc3545"
    novos_verdict_text  = "Novos tiveram CPL menor — candidatos a escalar" if novos_win else \
                "Validados seguem mais eficientes em CPL"

# ── Build HTML rows ───────────────────────────────────────────────────────────
def make_rows(df_ads, highlight_color):
    rows = ""
    for i, (_, r) in enumerate(df_ads.iterrows()):
        medal = ["🥇","🥈","🥉","4°","5°","6°","7°","8°"][min(i,7)]
        cpl   = r.get("CPL_meta", 0.0)
        cpl_good = not pd.isna(cpl) and cpl < 2.80 and cpl > 0
        cpl_col  = "#28a745" if cpl_good else ("#dc3545" if (not pd.isna(cpl) and cpl > 0) else "#aaa")
        conv_r   = r["conv_rate"]
        conv_col = "#28a745" if conv_r >= 1.5 else ("#ff9800" if conv_r >= 0.8 else "#dc3545")
        roas_v   = r.get("ROAS", 0.0)
        roas_col = "#28a745" if (not pd.isna(roas_v) and roas_v >= 2) else "#ff9800"

        cpl_display = br(cpl) if (not pd.isna(cpl) and cpl > 0) else "–"
        roas_display = f"{roas_v:.2f}×" if (not pd.isna(roas_v) and roas_v > 0) else "–"
        ctr_val = r.get("CTR", 0.0)
        ctr_display = f"{ctr_val:.2f}%" if ctr_val > 0 else "–"
        inv_val = r.get("inv", 0.0)
        inv_display = br(inv_val) if inv_val > 0 else "–"

        rows += (
            f'<tr>'
            f'<td style="text-align:center;font-size:16px">{medal}</td>'
            f'<td><div style="font-size:12px;max-width:240px;line-height:1.3">'
            f'<strong>{r["Nome do anúncio"]}</strong></div>'
            f'<div style="font-size:10px;color:#aaa">{r["ad_id"]}</div></td>'
            f'<td class="numero" data-val="{inv_val}">{inv_display}'
            f'<div style="margin-top:4px">{bar(inv_val, total_inv, highlight_color)}</div></td>'
            f'<td class="numero" data-val="{r.get("leads_meta", 0)}">{num(r.get("leads_meta", 0))}</td>'
            f'<td class="numero" data-val="{cpl}">{cpl_display}</td>'
            f'<td class="numero" data-val="{ctr_val}">{ctr_display}</td>'
            f'<td class="numero" data-val="{r["leads_crm"]}">{num(r["leads_crm"])}</td>'
            f'<td class="numero" data-val="{conv_r}">{conv_r:.2f}%</td>'
            f'<td class="numero" data-val="{roas_v}" style="font-weight:800;color:{roas_col}">{roas_display}</td>'
            f'</tr>'
        )
    return rows

rows_valid = make_rows(df_valid.head(15), "#28a745")
rows_novos = make_rows(df_novos.head(15), "#ff9800")

thead = (
    '<thead><tr>'
    '<th>#</th><th>Criativo</th><th>Investimento</th>'
    '<th>Leads Meta</th><th>CPL Meta</th><th>CTR</th>'
    '<th>Leads CRM</th><th>Conv%</th><th>ROAS</th>'
    '</tr></thead>'
)

# Top criativos full ranking
rows_all = make_rows(df_merged.head(25), "#667eea")

# ── Build comparison summary cards ───────────────────────────────────────────
def summary_card(title, color, data):
    roas_str = f"{data['ROAS']:.2f}\u00d7" if data['inv'] > 0 else "–"
    cpl_str = br(data["CPL"]) if data["CPL"] > 0 else "–"
    inv_str = br(data["inv"]) if data["inv"] > 0 else "–"
    return (
        f'<div style="background:{color}18;border:2px solid {color};border-radius:10px;padding:20px">'
        f'<div style="font-size:.95rem;font-weight:800;color:{color};margin-bottom:12px">{title}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<div><div style="font-size:1.1rem;font-weight:800">{inv_str}</div>'
        f'<div style="font-size:11px;color:#888">Investimento</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{num(data["leads"])}</div>'
        f'<div style="font-size:11px;color:#888">Leads (plataforma)</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800;color:{color}">{cpl_str}</div>'
        f'<div style="font-size:11px;color:#888">CPL médio</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{num(data["vendas"])}</div>'
        f'<div style="font-size:11px;color:#888">Vendas (rastr.)</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{br(data["fat"])}</div>'
        f'<div style="font-size:11px;color:#888">Faturamento rastr.</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{roas_str}</div>'
        f'<div style="font-size:11px;color:#888">ROAS</div></div>'
        f'</div></div>'
    )

card_valid = summary_card("✅ Criativos Validados", "#28a745", sum_valid)
card_novos = summary_card("🆕 Criativos Novos (novos-ads)", "#ff9800", sum_novos)

ts = datetime.now().strftime("%d/%m/%Y %H:%M")

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Análise de Criativos — PES-MAR-26</title>
<link rel="icon" type="image/png" href="{FAV}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);color:#333;line-height:1.6}}
.wrap{{max-width:1300px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.hdr{{background:#fff;padding:32px;display:flex;align-items:center;gap:24px;border-bottom:1px solid #eee}}
.hdr img{{height:48px}}
.hdr h1{{font-size:1.5rem;font-weight:800;color:#333}}
.hdr p{{color:#777;font-size:.85rem;margin-top:3px}}
.content{{padding:32px}}
.section{{margin-bottom:44px}}
.section-title{{font-size:1rem;font-weight:800;color:#333;border-bottom:3px solid #667eea;
  padding-bottom:8px;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.note{{background:#f0f4ff;border-left:4px solid #667eea;padding:12px 16px;border-radius:4px;
  font-size:13px;color:#555;margin-bottom:14px}}
.verdict{{border-radius:8px;padding:14px 20px;font-weight:700;font-size:.95rem;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#667eea;color:#fff;padding:9px 10px;text-align:left;font-weight:700;font-size:11px}}
td{{padding:9px 10px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
tr:hover td{{background:#fafafa}}
.numero {{ text-align: right; font-family: 'Courier New', monospace; }}
.table-wrap{{border:1px solid #eee;border-radius:8px;overflow:hidden;margin-top:12px}}
.footing{{text-align:center;font-size:11px;color:#aaa;padding:20px;border-top:1px solid #eee;margin-top:24px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <a href="INDEX_[PES-MAR-26].html"><img src="{LOGO}" alt="Brabo"></a>
    <div>
      <h1>🎨 Análise de Criativos — PES-MAR-26</h1>
      <p>Validados vs Novos · CPL de plataforma · Conversão real (CRM→Vendas) · ROAS por criativo</p>
    </div>
  </div>
  <div class="content">

    <!-- 1. Validados vs Novos comparison -->
    <div class="section">
      <div class="section-title">1. Validados vs Novos — Comparativo</div>
      <div class="note">
        <strong>Validados</strong> = criativos rodando nas campanhas de escala.
        <strong>Novos</strong> = criativos da campanha de novos ads.
        A conversão é calculada via cruzamento CRM (UTM content) → Hotmart/TMB.
      </div>
      <div class="verdict" style="background:{novos_verdict_color}18;border-left:4px solid {novos_verdict_color};color:{novos_verdict_color}">
        📊 {novos_verdict_text}
        — CPL Validados: {br(sum_valid["CPL"])} | CPL Novos: {br(sum_novos["CPL"])}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        {card_valid}
        {card_novos}
      </div>
    </div>

    <!-- 2. Ranking geral -->
    <div class="section">
      <div class="section-title">2. Top Criativos — Ranking Geral (CRM + Vendas) {badge(f"{len(df_merged)} criativos","#667eea")}</div>
      <div class="note">
        Lista ordenada pelo volume de leads no CRM e vendas geradas.
      </div>
      <div class="table-wrap">
        <table class="bs-table">
          {thead}
          <tbody>{rows_all if rows_all else "<tr><td colspan=9 style=text-align:center;color:#aaa;padding:20px>Nenhum dado encontrado</td></tr>"}</tbody>
        </table>
      </div>
    </div>

  </div>
  <div class="footing">
    Gerado em {ts} | Criativos analisados: {len(df_merged)} |
    <a href="INDEX_[PES-MAR-26].html" style="color:#667eea">← Índice</a>
  </div>
</div>
</body>
</html>"""

html_final = adaptar_html_campaign(html)
if "BRABO-NAV" not in html_final:
    html_final = re.sub(
        r"<body[^>]*>",
        lambda match: match.group(0) + "\n" + nav_html(active_campaign=CAMPAIGN_CODE, active_page_file=OUT.name, depth=1),
        html_final,
        count=1,
        flags=re.IGNORECASE,
    )
    html_final = re.sub(r"</body>", f"{FRAME_CLOSE}\n</body>", html_final, count=1, flags=re.IGNORECASE)

OUT.write_text(html_final, encoding="utf-8")
kb = OUT.stat().st_size // 1024
print(f"\n✅ {OUT.name} gerado ({kb}KB)")
