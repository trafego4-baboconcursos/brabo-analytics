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
import warnings
warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nav_component import FRAME_CLOSE, nav_html

# ── Paths ────────────────────────────────────────────────────────────────────
BASE    = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
CAMPAIGN_CODE = "PES-MAI-26"
CAMPAIGN_FOLDER = "[PES-MAI-26]"
PERIOD_LABEL = "Abril a Maio de 2026"
ABR_DIR = BASE / "analises" / CAMPAIGN_FOLDER
OUT     = ABR_DIR / "ANALISE_FUNIL_[PES-MAI-26].html"
LOGO    = "../../img/logo-brabo-concursos.png"
FAV     = "../../img/favicon-brabo-concursos.png"

print("="*70)
print("🚀 ANALISE_FUNIL — PBB-ABR-26")
print("="*70)


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
    "Abril de 2026": PERIOD_LABEL,
    "Abril 2026": PERIOD_LABEL,
    "Brabo Analytics — PBB-ABR-26": f"Brabo Analytics — {CAMPAIGN_CODE}",
  }
  for old, new in replacements.items():
    html = html.replace(old, new)
  if nav_block is not None:
    html = html.replace("__BRABO_NAV__", nav_block)
  return html

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


def campanha_pes(valor):
  return CAMPAIGN_CODE.lower() in str(valor).lower()

# ── Load data ─────────────────────────────────────────────────────────────────
print("\n📊 Carregando dados...")

# Meta Ads
df_meta = pd.read_csv(ABR_DIR / "Meta Ads" / "Campanhas-Completas-pes-mai-26.csv",
                      encoding="utf-8")
df_meta = df_meta[df_meta["Nome da campanha"].apply(campanha_pes)].copy()
for col in ["Valor usado (BRL)", "Leads", "Impressões", "Cliques (todos)",
            "ThruPlays", "Visualizações", "Cliques no link"]:
    if col in df_meta.columns:
        df_meta[col] = pd.to_numeric(df_meta[col], errors="coerce").fillna(0)
for col in ["ThruPlays", "Visualizações", "Cliques (todos)", "Cliques no link", "Leads", "Impressões", "Valor usado (BRL)"]:
  if col not in df_meta.columns:
    df_meta[col] = 0
if "Nome do anúncio" not in df_meta.columns:
  df_meta["Nome do anúncio"] = "Sem nome"
df_meta["Dia"] = pd.to_datetime(df_meta["Dia"], errors="coerce")
df_meta["etapa"]  = df_meta["Nome da campanha"].apply(get_etapa_meta)
df_meta["publico"] = df_meta["Nome da campanha"].apply(get_publico)
df_meta["bucket"]  = df_meta["Nome da campanha"].apply(get_bucket)
print("  ✓ Meta Ads:", len(df_meta), "linhas")

# Google Ads
df_ga = pd.read_csv(ABR_DIR / "Google Ads" / "Performance da campanha-pes-mai-26.csv",
                    encoding="utf-8", skiprows=2)
df_ga = df_ga[df_ga["Campanha"].apply(campanha_pes)].copy()
for col in ["Custo", "Conversões", "Cliques", "Impr.", "Conv. de visualização"]:
    if col in df_ga.columns:
        df_ga[col] = pd.to_numeric(df_ga[col].astype(str).str.replace(",","."), errors="coerce").fillna(0)
df_ga["etapa"] = df_ga["Campanha"].apply(get_etapa_ga)
print("  ✓ Google Ads:", len(df_ga), "campanhas")

# Hotmart — RI cobrança=1 × parcelas (líquido); excluir cobrança>1
_f_hot_raw = pd.read_csv(ABR_DIR / "Vendas" / "pes-mai-26-hotmart.csv", sep=";", encoding="utf-8")
_f_hot_raw["_email"] = _f_hot_raw["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
_f_hot_raw = _f_hot_raw[_f_hot_raw["_email"].str.contains("@", na=False)].copy()
_tipo_f = next((c for c in _f_hot_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
if _tipo_f:
    _par_f = "Quantidade total de parcelas"
    _cob_f = "Quantidade de cobranças"
    _fn = _f_hot_raw[_f_hot_raw[_tipo_f].astype(str).str.strip() != "Recuperador Inteligente"].copy()
    _fn["val"] = pd.to_numeric(_fn["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
    _fr = _f_hot_raw[
        (_f_hot_raw[_tipo_f].astype(str).str.strip() == "Recuperador Inteligente") &
        (pd.to_numeric(_f_hot_raw[_cob_f], errors="coerce").fillna(0) == 1)
    ].copy()
    _fr[_par_f] = pd.to_numeric(_fr[_par_f], errors="coerce").fillna(1)
    _fr["val"] = pd.to_numeric(_fr["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0) * _fr[_par_f]
    df_hot = pd.concat([_fn, _fr], ignore_index=True)
else:
    df_hot = _f_hot_raw.copy()
    df_hot["val"] = pd.to_numeric(df_hot["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
total_hot_fat = df_hot["val"].sum()
total_hot_n   = len(df_hot)
print(f"  ✓ Hotmart: {total_hot_n} vendas | R${total_hot_fat:,.0f}")

# TMB — todas as linhas
try:
  df_tmb = pd.read_csv(ABR_DIR / "Vendas" / "pes-mai-26-tmb.csv", sep=";", encoding="utf-8")
except UnicodeDecodeError:
  df_tmb = pd.read_csv(ABR_DIR / "Vendas" / "pes-mai-26-tmb.csv", sep=";", encoding="latin-1")
df_tmb_vig = df_tmb.copy()
_tmb_status_col = next((c for c in df_tmb_vig.columns if "situa" in str(c).lower()), None)
if _tmb_status_col:
  _tmb_status = df_tmb_vig[_tmb_status_col].astype(str).str.strip().str.lower()
  df_tmb_vig = df_tmb_vig[_tmb_status.isin(["vigente", "efetivado"])].copy()
tmb_tick_col = next(c for c in df_tmb.columns if "icket" in str(c).lower() and "pedido" in str(c).lower())
df_tmb_vig = df_tmb_vig.copy()
df_tmb_vig["ticket"] = pd.to_numeric(
    df_tmb_vig[tmb_tick_col].astype(str).str.replace(",","."), errors="coerce").fillna(0)
total_tmb_fat = df_tmb_vig["ticket"].sum()
total_tmb_n   = len(df_tmb_vig)
print(f"  ✓ TMB: {total_tmb_n} vigentes | R${total_tmb_fat:,.0f}")

# Typeform
typeform_frames = []
typeform_counts = []
for typeform_file in sorted((ABR_DIR / "Typeform").glob("*.csv")):
  df_tf = pd.read_csv(typeform_file, encoding="utf-8", low_memory=False)
  tf_email_col = next((c for c in df_tf.columns if "mail" in str(c).lower()), None)
  if not tf_email_col:
    continue
  df_tf = df_tf.copy()
  df_tf["email_norm"] = df_tf[tf_email_col].astype(str).str.strip().str.lower()
  df_tf = df_tf[df_tf["email_norm"].str.contains("@", na=False)].copy()
  typeform_counts.append(f"{typeform_file.stem}: {len(df_tf):,}")
  typeform_frames.append(df_tf)
if typeform_frames:
  df_typeform = pd.concat(typeform_frames, ignore_index=True, sort=False)
  total_typeform = df_typeform["email_norm"].nunique()
  print(f"  ✓ Typeform: {total_typeform:,} emails únicos ({' | '.join(typeform_counts)})")
else:
  df_typeform = pd.DataFrame()
  total_typeform = 0
  print("  ✓ Typeform: 0 respostas")

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

meta_capt  = meta_agg[meta_agg["etapa"] == "captacao"].iloc[0]  if len(meta_agg[meta_agg["etapa"]=="captacao"]) else None
meta_pq    = meta_agg[meta_agg["etapa"] == "pre_quali"].iloc[0] if len(meta_agg[meta_agg["etapa"]=="pre_quali"]) else None
meta_rmk   = meta_agg[meta_agg["etapa"] == "rmk"].iloc[0]       if len(meta_agg[meta_agg["etapa"]=="rmk"]) else None

# GA by etapa
ga_agg = df_ga.groupby("etapa").agg(
    custo = ("Custo",      "sum"),
    conv  = ("Conversões", "sum"),
    click = ("Cliques",    "sum"),
).reset_index()

ga_total_inv  = df_ga["Custo"].sum()
ga_total_conv = df_ga["Conversões"].sum()

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

# Funil macro
meta_clicks_total = df_meta["Cliques (todos)"].sum() if "Cliques (todos)" in df_meta.columns else 0
ga_clicks_total = df_ga["Cliques"].sum() if "Cliques" in df_ga.columns else 0
total_clicks = meta_clicks_total + ga_clicks_total
meta_topo = df_meta["Impressões"].sum() if "Impressões" in df_meta.columns else 0
ga_topo = df_ga["Impr."].sum() if "Impr." in df_ga.columns else 0
topo_funil = meta_topo + ga_topo

def funil_rate(numerador, denominador):
  return (numerador / denominador * 100) if denominador else 0

topo_to_click = funil_rate(total_clicks, topo_funil)
click_to_lead = funil_rate(total_leads_crm, total_clicks)
lead_to_typeform = funil_rate(total_typeform, total_leads_crm)
typeform_to_sale = funil_rate(total_vendas, total_typeform)
typeform_rate_label = pct(typeform_to_sale) if total_typeform >= total_vendas else "amostra parcial"

def funil_width(indice, total_etapas):
  if total_etapas <= 1:
    return "100.0%"
  topo_visual = 100.0
  base_visual = 46.0
  passo = (topo_visual - base_visual) / (total_etapas - 1)
  return f"{(topo_visual - indice * passo):.1f}%"

_funil_values = [topo_funil, total_clicks, total_leads_crm, total_typeform, total_vendas]
_funil_widths = [funil_width(i, len(_funil_values)) for i in range(len(_funil_values))]

funil_steps_html = (
  f'<div class="funil-step" style="--w:{_funil_widths[0]};--c:#17a2b8">'
  f'<span class="funil-step-label">Impressões (Meta + Google)</span>'
  f'<span class="funil-step-value">{num(topo_funil)}<small>100,0%</small></span>'
  f'</div>'
  f'<div class="funil-step" style="--w:{_funil_widths[1]};--c:#4f7cff">'
  f'<span class="funil-step-label">Cliques (Meta + Google)</span>'
  f'<span class="funil-step-value">{num(total_clicks)}<small>{pct(topo_to_click)} do topo</small></span>'
  f'</div>'
  f'<div class="funil-step" style="--w:{_funil_widths[2]};--c:#667eea">'
  f'<span class="funil-step-label">Leads CRM</span>'
  f'<span class="funil-step-value">{num(total_leads_crm)}<small>{pct(funil_rate(total_leads_crm, topo_funil))} do topo</small></span>'
  f'</div>'
  f'<div class="funil-step" style="--w:{_funil_widths[3]};--c:#764ba2">'
  f'<span class="funil-step-label">Responderam a pesquisa</span>'
  f'<span class="funil-step-value">{num(total_typeform)}<small>{pct(funil_rate(total_typeform, topo_funil))} do topo</small></span>'
  f'</div>'
  f'<div class="funil-step" style="--w:{_funil_widths[4]};--c:#f5576c">'
  f'<span class="funil-step-label">Vendas (Hotmart + TMB)</span>'
  f'<span class="funil-step-value">{num(total_vendas)}<small>{pct(funil_rate(total_vendas, topo_funil))} do topo</small></span>'
  f'</div>'
)

funil_rates_html = (
  f'<span class="funil-rate"><strong>Topo -> Clique:</strong> {pct(topo_to_click)}</span>'
  f'<span class="funil-rate"><strong>Clique -> Lead:</strong> {pct(click_to_lead)}</span>'
  f'<span class="funil-rate"><strong>Lead -> Pesquisa:</strong> {pct(lead_to_typeform)}</span>'
  f'<span class="funil-rate"><strong>Pesquisa -> Venda:</strong> {typeform_rate_label}</span>'
  f'<span class="funil-rate"><strong>ROAS Total:</strong> {roas:.2f}x</span>'
)

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
peak_day = daily.loc[daily["inv"].idxmax()] if not daily.empty else {"Dia": pd.Timestamp.today(), "inv": 0}

# Define phases based on the actual PES campaign window.
_daily_start = daily["Dia"].min()
_daily_end = daily["Dia"].max()
PITCH_START = _daily_end - pd.Timedelta(days=5)
CAPT_START = max(_daily_start, PITCH_START - pd.Timedelta(days=15))
PRE_START_LABEL = _daily_start.strftime("%d/%m")
CAPT_START_LABEL = CAPT_START.strftime("%d/%m")
PITCH_START_LABEL = PITCH_START.strftime("%d/%m")
END_LABEL = _daily_end.strftime("%d/%m")

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
    cpconv_pq = ga_pq_inv_v / ga_pq_conv_v if ga_pq_conv_v > 0 else 0
    pq_rows += (
        f'<tr><td>{badge("Google Ads Pré-Q","#4285f4")}</td>'
        f'<td>{br(ga_pq_inv_v)}</td>'
        f'<td>{num(ga_pq_conv_v)} conv</td>'
        f'<td style="font-weight:700">{br(cpconv_pq, "R$ ")}</td>'
        f'<td>Custo/Conv</td></tr>'
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
.kpi-funil-layout{{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:18px;align-items:stretch}}
.kpi-funil-layout .funil-kpi-wrap{{margin-bottom:0;height:100%}}
.kpi-funil-layout .kpi-grid{{grid-template-columns:repeat(2,minmax(160px,1fr));margin-bottom:0}}
.funil-kpi-wrap{{background:#f7f9ff;border:1px solid #e9eeff;border-radius:12px;padding:18px;margin-bottom:18px}}
.funil-kpi-head{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:12px;flex-wrap:wrap}}
.funil-kpi-head h3{{font-size:14px;font-weight:800;color:#2b2f3a}}
.funil-kpi-head p{{font-size:12px;color:#7a8299}}
.funil-viz{{display:flex;flex-direction:column;gap:12px;max-width:100%;margin:0 auto}}
.funil-step{{position:relative;width:var(--w);max-width:100%;min-width:0;margin:0 auto;padding:14px 18px;
  color:#fff;border-radius:8px;clip-path:polygon(0 0,100% 0,97% 100%,3% 100%);
  background:linear-gradient(135deg,var(--c),color-mix(in srgb,var(--c) 78%,#000));
  display:flex;justify-content:space-between;align-items:center;gap:10px;box-shadow:0 8px 20px rgba(0,0,0,.12)}}
.funil-step-label{{font-size:12px;font-weight:700;line-height:1.25;max-width:60%}}
.funil-step-value{{font-size:17px;font-weight:800;text-align:right;line-height:1.1;white-space:nowrap}}
.funil-step-value small{{display:block;font-size:11px;font-weight:700;opacity:.9}}
.funil-rates{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.funil-rate{{background:#fff;border:1px solid #e6e9f6;border-radius:999px;padding:6px 10px;font-size:11px;color:#4b5563}}
@media (max-width:1000px){{
  .kpi-funil-layout{{grid-template-columns:1fr}}
  .kpi-funil-layout .kpi-grid{{grid-template-columns:repeat(auto-fill,minmax(180px,1fr))}}
}}
@media (max-width:700px){{.funil-viz{{max-width:none}}.funil-step{{width:100%;padding:12px 14px}}.funil-step-label{{max-width:58%}}}}
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
      <div class="kpi-funil-layout">
        <div class="funil-kpi-wrap">
          <div class="funil-kpi-head">
            <h3>Funil de Conversão Geral</h3>
            <p>Jornada completa do aquecimento até vendas</p>
          </div>
          <div class="funil-viz">{funil_steps_html}</div>
          <div class="funil-rates">{funil_rates_html}</div>
        </div>
        <div>
          <div class="kpi-grid">{kpis_html}</div>
        </div>
      </div>
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
        <strong>Fase 1 — Pré-Qualificação</strong> ({PRE_START_LABEL} até {(CAPT_START - pd.Timedelta(days=1)).strftime("%d/%m")}): aquecimento com vídeo, verba baixa. &nbsp;|&nbsp;
        <strong>Fase 2 — Captação</strong> ({CAPT_START_LABEL} até {(PITCH_START - pd.Timedelta(days=1)).strftime("%d/%m")}): ramp-up de leads, pico {peak_day['Dia'].strftime("%d/%m")} ({br(peak_day['inv'])}). &nbsp;|&nbsp;
        <strong>Fase 3 — Pitch/ROAS</strong> ({PITCH_START_LABEL} até {END_LABEL}): janela crítica de vendas,
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

html = html.replace(
    "<body>\n",
  "<body>\n" + nav_html(
    active_campaign=CAMPAIGN_CODE,
    active_page_file=f"ANALISE_FUNIL_[{CAMPAIGN_CODE}].html",
    depth=1,
  ),
    1,
)
html = html.replace(
    "</body>\n</html>",
    f"{FRAME_CLOSE}\n</body>\n</html>",
    1,
)

OUT.write_text(adaptar_html_campaign(html), encoding="utf-8")
size_kb = OUT.stat().st_size // 1024
print(f"\n✅ {OUT.name} gerado ({size_kb}KB)")
