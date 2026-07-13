#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_analise_criativos_abr_v2.py  — versão melhorada
Análise de Criativos — PBB-ABR-26

Melhorias vs versão anterior:
  • Classificação Validados vs Novos (via campanha [novos-ads])
  • Dados Meta Ads (investimento, CPL plataforma) cruzados com UTM content
  • Ranking unificado: Meta-side + CRM-side (conversão real)
  • Fix encoding TMB (latin-1)
  • Visual atualizado com cards de destaque
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime
import csv as csv_mod
import warnings
warnings.filterwarnings('ignore')

BASE    = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ABR_DIR = BASE / "analises" / "[PBB-ABR-26]"
FEV_DIR = BASE / "analises" / "[PBB-FEV-26]"
OUT     = ABR_DIR / "ANALISE_CRIATIVOS_[PBB-ABR-26].html"
LOGO    = "../../img/logo-brabo-concursos.png"
FAV     = "../../img/favicon-brabo-concursos.png"

print("="*70)
print("🎨 ANALISE_CRIATIVOS — PBB-ABR-26 (v2 melhorado)")
print("="*70)

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
    """Extract 'AD###' base ID (case-insensitive) for cross-referencing."""
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

# Meta Ads (suporta variações de nome do arquivo)
abr_meta_candidates = [
  ABR_DIR / "Meta Ads" / "MA-Campanhas-Completas-PBB-ABR-26.csv",
  ABR_DIR / "Meta Ads" / "MA-Campanhas-completas-PBB-ABR-26.csv",
  ABR_DIR / "Meta Ads" / "meta-pbb-abr-26.csv",
]
abr_meta_file = next((p for p in abr_meta_candidates if p.exists()), None)
if abr_meta_file is None:
  raise FileNotFoundError("Arquivo Meta Ads ABR não encontrado")

df_meta = pd.read_csv(abr_meta_file, encoding="utf-8")
for col in ["Valor usado (BRL)", "Leads", "Impressões", "Cliques (todos)"]:
    if col in df_meta.columns:
        df_meta[col] = pd.to_numeric(df_meta[col], errors="coerce").fillna(0)

# Fallback para exportações que não trazem "Cliques (todos)"
if "Cliques (todos)" in df_meta.columns:
  df_meta["_clicks"] = pd.to_numeric(df_meta["Cliques (todos)"], errors="coerce").fillna(0)
elif "Cliques no link" in df_meta.columns:
  df_meta["_clicks"] = pd.to_numeric(df_meta["Cliques no link"], errors="coerce").fillna(0)
else:
  df_meta["_clicks"] = 0

# Tag captação campaigns only (robusto para variações de nomenclatura)
capt_meta = df_meta[df_meta["Nome da campanha"].astype(str).str.lower().str.contains(
  "capta", na=False)].copy()

# FEV Meta Ads (referência para determinar criativos validados por ADXXX)
fev_meta_candidates = [
  FEV_DIR / "Meta Ads" / "MA-Campanhas-Completas-PBB-FEV-26.csv",
  FEV_DIR / "Meta Ads" / "MA-Campanhas-completas-PBB-FEV-26.csv",
  FEV_DIR / "Meta Ads" / "meta-pbb-fev-26.csv",
]
fev_meta_file = next((p for p in fev_meta_candidates if p.exists()), None)
if fev_meta_file is None:
  raise FileNotFoundError("Arquivo Meta Ads FEV não encontrado para validar ADXXX")

df_meta_fev = pd.read_csv(fev_meta_file, encoding="utf-8")
capt_meta_fev = df_meta_fev[df_meta_fev["Nome da campanha"].astype(str).str.lower().str.contains(
  "capta", na=False)].copy()

capt_meta["ad_id"] = capt_meta["Nome do anúncio"].apply(normalize_ad_id)
capt_meta_fev["ad_id"] = capt_meta_fev["Nome do anúncio"].apply(normalize_ad_id)
ad_ids_fev = set(capt_meta_fev["ad_id"].dropna().unique())

# Regra: Validado = ADXXX presente no FEV; Novo = ADXXX só no ABR
capt_meta["tipo"] = capt_meta["ad_id"].apply(
  lambda ad: "Validado" if ad in ad_ids_fev else "Novo"
)

meta_by_ad = capt_meta.groupby(["Nome do anúncio", "ad_id", "tipo"]).agg(
    inv    = ("Valor usado (BRL)", "sum"),
    leads_meta = ("Leads", "sum"),
    impr   = ("Impressões", "sum"),
  clicks = ("_clicks", "sum"),
).reset_index()
meta_by_ad["CPL_meta"] = meta_by_ad["inv"] / meta_by_ad["leads_meta"].replace(0, np.nan)
meta_by_ad["CTR"]      = meta_by_ad["clicks"] / meta_by_ad["impr"].replace(0, np.nan) * 100
print(f"  ✓ Meta Ads: {len(meta_by_ad)} criativos únicos na captação")
print(f"  ✓ Referência FEV: {len(ad_ids_fev)} códigos ADXXX de captação")

# CRM Leads
leads_candidates = list((ABR_DIR / "Active Campaign").glob("*.csv"))
leads_file = max(leads_candidates, key=lambda f: f.stat().st_mtime)
df_leads = pd.read_csv(leads_file, encoding="utf-8", low_memory=False,
                       quoting=csv_mod.QUOTE_MINIMAL)
df_leads["Email"] = df_leads["Email"].astype(str).str.strip().str.lower()
df_leads_utm = df_leads[df_leads["*Utm_content"].notna()].copy()
df_leads_utm["ad_id"] = df_leads_utm["*Utm_content"].apply(normalize_ad_id)
print(f"  ✓ CRM: {len(df_leads):,} leads | {len(df_leads_utm):,} com UTM content")

# Hotmart — Parcelado/À vista líquido direto; RI cobrança=1 × parcelas
_hm_raw = pd.read_csv(ABR_DIR / "Vendas" / "hotmart pbb-abr-26.csv", sep=";", encoding="utf-8")
_tipo_col_hm2 = next((c for c in _hm_raw.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
_par_col_hm2  = "Quantidade total de parcelas"
_cob_col_hm2  = "Quantidade de cobranças"
_cr_norm = _hm_raw[_hm_raw[_tipo_col_hm2].astype(str).str.strip() != "Recuperador Inteligente"].copy()
_cr_norm["val"] = pd.to_numeric(_cr_norm["Faturamento líquido do(a) Produtor(a)"].astype(str), errors="coerce").fillna(0)
_cr_ri = _hm_raw[
    (_hm_raw[_tipo_col_hm2].astype(str).str.strip() == "Recuperador Inteligente") &
    (pd.to_numeric(_hm_raw[_cob_col_hm2], errors="coerce").fillna(0) == 1)
].copy()
_cr_ri[_par_col_hm2] = pd.to_numeric(_cr_ri[_par_col_hm2], errors="coerce").fillna(1)
_cr_ri["val"] = pd.to_numeric(_cr_ri["Faturamento líquido do(a) Produtor(a)"].astype(str), errors="coerce").fillna(0) * _cr_ri[_par_col_hm2]
df_hot = pd.concat([_cr_norm, _cr_ri], ignore_index=True)
df_hot["email"] = df_hot["Email do(a) Comprador(a)"].astype(str).str.strip().str.lower()
hot_emails = set(df_hot["email"])
print(f"  ✓ Hotmart: {len(df_hot):,} vendas")

# TMB — todos os rows (utf-8)
df_tmb = pd.read_csv(ABR_DIR / "Vendas" / "tmb pbb-abr-26.csv", sep=";", encoding="utf-8")
df_tmb_v = df_tmb.copy()  # todos
tmb_email_col  = "E-mail do Cliente"
tmb_ticket_col = "Ticket do pedido"
df_tmb_v["email"] = df_tmb_v[tmb_email_col].astype(str).str.strip().str.lower()
df_tmb_v["val"]   = pd.to_numeric(df_tmb_v[tmb_ticket_col].astype(str).str.replace(",","."),
                                   errors="coerce").fillna(0)
tmb_emails = set(df_tmb_v["email"])
print(f"  ✓ TMB: {len(df_tmb_v):,} rows")

# Facebook e YouTube já consolidados (sempre com vendas)
df_fb = pd.read_csv(ABR_DIR / "ANALISE_FACEBOOK_[PBB-ABR-26].csv")
df_yt = pd.read_csv(ABR_DIR / "ANALISE_YOUTUBE_[PBB-ABR-26].csv")
for _df in (df_fb, df_yt):
  for c in ["investimento", "leads", "vendas", "faturamento", "cpl", "custo_por_venda", "roas", "taxa_conversao"]:
    if c in _df.columns:
      _df[c] = pd.to_numeric(_df[c], errors="coerce").fillna(0)

sum_fb = {
  "investimento": df_fb["investimento"].sum(),
  "leads": df_fb["leads"].sum(),
  "vendas": df_fb["vendas"].sum(),
  "faturamento": df_fb["faturamento"].sum(),
}
sum_yt = {
  "investimento": df_yt["investimento"].sum(),
  "leads": df_yt["leads"].sum(),
  "vendas": df_yt["vendas"].sum(),
  "faturamento": df_yt["faturamento"].sum(),
}
sum_fb["cpl"] = sum_fb["investimento"] / sum_fb["leads"] if sum_fb["leads"] else 0
sum_yt["cpl"] = sum_yt["investimento"] / sum_yt["leads"] if sum_yt["leads"] else 0
sum_fb["roas"] = sum_fb["faturamento"] / sum_fb["investimento"] if sum_fb["investimento"] else 0
sum_yt["roas"] = sum_yt["faturamento"] / sum_yt["investimento"] if sum_yt["investimento"] else 0

# Pesquisa (Typeform) — bloco opcional de contexto
tf_path = ABR_DIR / "Typeform" / "typeform-pesquisa-pbb-abr-26.csv"
tf_n = 0
tf_brand = None
tf_mtd = None
tf_crm_rate = None
tf_sale_rate = None
tf_compromisso = None
tf_age_18_22 = None
tf_sem_dinheiro = None
tf_cronograma = None
tf_procrast = None
top_estados_txt = ""
if tf_path.exists():
  tf = pd.read_csv(tf_path, low_memory=False)
  tf_n = len(tf)
  tf_email_col = "Digite o seu e-mail."
  if tf_email_col in tf.columns:
    tf["email_n"] = tf[tf_email_col].astype(str).str.lower().str.strip()
    crm_emails = set(df_leads["Email"].astype(str).str.lower().str.strip())
    buyer_emails = set(df_hot["email"]) | set(df_tmb_v["email"])
    tf_crm_rate = (len(set(tf["email_n"]) & crm_emails) / max(len(tf), 1)) * 100
    tf_sale_rate = (len(set(tf["email_n"]) & buyer_emails) / max(len(tf), 1)) * 100

  col_brand = "Você já assistiu a algum vídeo ou Aula do Felipe Graton?"
  col_metodo = "Não sei estudar do jeito certo (falta de técnicas de estudos)"
  col_compromisso = "Você se Compromete a estudar pelo menos 2 horas por dia para ser Aprovado(a) no próximo concurso do Banco do Brasil?"
  col_idade = "Qual a sua idade?"
  col_sem_dinheiro = "Não tenho dinheiro para investir em um curso"
  col_cronograma = "Não sei montar um cronograma de estudos"
  col_procrast = "Procrastinação (não conseguir estudar)"
  col_estado = "De qual estado você é?"

  if col_brand in tf.columns:
    tf_brand = (tf[col_brand] == 1).mean() * 100
  if col_metodo in tf.columns:
    tf_mtd = tf[col_metodo].notna().mean() * 100
  if col_compromisso in tf.columns:
    tf_compromisso = tf[col_compromisso].astype(str).str.lower().str.contains("sim", na=False).mean() * 100
  if col_idade in tf.columns:
    tf_age_18_22 = tf[col_idade].astype(str).str.contains("18|19|20|21|22", regex=True, na=False).mean() * 100
  if col_sem_dinheiro in tf.columns:
    tf_sem_dinheiro = tf[col_sem_dinheiro].notna().mean() * 100
  if col_cronograma in tf.columns:
    tf_cronograma = tf[col_cronograma].notna().mean() * 100
  if col_procrast in tf.columns:
    tf_procrast = tf[col_procrast].notna().mean() * 100
  if col_estado in tf.columns:
    top_estados = tf[col_estado].value_counts().head(3)
    top_estados_txt = " | ".join([f"{k}: {v}" for k, v in top_estados.items()])

# ── Build CRM-side stats per ad_id ────────────────────────────────────────────
print("\n📐 Calculando conversões por criativo...")

crm_rows = []
for ad_id, grp in df_leads_utm.groupby("ad_id"):
    emails = set(grp["Email"].unique())
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
print(f"  ✓ {len(df_crm)} criativos com dados CRM")

# ── Merge Meta + CRM ──────────────────────────────────────────────────────────
df_merged = pd.merge(meta_by_ad, df_crm, on="ad_id", how="left")
df_merged["leads_crm"]  = df_merged["leads_crm"].fillna(0)
df_merged["vendas"]     = df_merged["vendas"].fillna(0)
df_merged["fat"]        = df_merged["fat"].fillna(0)
df_merged["conv_rate"]  = df_merged["conv_rate"].fillna(0)
df_merged["CPA_real"]   = df_merged["inv"] / df_merged["vendas"].replace(0, np.nan)
df_merged["ROAS"]       = df_merged["fat"] / df_merged["inv"].replace(0, np.nan)

df_merged = df_merged.sort_values("leads_meta", ascending=False)

total_inv = df_merged["inv"].sum()

# Separate validados / novos
df_valid = df_merged[df_merged["tipo"] == "Validado"].sort_values("leads_meta", ascending=False)
df_novos = df_merged[df_merged["tipo"] == "Novo"].sort_values("leads_meta", ascending=False)

print(f"  ✓ Validados: {len(df_valid)} | Novos: {len(df_novos)}")

# ── Summary comparison ────────────────────────────────────────────────────────
sum_valid = {
    "inv":    df_valid["inv"].sum(),
    "leads":  df_valid["leads_meta"].sum(),
    "vendas": df_valid["vendas"].sum(),
    "fat":    df_valid["fat"].sum(),
}
sum_novos = {
    "inv":    df_novos["inv"].sum(),
    "leads":  df_novos["leads_meta"].sum(),
    "vendas": df_novos["vendas"].sum(),
    "fat":    df_novos["fat"].sum(),
}
sum_valid["CPL"]  = sum_valid["inv"] / sum_valid["leads"]  if sum_valid["leads"]  > 0 else 0
sum_novos["CPL"]  = sum_novos["inv"] / sum_novos["leads"]  if sum_novos["leads"]  > 0 else 0
sum_valid["ROAS"] = sum_valid["fat"] / sum_valid["inv"]    if sum_valid["inv"]    > 0 else 0
sum_novos["ROAS"] = sum_novos["fat"] / sum_novos["inv"]    if sum_novos["inv"]    > 0 else 0

novos_win = sum_novos["CPL"] < sum_valid["CPL"]
novos_verdict_color = "#28a745" if novos_win else "#dc3545"
novos_verdict_text  = "Novos tiveram CPL menor — candidatos a escalar" if novos_win else \
                      "Validados seguem mais eficientes em CPL"

# ── Build HTML rows ───────────────────────────────────────────────────────────
def make_rows(df_ads, highlight_color):
    rows = ""
    for i, (_, r) in enumerate(df_ads.iterrows()):
        medal = ["🥇","🥈","🥉","4°","5°","6°","7°","8°"][min(i,7)]
        cpl   = r["CPL_meta"]
        cpl_good = not pd.isna(cpl) and cpl < 2.80
        cpl_col  = "#28a745" if cpl_good else ("#dc3545" if not pd.isna(cpl) else "#aaa")
        conv_r   = r["conv_rate"]
        conv_col = "#28a745" if conv_r >= 1.5 else ("#ff9800" if conv_r >= 0.8 else "#dc3545")
        roas_v   = r["ROAS"]
        roas_col = "#28a745" if (not pd.isna(roas_v) and roas_v >= 2) else "#ff9800"
        custo_venda = r["inv"] / r["vendas"] if r["vendas"] else np.nan

        rows += (
            f'<tr>'
            f'<td style="text-align:center;font-size:16px">{medal}</td>'
            f'<td><div style="font-size:12px;max-width:240px;line-height:1.3">'
            f'<strong>{r["Nome do anúncio"]}</strong></div>'
            f'<div style="font-size:10px;color:#aaa">{r["ad_id"]}</div></td>'
            f'<td>{br(r["inv"])}'
            f'<div style="margin-top:4px">{bar(r["inv"], total_inv, highlight_color)}</div></td>'
            f'<td style="font-weight:800;color:{highlight_color}">{num(r["leads_meta"])}</td>'
            f'<td style="font-weight:800;color:{cpl_col}">{br(cpl) if not pd.isna(cpl) else "–"}</td>'
            f'<td>{r["CTR"]:.2f}%</td>'
            f'<td style="font-weight:700">{num(r["leads_crm"])}</td>'
            f'<td style="font-weight:700">{num(r["vendas"])}</td>'
          f'<td style="font-weight:700">{br(r["fat"]) if not pd.isna(r["fat"]) else "–"}</td>'
            f'<td style="font-weight:700">{br(custo_venda) if not pd.isna(custo_venda) else "–"}</td>'
            f'<td style="font-weight:700;color:{conv_col}">{conv_r:.2f}%</td>'
            f'<td style="font-weight:800;color:{roas_col}">'
            f'{f"{roas_v:.2f}×" if not pd.isna(roas_v) and roas_v > 0 else "–"}</td>'
            f'</tr>'
        )
    return rows

rows_valid = make_rows(df_valid.head(8), "#28a745")
rows_novos = make_rows(df_novos.head(8), "#ff9800")

thead = (
    '<thead><tr>'
    '<th>#</th><th>Criativo</th><th>Investimento</th>'
    '<th>Leads Meta</th><th>CPL Meta</th><th>CTR</th>'
  '<th>Leads CRM</th><th>Vendas</th><th>Faturamento</th><th>Custo</th><th>Conv%</th><th>ROAS</th>'
    '</tr></thead>'
)

# Ranking geral unificado: Facebook + YouTube com validação CRM
df_fb_u = df_fb.copy()
df_fb_u["origem"] = "Facebook"
df_yt_u = df_yt.copy()
df_yt_u["origem"] = "YouTube"
df_all_platform = pd.concat([df_fb_u, df_yt_u], ignore_index=True)
df_all_platform["ad_id"] = df_all_platform["criativo"].apply(normalize_ad_id)

df_rank_all = df_all_platform.groupby(["ad_id", "origem"], as_index=False).agg(
  investimento=("investimento", "sum"),
  leads_plat=("leads", "sum"),
  vendas_plat=("vendas", "sum"),
  fat_plat=("faturamento", "sum"),
)

df_rank_all = pd.merge(df_rank_all, df_crm[["ad_id", "leads_crm", "conv_rate"]], on="ad_id", how="left")
df_rank_all["leads_crm"] = df_rank_all["leads_crm"].fillna(0)
df_rank_all["conv_rate"] = df_rank_all["conv_rate"].fillna(0)
df_rank_all["roas"] = df_rank_all["fat_plat"] / df_rank_all["investimento"].replace(0, np.nan)
df_rank_all = df_rank_all.sort_values(["vendas_plat", "fat_plat"], ascending=False)

def make_rows_all(df_ads):
  rows = ""
  top = df_ads.head(15)
  for i, (_, r) in enumerate(top.iterrows()):
    medal = ["🥇","🥈","🥉","4°","5°","6°","7°","8°","9°","10°","11°","12°","13°","14°","15°"][i]
    origem_color = "#1877f2" if r["origem"] == "Facebook" else "#ff0000"
    conv_col = "#28a745" if r["conv_rate"] >= 1.5 else ("#ff9800" if r["conv_rate"] >= 0.8 else "#dc3545")
    roas_col = "#28a745" if (not pd.isna(r["roas"]) and r["roas"] >= 2) else "#ff9800"
    rows += (
      f'<tr>'
      f'<td style="text-align:center">{medal}</td>'
      f'<td><strong>{r["ad_id"]}</strong></td>'
      f'<td><span style="background:{origem_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{r["origem"]}</span></td>'
      f'<td style="text-align:right">{br(r["investimento"])}</td>'
      f'<td style="text-align:right">{num(r["leads_plat"])}</td>'
      f'<td style="text-align:right;font-weight:800">{num(r["vendas_plat"])}</td>'
      f'<td style="text-align:right">{br(r["fat_plat"])}</td>'
      f'<td style="text-align:right">{num(r["leads_crm"])}</td>'
      f'<td style="text-align:right;color:{conv_col};font-weight:700">{r["conv_rate"]:.2f}%</td>'
      f'<td style="text-align:right;color:{roas_col};font-weight:700">{f"{r['roas']:.2f}×" if not pd.isna(r["roas"]) else "–"}</td>'
      f'</tr>'
    )
  return rows

rows_all = make_rows_all(df_rank_all)

# Insights acionáveis
top_cross = df_rank_all.head(1)
if len(top_cross) > 0:
  _r = top_cross.iloc[0]
  top_cross_txt = f"{_r['ad_id']} ({_r['origem']}) com {int(_r['vendas_plat'])} vendas e ROAS {(_r['roas'] if pd.notna(_r['roas']) else 0):.2f}×"
else:
  top_cross_txt = "Sem criativo líder identificado"

better_channel = "Facebook" if sum_fb["roas"] >= sum_yt["roas"] else "YouTube"
better_channel_roas = max(sum_fb["roas"], sum_yt["roas"])
novos_vs_valid_delta = ((sum_valid["CPL"] - sum_novos["CPL"]) / sum_valid["CPL"] * 100) if sum_valid["CPL"] else 0

insights_rows = ""
insights_list = [
  f"<strong>Canal mais eficiente em retorno:</strong> {better_channel} com ROAS {better_channel_roas:.2f}×.",
  f"<strong>Teste criativo funcionou:</strong> novos vieram com CPL {novos_vs_valid_delta:.1f}% {'menor' if novos_vs_valid_delta >= 0 else 'maior'} que validados.",
  f"<strong>Criativo líder no consolidado:</strong> {top_cross_txt}.",
  f"<strong>Pesquisa reforça ângulo de método:</strong> dor 'não sei estudar do jeito certo' em {(tf_mtd if tf_mtd is not None else 0):.1f}% dos respondentes.",
  f"<strong>Qualificação de marca:</strong> já conheciam o Graton em {(tf_brand if tf_brand is not None else 0):.1f}% — ainda há espaço para educação de audiência fria.",
]
for it in insights_list:
  insights_rows += f"<tr><td style='padding:10px 12px'>{it}</td></tr>"

def rows_platform(df_ads, color):
  rows = ""
  top = df_ads.sort_values("vendas", ascending=False).head(10)
  for i, (_, r) in enumerate(top.iterrows()):
    medal = ["🥇","🥈","🥉","4°","5°","6°","7°","8°","9°","10°"][i]
    rows += (
      f'<tr>'
      f'<td style="text-align:center">{medal}</td>'
      f'<td><strong>{r.get("criativo", "-")}</strong></td>'
      f'<td style="text-align:right">{br(r.get("investimento", 0))}</td>'
      f'<td style="text-align:right">{num(r.get("leads", 0))}</td>'
      f'<td style="text-align:right;font-weight:800;color:{color}">{num(r.get("vendas", 0))}</td>'
      f'<td style="text-align:right">{br(r.get("faturamento", 0))}</td>'
      f'<td style="text-align:right">{r.get("roas", 0):.2f}×</td>'
      f'</tr>'
    )
  return rows

rows_fb = rows_platform(df_fb, "#1877f2")
rows_yt = rows_platform(df_yt, "#ff0000")

# ── Build comparison summary cards ───────────────────────────────────────────
def summary_card(title, color, data):
    roas_str = f"{data['ROAS']:.2f}\u00d7"
    return (
        f'<div style="background:{color}18;border:2px solid {color};border-radius:10px;padding:20px">'
        f'<div style="font-size:.95rem;font-weight:800;color:{color};margin-bottom:12px">{title}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<div><div style="font-size:1.1rem;font-weight:800">{br(data["inv"])}</div>'
        f'<div style="font-size:11px;color:#888">Investimento</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{num(data["leads"])}</div>'
        f'<div style="font-size:11px;color:#888">Leads (plataforma)</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800;color:{color}">{br(data["CPL"])}</div>'
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
card_novos = summary_card("🆕 Criativos Novos (ADXXX só no ABR)", "#ff9800", sum_novos)

ts = datetime.now().strftime("%d/%m/%Y %H:%M")

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Análise de Criativos — PBB-ABR-26</title>
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
.table-wrap{{border:1px solid #eee;border-radius:8px;overflow:hidden;margin-top:12px}}
.footing{{text-align:center;font-size:11px;color:#aaa;padding:20px;border-top:1px solid #eee;margin-top:24px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <a href="INDEX_[PBB-ABR-26].html"><img src="{LOGO}" alt="Brabo"></a>
    <div>
      <h1>🎨 Análise de Criativos — PBB-ABR-26</h1>
      <p>Facebook + YouTube · Validados por ADXXX (ABR ∩ FEV) vs Novos no ABR · sempre com vendas e faturamento</p>
    </div>
  </div>
  <div class="content">

    <!-- 1. Validados vs Novos comparison -->
    <div class="section">
      <div class="section-title">1. Validados vs Novos — Comparativo</div>
      <div class="note">
        <strong>Validados</strong> = códigos <code>ADXXX</code> que aparecem no FEV e no ABR.
        <strong>Novos</strong> = códigos <code>ADXXX</code> que aparecem no ABR e <strong>não</strong> aparecem no FEV.
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

    <!-- 1.5 Facebook vs YouTube -->
    <div class="section">
      <div class="section-title">1.5 Facebook vs YouTube — Visão de Vendas por Criativo</div>
      <div class="note">
        Este bloco consolida os criativos de <strong>Facebook</strong> e <strong>YouTube</strong> com foco em vendas rastreadas,
        faturamento e ROAS por criativo.
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:14px">
        <div style="background:#1877f214;border:2px solid #1877f2;border-radius:10px;padding:16px">
          <div style="font-weight:800;color:#1877f2;margin-bottom:8px">Facebook</div>
          <div>Investimento: <strong>{br(sum_fb['investimento'])}</strong></div>
          <div>Leads: <strong>{num(sum_fb['leads'])}</strong> | Vendas: <strong>{num(sum_fb['vendas'])}</strong></div>
          <div>Faturamento: <strong>{br(sum_fb['faturamento'])}</strong> | ROAS: <strong>{sum_fb['roas']:.2f}×</strong></div>
        </div>
        <div style="background:#ff000014;border:2px solid #ff0000;border-radius:10px;padding:16px">
          <div style="font-weight:800;color:#ff0000;margin-bottom:8px">YouTube</div>
          <div>Investimento: <strong>{br(sum_yt['investimento'])}</strong></div>
          <div>Leads: <strong>{num(sum_yt['leads'])}</strong> | Vendas: <strong>{num(sum_yt['vendas'])}</strong></div>
          <div>Faturamento: <strong>{br(sum_yt['faturamento'])}</strong> | ROAS: <strong>{sum_yt['roas']:.2f}×</strong></div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="table-wrap">
          <table>
            <thead><tr><th>#</th><th>Criativo FB</th><th style="text-align:right">Invest.</th><th style="text-align:right">Leads</th><th style="text-align:right">Vendas</th><th style="text-align:right">Faturamento</th><th style="text-align:right">ROAS</th></tr></thead>
            <tbody>{rows_fb}</tbody>
          </table>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>#</th><th>Criativo YT</th><th style="text-align:right">Invest.</th><th style="text-align:right">Leads</th><th style="text-align:right">Vendas</th><th style="text-align:right">Faturamento</th><th style="text-align:right">ROAS</th></tr></thead>
            <tbody>{rows_yt}</tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 2. Validados ranking -->
    <div class="section">
      <div class="section-title">2. Ranking — Criativos Validados {badge(f"{len(df_valid)} criativos","#28a745")}</div>
      <div class="table-wrap">
        <table>
          {thead}
          <tbody>{rows_valid}</tbody>
        </table>
      </div>
    </div>

    <!-- 3. Novos ranking -->
    <div class="section">
      <div class="section-title">3. Ranking — Criativos Novos {badge(f"{len(df_novos)} criativos","#ff9800")}</div>
      <div class="note">
        Critério: criativos com código <code>ADXXX</code> presente apenas no ABR (sem ocorrência no FEV).
      </div>
      <div class="table-wrap">
        <table>
          {thead}
          <tbody>{rows_novos if rows_novos else "<tr><td colspan=12 style=text-align:center;color:#aaa;padding:20px>Nenhum criativo novo com dados suficientes</td></tr>"}</tbody>
        </table>
      </div>
    </div>

    <!-- 4. Ranking geral -->
    <div class="section">
      <div class="section-title">4. Top 15 Criativos — Ranking Geral (Facebook + YouTube + CRM)</div>
      <div class="note">
        Validação cruzada por código <code>ADXXX</code>: dados de plataforma (Facebook/YouTube) consolidados
        com sinais de CRM (leads e taxa de conversão CRM→venda).
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>ADXXX</th><th>Origem</th><th style="text-align:right">Investimento</th><th style="text-align:right">Leads Plataforma</th><th style="text-align:right">Vendas</th><th style="text-align:right">Faturamento</th><th style="text-align:right">Leads CRM</th><th style="text-align:right">Conv CRM→Venda</th><th style="text-align:right">ROAS</th></tr></thead>
          <tbody>{rows_all}</tbody>
        </table>
      </div>
    </div>

    <!-- 5. Pesquisa -->
    <div class="section">
      <div class="section-title">5. Contexto de Pesquisa (Typeform)</div>
      <div class="note">{f"Base pesquisada: {tf_n:,} respostas." if tf_n else "Arquivo de pesquisa não encontrado para este período."}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:14px">
        <div style="background:#eef3ff;border:1px solid #cbd5ff;border-radius:10px;padding:14px">
          <div style="font-weight:800;color:#334155;margin-bottom:8px">Perfil e Qualificação</div>
          <div>Já conheciam o Graton: <strong>{f'{tf_brand:.1f}%' if tf_brand is not None else 'n/d'}</strong></div>
          <div>Compromisso 2h/dia: <strong>{f'{tf_compromisso:.1f}%' if tf_compromisso is not None else 'n/d'}</strong></div>
          <div>Faixa 18–22 anos: <strong>{f'{tf_age_18_22:.1f}%' if tf_age_18_22 is not None else 'n/d'}</strong></div>
          <div>TF → CRM: <strong>{f'{tf_crm_rate:.1f}%' if tf_crm_rate is not None else 'n/d'}</strong></div>
          <div>TF → Venda: <strong>{f'{tf_sale_rate:.2f}%' if tf_sale_rate is not None else 'n/d'}</strong></div>
        </div>
        <div style="background:#fff7ed;border:1px solid #fdba74;border-radius:10px;padding:14px">
          <div style="font-weight:800;color:#9a3412;margin-bottom:8px">Principais Dores (Pesquisa)</div>
          <div>Não sei estudar do jeito certo: <strong>{f'{tf_mtd:.1f}%' if tf_mtd is not None else 'n/d'}</strong></div>
          <div>Não sei montar cronograma: <strong>{f'{tf_cronograma:.1f}%' if tf_cronograma is not None else 'n/d'}</strong></div>
          <div>Procrastinação: <strong>{f'{tf_procrast:.1f}%' if tf_procrast is not None else 'n/d'}</strong></div>
          <div>Sem dinheiro para curso: <strong>{f'{tf_sem_dinheiro:.1f}%' if tf_sem_dinheiro is not None else 'n/d'}</strong></div>
          <div>Top estados: <strong>{top_estados_txt if top_estados_txt else 'n/d'}</strong></div>
        </div>
      </div>
    </div>

    <!-- 6. Insights -->
    <div class="section">
      <div class="section-title">6. Insights que podemos tirar desse relatório</div>
      <div class="table-wrap">
        <table>
          <tbody>{insights_rows}</tbody>
        </table>
      </div>
    </div>

  </div>
  <div class="footing">
    Gerado em {ts} | Criativos analisados: {len(df_merged)} validados+novos |
    <a href="INDEX_[PBB-ABR-26].html" style="color:#667eea">← Índice</a>
  </div>
</div>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
kb = OUT.stat().st_size // 1024
print(f"\n✅ {OUT.name} gerado ({kb}KB)")
print(f"   Validados: {len(df_valid)} | Novos: {len(df_novos)}")
print(f"   CPL Validados: R${sum_valid['CPL']:.2f} | CPL Novos: R${sum_novos['CPL']:.2f}")
print(f"   Veredicto: {novos_verdict_text}")
