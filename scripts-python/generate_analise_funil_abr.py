#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_analise_funil_abr.py
Análise Completa de Funil — PBB-ABR-26

Segmentação automática por tags de nomenclatura:
  [captação] / [pré-qualificação] / [rmk/engajamento/tráfego]

Seções geradas:
  1. KPIs do Funil Completo
  2. Investimento por Etapa (Meta + Google)
  3. Meta Ads: Distribuição de Verba vs Meta Estratégica
  4. Público Quente vs Frio vs Específico
  5. Pré-Qualificação: Eficiência de Aquecimento
  6. Ranking de Criativos: Validados (5) vs Novos (3)
  7. Comparativo de Canais: Meta vs Google
  8. Curva Diária + Janela Crítica (Pitch → ROAS)
  9. Diagnóstico e Recomendações de Realocação
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import unicodedata
import warnings
warnings.filterwarnings('ignore')

# ── Paths ────────────────────────────────────────────────────────────────────
BASE    = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ABR_DIR = BASE / "analises" / "[PBB-ABR-26]"
OUT     = ABR_DIR / "ANALISE_FUNIL_[PBB-ABR-26].html"
LOGO    = "../../img/logo-brabo-concursos.png"
FAV     = "../../img/favicon-brabo-concursos.png"

print("="*70)
print("🚀 ANALISE_FUNIL — PBB-ABR-26")
print("="*70)

# ── Helpers ───────────────────────────────────────────────────────────────────
def br(v, prefix="R$ "):
    try: return f"{prefix}{float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return str(v)

def pct(v):
    try: return f"{float(v):.1f}%"
    except: return "-"

def num(v):
    try:
        f = float(v)
        return f"{int(f):,}".replace(",", ".") if f >= 1000 else str(int(f))
    except: return str(v)

def dec(v, d=2):
    try: return f"{float(v):.{d}f}"
    except: return "-"

def pct1(v):
  try:
    return f"{float(v):.1f}%".replace(".", ",")
  except:
    return "-"

def _norm_key(s):
  s = str(s)
  s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
  return "".join(ch for ch in s.lower() if ch.isalnum())

def pick_col(df, aliases):
  alias_keys = {_norm_key(a) for a in aliases}
  for c in df.columns:
    if _norm_key(c) in alias_keys:
      return c
  return None

def get_etapa_meta(nome):
    n = str(nome).lower()
    if "[captação]" in n or "[captacao]" in n: return "captacao"
    if "[pré-qualificação]" in n or "[pre-qualificacao]" in n: return "pre_quali"
    if any(k in n for k in ["[engajamento]","[rmk]","[replay]","[depoimento]",
                              "[lembrete]","[tráfego]","[trafego]","[aula"]): return "rmk"
    return "outro"

def get_etapa_ga(nome):
    n = str(nome).lower()
    if "[performance-max]" in n: return "p_max"
    if "[captação]" in n or "[captacao]" in n: return "captacao"
    if "[pré-qualificação]" in n or "[pre-qualificacao]" in n: return "pre_quali"
    if any(k in n for k in ["[tráfego]","[trafego]","[alcance]","[replay]",
                              "[aula","[rmk]"]): return "rmk"
    return "outro"

def get_publico(nome):
    n = str(nome).lower()
    if "[quente]" in n: return "quente"
    if "[frio]" in n: return "frio"
    if "[específico]" in n or "[especifico]" in n: return "especifico"
    return "outro"

def get_bucket(nome):
    n = str(nome).lower()
    if "[principal]" in n: return "principal"
    if "[potencial]" in n: return "potencial"
    if "[reels]" in n: return "reels"
    if "[novos-ads]" in n: return "novos-ads"
    if "[imagem]" in n: return "imagem"
    if "[teste]" in n: return "teste"
    return "outro"

def bar_pct(val, total, color="#667eea", height=20):
    p = min(val / total * 100, 100) if total else 0
    return (f'<div style="background:#eee;border-radius:4px;height:{height}px;overflow:hidden">'
            f'<div style="background:{color};width:{p:.1f}%;height:100%;border-radius:4px"></div></div>')

def badge(text, color="#667eea"):
    return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:12px;font-size:11px;font-weight:700">{text}</span>')

# ── Load data ─────────────────────────────────────────────────────────────────
print("\n📊 Carregando dados...")

# Meta Ads
meta_dir = ABR_DIR / "Meta Ads"
meta_candidates = [
  meta_dir / "MA-Campanhas-Completas-PBB-ABR-26.csv",
  meta_dir / "meta-pbb-abr-26.csv",
]
meta_file = next((p for p in meta_candidates if p.exists()), None)
if meta_file is None:
  csvs = sorted(meta_dir.glob("*.csv"))
  if not csvs:
    raise FileNotFoundError(f"Nenhum CSV encontrado em {meta_dir}")
  meta_file = csvs[0]

df_meta = pd.read_csv(meta_file, encoding="utf-8")
for col in ["Valor usado (BRL)", "Leads", "Impressões", "Cliques (todos)",
            "ThruPlays", "Visualizações", "Cliques no link"]:
    if col in df_meta.columns:
        df_meta[col] = pd.to_numeric(df_meta[col], errors="coerce").fillna(0)
df_meta["Dia"] = pd.to_datetime(df_meta["Dia"], errors="coerce")
df_meta["etapa"]  = df_meta["Nome da campanha"].apply(get_etapa_meta)
df_meta["publico"] = df_meta["Nome da campanha"].apply(get_publico)
df_meta["bucket"]  = df_meta["Nome da campanha"].apply(get_bucket)
print("  ✓ Meta Ads:", len(df_meta), "linhas")

# Google Ads
ga_dir = ABR_DIR / "Google Ads"
ga_campaign_candidates = [
  ga_dir / "Performance da campanha-pbb-abr-26.csv",
  ga_dir / "google-ads-performance-da-campanha-pbb-abr-26.csv",
]
ga_campaign_file = next((p for p in ga_campaign_candidates if p.exists()), None)
if ga_campaign_file is None:
  csvs = sorted(ga_dir.glob("*.csv"))
  ga_campaign_file = next((p for p in csvs if "performancedacampanha" in _norm_key(p.name)), None)
  if ga_campaign_file is None:
    raise FileNotFoundError(f"CSV de campanha Google Ads não encontrado em {ga_dir}")

ga_ads_file = next((p for p in sorted(ga_dir.glob("*.csv")) if "performancedosanuncios" in _norm_key(p.name)), None)

df_ga = pd.read_csv(ga_campaign_file, encoding="utf-8", skiprows=2)
ga_click_col = pick_col(df_ga, ["Cliques"])
ga_conv_col = pick_col(df_ga, ["Conversões", "Conversoes"])
ga_view_col = pick_col(df_ga, [
  "Visualizações", "Visualizacoes", "Visualizações de vídeo", "Visualizacoes de video",
  "Views", "Video views"
])
ga_view_conv_col = pick_col(df_ga, [
  "Conv. de visualização", "Conv. de visualizacao", "Conversões de visualização", "Conversoes de visualizacao"
])
ga_cpv_col = pick_col(df_ga, [
  "CPV méd.", "CPV médio", "CPV medio", "Custo por visualização", "Custo por visualizacao"
])

for col in ["Custo", ga_conv_col, ga_click_col, "Impr.", ga_view_col, ga_view_conv_col, ga_cpv_col]:
  if col and col in df_ga.columns:
    df_ga[col] = pd.to_numeric(
      df_ga[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
      errors="coerce"
    ).fillna(0)

if ga_click_col and ga_click_col != "Cliques":
  df_ga["Cliques"] = df_ga[ga_click_col]
if ga_conv_col and ga_conv_col != "Conversões":
  df_ga["Conversões"] = df_ga[ga_conv_col]

ga_views_source = "none"
if ga_view_col and ga_view_col in df_ga.columns:
  df_ga["VisualizacoesGA"] = df_ga[ga_view_col]
  ga_views_source = "views"
elif ga_view_conv_col and ga_view_conv_col in df_ga.columns:
  # Fallback: não é view real, mas permite manter continuidade até o export correto.
  df_ga["VisualizacoesGA"] = df_ga[ga_view_conv_col]
  ga_views_source = "view_conv_proxy"
else:
  df_ga["VisualizacoesGA"] = 0

if ga_cpv_col and ga_cpv_col in df_ga.columns:
  df_ga["CPV_GA"] = df_ga[ga_cpv_col]
else:
  df_ga["CPV_GA"] = np.nan

# Fallback real de vídeo/CPV a partir de "Performance dos anúncios"
if ga_ads_file is not None:
  df_ga_ads = pd.read_csv(ga_ads_file, encoding="utf-8", skiprows=2)
  ga_ads_campaign_col = pick_col(df_ga_ads, ["Campanha"])
  ga_ads_cost_col = pick_col(df_ga_ads, ["Custo"])
  ga_ads_view_col = pick_col(df_ga_ads, [
    "Visualizações do TrueView", "Visualizacoes do TrueView", "Visualizações", "Visualizacoes",
    "Views", "Video views"
  ])
  ga_ads_cpv_col = pick_col(df_ga_ads, [
    "CPV médio do TrueView", "CPV medio do TrueView", "CPV méd.", "CPV médio", "CPV medio",
    "Custo por visualização", "Custo por visualizacao"
  ])

  for col in [ga_ads_cost_col, ga_ads_view_col, ga_ads_cpv_col]:
    if col and col in df_ga_ads.columns:
      df_ga_ads[col] = pd.to_numeric(
        df_ga_ads[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce"
      ).fillna(0)

  if ga_ads_campaign_col and ga_ads_view_col:
    ga_ads_grp = df_ga_ads.groupby(ga_ads_campaign_col).agg(
      views_ads=(ga_ads_view_col, "sum"),
      cost_ads=(ga_ads_cost_col, "sum") if ga_ads_cost_col else (ga_ads_view_col, "sum"),
      cpv_ads_mean=(ga_ads_cpv_col, "mean") if ga_ads_cpv_col else (ga_ads_view_col, "sum"),
    )
    ga_ads_grp["cpv_ads"] = np.where(
      ga_ads_grp["views_ads"] > 0,
      ga_ads_grp["cost_ads"] / ga_ads_grp["views_ads"],
      ga_ads_grp["cpv_ads_mean"]
    )

    df_ga = df_ga.merge(ga_ads_grp[["views_ads", "cpv_ads"]], left_on="Campanha", right_index=True, how="left")

    if ga_views_source != "views":
      # Quando houver views reais em nível anúncio, prioriza esse valor sobre proxy.
      has_ads_views = (df_ga["views_ads"].fillna(0) > 0)
      df_ga["VisualizacoesGA"] = np.where(has_ads_views, df_ga["views_ads"], df_ga["VisualizacoesGA"])
      df_ga["VisualizacoesGA"] = pd.to_numeric(df_ga["VisualizacoesGA"], errors="coerce").fillna(0)
      if has_ads_views.any():
        ga_views_source = "views_trueview_ads"

    if df_ga["CPV_GA"].isna().all() and "cpv_ads" in df_ga.columns:
      df_ga["CPV_GA"] = df_ga["cpv_ads"]

df_ga["etapa"] = df_ga["Campanha"].apply(get_etapa_ga)
print("  ✓ Google Ads:", len(df_ga), "campanhas")

# Hotmart — Parcelado/À vista líquido direto; RI cobrança=1 × parcelas = valor total do contrato
df_hot_raw = pd.read_csv(ABR_DIR / "Vendas" / "hotmart pbb-abr-26.csv", sep=";", encoding="utf-8")
_tipo_col_hot = next((c for c in df_hot_raw.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
_par_col_hot  = "Quantidade total de parcelas"
_cob_col_hot  = "Quantidade de cobranças"
_hot_norm = df_hot_raw[df_hot_raw[_tipo_col_hot].astype(str).str.strip() != "Recuperador Inteligente"].copy()
_hot_norm["val"] = pd.to_numeric(_hot_norm["Faturamento líquido do(a) Produtor(a)"].astype(str), errors="coerce").fillna(0)
_hot_ri = df_hot_raw[
    (df_hot_raw[_tipo_col_hot].astype(str).str.strip() == "Recuperador Inteligente") &
    (pd.to_numeric(df_hot_raw[_cob_col_hot], errors="coerce").fillna(0) == 1)
].copy()
_hot_ri[_par_col_hot] = pd.to_numeric(_hot_ri[_par_col_hot], errors="coerce").fillna(1)
_hot_ri["val"] = pd.to_numeric(_hot_ri["Faturamento líquido do(a) Produtor(a)"].astype(str), errors="coerce").fillna(0) * _hot_ri[_par_col_hot]
df_hot = pd.concat([_hot_norm, _hot_ri], ignore_index=True)
total_hot_fat = df_hot["val"].sum()
total_hot_n   = len(df_hot)
print(f"  ✓ Hotmart: {total_hot_n} vendas | R${total_hot_fat:,.0f} líquido")

# TMB — todos os 170 rows (oficial inclui cancelados)
df_tmb = pd.read_csv(ABR_DIR / "Vendas" / "tmb pbb-abr-26.csv", sep=";", encoding="utf-8")
tmb_tick_col = next((c for c in df_tmb.columns if "icket" in c.lower() and "pedido" in c.lower()), None)
df_tmb_vig = df_tmb.copy()  # todos
df_tmb_vig["ticket"] = pd.to_numeric(
    df_tmb_vig[tmb_tick_col].astype(str).str.replace(",","."), errors="coerce").fillna(0)
total_tmb_fat = df_tmb_vig["ticket"].sum()
total_tmb_n   = len(df_tmb_vig)
print(f"  ✓ TMB: {total_tmb_n} rows | R${total_tmb_fat:,.0f}")

# CRM Leads
leads_candidates = list((ABR_DIR / "Active Campaign").glob("*.csv"))
leads_file = max(leads_candidates, key=lambda f: f.stat().st_mtime)
df_leads = pd.read_csv(leads_file, encoding="utf-8", low_memory=False)
total_leads_crm = len(df_leads)
print(f"  ✓ CRM: {total_leads_crm:,} leads ({leads_file.name})")

# ── Compute KPIs ──────────────────────────────────────────────────────────────
print("\n📐 Calculando métricas...")

# Meta by etapa
meta_agg = df_meta.groupby("etapa").agg(
    inv   = ("Valor usado (BRL)", "sum"),
    leads = ("Leads",             "sum"),
    impr  = ("Impressões",        "sum"),
    tp    = ("ThruPlays",         "sum"),
).reset_index()

meta_total_inv   = df_meta["Valor usado (BRL)"].sum()
meta_total_leads = df_meta["Leads"].sum()
meta_total_link_clicks = df_meta["Cliques no link"].sum() if "Cliques no link" in df_meta.columns else 0

meta_capt  = meta_agg[meta_agg["etapa"] == "captacao"].iloc[0]  if len(meta_agg[meta_agg["etapa"]=="captacao"]) else None
meta_pq    = meta_agg[meta_agg["etapa"] == "pre_quali"].iloc[0] if len(meta_agg[meta_agg["etapa"]=="pre_quali"]) else None
meta_rmk   = meta_agg[meta_agg["etapa"] == "rmk"].iloc[0]       if len(meta_agg[meta_agg["etapa"]=="rmk"]) else None

# GA by etapa
ga_agg = df_ga.groupby("etapa").agg(
    custo = ("Custo",      "sum"),
    conv  = ("Conversões", "sum"),
    click = ("Cliques",    "sum"),
  view  = ("VisualizacoesGA", "sum"),
).reset_index()

ga_total_inv  = df_ga["Custo"].sum()
ga_total_conv = df_ga["Conversões"].sum()
ga_total_clicks = df_ga["Cliques"].sum() if "Cliques" in df_ga.columns else 0
ga_total_views = df_ga["VisualizacoesGA"].sum()
ga_cpv_calc = ga_total_inv / ga_total_views if ga_total_views > 0 else np.nan

ga_capt = ga_agg[ga_agg["etapa"] == "captacao"].iloc[0] if len(ga_agg[ga_agg["etapa"]=="captacao"]) else None
ga_pq   = ga_agg[ga_agg["etapa"] == "pre_quali"].iloc[0] if len(ga_agg[ga_agg["etapa"]=="pre_quali"]) else None
ga_pmax = ga_agg[ga_agg["etapa"] == "p_max"].iloc[0]     if len(ga_agg[ga_agg["etapa"]=="p_max"]) else None

# Totals
total_inv = meta_total_inv + ga_total_inv
total_vendas = total_hot_n + total_tmb_n
total_fat    = total_hot_fat + total_tmb_fat
roas = total_fat / total_inv if total_inv > 0 else 0

# Avg ticket
avg_ticket = total_fat / total_vendas if total_vendas > 0 else 0

# CPL (Meta only, captação)
meta_capt_inv   = float(meta_capt["inv"])   if meta_capt is not None else 0
meta_capt_leads = float(meta_capt["leads"]) if meta_capt is not None else 0
cpl_meta = meta_capt_inv / meta_capt_leads if meta_capt_leads > 0 else 0

# CPA total
cpa_total = total_inv / total_vendas if total_vendas > 0 else 0

# Pré-quali
meta_pq_inv = float(meta_pq["inv"]) if meta_pq is not None else 0
meta_pq_tp  = float(meta_pq["tp"])  if meta_pq is not None else 0
meta_pq_impr= float(meta_pq["impr"]) if meta_pq is not None else 0
cptp_meta = meta_pq_inv / meta_pq_tp if meta_pq_tp > 0 else 0

ga_pq_inv  = float(ga_pq["custo"]) if ga_pq is not None else 0
ga_pq_conv = float(ga_pq["conv"])  if ga_pq is not None else 0
ga_pq_view = float(ga_pq["view"])  if ga_pq is not None else 0

# Budget distribution Meta captação
capt_meta = df_meta[df_meta["etapa"] == "captacao"]
bkt_agg = capt_meta.groupby("bucket").agg(
    inv   = ("Valor usado (BRL)", "sum"),
    leads = ("Leads", "sum"),
).reset_index()
bkt_total = bkt_agg["inv"].sum()
bkt_agg["perc"] = bkt_agg["inv"] / bkt_total * 100
bkt_agg["CPL"]  = bkt_agg["inv"] / bkt_agg["leads"].replace(0, np.nan)

# Público breakdown in captação
pub_agg = capt_meta.groupby("publico").agg(
    inv   = ("Valor usado (BRL)", "sum"),
    leads = ("Leads", "sum"),
).reset_index()
pub_agg["perc"] = pub_agg["inv"] / pub_agg["inv"].sum() * 100
pub_agg["CPL"]  = pub_agg["inv"] / pub_agg["leads"].replace(0, np.nan)

# Criativos: Validados vs Novos
novos_camp = capt_meta[capt_meta["bucket"] == "novos-ads"]
valid_camp = capt_meta[capt_meta["bucket"] != "novos-ads"]

def top_ads(df_camp, n=10):
    agg = df_camp.groupby("Nome do anúncio").agg(
        inv    = ("Valor usado (BRL)", "sum"),
        leads  = ("Leads",             "sum"),
        impr   = ("Impressões",        "sum"),
        clicks = ("Cliques (todos)",   "sum"),
    ).reset_index()
    agg["CPL"] = agg["inv"] / agg["leads"].replace(0, np.nan)
    agg["CTR"] = agg["clicks"] / agg["impr"].replace(0, np.nan) * 100
    return agg.sort_values("leads", ascending=False).head(n)

top_valid = top_ads(valid_camp, 6)
top_novos = top_ads(novos_camp, 6)

# Daily curve
daily = df_meta.groupby("Dia").agg(
    inv   = ("Valor usado (BRL)", "sum"),
    leads = ("Leads",             "sum"),
).reset_index().dropna(subset=["Dia"]).sort_values("Dia")
daily["CPL"] = daily["inv"] / daily["leads"].replace(0, np.nan)

# Define phases based on daily data
# Phase 1: Pre-quali (before captação ramp-up = before Mar 29)
# Phase 2: Captação (Mar 29 – Apr 12)
# Phase 3: Pitch/RMK (Apr 13+)
PITCH_START = pd.Timestamp("2026-04-13")
CAPT_START  = pd.Timestamp("2026-03-29")

def get_fase(d):
    if d < CAPT_START:  return "pre_quali"
    if d < PITCH_START: return "captacao"
    return "pitch_roas"

daily["fase"] = daily["Dia"].apply(get_fase)
fase_agg = daily.groupby("fase").agg(inv=("inv","sum"), leads=("leads","sum")).reset_index()
fase_total = fase_agg["inv"].sum()
fase_agg["perc"] = fase_agg["inv"] / fase_total * 100

max_daily_inv = daily["inv"].max()

print("  ✓ Métricas calculadas")
print(f"    Investimento total: R${total_inv:,.0f}")
print(f"    ROAS: {roas:.2f}x")
print(f"    CPA: R${cpa_total:,.2f}")

# ── Build HTML sections ───────────────────────────────────────────────────────

# ---- Funnel KPIs cards
def kpi_card(label, value, sub="", color="#667eea"):
    return (f'<div class="kpi-card" style="border-top:4px solid {color}">'
            f'<div class="kpi-val" style="color:{color}">{value}</div>'
            f'<div class="kpi-lbl">{label}</div>'
            f'{"<div class=kpi-sub>"+sub+"</div>" if sub else ""}'
            f'</div>')

kpis_html = (
    kpi_card("Investimento Total",   br(total_inv),     f"Meta: {br(meta_total_inv)} | Google: {br(ga_total_inv)}", "#f5576c") +
    kpi_card("Faturamento Total",    br(total_fat),     f"Hotmart: {br(total_hot_fat)} | TMB: {br(total_tmb_fat)}", "#28a745") +
    kpi_card("ROAS",                 f"{roas:.2f}×",    f"Meta {br(meta_total_inv)} | GA {br(ga_total_inv)}",       "#ff9800") +
    kpi_card("Leads CRM",            num(total_leads_crm), f"Captação Meta: {num(meta_capt_leads)} leads",          "#667eea") +
    kpi_card("Vendas",               num(total_vendas), f"Hotmart: {num(total_hot_n)} | TMB: {num(total_tmb_n)}",  "#17a2b8") +
    kpi_card("CPA Total",            br(cpa_total, "R$ "), f"Ticket médio: {br(avg_ticket)}",                      "#764ba2")
)

# ---- Funil visual (Topo -> Cliques -> Leads -> Vendas)
top_funnel = float(meta_pq_tp + ga_pq_view)
clicks_total = float(meta_total_link_clicks + ga_total_clicks)
leads_funnel = float(total_leads_crm)
vendas_funnel = float(total_vendas)

def safe_ratio(a, b):
    return (a / b * 100) if b and b > 0 else 0

f_click_top = safe_ratio(clicks_total, top_funnel)
f_lead_click = safe_ratio(leads_funnel, clicks_total)
f_venda_lead = safe_ratio(vendas_funnel, leads_funnel)
f_lead_top = safe_ratio(leads_funnel, top_funnel)
f_venda_top = safe_ratio(vendas_funnel, top_funnel)

top_label = "ThruPlays + Views YouTube (Meta + Google)" if ga_pq_view > 0 else "ThruPlays (Meta Pre-Qualificação)"
top_value = top_funnel if ga_pq_view > 0 else meta_pq_tp

funnel_html = f"""
      <div class="kpi-funil-layout">
        <div class="funil-kpi-wrap">
          <div class="funil-kpi-head">
            <h3>Funil de Conversão Geral</h3>
            <p>Jornada completa do aquecimento até vendas</p>
          </div>
          <div class="funil-viz">
            <div class="funil-step" style="--w:100%;--c:#17a2b8">
              <span class="funil-step-label">{top_label}</span>
              <span class="funil-step-value">{num(top_value)}<small>100,0%</small></span>
            </div>
            <div class="funil-step" style="--w:82%;--c:#4f7cff">
              <span class="funil-step-label">Cliques (Meta + Google)</span>
              <span class="funil-step-value">{num(clicks_total)}<small>{pct1(f_click_top)} do topo</small></span>
            </div>
            <div class="funil-step" style="--w:56%;--c:#667eea">
              <span class="funil-step-label">Leads CRM</span>
              <span class="funil-step-value">{num(leads_funnel)}<small>{pct1(f_lead_top)} do topo</small></span>
            </div>
            <div class="funil-step" style="--w:42%;--c:#f5576c">
              <span class="funil-step-label">Vendas (Hotmart + TMB)</span>
              <span class="funil-step-value">{num(vendas_funnel)}<small>{pct1(f_venda_top)} do topo</small></span>
            </div>
          </div>
          <div class="funil-rates">
            <span class="funil-rate"><strong>Topo -> Clique:</strong> {pct1(f_click_top)}</span>
            <span class="funil-rate"><strong>Clique -> Lead:</strong> {pct1(f_lead_click)}</span>
            <span class="funil-rate"><strong>Lead -> Venda:</strong> {pct1(f_venda_lead)}</span>
            <span class="funil-rate"><strong>ROAS Total:</strong> {roas:.2f}x</span>
          </div>
        </div>
        <div>
          <div class="kpi-grid">{kpis_html}</div>
        </div>
      </div>
"""

# ---- Investment by stage
def etapa_row(label, inv, total_inv_all, leads_or_conv, metric_lbl, color):
    p = inv / total_inv_all * 100 if total_inv_all else 0
    cpl = inv / leads_or_conv if leads_or_conv > 0 else 0
    return (f'<tr>'
            f'<td>{badge(label, color)}</td>'
            f'<td>{br(inv)}</td>'
            f'<td><div style="display:flex;align-items:center;gap:8px">'
            f'{bar_pct(inv, total_inv_all, color)}'
            f'<span style="font-weight:700;color:{color}">{p:.1f}%</span></div></td>'
            f'<td>{num(leads_or_conv)}</td>'
            f'<td style="font-weight:700">{br(cpl, "R$ ")}</td>'
            f'<td><small style="color:#888">{metric_lbl}</small></td>'
            f'</tr>')

etapa_rows_meta = ""
for _, r in meta_agg.iterrows():
    color = {"captacao":"#667eea","pre_quali":"#f5576c","rmk":"#ff9800","outro":"#ccc"}[r["etapa"]]
    label = {"captacao":"Captação","pre_quali":"Pré-Qualificação","rmk":"RMK/Engajamento","outro":"Outro"}[r["etapa"]]
    cpl_v = r["inv"] / r["leads"] if r["leads"] > 0 else 0
    ml = "CPThruPlay" if r["etapa"] == "pre_quali" else "CPL"
    ml_val = (r["inv"] / r["tp"] if r["tp"] > 0 else 0) if r["etapa"] == "pre_quali" else cpl_v
    etapa_rows_meta += (
        f'<tr>'
        f'<td>{badge(label, color)}</td>'
        f'<td>{br(r["inv"])}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">'
        f'{bar_pct(r["inv"], meta_total_inv, color)}'
        f'<span style="font-weight:700;color:{color}">{r["inv"]/meta_total_inv*100:.1f}%</span></div></td>'
        f'<td>{num(r["leads"]) if r["etapa"] != "pre_quali" else num(r["tp"])}</td>'
        f'<td style="font-weight:700">{br(ml_val, "R$ ")}</td>'
        f'<td><small style="color:#888">{"CPThruPlay" if r["etapa"]=="pre_quali" else "CPL"}</small></td>'
        f'</tr>'
    )

etapa_rows_ga = ""
for _, r in ga_agg.iterrows():
    color = {"captacao":"#667eea","pre_quali":"#f5576c","p_max":"#9c27b0","rmk":"#ff9800","outro":"#ccc"}[r["etapa"]]
    label = {"captacao":"Captação","pre_quali":"Pré-Qualificação","p_max":"Performance Max","rmk":"RMK/Tráfego","outro":"Outro"}[r["etapa"]]
    cpa_v = r["custo"] / r["conv"] if r["conv"] > 0 else 0
    etapa_rows_ga += (
        f'<tr>'
        f'<td>{badge(label, color)}</td>'
        f'<td>{br(r["custo"])}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">'
        f'{bar_pct(r["custo"], ga_total_inv, color)}'
        f'<span style="font-weight:700;color:{color}">{r["custo"]/ga_total_inv*100:.1f}%</span></div></td>'
        f'<td>{num(r["conv"])}</td>'
        f'<td style="font-weight:700">{br(cpa_v, "R$ ")}</td>'
        f'<td><small style="color:#888">Custo/Conv</small></td>'
        f'</tr>'
    )

# ---- Budget distribution vs target
TARGETS = {"principal": 70, "potencial": 25, "reels": 5, "novos-ads": 0, "imagem": 5, "teste": 0}
BUCKET_LABELS = {
    "principal": "Principal (70% meta)",
    "potencial": "Potencial (25% meta)",
    "reels":     "Reels (5% meta)",
    "novos-ads": "Novos Ads (teste)",
    "imagem":    "Imagem",
    "teste":     "Teste",
    "outro":     "Outro",
}
bkt_rows = ""
for _, r in bkt_agg.sort_values("inv", ascending=False).iterrows():
    bk  = r["bucket"]
    tgt = TARGETS.get(bk, None)
    real_p = r["perc"]
    tgt_lbl = f'{tgt}%' if tgt else "–"
    delta = real_p - tgt if tgt is not None else None
    delta_html = ""
    if delta is not None:
        arrow = "▲" if delta > 0 else "▼"
        col   = "#dc3545" if abs(delta) > 10 else "#28a745"
        delta_html = f'<span style="color:{col};font-weight:700">{arrow}{abs(delta):.1f}pp</span>'
    bkt_rows += (
        f'<tr>'
        f'<td><strong>{BUCKET_LABELS.get(bk, bk)}</strong></td>'
        f'<td>{br(r["inv"])}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">'
        f'{bar_pct(r["inv"], bkt_total, "#667eea")}'
        f'<span style="font-weight:700">{real_p:.1f}%</span></div></td>'
        f'<td style="color:#888">{tgt_lbl}</td>'
        f'<td>{delta_html}</td>'
        f'<td>{num(r["leads"])}</td>'
        f'<td style="font-weight:700">{br(r["CPL"], "R$ ") if not pd.isna(r["CPL"]) else "–"}</td>'
        f'</tr>'
    )

# ---- Público (quente/frio/específico)
pub_colors = {"quente":"#f5576c","frio":"#667eea","especifico":"#ff9800","outro":"#ccc"}
pub_rows = ""
for _, r in pub_agg.sort_values("inv", ascending=False).iterrows():
    col = pub_colors.get(r["publico"], "#ccc")
    pub_rows += (
        f'<tr>'
        f'<td>{badge(r["publico"].capitalize(), col)}</td>'
        f'<td>{br(r["inv"])}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">'
        f'{bar_pct(r["inv"], pub_agg["inv"].sum(), col)}'
        f'<span style="font-weight:700;color:{col}">{r["perc"]:.1f}%</span></div></td>'
        f'<td>{num(r["leads"])}</td>'
        f'<td style="font-weight:700">{br(r["CPL"], "R$ ") if not pd.isna(r["CPL"]) else "–"}</td>'
        f'</tr>'
    )

# ---- Criativos table builder
def criativo_table(df_ads, title, color, is_novos=False):
    rows = ""
    for i, (_, r) in enumerate(df_ads.iterrows()):
        medal = ["🥇","🥈","🥉","4°","5°","6°"][i] if i < 6 else f"{i+1}°"
        cpl_v = r["CPL"]
        cpl_good = not pd.isna(cpl_v) and cpl_v < 2.80
        cpl_html  = (f'<span style="color:#28a745;font-weight:800">{br(cpl_v, "R$ ")}</span>'
                     if cpl_good else f'<span style="color:#dc3545;font-weight:700">{br(cpl_v, "R$ ") if not pd.isna(cpl_v) else "–"}</span>')
        rows += (
            f'<tr>'
            f'<td style="font-size:18px;text-align:center">{medal}</td>'
            f'<td style="max-width:260px"><small>{r["Nome do anúncio"]}</small></td>'
            f'<td>{br(r["inv"])}</td>'
            f'<td style="font-weight:700">{num(r["leads"])}</td>'
            f'<td>{cpl_html}</td>'
            f'<td>{dec(r["CTR"])}%</td>'
            f'</tr>'
        )
    return (
        f'<h3 style="margin-top:24px;color:{color}">{title}</h3>'
        f'<table>'
        f'<thead><tr>'
        f'<th>#</th><th>Criativo</th><th>Investimento</th>'
        f'<th>Leads</th><th>CPL</th><th>CTR</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    )

criativos_html = (
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">'
    + '<div>' + criativo_table(top_valid, "✅ Criativos Validados", "#28a745") + '</div>'
    + '<div>' + criativo_table(top_novos, "🆕 Criativos Novos (novos-ads)", "#ff9800", True) + '</div>'
    + '</div>'
)

# Summary: best novo vs best validado
best_novo_cpl  = float(top_novos.iloc[0]["CPL"])  if len(top_novos) > 0 else 0
best_valid_cpl = float(top_valid.iloc[0]["CPL"]) if len(top_valid) > 0 else 0
novos_verdict = "superou os validados" if best_novo_cpl < best_valid_cpl else "não superou os validados"
novos_verdict_color = "#28a745" if best_novo_cpl < best_valid_cpl else "#dc3545"
best_novo_name  = top_novos.iloc[0]["Nome do anúncio"] if len(top_novos) > 0 else "–"
best_valid_name = top_valid.iloc[0]["Nome do anúncio"] if len(top_valid) > 0 else "–"

# ---- Channel comparison
meta_capt_inv_v   = float(meta_capt["inv"])   if meta_capt is not None else 0
meta_capt_leads_v = float(meta_capt["leads"]) if meta_capt is not None else 0
ga_capt_inv_v     = float(ga_capt["custo"])   if ga_capt is not None else 0
ga_capt_conv_v    = float(ga_capt["conv"])    if ga_capt is not None else 0

cpl_meta_capt = meta_capt_inv_v / meta_capt_leads_v if meta_capt_leads_v > 0 else 0
cpa_ga_capt   = ga_capt_inv_v   / ga_capt_conv_v   if ga_capt_conv_v   > 0 else 0
ga_pq_inv_v   = float(ga_pq["custo"]) if ga_pq is not None else 0
ga_pq_conv_v  = float(ga_pq["conv"])  if ga_pq is not None else 0

canal_rows = (
    f'<tr><td>{badge("Meta Ads","#1877f2")}</td>'
    f'<td>{br(meta_total_inv)}</td>'
    f'<td>{num(meta_total_leads)}</td>'
    f'<td style="font-weight:700">{br(cpl_meta, "R$ ")}</td>'
    f'<td>CPL</td>'
    f'<td>{bar_pct(meta_total_inv, total_inv, "#1877f2")}</td></tr>'

    f'<tr><td>{badge("Google Ads","#4285f4")}</td>'
    f'<td>{br(ga_total_inv)}</td>'
    f'<td>{num(ga_total_conv)}</td>'
    f'<td style="font-weight:700">{br(ga_total_inv/ga_total_conv if ga_total_conv else 0, "R$ ")}</td>'
    f'<td>Custo/Conv</td>'
    f'<td>{bar_pct(ga_total_inv, total_inv, "#4285f4")}</td></tr>'
)

# Pre-quali channel comparison
pq_rows = ""
if meta_pq is not None:
    pq_rows += (
        f'<tr><td>{badge("Meta Ads Pré-Q","#1877f2")}</td>'
        f'<td>{br(meta_pq_inv)}</td>'
        f'<td>{num(meta_pq_tp)} ThruPlays</td>'
        f'<td style="font-weight:700">{br(cptp_meta, "R$ ")}</td>'
        f'<td>R$/ThruPlay</td></tr>'
    )
if ga_pq is not None:
  if ga_pq_view > 0:
    cpv_pq = ga_pq_inv_v / ga_pq_view
    pq_rows += (
      f'<tr><td>{badge("Google Ads Pré-Q","#4285f4")}</td>'
      f'<td>{br(ga_pq_inv_v)}</td>'
      f'<td>{num(ga_pq_view)} views</td>'
      f'<td style="font-weight:700">{br(cpv_pq, "R$ ")}</td>'
      f'<td>CPV</td></tr>'
    )
  else:
    cpconv_pq = ga_pq_inv_v / ga_pq_conv_v if ga_pq_conv_v > 0 else 0
    pq_rows += (
      f'<tr><td>{badge("Google Ads Pré-Q","#4285f4")}</td>'
      f'<td>{br(ga_pq_inv_v)}</td>'
      f'<td>{num(ga_pq_conv_v)} conv</td>'
      f'<td style="font-weight:700">{br(cpconv_pq, "R$ ")}</td>'
      f'<td>Custo/Conv</td></tr>'
    )

ga_pre_quali_note = ""
if ga_pq_view > 0:
  if ga_views_source == "views_trueview_ads":
    src = "visualizações do TrueView"
  elif ga_views_source == "views":
    src = "visualizações"
  else:
    src = "conv. de visualização (proxy)"
  cpv_pq_note = ga_pq_inv_v / ga_pq_view if ga_pq_view > 0 else np.nan
  ga_pre_quali_note = (
    f' Google/YouTube registrou <strong>{num(ga_pq_view)} {src}</strong>'
    f' com custo médio de <strong>{br(cpv_pq_note, "R$ ")}/view</strong> na pré-quali.'
  )

# ---- Daily curve (CSS bars)
daily_rows = ""
max_daily = daily["inv"].max()
for _, r in daily.iterrows():
    d    = r["Dia"].strftime("%d/%m")
    fase = r["fase"]
    col  = {"pre_quali":"#f5576c","captacao":"#667eea","pitch_roas":"#28a745"}[fase]
    h    = max(int(r["inv"] / max_daily * 120), 2)
    cpl_txt = f'CPL R${r["CPL"]:.2f}' if not pd.isna(r["CPL"]) and r["leads"] > 5 else ""
    daily_rows += (
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:28px">'
        f'<span style="font-size:9px;color:{col};font-weight:700;writing-mode:vertical-rl;'
        f'transform:rotate(180deg);height:36px;overflow:hidden">{cpl_txt}</span>'
        f'<div title="{d}: R${r["inv"]:,.0f} | {int(r["leads"])} leads" '
        f'style="background:{col};width:20px;height:{h}px;border-radius:3px 3px 0 0;cursor:default"></div>'
        f'<span style="font-size:9px;color:#666;writing-mode:vertical-rl;'
        f'transform:rotate(180deg);height:28px">{d}</span>'
        f'</div>'
    )

# Phase legend
fase_total_v = fase_agg["inv"].sum()
fase_legend = ""
for _, r in fase_agg.iterrows():
    col_f = {"pre_quali":"#f5576c","captacao":"#667eea","pitch_roas":"#28a745"}[r["fase"]]
    lbl   = {"pre_quali":"Pré-Qualificação","captacao":"Captação","pitch_roas":"Pitch/ROAS"}[r["fase"]]
    fase_legend += (
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<div style="background:{col_f};width:12px;height:12px;border-radius:2px"></div>'
        f'<span><strong>{lbl}</strong> — {br(r["inv"])} ({r["perc"]:.1f}%)</span>'
        f'</div>'
    )

# ---- Recommendations
recos = []

# Budget distribution diagnostic
principal_pct = float(bkt_agg[bkt_agg["bucket"]=="principal"]["perc"].values[0]) if "principal" in bkt_agg["bucket"].values else 0
reels_pct     = float(bkt_agg[bkt_agg["bucket"]=="reels"]["perc"].values[0])     if "reels"     in bkt_agg["bucket"].values else 0
potencial_pct = float(bkt_agg[bkt_agg["bucket"]=="potencial"]["perc"].values[0]) if "potencial" in bkt_agg["bucket"].values else 0

if principal_pct < 60:
    recos.append(("danger", "Distribuição Meta — Principal abaixo do target",
                  f"Campanha Principal recebeu {principal_pct:.1f}% da verba de captação (meta: 70%). "
                  f"Aumentar concentração em Principal pode melhorar eficiência de scale."))
if reels_pct > 15:
    recos.append(("warning", "Reels com verba acima do estratégico",
                  f"Reels recebeu {reels_pct:.1f}% vs meta de 5%. "
                  f"Avaliar se o CPL do Reels ({br(float(bkt_agg[bkt_agg['bucket']=='reels']['CPL'].values[0]) if 'reels' in bkt_agg['bucket'].values else 0, 'R$ ')}) "
                  f"justifica a sobrealocação ou redirecionar para Principal."))

# GA pre-quali overspend
ga_pq_perc = ga_pq_inv_v / ga_total_inv * 100 if ga_total_inv > 0 else 0
if ga_pq_perc > 12:
    recos.append(("warning", "Google Ads — Pré-Qualificação com alto % da verba",
                  f"Pré-Qualificação Google consumiu {ga_pq_perc:.1f}% do investimento Google "
                  f"({br(ga_pq_inv_v)}) com apenas {num(ga_pq_conv_v)} conversões. "
                  f"Reavaliar orçamento ou pausar se ROAS de pré-quali não for rastreável."))

# Novo ads verdict
if best_novo_cpl < best_valid_cpl:
    recos.append(("success", f"Novos Ads: {best_novo_name[:30]}… é promissor",
                  f"Melhor novo criativo atingiu CPL R${best_novo_cpl:.2f} vs R${best_valid_cpl:.2f} "
                  f"do melhor validado. Recomendar escalar em Principal com budget maior."))
else:
    recos.append(("info", "Novos Ads: Nenhum superou os validados em CPL",
                  f"Melhor novo: CPL R${best_novo_cpl:.2f}. Melhor validado: CPL R${best_valid_cpl:.2f}. "
                  f"Manter validados como base e testar novos com budget menor."))

# ROAS
if roas < 2.0:
    recos.append(("danger", f"ROAS {roas:.2f}× abaixo de 2.0×",
                  f"Com investimento de {br(total_inv)} e faturamento de {br(total_fat)}, "
                  f"o ROAS está abaixo do benchmark. Priorizar canais com menor CPA: "
                  f"Meta captação (CPL R${cpl_meta:.2f}) vs Google (R${ga_total_inv/ga_total_conv:.2f}/conv)."))

recos.append(("info", "Janela Crítica Pós-Pitch",
              "De quinta a segunda após o pitch é o período de foco em ROAS. "
              "Verificar se verba de remarketing foi maximizada no carrinho aberto (Abr 13-17). "
              f"Investimento total nessa janela: {br(float(fase_agg[fase_agg['fase']=='pitch_roas']['inv'].values[0]) if 'pitch_roas' in fase_agg['fase'].values else 0)}."
              ))

reco_colors = {"danger":"#dc3545","warning":"#ff9800","success":"#28a745","info":"#667eea"}
reco_icons  = {"danger":"🚨","warning":"⚠️","success":"✅","info":"💡"}
reco_html = ""
for level, title, text in recos:
    col = reco_colors[level]
    ico = reco_icons[level]
    reco_html += (
        f'<div style="border-left:4px solid {col};background:{col}18;'
        f'padding:14px 16px;border-radius:4px;margin-bottom:12px">'
        f'<div style="font-weight:700;color:{col};margin-bottom:4px">{ico} {title}</div>'
        f'<div style="color:#444;font-size:13px">{text}</div>'
        f'</div>'
    )

# ── HTML ──────────────────────────────────────────────────────────────────────
ts = datetime.now().strftime("%d/%m/%Y %H:%M")
html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Análise de Funil — PBB-ABR-26</title>
<link rel="icon" type="image/png" href="{FAV}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);color:#333;line-height:1.6}}
.wrap{{max-width:1280px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.hdr{{background:#fff;padding:36px 32px;display:flex;align-items:center;gap:24px;border-bottom:1px solid #eee}}
.hdr img{{height:52px}}
.hdr h1{{font-size:1.6rem;color:#333;font-weight:800}}
.hdr p{{color:#777;font-size:.9rem;margin-top:4px}}
.content{{padding:36px 32px}}
.section{{margin-bottom:48px}}
.section-title{{font-size:1.1rem;font-weight:800;color:#333;padding-bottom:10px;
  border-bottom:3px solid #667eea;margin-bottom:20px;display:flex;align-items:center;gap:8px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:8px}}
.kpi-card{{background:#f9f9f9;border-radius:8px;padding:18px;border-top:4px solid #667eea}}
.kpi-val{{font-size:1.5rem;font-weight:800;margin-bottom:4px}}
.kpi-lbl{{font-size:.75rem;color:#777;text-transform:uppercase;font-weight:600;letter-spacing:.04em}}
.kpi-sub{{font-size:.7rem;color:#aaa;margin-top:4px}}
.kpi-funil-layout{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:16px;align-items:stretch}}
.kpi-funil-layout .funil-kpi-wrap{{margin-bottom:0;height:100%}}
.kpi-funil-layout .kpi-grid{{grid-template-columns:repeat(2,minmax(160px,1fr));margin-bottom:0}}
.funil-kpi-wrap{{background:#f7f9ff;border:1px solid #e9eeff;border-radius:12px;padding:18px;margin-bottom:18px}}
.funil-kpi-head{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:12px;flex-wrap:wrap}}
.funil-kpi-head h3{{font-size:14px;font-weight:800;color:#2b2f3a}}
.funil-kpi-head p{{font-size:12px;color:#7a8299}}
.funil-viz{{display:flex;flex-direction:column;gap:10px}}
.funil-step{{position:relative;width:var(--w);min-width:260px;margin:0 auto;padding:12px 16px;
  color:#fff;border-radius:8px;clip-path:polygon(3% 0,97% 0,100% 100%,0 100%);
  background:linear-gradient(135deg,var(--c),color-mix(in srgb,var(--c) 78%,#000));
  display:flex;justify-content:space-between;align-items:center;gap:10px;box-shadow:0 8px 20px rgba(0,0,0,.12)}}
.funil-step-label{{font-size:12px;font-weight:700;line-height:1.2}}
.funil-step-value{{font-size:16px;font-weight:800;text-align:right;line-height:1.1;white-space:nowrap}}
.funil-step-value small{{display:block;font-size:11px;font-weight:700;opacity:.9}}
.funil-rates{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.funil-rate{{background:#fff;border:1px solid #e6e9f6;border-radius:999px;padding:6px 10px;font-size:11px;color:#4b5563}}
@media (max-width:1000px){{
  .kpi-funil-layout{{grid-template-columns:1fr}}
  .kpi-funil-layout .kpi-grid{{grid-template-columns:repeat(auto-fill,minmax(180px,1fr))}}
}}
@media (max-width:700px){{.funil-step{{min-width:100%}}}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:0}}
th{{background:#667eea;color:#fff;padding:10px 12px;text-align:left;font-weight:700;font-size:12px}}
td{{padding:10px 12px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#fafafa}}
.table-wrap{{border:1px solid #eee;border-radius:8px;overflow:hidden;margin-top:12px}}
.note{{background:#f0f4ff;border-left:4px solid #667eea;padding:12px 16px;border-radius:4px;
  font-size:13px;color:#555;margin-bottom:16px}}
.footing{{text-align:center;font-size:11px;color:#aaa;padding:24px;border-top:1px solid #eee;margin-top:32px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <a href="INDEX_[PBB-ABR-26].html"><img src="{LOGO}" alt="Brabo"></a>
    <div>
      <h1>📊 Análise de Funil — PBB-ABR-26</h1>
      <p>Segmentação por etapa de funil | Validados vs Novos | Curva diária | Diagnóstico de verba</p>
    </div>
  </div>
  <div class="content">

    <!-- 1. KPIs -->
    <div class="section">
      <div class="section-title">1. KPIs do Funil Completo</div>
      {funnel_html}
    </div>

    <!-- 2. Etapas Meta -->
    <div class="section">
      <div class="section-title">2. Meta Ads — Investimento por Etapa de Funil</div>
      <div class="note">Segmentação automática via tags nas nomenclaturas das campanhas:
        <strong>[captação]</strong> → geração de leads |
        <strong>[pré-qualificação]</strong> → aquecimento com vídeo |
        <strong>[engajamento/replay/tráfego]</strong> → remarketing
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Etapa</th><th>Investimento</th><th>% Verba</th>
            <th>Volume</th><th>Custo</th><th>Métrica</th></tr></thead>
          <tbody>{etapa_rows_meta}</tbody>
        </table>
      </div>
    </div>

    <!-- 3. Google Etapas -->
    <div class="section">
      <div class="section-title">3. Google Ads — Investimento por Etapa de Funil</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Etapa</th><th>Investimento</th><th>% Verba</th>
            <th>Conversões</th><th>Custo/Conv</th><th>Métrica</th></tr></thead>
          <tbody>{etapa_rows_ga}</tbody>
        </table>
      </div>
    </div>

    <!-- 4. Budget Distribution Meta Captação -->
    <div class="section">
      <div class="section-title">4. Distribuição de Verba Meta Captação vs Meta Estratégica</div>
      <div class="note">
        Meta estratégica: <strong>Principal 70%</strong> | <strong>Potencial 25%</strong> |
        <strong>Reels 5%</strong> | Imagem 5%
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Bucket</th><th>Investimento</th><th>% Real</th>
            <th>% Meta</th><th>Desvio</th><th>Leads</th><th>CPL</th></tr></thead>
          <tbody>{bkt_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- 5. Público Quente/Frio/Específico -->
    <div class="section">
      <div class="section-title">5. Performance por Temperatura de Público — Meta Captação</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Público</th><th>Investimento</th><th>% Verba</th>
            <th>Leads</th><th>CPL</th></tr></thead>
          <tbody>{pub_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- 6. Pré-Quali -->
    <div class="section">
      <div class="section-title">6. Pré-Qualificação — Eficiência de Aquecimento</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Canal</th><th>Investimento</th><th>Volume</th>
            <th>Custo Unitário</th><th>Métrica</th></tr></thead>
          <tbody>{pq_rows}</tbody>
        </table>
      </div>
      <div class="note" style="margin-top:12px">
        Meta pré-quali gerou <strong>{num(meta_pq_impr)} impressões</strong> e
        <strong>{num(meta_pq_tp)} ThruPlays</strong> (vídeo completo)
        a <strong>R${cptp_meta:.2f}/ThruPlay</strong>.
        {ga_pre_quali_note}
        Objetivo: levar público quente a consumir o conteúdo e depois converter melhor na captação.
      </div>
    </div>

    <!-- 7. Criativos Validados vs Novos -->
    <div class="section">
      <div class="section-title">7. Ranking de Criativos — Validados vs Novos</div>
      <div class="note">
        <strong>Validados</strong> = criativos em campanhas de escala (Principal/Potencial/Reels) |
        <strong>Novos</strong> = criativos exclusivos da campanha <code>[novos-ads]</code>.
        Resultado: melhor novo criativo
        <span style="color:{novos_verdict_color};font-weight:700">{novos_verdict}</span>
        (CPL R${best_novo_cpl:.2f} vs R${best_valid_cpl:.2f}).
      </div>
      {criativos_html}
    </div>

    <!-- 8. Canal Meta vs Google -->
    <div class="section">
      <div class="section-title">8. Comparativo de Canais — Meta vs Google</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Canal</th><th>Investimento</th><th>Volume</th>
            <th>Custo</th><th>Métrica</th><th>% do Total</th></tr></thead>
          <tbody>{canal_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- 9. Curva Diária -->
    <div class="section">
      <div class="section-title">9. Curva Diária — Meta Ads (Fases do Lançamento)</div>
      <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap">{fase_legend}</div>
      <div style="overflow-x:auto;padding-bottom:8px">
        <div style="display:flex;align-items:flex-end;gap:4px;min-width:600px;
          border-bottom:2px solid #eee;padding-bottom:8px">
          {daily_rows}
        </div>
      </div>
      <div class="note" style="margin-top:12px">
        <strong>Fase 1 — Pré-Qualificação</strong> (Mar 16-28): aquecimento com vídeo, verba baixa. &nbsp;|&nbsp;
        <strong>Fase 2 — Captação</strong> (Mar 29 – Abr 12): ramp-up de leads, pico Mar 31 (R$14.3k). &nbsp;|&nbsp;
        <strong>Fase 3 — Pitch/ROAS</strong> (Abr 13+): janela crítica de vendas,
        foco em remarketing e conversão.
      </div>
    </div>

    <!-- 10. Diagnóstico -->
    <div class="section">
      <div class="section-title">10. Diagnóstico e Recomendações</div>
      {reco_html}
    </div>

  </div>
  <div class="footing">Gerado em {ts} | Brabo Analytics — PBB-ABR-26</div>
</div>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
size_kb = OUT.stat().st_size // 1024
print(f"\n✅ {OUT.name} gerado ({size_kb}KB)")
