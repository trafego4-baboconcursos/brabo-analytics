#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE_TYPEFORM_[PBB-ABR-26].html
Confronto: Pesquisa Typeform x Leads CRM x Campanhas x Vendas
"""

import pandas as pd
import csv as csvmod
from datetime import datetime
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nav_component import FRAME_CLOSE, nav_html

BASE_PATH = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES_PATH = BASE_PATH / "analises" / "[PES-MAI-26]"
LOGO_PATH = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"
CAMPAIGN_CODE = "PES-MAI-26"


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
        "[PBB-ABR-26]": "[PES-MAI-26]",
        "PBB-ABR-26": CAMPAIGN_CODE,
        "Abril de 2026": "Abril a Maio de 2026",
        "typeform-pesquisa-pbb-abr-26.csv": "typeform-projeto-pes-mai-26.csv + typeform-alunos-pes-mai-26.csv",
        "hotmart-pbb-abr-26.csv": "pes-mai-26-hotmart.csv",
        "tmb-pbb-abr-26.csv": "pes-mai-26-tmb.csv",
        "MA-Campanhas-completas-PBB-ABR-26.csv": "Campanhas-Completas-pes-mai-26.csv",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    if nav_block is not None:
        html = html.replace("__BRABO_NAV__", nav_block)
    return html


def encontrar_coluna_email(df):
    for col in df.columns:
        if 'mail' in str(col).lower():
            return col
    raise KeyError('Coluna de e-mail não encontrada no arquivo Typeform')


def encontrar_coluna(df, *terms):
    termos = [str(term).lower() for term in terms]
    for col in df.columns:
        lowered = str(col).lower()
        if all(term in lowered for term in termos):
            return col
    return None

print("=" * 80)
print("ANALISE TYPEFORM - PBB-ABR-26")
print("=" * 80)

# ============================================================================
# CARREGAR DADOS
# ============================================================================

print("\nCarregando dados...")

tf_cap_path = ANALISES_PATH / "Typeform" / "typeform-projeto-pes-mai-26.csv"
tf_alunos_path = ANALISES_PATH / "Typeform" / "typeform-alunos-pes-mai-26.csv"
tf_cap = pd.read_csv(tf_cap_path, low_memory=False)
tf_alunos = pd.read_csv(tf_alunos_path, low_memory=False)
tf_cap["origem_typeform"] = "Projeto"
tf_alunos["origem_typeform"] = "Alunos"
tf_cap_email_col = encontrar_coluna_email(tf_cap)
tf_alunos_email_col = encontrar_coluna_email(tf_alunos)
tf_cap["email_norm"] = tf_cap[tf_cap_email_col].astype(str).str.strip().str.lower()
tf_alunos["email_norm"] = tf_alunos[tf_alunos_email_col].astype(str).str.strip().str.lower()
tf_cap = tf_cap[tf_cap["email_norm"].str.contains("@", na=False)].copy()
tf_alunos = tf_alunos[tf_alunos["email_norm"].str.contains("@", na=False)].copy()
tf = pd.concat([tf_cap, tf_alunos], ignore_index=True, sort=False)
print(f"  Typeform: {len(tf_cap):,} projeto + {len(tf_alunos):,} alunos = {tf['email_norm'].nunique():,} emails únicos")

crm_path = max((ANALISES_PATH / "Active Campaign").glob("*.csv"), key=lambda path: path.stat().st_mtime)
crm = pd.read_csv(crm_path, sep=",", quoting=csvmod.QUOTE_MINIMAL, low_memory=False)
crm["email_norm"] = crm["Email"].astype(str).str.strip().str.lower()
print(f"  CRM: {len(crm):,} leads")

_hm_raw = pd.read_csv(ANALISES_PATH / "Vendas" / "pes-mai-26-hotmart.csv", sep=";", low_memory=False)
_hm_tipo = next((c for c in _hm_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
if _hm_tipo:
    _hm_par = "Quantidade total de parcelas"
    _hm_cob = "Quantidade de cobranças"
    _hm_norm = _hm_raw[_hm_raw[_hm_tipo].astype(str).str.strip() != "Recuperador Inteligente"].copy()
    _hm_norm["valor"] = pd.to_numeric(_hm_norm["Faturamento bruto (sem impostos)"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
    _hm_ri = _hm_raw[
        (_hm_raw[_hm_tipo].astype(str).str.strip() == "Recuperador Inteligente") &
        (pd.to_numeric(_hm_raw[_hm_cob], errors="coerce").fillna(0) == 1)
    ].copy()
    _hm_ri[_hm_par] = pd.to_numeric(_hm_ri[_hm_par], errors="coerce").fillna(1)
    _hm_ri["valor"] = pd.to_numeric(_hm_ri["Faturamento bruto (sem impostos)"].astype(str).str.replace(",", "."), errors="coerce").fillna(0) * _hm_ri[_hm_par]
    hm = pd.concat([_hm_norm, _hm_ri], ignore_index=True)
else:
    hm = _hm_raw.copy()
    hm["valor"] = pd.to_numeric(hm["Faturamento bruto (sem impostos)"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
hm["email_norm"] = hm["Email do(a) Comprador(a)"].astype(str).str.strip().str.lower()
print(f"  Hotmart: {len(hm):,} vendas")

try:
    tmb = pd.read_csv(ANALISES_PATH / "Vendas" / "pes-mai-26-tmb.csv", sep=";", encoding="utf-8", low_memory=False)
except UnicodeDecodeError:
    tmb = pd.read_csv(ANALISES_PATH / "Vendas" / "pes-mai-26-tmb.csv", sep=";", encoding="latin-1", low_memory=False)
tmb_status_col = next((c for c in tmb.columns if 'situa' in str(c).lower()), None)
if tmb_status_col:
    tmb = tmb[tmb[tmb_status_col].astype(str).str.lower().str.contains('vigente|efetivado', na=False, regex=True)].copy()
tmb_email_col = next((c for c in tmb.columns if 'mail' in str(c).lower()), 'E-mail do Cliente')
tmb_valor_col = next((c for c in tmb.columns if 'icket' in str(c).lower() and 'pedido' in str(c).lower()), 'Ticket do pedido')
tmb["email_norm"] = tmb[tmb_email_col].astype(str).str.strip().str.lower()
tmb["valor"] = pd.to_numeric(tmb[tmb_valor_col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
print(f"  TMB: {len(tmb):,} vendas")

# ============================================================================
# CRUZAMENTOS
# ============================================================================

tf_emails = set(tf["email_norm"])
crm_emails = set(crm["email_norm"])
hm_emails = set(hm["email_norm"])
tmb_emails = set(tmb["email_norm"])
vendas_emails = hm_emails | tmb_emails

tf_e_crm = tf_emails & crm_emails
tf_e_vendas = tf_emails & vendas_emails
crm_e_vendas = crm_emails & vendas_emails
tf_e_crm_e_vendas = tf_emails & crm_emails & vendas_emails

tf_comp = tf[tf["email_norm"].isin(tf_e_vendas)].copy()
tf_ncomp = tf[~tf["email_norm"].isin(tf_e_vendas)].copy()
tf_demografico = tf_cap.copy()
tf_comp_dem = tf_demografico[tf_demografico["email_norm"].isin(tf_e_vendas)].copy()
tf_ncomp_dem = tf_demografico[~tf_demografico["email_norm"].isin(tf_e_vendas)].copy()
tf_genero_col = encontrar_coluna(tf_demografico, "gênero") or encontrar_coluna(tf_demografico, "genero")
tf_situacao_col = encontrar_coluna(tf_demografico, "situação", "profissional") or encontrar_coluna(tf_demografico, "situacao", "profissional")
tf_nivel_col = encontrar_coluna(tf_demografico, "você se considera") or encontrar_coluna(tf_demografico, "voce se considera")
tf_idade_col = encontrar_coluna(tf_demografico, "idade")
tf_estado_col = encontrar_coluna(tf_demografico, "estado")

hm_tf = hm[hm["email_norm"].isin(tf_e_vendas)]
tmb_tf = tmb[tmb["email_norm"].isin(tf_e_vendas)]

fat_hm_total = hm["valor"].sum()
fat_tmb_total = tmb["valor"].sum()
fat_total = fat_hm_total + fat_tmb_total
fat_tf_hm = hm_tf["valor"].sum()
fat_tf_tmb = tmb_tf["valor"].sum()
fat_tf_total = fat_tf_hm + fat_tf_tmb

print(f"\n  TF -> Lead CRM: {len(tf_e_crm):,} ({len(tf_e_crm)/len(tf_emails)*100:.1f}%)")
print(f"  TF -> Compra:   {len(tf_e_vendas):,} ({len(tf_e_vendas)/len(tf_emails)*100:.1f}%)")
print(f"  Faturamento TF: R$ {fat_tf_total:,.2f} ({fat_tf_total/fat_total*100:.1f}% do total)")

# ============================================================================
# HELPERS HTML
# ============================================================================

def row_perc(label, n_total, val_comp, val_ncomp, invert=False):
    """Gera linha de tabela com barra visual comparativa."""
    bar_c = f'<div style="height:8px;background:#667eea;border-radius:3px;width:{min(val_comp,100):.0f}%"></div>'
    bar_n = f'<div style="height:8px;background:#ccc;border-radius:3px;width:{min(val_ncomp,100):.0f}%"></div>'
    color = "#28a745" if (val_comp >= val_ncomp) != invert else "#dc3545"
    diff = val_comp - val_ncomp
    diff_str = f'+{diff:.0f}pp' if diff >= 0 else f'{diff:.0f}pp'
    diff_color = "#28a745" if diff > 0 else "#dc3545"
    return (
        f"<tr><td>{label}</td>"
        f"<td style='text-align:right'><strong>{val_comp:.1f}%</strong><br>{bar_c}</td>"
        f"<td style='text-align:right'>{val_ncomp:.1f}%<br>{bar_n}</td>"
        f"<td style='text-align:right;color:{diff_color};font-weight:bold'>{diff_str}</td></tr>"
    )

def pct(df, col, val):
    if col not in df.columns or df.empty:
        return 0
    return df[col].value_counts(normalize=True).get(val, 0) * 100

def pct_notnull(df, col):
    if col not in df.columns or df.empty:
        return 0
    return df[col].notna().sum() / len(df) * 100

# ============================================================================
# CALCULAR METRICAS
# ============================================================================

# Funil
funil_tf = len(tf_emails)
funil_leads = len(tf_e_crm)
funil_compras = len(tf_e_vendas)
funil_tx_lead = funil_leads / funil_tf * 100
funil_tx_venda_tf = funil_compras / funil_tf * 100
funil_tx_venda_lead = len(crm_e_vendas) / len(crm_emails) * 100

# UTM sources dos compradores Typeform no CRM
utm_col = next((c for c in crm.columns if "utm_source" in c.lower()), None)
utm_rows = ""
if utm_col:
    crm_comp_tf = crm[crm["email_norm"].isin(tf_e_vendas)]
    utm_vc = crm_comp_tf[utm_col].value_counts().head(10)
    for src, cnt in utm_vc.items():
        plat = "YouTube" if str(src).startswith("yt") else ("Meta/FB" if str(src).startswith("fb") else "Outros")
        badge_color = "#ff0000" if plat == "YouTube" else ("#1877f2" if plat == "Meta/FB" else "#666")
        badge = f'<span style="background:{badge_color};color:white;padding:1px 6px;border-radius:10px;font-size:11px">{plat}</span>'
        utm_rows += f"<tr><td>{badge} {src}</td><td style='text-align:right'>{cnt}</td></tr>"

# Perfil demográfico - linhas de comparação
rows_genero = ""
if tf_genero_col:
    for v in ["Masculino", "Feminino"]:
        rows_genero += row_perc(v, len(tf_demografico), pct(tf_comp_dem, tf_genero_col, v),
                                 pct(tf_ncomp_dem, tf_genero_col, v))

rows_situacao = ""
if tf_situacao_col:
    for v in ["Desempregado(a)", "Funcionário(a) de empresa privada", "Autônomo(a)", "Funcionário(a) público"]:
        rows_situacao += row_perc(v, len(tf_demografico), pct(tf_comp_dem, tf_situacao_col, v),
                                   pct(tf_ncomp_dem, tf_situacao_col, v))

rows_nivel = ""
if tf_nivel_col:
    for v in ["Estou do zero", "Do zero", "Sou Iniciante", "Iniciante", "Sou Intermediário(a)", "Intermediário", "Sou Avançado(a)", "Avançado"]:
        rows_nivel += row_perc(v, len(tf_demografico), pct(tf_comp_dem, tf_nivel_col, v),
                                pct(tf_ncomp_dem, tf_nivel_col, v))

rows_idade = ""
if tf_idade_col:
    for v in ["18 a 22 anos", "23 a 27 anos", "28 a 32 anos", "33 a 37 anos", "38 a 45 anos", "46 a 52 anos", "53 anos ou mais"]:
        rows_idade += row_perc(v, len(tf_demografico), pct(tf_comp_dem, tf_idade_col, v),
                                pct(tf_ncomp_dem, tf_idade_col, v))

# Obstaculos
obstaculos = [
    ("Não sei estudar do jeito certo", "Não sei estudar do jeito certo (falta de técnicas de estudos)"),
    ("Não sei montar um cronograma", "Não sei montar um cronograma de estudos"),
    ("Procrastinação", "Procrastinação (não conseguir estudar)"),
    ("Estou há muito tempo sem estudar", "Estou há muito tempo sem estudar"),
    ("Pouco tempo disponível", "Pouco tempo disponível pra me dedicar aos estudos"),
    ("Medo de esquecer no dia da prova", "Medo de esquecer tudo no dia da prova"),
    ("Medo de estudar e não passar", "Medo de estudar muito e não conseguir passar"),
    ("Sem dinheiro para curso", "Não tenho dinheiro para investir em um curso"),
    ("Medo de não sair o concurso", "Medo de não sair o concurso este ano"),
]
rows_obst = ""
for label, col in obstaculos:
    if col in tf_demografico.columns:
        pc = pct_notnull(tf_comp_dem, col)
        pn = pct_notnull(tf_ncomp_dem, col)
        rows_obst += row_perc(label, len(tf_demografico), pc, pn, invert=(label == "Sem dinheiro para curso"))

# Graton
video_col = next((col for col in tf_demografico.columns if "você já assistiu" in str(col).lower() and ("ivan neto" in str(col).lower() or "felipe graton" in str(col).lower())), None)
graton_c = pct(tf_comp_dem, video_col, 1) if video_col else 0
graton_n = pct(tf_ncomp_dem, video_col, 1) if video_col else 0
graton_0c = pct(tf_comp_dem, video_col, 0) if video_col else 0
graton_0n = pct(tf_ncomp_dem, video_col, 0) if video_col else 0
graton_ratio = (graton_c / graton_n) if graton_n else 0
graton_inverse_ratio = (graton_0n / graton_0c) if graton_0c else 0

# Top estados compradores
rows_estados = ""
if tf_estado_col and tf_estado_col in tf_comp_dem.columns:
    top_estados = tf_comp_dem[tf_estado_col].value_counts().head(10)
    for estado, cnt in top_estados.items():
        pct_estado = cnt / len(tf_comp_dem) * 100 if len(tf_comp_dem) else 0
        rows_estados += f"<tr><td>{estado}</td><td style='text-align:right'>{cnt}</td><td style='text-align:right'>{pct_estado:.1f}%</td></tr>"

# Top estados geral Typeform
rows_estados_geral = ""
if tf_estado_col and tf_estado_col in tf_demografico.columns:
    top_estados_g = tf_demografico[tf_estado_col].value_counts().head(10)
    for estado, cnt in top_estados_g.items():
        pct_estado = cnt / len(tf_demografico) * 100 if len(tf_demografico) else 0
        rows_estados_geral += f"<tr><td>{estado}</td><td style='text-align:right'>{cnt:,}</td><td style='text-align:right'>{pct_estado:.1f}%</td></tr>"

# ============================================================================
# GERAR HTML
# ============================================================================

print("\nGerando HTML...")

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Typeform - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif; background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%); color:#333; }}
        .container {{ max-width:1200px; margin:20px auto; background:white; box-shadow:0 20px 60px rgba(0,0,0,0.3); overflow:hidden; border-radius:8px; }}
        .header {{ background:white; color:#333; padding:40px 20px; display:flex; justify-content:center; align-items:center; text-align:center; flex-wrap:wrap; border-bottom:1px solid #eee; }}
        .header-logo {{ margin-right:30px; }}
        .header-logo img {{ max-width:120px; height:auto; }}
        .header-title h1 {{ font-size:28px; margin-bottom:8px; color:#333; }}
        .header-title p {{ font-size:13px; color:#666; margin:4px 0; }}
        .content {{ padding:40px; }}
        .metric-box {{ background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%); color:white; padding:18px; border-radius:8px; display:inline-block; min-width:160px; margin:6px; vertical-align:top; }}
        .metric-box.blue {{ background:linear-gradient(135deg,#4285f4 0%,#34a853 100%); }}
        .metric-box.purple {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); }}
        .metric-box.orange {{ background:linear-gradient(135deg,#eb5757 0%,#ff9500 100%); }}
        .metric-box.green {{ background:linear-gradient(135deg,#11998e 0%,#38ef7d 100%); }}
        .metric-box .label {{ font-size:11px; text-transform:uppercase; opacity:.9; margin-bottom:4px; }}
        .metric-box .value {{ font-size:22px; font-weight:bold; }}
        .metric-box .sub {{ font-size:11px; opacity:.85; margin-top:3px; }}
        .recommendation-box {{ background:#fff3cd; border-left:4px solid #ffc107; padding:14px; margin:12px 0; border-radius:4px; }}
        .success-box {{ background:#d4edda; border-left:4px solid #28a745; padding:14px; margin:12px 0; border-radius:4px; }}
        .insight-box {{ background:#e8f0fe; border-left:4px solid #4285f4; padding:14px; margin:12px 0; border-radius:4px; }}
        .alert-box {{ background:#f8d7da; border-left:4px solid #dc3545; padding:14px; margin:12px 0; border-radius:4px; }}
        table {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:13px; }}
        table th {{ background:#667eea; color:white; padding:10px; text-align:left; font-weight:600; }}
        table td {{ padding:10px; border-bottom:1px solid #eee; vertical-align:middle; }}
        table tr:hover {{ background:#f9f9f9; }}
        h2 {{ margin-top:32px; margin-bottom:14px; color:#333; border-bottom:2px solid #f5576c; padding-bottom:8px; }}
        h3 {{ margin-top:18px; margin-bottom:8px; color:#555; }}
        .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; margin:16px 0; }}
        .card {{ background:#f8f9fa; padding:18px; border-radius:8px; border-left:4px solid #667eea; }}
        .funnel {{ display:flex; flex-direction:column; gap:0; margin:20px 0; }}
        .funnel-step {{ display:flex; align-items:center; padding:14px 20px; border-radius:6px; margin:4px 0; position:relative; }}
        .funnel-step .num {{ font-size:24px; font-weight:bold; min-width:100px; }}
        .funnel-step .desc {{ flex:1; }}
        .funnel-step .pct {{ font-size:14px; opacity:.85; font-weight:600; }}
        .footer {{ background:#f8f9fa; padding:20px; text-align:center; font-size:12px; color:#666; border-top:1px solid #eee; margin-top:40px; }}
        .badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; margin:1px; }}
        .badge.up {{ background:#d4edda; color:#155724; }}
        .badge.down {{ background:#f8d7da; color:#721c24; }}
        .section-intro {{ background:#f8f9fa; padding:14px; border-radius:6px; margin-bottom:16px; font-size:14px; color:#555; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-logo">
            <a href="INDEX_[PBB-ABR-26].html">
                <img src="{LOGO_PATH}" alt="Brabo Concursos">
            </a>
        </div>
        <div class="header-title">
            <h1>📋 Análise Typeform — Projeto + Alunos</h1>
            <p>Confronto: Pesquisa × Leads CRM × Campanhas × Vendas</p>
            <p>Campanha {CAMPAIGN_CODE} | Período: Abril de 2026</p>
        </div>
    </div>

    <div class="content">

        <!-- RESUMO EXECUTIVO -->
        <h2>📊 Resumo Executivo</h2>
        <div class="section-intro">
            Esta análise cruza as <strong>{len(tf_emails):,} respostas únicas das pesquisas Typeform</strong> do Projeto e do survey de alunos do PBB-ABR-26 com
            os leads do CRM Active Campaign, as campanhas do Meta Ads e Google Ads, e as vendas da Hotmart e TMB —
            revelando o perfil dos respondentes, a taxa de conversão por segmento e oportunidades de otimização.
        </div>
        <div style="margin:16px 0;">
            <div class="metric-box">
                <div class="label">Respostas Typeform</div>
                <div class="value">{len(tf_emails):,}</div>
                <div class="sub">Projeto: {len(tf_cap):,} | Alunos: {len(tf_alunos):,}</div>
            </div>
            <div class="metric-box purple">
                <div class="label">Leads no CRM</div>
                <div class="value">{len(crm):,}</div>
                <div class="sub">Active Campaign</div>
            </div>
            <div class="metric-box orange">
                <div class="label">TF → Lead CRM</div>
                <div class="value">{len(tf_e_crm):,}</div>
                <div class="sub">{funil_tx_lead:.1f}% dos respondentes</div>
            </div>
            <div class="metric-box green">
                <div class="label">TF → Compra</div>
                <div class="value">{len(tf_e_vendas):,}</div>
                <div class="sub">{funil_tx_venda_tf:.1f}% dos respondentes</div>
            </div>
            <div class="metric-box blue">
                <div class="label">Receita via TF</div>
                <div class="value">R$ {fat_tf_total/1000:.0f}k</div>
                <div class="sub">{fat_tf_total/fat_total*100:.1f}% do total</div>
            </div>
            <div class="metric-box">
                <div class="label">Receita Total</div>
                <div class="value">R$ {fat_total/1000:.0f}k</div>
                <div class="sub">Hotmart + TMB</div>
            </div>
        </div>

        <!-- FUNIL DE CONVERSÃO -->
        <h2>🔽 Funil de Conversão</h2>
        <div class="funnel">
            <div class="funnel-step" style="background:#e8f0fe;">
                <div class="num" style="color:#4285f4">{len(tf_emails):,}</div>
                <div class="desc"><strong>Responderam a pesquisa Typeform</strong><br><small>Base total da análise</small></div>
                <div class="pct" style="color:#4285f4">100%</div>
            </div>
            <div class="funnel-step" style="background:#e3f2fd;">
                <div class="num" style="color:#1565c0">{len(tf_e_crm):,}</div>
                <div class="desc"><strong>Converteram para Lead no CRM</strong><br><small>Respondentes identificados no Active Campaign</small></div>
                <div class="pct" style="color:#1565c0">{funil_tx_lead:.1f}%</div>
            </div>
            <div class="funnel-step" style="background:#fff3e0;">
                <div class="num" style="color:#e65100">{len(tf_e_crm_e_vendas):,}</div>
                <div class="desc"><strong>Lead CRM → Comprou</strong><br><small>Respondentes que estão no CRM e compraram</small></div>
                <div class="pct" style="color:#e65100">{len(tf_e_crm_e_vendas)/len(tf_e_crm)*100:.1f}% dos leads TF</div>
            </div>
            <div class="funnel-step" style="background:#e8f5e9;">
                <div class="num" style="color:#2e7d32">{len(tf_e_vendas):,}</div>
                <div class="desc"><strong>Respondentes que compraram (total)</strong><br><small>Hotmart: {len(hm_tf)} | TMB: {len(tmb_tf)} | R$ {fat_tf_total:,.2f}</small></div>
                <div class="pct" style="color:#2e7d32">{funil_tx_venda_tf:.2f}% conversão</div>
            </div>
        </div>

        <div class="grid">
            <div class="insight-box">
                <strong>📌 Taxa de conversão Typeform → Venda: {funil_tx_venda_tf:.2f}%</strong><br>
                Para comparação: a taxa geral de conversão CRM → Venda é de <strong>{funil_tx_venda_lead:.2f}%</strong>.
                Respondentes da pesquisa convertem em vendas a uma taxa <strong>{'superior' if funil_tx_venda_tf > funil_tx_venda_lead else 'similar'}</strong> à base geral do CRM.
            </div>
            <div class="success-box">
                <strong>💰 Receita rastreável via Typeform</strong><br>
                R$ {fat_tf_hm:,.2f} na Hotmart ({len(hm_tf)} vendas) + R$ {fat_tf_tmb:,.2f} na TMB ({len(tmb_tf)} vendas) =
                <strong>R$ {fat_tf_total:,.2f}</strong> ({fat_tf_total/fat_total*100:.1f}% do faturamento total de R$ {fat_total:,.2f}).
            </div>
        </div>

        <!-- ORIGEM DAS CAMPANHAS DOS COMPRADORES -->
        <h2>📡 Origem das Campanhas (Compradores via Typeform)</h2>
        <div class="section-intro">
            UTM sources dos {len(tf_e_vendas)} compradores que responderam o Typeform, rastreados no CRM.
        </div>
        {'<table><tr><th>Plataforma / utm_source</th><th style="text-align:right">Compradores</th></tr>' + utm_rows + '</table>' if utm_rows else '<p>Dados de UTM não disponíveis.</p>'}

        <div class="recommendation-box">
            <strong>💡 Insight:</strong> A origem do comprador no Typeform deve ser lida como sinal de qualificação, não apenas como última plataforma clicada.
            O recorte sugere que a pesquisa ajuda a separar quem está realmente pronto para avançar para compra.
        </div>

        <!-- PERFIL DEMOGRAFICO GERAL -->
        <h2>👤 Perfil Demográfico — Projeto Pré-Lançamento ({len(tf_demografico):,})</h2>
        <div class="grid">
            <div class="card">
                <h3>Gênero</h3>
                <table>
                    <tr><th>Grupo</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não compradores</th><th style="text-align:right">Dif.</th></tr>
                    {rows_genero or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
            <div class="card">
                <h3>Faixa Etária</h3>
                <table>
                    <tr><th>Faixa</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não compradores</th><th style="text-align:right">Dif.</th></tr>
                    {rows_idade or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
            <div class="card">
                <h3>Situação Profissional</h3>
                <table>
                    <tr><th>Perfil</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não compradores</th><th style="text-align:right">Dif.</th></tr>
                    {rows_situacao or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
            <div class="card">
                <h3>Nível nos Estudos</h3>
                <table>
                    <tr><th>Nível</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não compradores</th><th style="text-align:right">Dif.</th></tr>
                    {rows_nivel or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
        </div>

        <h3>Top 10 Estados — Respondentes Typeform</h3>
        <table>
            <tr><th>Estado</th><th style="text-align:right">Respondentes</th><th style="text-align:right">% do Total</th></tr>
            {rows_estados_geral}
        </table>

        <!-- PERFIL DOS COMPRADORES vs NÃO COMPRADORES -->
        <h2>🎯 Leitura Tática — Respondentes vs. Alunos</h2>
        <div class="section-intro">
            A leitura mais útil para o PES-MAI-26 não é demográfica pura, e sim a combinação entre <strong>intenção de mudança</strong>,
            <strong>dor de organização dos estudos</strong> e <strong>capacidade financeira de agir agora</strong>.
            Neste recorte, há <strong>{len(tf_e_vendas)}</strong> respondentes que viraram compradores, e o Typeform funciona mais como filtro de intenção
            do que como simples pesquisa de opinião.
        </div>

        <h3>Sinais que mais se aproximam da compra</h3>
        <div class="grid">
            <div class="card">
                <h3>Situação Profissional</h3>
                <table>
                    <tr><th>Indicador</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Leitura</th></tr>
                    {rows_situacao or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
            <div class="card">
                <h3>Faixa Etária</h3>
                <table>
                    <tr><th>Indicador</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Leitura</th></tr>
                    {rows_idade or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
            <div class="card">
                <h3>Obstáculos Declarados</h3>
                <table>
                    <tr><th>Indicador</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Leitura</th></tr>
                    {rows_obst or '<tr><td colspan="4">Sem dados suficientes.</td></tr>'}
                </table>
            </div>
        </div>

        <div class="grid">
            <div class="insight-box">
                <strong>📌 Hipótese de mídia:</strong><br>
                O público que mais fecha não é necessariamente o mais volumoso. A campanha parece responder melhor em perfis com
                rotina de trabalho, sensação de estagnação profissional e urgência por estabilidade. A faixa 18–22 gera interesse,
                mas precisa de mais aquecimento para comprar.
            </div>
            <div class="insight-box">
                <strong>📌 Hipótese de copy:</strong><br>
                O fechamento acontece mais pela promessa de <strong>organização prática</strong> do que por promessa ampla de aprovação.
                Método, cronograma, direção e constância resolvem dores mais próximas da compra do que mensagens genéricas de concurso.
            </div>
        </div>

        <h3>Leitura qualitativa do survey de alunos</h3>
        <div class="grid">
            <div class="card">
                <h3>O que mais puxa a compra</h3>
                <p><strong>Método claro</strong>, <strong>cronograma pronto</strong>, <strong>acompanhamento</strong>, <strong>confiança no Ivan Neto</strong> e <strong>acesso vitalício</strong> aparecem repetidamente nas respostas dos alunos.</p>
            </div>
            <div class="card">
                <h3>O que mais trava a compra</h3>
                <p><strong>Preço e condição financeira</strong> são a objeção dominante. O bloqueio principal não é desconfiança no produto; é caixa para agir agora.</p>
            </div>
            <div class="card">
                <h3>Leitura de autoridade</h3>
                <p>No PES, a autoridade relevante é <strong>Ivan Neto</strong>. A conversão parece vir menos de fama abstrata e mais da percepção de que o Ivan entrega direção prática para sair do improviso.</p>
            </div>
        </div>

        <div class="success-box">
            <strong>✅ Síntese tática:</strong> o Typeform do PES-MAI-26 captura uma base mais qualificada que o CRM médio. O aluno não está comprando apenas um curso para o TJSP; ele está comprando uma forma de <strong>parar de estudar sem método</strong>, ganhar direção e encaixar a preparação numa rotina imperfeita.
        </div>

        <!-- RECOMENDACOES ACIONAVEIS -->
        <h2>🎯 Recomendações Acionáveis</h2>

        <div class="alert-box">
            <strong>1. Tratar o Typeform como filtro de intenção, não só como pesquisa</strong><br>
            Respondentes do Typeform convertem acima da base média do CRM. Vale usar esse público como insumo de remarketing, lookalike e nutrição, em vez de tratá-lo apenas como material de diagnóstico.
        </div>

        <div class="recommendation-box">
            <strong>2. Subir o peso da promessa de método e cronograma</strong><br>
            Headlines, criativos e landing pages devem falar mais sobre sair do improviso, receber plano claro de estudo e manter constância mesmo com pouco tempo. Esse é o centro do fit percebido.
        </div>

        <div class="recommendation-box">
            <strong>3. Separar trilhas de mídia por maturidade</strong><br>
            Criar uma trilha para quem está totalmente do zero e outra para quem já tentou estudar e se perdeu. A segunda tende a reconhecer valor mais rápido; a primeira precisa de comunicação mais educativa.
        </div>

        <div class="recommendation-box">
            <strong>4. Tratar faixa 18–22 como público de aquecimento</strong><br>
            Esse grupo participa bastante da pesquisa, mas aparece sub-representado entre compradores. Vale nutrir com conteúdo, prova social e argumentação de viabilidade antes de pressionar oferta direta.
        </div>

        <div class="recommendation-box">
            <strong>5. Trabalhar condição comercial sem reduzir valor percebido</strong><br>
            Parcelamento, acesso vitalício e ganho de organização precisam aparecer com mais força no comercial. A objeção dominante é financeira, então o destrave é de formato de pagamento, não de credibilidade.
        </div>

        <div class="success-box">
            <strong>6. Usar Ivan Neto como garantia de segurança metodológica</strong><br>
            A autoridade do Ivan Neto deve ser usada como prova de clareza prática, acompanhamento e caminho validado, e não apenas como figura inspiracional. Isso alinha melhor a promessa com a dor real do comprador.
        </div>

        <!-- DADOS DE REFERÊNCIA -->
        <h2>📁 Bases de Dados Utilizadas</h2>
        <table>
            <tr><th>Fonte</th><th style="text-align:right">Registros</th><th>Arquivo</th></tr>
            <tr><td>Pesquisa Typeform</td><td style="text-align:right">{len(tf_emails):,}</td><td><code>{tf_cap_path.name} + {tf_alunos_path.name}</code></td></tr>
            <tr><td>Leads CRM (Active Campaign)</td><td style="text-align:right">{len(crm):,}</td><td><code>pes-mai-26-9h-13-05-26.csv</code></td></tr>
            <tr><td>Vendas Hotmart</td><td style="text-align:right">{len(hm):,}</td><td><code>pes-mai-26-hotmart.csv</code> | R$ {fat_hm_total:,.2f}</td></tr>
            <tr><td>Vendas TMB</td><td style="text-align:right">{len(tmb):,}</td><td><code>pes-mai-26-tmb.csv</code> | R$ {fat_tmb_total:,.2f}</td></tr>
            <tr><td>Meta Ads</td><td style="text-align:right">2.768</td><td><code>MA-Campanhas-completas-PES-MAI-26.csv</code></td></tr>
        </table>

        <div class="footer">
            <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
            <p><a href="INDEX_[PES-MAI-26].html" style="color:#667eea;text-decoration:none;font-weight:bold">← Voltar para INDEX</a></p>
        </div>
    </div>
</div>
</body>
</html>
"""

output_path = ANALISES_PATH / "ANALISE_TYPEFORM_[PES-MAI-26].html"
html_final = adaptar_html_campaign(html).replace("PBB-ABR-14h-12-05-26.csv", crm_path.name)
if "BRABO-NAV" not in html_final:
    html_final = re.sub(
        r"<body[^>]*>",
        lambda match: match.group(0) + "\n" + nav_html(active_campaign=CAMPAIGN_CODE, active_page_file=output_path.name, depth=1),
        html_final,
        count=1,
        flags=re.IGNORECASE,
    )
    html_final = re.sub(r"</body>", f"{FRAME_CLOSE}\n</body>", html_final, count=1, flags=re.IGNORECASE)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_final)

import os
print(f"\nArquivo gerado: {output_path}")
print(f"Tamanho: {os.path.getsize(output_path)//1024} KB")
print("=" * 80)
