#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_insights_pes_mai.py
Insights e Recomendações — PES-MAI-26
Mesmo layout/estrutura do generate_insights_abr.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

BASE    = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
PES_DIR = BASE / "analises" / "[PES-MAI-26]"
OUT     = PES_DIR / "INSIGHTS_RECOMENDACOES_[PES-MAI-26].html"
LOGO    = "../../img/logo-brabo-concursos.png"
FAV     = "../../img/favicon-brabo-concursos.png"

print("=" * 70)
print("💡 INSIGHTS_RECOMENDACOES — PES-MAI-26")
print("=" * 70)

# ── Helpers ───────────────────────────────────────────────────────────────────
def br(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "-"

def num(v):
    try:
        f = float(v)
        return f"{int(f):,}".replace(",", ".")
    except: return "-"

def pct(v):
    try: return f"{float(v):.1f}%"
    except: return "-"

def badge(text, color="#667eea"):
    return (f'<span style="background:{color};color:#fff;padding:2px 9px;'
            f'border-radius:12px;font-size:11px;font-weight:700">{text}</span>')

def bar(val, total, color="#667eea"):
    p = min(val / total * 100, 100) if total else 0
    return (f'<div style="background:#eee;border-radius:3px;height:10px">'
            f'<div style="background:{color};width:{p:.1f}%;height:10px;border-radius:3px"></div></div>')

# ── Load data ─────────────────────────────────────────────────────────────────
print("\n📊 Carregando dados...")

df_meta = pd.read_csv(PES_DIR / "Meta Ads" / "Campanhas-Completas-pes-mai-26.csv", encoding="utf-8")
for col in ["Valor usado (BRL)", "Leads", "Impressões", "Cliques (todos)", "ThruPlays"]:
    if col in df_meta.columns:
        df_meta[col] = pd.to_numeric(df_meta[col], errors="coerce").fillna(0)
df_meta["Dia"] = pd.to_datetime(df_meta.get("Dia", pd.Series()), errors="coerce")
df_meta = df_meta[df_meta["Nome da campanha"].notna()].copy()

df_ga = pd.read_csv(PES_DIR / "Google Ads" / "Performance da campanha-pes-mai-26.csv",
                    encoding="utf-8", skiprows=2)
for col in ["Custo", "Conversões", "Cliques", "Impr."]:
    if col in df_ga.columns:
        df_ga[col] = pd.to_numeric(df_ga[col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)

# Hotmart — RI cobrança=1 × parcelas (líquido); excluir cobrança>1
_hm_raw = pd.read_csv(PES_DIR / "Vendas" / "pes-mai-26-hotmart.csv", sep=";", encoding="utf-8")
_tipo_col = next((c for c in _hm_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
_par_col  = "Quantidade total de parcelas"
_cob_col  = "Quantidade de cobranças"
_h_norm = _hm_raw[_hm_raw[_tipo_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
_h_norm["val"] = pd.to_numeric(_h_norm["Faturamento líquido do(a) Produtor(a)"].astype(str), errors="coerce").fillna(0)
_h_ri = _hm_raw[
    (_hm_raw[_tipo_col].astype(str).str.strip() == "Recuperador Inteligente") &
    (pd.to_numeric(_hm_raw[_cob_col], errors="coerce").fillna(0) == 1)
].copy()
_h_ri[_par_col] = pd.to_numeric(_h_ri[_par_col], errors="coerce").fillna(1)
_h_ri["val"] = pd.to_numeric(_h_ri["Faturamento líquido do(a) Produtor(a)"].astype(str), errors="coerce").fillna(0) * _h_ri[_par_col]
df_hot = pd.concat([_h_norm, _h_ri], ignore_index=True)
total_hot_fat = df_hot["val"].sum()
total_hot_n   = len(df_hot)

# TMB — todas as linhas
  df_tmb = pd.read_csv(PES_DIR / "Vendas" / "pes-mai-26-tmb.csv", sep=";", encoding="utf-8")
tmb_tick = next((c for c in df_tmb.columns if "icket" in c.lower() and "pedido" in c.lower()), "Ticket do pedido")
df_tmb["val"] = pd.to_numeric(df_tmb[tmb_tick].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
total_tmb_fat = df_tmb["val"].sum()
total_tmb_n   = len(df_tmb)

leads_file = max(list((PES_DIR / "Active Campaign").glob("*.csv")), key=lambda f: f.stat().st_mtime)
df_leads   = pd.read_csv(leads_file, encoding="utf-8", low_memory=False)
total_leads_crm = len(df_leads)

print("  ✓ Dados carregados")

# ── Stage segmentation ────────────────────────────────────────────────────────
def etapa_meta(n):
    n = str(n).lower()
    if "captação" in n or "captacao" in n: return "captacao"
    if "pré-qualificação" in n or "pre-qualificacao" in n: return "pre_quali"
    if any(k in n for k in ["[engajamento]", "[rmk]", "[replay]", "[depoimento]",
                             "[lembrete]", "[tráfego]", "[trafego]", "[aula"]): return "rmk"
    return "outro"

def etapa_ga(n):
    n = str(n).lower()
    if "[performance-max]" in n or "[p-max]" in n: return "p_max"
    if "captação" in n or "captacao" in n: return "captacao"
    if "pré-qualificação" in n or "pre-qualificacao" in n: return "pre_quali"
    if any(k in n for k in ["[tráfego]", "[trafego]", "[alcance]", "[replay]", "[aula"]): return "rmk"
    return "outro"

def bucket(n):
    n = str(n).lower()
    if "[principal]" in n: return "principal"
    if "[potencial]" in n: return "potencial"
    if "[reels]" in n: return "reels"
    if "[novos-ads]" in n: return "novos-ads"
    if "[imagem]" in n: return "imagem"
    if "[video]" in n or "[vídeo]" in n: return "video"
    return "outro"

df_meta["etapa"]  = df_meta["Nome da campanha"].apply(etapa_meta)
df_meta["bucket"] = df_meta["Nome da campanha"].apply(bucket)
df_ga["etapa"]    = df_ga["Campanha"].apply(etapa_ga)

# Totals
meta_inv   = df_meta["Valor usado (BRL)"].sum()
meta_leads = df_meta["Leads"].sum()
ga_inv     = df_ga["Custo"].sum()
ga_conv    = df_ga["Conversões"].sum() if "Conversões" in df_ga.columns else 0
total_inv  = meta_inv + ga_inv
total_fat  = total_hot_fat + total_tmb_fat
total_vend = total_hot_n + total_tmb_n
roas       = total_fat / total_inv if total_inv > 0 else 0
cpa        = total_inv / total_vend if total_vend > 0 else 0

# Meta by etapa
m_agg = df_meta.groupby("etapa").agg(
    inv=("Valor usado (BRL)", "sum"),
    leads=("Leads", "sum"),
).reset_index()

m_capt = m_agg[m_agg["etapa"] == "captacao"].iloc[0] if len(m_agg[m_agg["etapa"] == "captacao"]) else None
m_pq   = m_agg[m_agg["etapa"] == "pre_quali"].iloc[0] if len(m_agg[m_agg["etapa"] == "pre_quali"]) else None
m_rmk  = m_agg[m_agg["etapa"] == "rmk"].iloc[0] if len(m_agg[m_agg["etapa"] == "rmk"]) else None

m_capt_inv    = float(m_capt["inv"])   if m_capt is not None else 0
m_capt_leads  = float(m_capt["leads"]) if m_capt is not None else 0
m_pq_inv      = float(m_pq["inv"])     if m_pq is not None else 0
m_rmk_inv     = float(m_rmk["inv"])    if m_rmk is not None else 0
cpl_meta      = m_capt_inv / m_capt_leads if m_capt_leads > 0 else 0

# GA by etapa
ga_agg = df_ga.groupby("etapa").agg(custo=("Custo", "sum"), conv=("Conversões", "sum")).reset_index() if "Conversões" in df_ga.columns else df_ga.groupby("etapa").agg(custo=("Custo", "sum")).assign(conv=0).reset_index()
ga_capt = ga_agg[ga_agg["etapa"] == "captacao"].iloc[0] if len(ga_agg[ga_agg["etapa"] == "captacao"]) else None
ga_pq   = ga_agg[ga_agg["etapa"] == "pre_quali"].iloc[0] if len(ga_agg[ga_agg["etapa"] == "pre_quali"]) else None
ga_capt_inv  = float(ga_capt["custo"]) if ga_capt is not None else 0
ga_capt_conv = float(ga_capt["conv"])  if ga_capt is not None else 0
ga_pq_inv    = float(ga_pq["custo"])   if ga_pq is not None else 0
ga_pq_conv   = float(ga_pq["conv"])    if ga_pq is not None else 0
cpa_ga_capt  = ga_capt_inv / ga_capt_conv if ga_capt_conv > 0 else 0
cpa_ga_pq    = ga_pq_inv / ga_pq_conv if ga_pq_conv > 0 else 0

# Budget distribution Meta captação (por bucket)
capt_df = df_meta[df_meta["etapa"] == "captacao"]
bkt_agg = capt_df.groupby("bucket").agg(inv=("Valor usado (BRL)", "sum"), leads=("Leads", "sum")).reset_index()
bkt_tot = bkt_agg["inv"].sum()
bkt_agg["perc"] = bkt_agg["inv"] / bkt_tot * 100
bkt_agg["CPL"]  = bkt_agg["inv"] / bkt_agg["leads"].replace(0, np.nan)
bkt_dict = dict(zip(bkt_agg["bucket"], bkt_agg["perc"]))
bkt_cpl  = dict(zip(bkt_agg["bucket"], bkt_agg["CPL"]))

# Daily curve for janela crítica
daily = df_meta.groupby("Dia").agg(inv=("Valor usado (BRL)", "sum"), leads=("Leads", "sum")).reset_index()
daily = daily.dropna(subset=["Dia"]).sort_values("Dia")
# PES-MAI-26 timeline: pre-quali starts Apr 13; captação Apr 27; pitch ~May 5
PITCH = pd.Timestamp("2026-05-05")
CAPT  = pd.Timestamp("2026-04-27")
pitch_inv      = float(daily[daily["Dia"] >= PITCH]["inv"].sum())
capt_inv_daily = float(daily[(daily["Dia"] >= CAPT) & (daily["Dia"] < PITCH)]["inv"].sum())
pq_inv_daily   = float(daily[daily["Dia"] < CAPT]["inv"].sum())
peak_day       = daily.loc[daily["inv"].idxmax()]

# ── Channel comparison ────────────────────────────────────────────────────────
cpl_ga = ga_inv / ga_conv if ga_conv > 0 else 0

def cmp_row(platform, inv, inv_total, volume, vol_label, cost_per, cost_label, color):
    return (
        f'<tr>'
        f'<td>{badge(platform, color)}</td>'
        f'<td>{br(inv)}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">'
        f'{bar(inv, inv_total, color)}'
        f'<strong style="color:{color}">{inv/inv_total*100:.1f}%</strong></div></td>'
        f'<td>{num(volume)} {vol_label}</td>'
        f'<td style="font-weight:700">{br(cost_per)}</td>'
        f'<td><small style="color:#888">{cost_label}</small></td>'
        f'</tr>'
    )

canal_rows = (
    cmp_row("Meta Ads",  meta_inv, total_inv, meta_leads, "leads", cpl_meta, "CPL (captação)", "#1877f2") +
    cmp_row("Google Ads", ga_inv,  total_inv, ga_conv,    "conv",  cpl_ga,   "Custo/Conversão", "#4285f4")
)

# ── Budget distribution table ─────────────────────────────────────────────────
TARGETS = {"principal": 50, "potencial": 25, "reels": 10, "imagem": 10, "novos-ads": 5, "video": 5, "outro": 0}
LABELS  = {"principal": "Principal", "potencial": "Potencial", "reels": "Reels",
           "imagem": "Imagem", "novos-ads": "Novos Ads (teste)", "video": "Vídeo", "outro": "Outro"}
bkt_rows = ""
for _, r in bkt_agg.sort_values("inv", ascending=False).iterrows():
    bk   = r["bucket"]
    tgt  = TARGETS.get(bk, None)
    real = r["perc"]
    delta = real - tgt if tgt is not None else None
    tgt_html = f"{tgt}%" if tgt else "–"
    if delta is not None:
        col   = "#dc3545" if abs(delta) > 15 else ("#ff9800" if abs(delta) > 8 else "#28a745")
        arrow = "▲" if delta > 0 else "▼"
        delta_html = f'<span style="color:{col};font-weight:700">{arrow}{abs(delta):.1f}pp</span>'
    else:
        delta_html = "–"
    cpl_v = r["CPL"]
    cpl_html = br(cpl_v) if not pd.isna(cpl_v) else "–"
    status = "⚠️" if (delta is not None and abs(delta) > 15) else "✅"
    bkt_rows += (
        f'<tr>'
        f'<td>{status} <strong>{LABELS.get(bk, bk)}</strong></td>'
        f'<td>{br(r["inv"])}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">'
        f'{bar(r["inv"], bkt_tot, "#667eea")}'
        f'<strong>{real:.1f}%</strong></div></td>'
        f'<td style="color:#888">{tgt_html}</td>'
        f'<td>{delta_html}</td>'
        f'<td style="font-weight:700">{cpl_html}</td>'
        f'</tr>'
    )

# ── Action plan ───────────────────────────────────────────────────────────────
actions = []

principal_pct = bkt_dict.get("principal", 0)
reels_pct     = bkt_dict.get("reels", 0)
potencial_pct = bkt_dict.get("potencial", 0)
imagem_pct    = bkt_dict.get("imagem", 0)
principal_cpl = float(bkt_cpl.get("principal", 0)) if not pd.isna(bkt_cpl.get("principal", float("nan"))) else 0
imagem_cpl    = float(bkt_cpl.get("imagem", 0))    if not pd.isna(bkt_cpl.get("imagem",   float("nan"))) else 0

ga_pq_pct = ga_pq_inv / ga_inv * 100 if ga_inv > 0 else 0

# 1. Budget: Principal concentration
if principal_pct < 55:
    actions.append({
        "priority": "CRÍTICO",
        "color": "#dc3545",
        "icon": "🚨",
        "title": f"Realocar verba: Principal {principal_pct:.0f}% está abaixo do ideal de 50%",
        "impact": "Alto",
        "effort": "Baixo",
        "desc": (f"Campanha Principal recebeu {principal_pct:.1f}% da verba de captação, "
                 f"abaixo da meta de 50%. Com CPL de {br(principal_cpl)}, é a mais escalável. "
                 f"Redirecionar budget de Imagem ({imagem_pct:.0f}%) e Reels ({reels_pct:.0f}%) "
                 f"para Principal pode aumentar volume sem elevar CPL."),
        "link": '<a href="ANALISE_FUNIL_[PES-MAI-26].html">→ Ver Análise de Funil</a>',
    })

# 2. Imagem bucket share
if imagem_pct > 15:
    actions.append({
        "priority": "ALTO",
        "color": "#ff9800",
        "icon": "⚠️",
        "title": f"Bucket Imagem com {imagem_pct:.0f}% da verba — comparar CPL vs Principal",
        "impact": "Médio-Alto",
        "effort": "Baixo",
        "desc": (f"Imagem consumiu {br(bkt_dict.get('imagem', 0) / 100 * bkt_tot)} ({imagem_pct:.1f}%). "
                 f"CPL de Imagem: {br(imagem_cpl)} vs {br(principal_cpl)} do Principal. "
                 f"Se o CPL de Imagem for superior ao Principal em mais de 20%, "
                 f"redirecionar progressivamente para Principal em próximos lançamentos."),
        "link": '<a href="ANALISE_CRIATIVOS_[PES-MAI-26].html">→ Ver Criativos</a>',
    })

# 3. Google pre-quali allocation
if ga_pq_pct > 12:
    actions.append({
        "priority": "ALTO",
        "color": "#ff9800",
        "icon": "⚠️",
        "title": f"Google Pré-Quali: {ga_pq_pct:.0f}% do budget Google — avaliar ROI",
        "impact": "Médio",
        "effort": "Médio",
        "desc": (f"Google pré-quali consumiu {br(ga_pq_inv)} com {num(ga_pq_conv)} conversões "
                 f"({br(cpa_ga_pq)}/conv). Sem rastreabilidade de venda direta, "
                 f"avaliar se o aquecimento justifica o custo. "
                 f"Testar redução de 30% no próximo lançamento e monitorar CPL da captação."),
        "link": '<a href="ANALISE_GOOGLE_ADS_[PES-MAI-26].html">→ Ver Google Ads</a>',
    })

# 4. Scale best creative
actions.append({
    "priority": "MÉDIO",
    "color": "#667eea",
    "icon": "💡",
    "title": "Identificar e escalar o criativo com menor CPL validado no PES-MAI-26",
    "impact": "Alto",
    "effort": "Baixo",
    "desc": ("Identificar o criativo com melhor CPL entre os validados (bucket Principal) "
             "e alocar 30-40% do budget de captação exclusivamente para ele. "
             "Manter ao menos 10% do budget para testes de novos criativos com naming padronizado."),
    "link": '<a href="ANALISE_CRIATIVOS_[PES-MAI-26].html">→ Ver Criativos</a>',
})

# 5. TMB scale opportunity
tmb_share = total_tmb_fat / total_fat * 100 if total_fat > 0 else 0
if tmb_share > 30:
    actions.append({
        "priority": "MÉDIO",
        "color": "#28a745",
        "icon": "📋",
        "title": f"TMB representa {tmb_share:.0f}% do faturamento — oportunidade de escala",
        "impact": "Alto",
        "effort": "Médio",
        "desc": (f"TMB gerou {br(total_tmb_fat)} ({tmb_share:.1f}% do faturamento total) "
                 f"com {num(total_tmb_n)} clientes. "
                 f"Para o próximo lançamento, criar campanha específica de remarketing "
                 f"para base TMB (lembrete + depoimento + oferta especial)."),
        "link": '<a href="ANALISE_FUNIL_[PES-MAI-26].html">→ Ver Funil</a>',
    })

# 6. RMK janela crítica
if pitch_inv < 30000:
    actions.append({
        "priority": "MÉDIO",
        "color": "#764ba2",
        "icon": "⏰",
        "title": "Janela Crítica Pós-Pitch (Mai 5+): ampliar investimento em RMK",
        "impact": "Alto",
        "effort": "Baixo",
        "desc": (f"O período de Pitch e ROAS (Mai 5-11) teve {br(pitch_inv)} investidos. "
                 f"A janela de carrinho aberto é o momento de maior ROAS. "
                 f"Para o próximo lançamento: pré-alocar 15-20% do budget total para "
                 f"remarketing nessa janela (replay + depoimento + lembrete)."),
        "link": '<a href="ANALISE_FUNIL_[PES-MAI-26].html">→ Ver Curva Diária</a>',
    })

# 7. Attribution gap
utm_col = next((c for c in df_leads.columns if "utm_content" in c.lower() or "content" in c.lower()), None)
utm_gap_pct = (1 - df_leads[utm_col].notna().sum() / total_leads_crm) * 100 if utm_col and total_leads_crm > 0 else 0
if utm_gap_pct > 5:
    actions.append({
        "priority": "BAIXO",
        "color": "#aaa",
        "icon": "🔧",
        "title": f"Gap de atribuição: {utm_gap_pct:.0f}% dos leads sem UTM content",
        "impact": "Médio",
        "effort": "Alto",
        "desc": (f"{num(total_leads_crm - (df_leads[utm_col].notna().sum() if utm_col else 0))} "
                 f"leads ({utm_gap_pct:.1f}%) não têm UTM content rastreável. "
                 f"Padronizar parâmetros de URL em todos os anúncios e verificar "
                 f"integração CRM → FB Pixel / GA4."),
        "link": '<a href="ANALISE_LEADS_CONFRONTO_[PES-MAI-26].html">→ Ver Confronto Leads</a>',
    })

# ── Build action HTML ─────────────────────────────────────────────────────────
action_html = ""
for i, a in enumerate(actions):
    action_html += (
        f'<div style="border-left:4px solid {a["color"]};background:{a["color"]}12;'
        f'padding:16px 18px;border-radius:4px;margin-bottom:14px">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
        f'<span style="font-size:1.1rem">{a["icon"]}</span>'
        f'<strong style="color:{a["color"]};font-size:.95rem">'
        f'#{i+1} [{a["priority"]}] {a["title"]}</strong>'
        f'<span style="margin-left:auto;font-size:11px;color:#888">'
        f'Impacto: <strong>{a["impact"]}</strong> | Esforço: <strong>{a["effort"]}</strong></span>'
        f'</div>'
        f'<div style="font-size:13px;color:#444;line-height:1.6">{a["desc"]}</div>'
        f'{"<div style=margin-top:8px;font-size:12px>" + a["link"] + "</div>" if a.get("link") else ""}'
        f'</div>'
    )

# ── KPI cards ─────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", color="#667eea"):
    return (
        f'<div style="background:#f9f9f9;border-radius:8px;padding:16px;border-top:4px solid {color}">'
        f'<div style="font-size:1.4rem;font-weight:800;color:{color}">{value}</div>'
        f'<div style="font-size:.72rem;color:#888;text-transform:uppercase;font-weight:600;'
        f'letter-spacing:.04em;margin-top:3px">{label}</div>'
        f'{"<div style=font-size:.7rem;color:#aaa;margin-top:4px>" + sub + "</div>" if sub else ""}'
        f'</div>'
    )

kpis = (
    kpi("Investimento Total", br(total_inv),  f"Meta: {br(meta_inv)} | Google: {br(ga_inv)}", "#f5576c") +
    kpi("Faturamento",        br(total_fat),  f"Hotmart: {br(total_hot_fat)} | TMB: {br(total_tmb_fat)}", "#28a745") +
    kpi("ROAS",               f"{roas:.2f}×", f"Benchmark ideal: 2.0×+", "#ff9800") +
    kpi("CPA",                br(cpa),        f"{num(total_vend)} vendas totais", "#17a2b8") +
    kpi("Leads CRM",          num(total_leads_crm), f"CPL Meta captação: {br(cpl_meta)}", "#667eea") +
    kpi("CPL Meta Captação",  br(cpl_meta),   f"Google Custo/Conv: {br(cpl_ga)}", "#764ba2")
)

ts = datetime.now().strftime("%d/%m/%Y %H:%M")

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Insights e Recomendações — PES-MAI-26</title>
<link rel="icon" type="image/png" href="{FAV}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#f093fb,#f5576c);color:#333;line-height:1.6}}
.wrap{{max-width:1200px;margin:20px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.hdr{{background:#fff;padding:32px;display:flex;align-items:center;gap:24px;border-bottom:1px solid #eee}}
.hdr img{{height:48px}}
.hdr h1{{font-size:1.5rem;font-weight:800;color:#333}}
.hdr p{{color:#777;font-size:.85rem;margin-top:3px}}
.content{{padding:32px}}
.section{{margin-bottom:44px}}
.section-title{{font-size:1rem;font-weight:800;color:#333;border-bottom:3px solid #f5576c;
  padding-bottom:8px;margin-bottom:18px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px;margin-bottom:8px}}
.note{{background:#fff8f0;border-left:4px solid #ff9800;padding:12px 16px;border-radius:4px;
  font-size:13px;color:#555;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#f5576c;color:#fff;padding:10px 12px;text-align:left;font-weight:700;font-size:12px}}
td{{padding:10px 12px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
tr:hover td{{background:#fafafa}}
.table-wrap{{border:1px solid #eee;border-radius:8px;overflow:hidden;margin-top:12px}}
.footing{{text-align:center;font-size:11px;color:#aaa;padding:20px;border-top:1px solid #eee}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <a href="INDEX_[PES-MAI-26].html"><img src="{LOGO}" alt="Brabo"></a>
    <div>
      <h1>💡 Insights e Recomendações — PES-MAI-26</h1>
      <p>Diagnóstico completo · Realocação de verba · Janela crítica · Plano de ação priorizado</p>
    </div>
  </div>
  <div class="content">

    <!-- KPIs -->
    <div class="section">
      <div class="section-title">Visão Geral da Campanha</div>
      <div class="kpi-grid">{kpis}</div>
    </div>

    <!-- Canal comparison -->
    <div class="section">
      <div class="section-title">Comparativo de Canais — Meta vs Google</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Canal</th><th>Investimento</th><th>% do Total</th>
            <th>Volume</th><th>Custo Unitário</th><th>Métrica</th></tr></thead>
          <tbody>{canal_rows}</tbody>
        </table>
      </div>
      <div class="note" style="margin-top:12px">
        Meta Ads gera leads com rastreabilidade via UTM. Google converte audiências de busca.
        Para maximizar ROAS, priorizar a plataforma com menor custo por venda rastreável.
      </div>
    </div>

    <!-- Budget distribution -->
    <div class="section">
      <div class="section-title">Auditoria de Budget — Distribuição Meta Captação vs Meta Estratégica</div>
      <div class="note">
        Meta estratégica definida:
        <strong>Principal 50%</strong> (maior escala) |
        <strong>Potencial 25%</strong> (teste de novos públicos) |
        <strong>Imagem 10%</strong> (complemento visual) |
        <strong>Reels 10%</strong> (alcance complementar) |
        <strong>Novos Ads 5%</strong> (teste criativos)
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Bucket</th><th>Investimento</th><th>% Real</th>
            <th>% Meta</th><th>Desvio</th><th>CPL</th></tr></thead>
          <tbody>{bkt_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- Funnel stages -->
    <div class="section">
      <div class="section-title">Investimento por Etapa de Funil</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Etapa</th><th>Canal</th><th>Investimento</th><th>% Total Canal</th>
            <th>Volume</th><th>Custo Unit.</th></tr></thead>
          <tbody>
            <tr>
              <td>{badge("Captação","#667eea")}</td><td>Meta Ads</td>
              <td>{br(m_capt_inv)}</td>
              <td><strong>{m_capt_inv/meta_inv*100:.1f}%</strong></td>
              <td>{num(m_capt_leads)} leads</td>
              <td style="font-weight:700">{br(cpl_meta)} CPL</td>
            </tr>
            <tr>
              <td>{badge("Pré-Qualificação","#f5576c")}</td><td>Meta Ads</td>
              <td>{br(m_pq_inv)}</td>
              <td><strong>{m_pq_inv/meta_inv*100:.1f}%</strong></td>
              <td>–</td>
              <td style="font-weight:700">–</td>
            </tr>
            <tr>
              <td>{badge("RMK/Engajamento","#ff9800")}</td><td>Meta Ads</td>
              <td>{br(m_rmk_inv)}</td>
              <td><strong>{m_rmk_inv/meta_inv*100:.1f}%</strong></td>
              <td>–</td><td>–</td>
            </tr>
            <tr>
              <td>{badge("Captação","#667eea")}</td><td>Google Ads</td>
              <td>{br(ga_capt_inv)}</td>
              <td><strong>{ga_capt_inv/ga_inv*100:.1f}%</strong></td>
              <td>{num(ga_capt_conv)} conv</td>
              <td style="font-weight:700">{br(cpa_ga_capt)}/conv</td>
            </tr>
            <tr>
              <td>{badge("Pré-Qualificação","#f5576c")}</td><td>Google Ads</td>
              <td>{br(ga_pq_inv)}</td>
              <td><strong style="color:#dc3545">{ga_pq_inv/ga_inv*100:.1f}%</strong></td>
              <td>{num(ga_pq_conv)} conv</td>
              <td style="font-weight:700;color:#dc3545">{br(cpa_ga_pq)}/conv</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Janela crítica -->
    <div class="section">
      <div class="section-title">⏰ Janela Crítica — Análise do Pitch e Período de ROAS</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px">
        <div style="background:#f5f5f5;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:1.2rem;font-weight:800;color:#f5576c">{br(pq_inv_daily)}</div>
          <div style="font-size:.75rem;color:#888;margin-top:4px">Fase 1: Pré-Quali (Abr 13-26)</div>
          <div style="font-size:.7rem;color:#aaa">aquecimento com vídeo</div>
        </div>
        <div style="background:#f5f5f5;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:1.2rem;font-weight:800;color:#667eea">{br(capt_inv_daily)}</div>
          <div style="font-size:.75rem;color:#888;margin-top:4px">Fase 2: Captação (Abr 27 – Mai 4)</div>
          <div style="font-size:.7rem;color:#aaa">pico: {peak_day["Dia"].strftime("%d/%m")} ({br(float(peak_day["inv"]))})</div>
        </div>
        <div style="background:{'#fff3cd' if pitch_inv < 30000 else '#f0fff4'};border-radius:8px;
          padding:16px;text-align:center;border:2px solid {'#ff9800' if pitch_inv < 30000 else '#28a745'}">
          <div style="font-size:1.2rem;font-weight:800;color:{'#ff9800' if pitch_inv < 30000 else '#28a745'}">{br(pitch_inv)}</div>
          <div style="font-size:.75rem;color:#888;margin-top:4px">Fase 3: Pitch/ROAS (Mai 5+)</div>
          <div style="font-size:.7rem;color:{'#dc3545' if pitch_inv < 30000 else '#28a745'}">
            {'⚠️ baixo — janela subutilizada' if pitch_inv < 30000 else '✅ bem aproveitada'}</div>
        </div>
      </div>
      <div class="note">
        <strong>Protocolo recomendado para a Janela Crítica:</strong>
        Quarta (pitch): ativar campanhas de replay + lembrete.
        Quinta-Domingo: maximizar RMK com depoimentos + replay de aulas.
        Segunda (encerramento): push final com urgência.
        Budget sugerido: <strong>15-20% do investimento total</strong> concentrado nessa janela.
      </div>
    </div>

    <!-- Action plan -->
    <div class="section">
      <div class="section-title">🎯 Plano de Ação — Priorizado por Impacto</div>
      {action_html}
    </div>

    <!-- Links -->
    <div class="section">
      <div class="section-title">🔗 Análises Relacionadas</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px">
        {''.join(
          f'<a href="{href}" style="display:block;background:#f8f9fa;border:1px solid #eee;'
          f'border-radius:8px;padding:12px;text-decoration:none;color:#333;font-size:13px;'
          f'transition:background .15s" '
          f'onmouseover="this.style.background=\'#f0f4ff\'" onmouseout="this.style.background=\'#f8f9fa\'">'
          f'<strong>{label}</strong></a>'
          for label, href in [
            ("📊 Análise de Funil",     "ANALISE_FUNIL_[PES-MAI-26].html"),
            ("🎨 Criativos",            "ANALISE_CRIATIVOS_[PES-MAI-26].html"),
            ("📱 Meta Ads",             "ANALISE_META_ADS_[PES-MAI-26].html"),
            ("🔍 Google Ads",           "ANALISE_GOOGLE_ADS_[PES-MAI-26].html"),
            ("📘 Facebook",             "ANALISE_FACEBOOK_[PES-MAI-26].html"),
            ("▶️ YouTube",             "ANALISE_YOUTUBE_[PES-MAI-26].html"),
            ("📊 Consolidada",          "ANALISE_CONSOLIDADA_[PES-MAI-26].html"),
            ("📋 Typeform",             "ANALISE_TYPEFORM_[PES-MAI-26].html"),
          ]
        )}
      </div>
    </div>

  </div>
  <div class="footing">
    Gerado em {ts} | Brabo Analytics — PES-MAI-26 |
    <a href="INDEX_[PES-MAI-26].html" style="color:#f5576c">← Índice</a>
  </div>
</div>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
kb = OUT.stat().st_size // 1024
print(f"\n✅ {OUT.name} gerado ({kb}KB)")
print(f"   {len(actions)} recomendações geradas")
