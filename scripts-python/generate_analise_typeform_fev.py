#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE_TYPEFORM_[PBB-FEV-26].html
Confronto: Pesquisa Typeform x Leads CRM x Campanhas x Vendas
"""

import pandas as pd
import csv as csvmod
import os
from datetime import datetime
from pathlib import Path

BASE_PATH    = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES_PATH = BASE_PATH / "analises" / "[PBB-FEV-26]"
LOGO_PATH    = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"
CAMPAIGN_CODE = "PBB-FEV-26"

print("=" * 80)
print("ANALISE TYPEFORM - PBB-FEV-26")
print("=" * 80)

# ============================================================================
# CARREGAR DADOS
# ============================================================================

print("\nCarregando dados...")

tf = pd.read_csv(ANALISES_PATH / "typeform" / "typeform-pbb-fev-26.csv", low_memory=False)
tf["email_norm"] = tf["Digite o seu e-mail."].astype(str).str.strip().str.lower()
print(f"  Typeform: {len(tf):,} respostas")

crm = pd.read_csv(
    ANALISES_PATH / "active-campaing" / "PBB-FEV-26-16h-12-05-26.csv",
    sep=",", quoting=csvmod.QUOTE_MINIMAL, low_memory=False
)
crm["email_norm"] = crm["Email"].astype(str).str.strip().str.lower()
print(f"  CRM: {len(crm):,} leads")

hm = pd.read_csv(ANALISES_PATH / "vendas" / "hotmart-pbb-fev-26.csv", sep=";", low_memory=False)
hm["email_norm"] = hm["Email do(a) Comprador(a)"].astype(str).str.strip().str.lower()
hm["valor"] = pd.to_numeric(hm["Faturamento bruto (sem impostos)"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
print(f"  Hotmart: {len(hm):,} vendas")

tmb_raw = pd.read_csv(ANALISES_PATH / "vendas" / "tmb-pbb-fev-26.csv", sep=";", encoding="utf-8", low_memory=False)
if "Status" in tmb_raw.columns:
    tmb = tmb_raw[tmb_raw["Status"].astype(str).str.strip() == "Efetivado"].copy()
else:
    tmb = tmb_raw.copy()
tmb["email_norm"] = tmb["Cliente Email"].astype(str).str.strip().str.lower()
tmb["valor"] = pd.to_numeric(tmb["Ticket (R$)"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
print(f"  TMB: {len(tmb):,} vendas")

# ============================================================================
# CRUZAMENTOS
# ============================================================================

tf_emails     = set(tf["email_norm"])
crm_emails    = set(crm["email_norm"])
hm_emails     = set(hm["email_norm"])
tmb_emails    = set(tmb["email_norm"])
vendas_emails = hm_emails | tmb_emails

tf_e_crm          = tf_emails & crm_emails
tf_e_vendas       = tf_emails & vendas_emails
crm_e_vendas      = crm_emails & vendas_emails
tf_e_crm_e_vendas = tf_emails & crm_emails & vendas_emails

tf_comp  = tf[tf["email_norm"].isin(tf_e_vendas)].copy()
tf_ncomp = tf[~tf["email_norm"].isin(tf_e_vendas)].copy()

hm_tf  = hm[hm["email_norm"].isin(tf_e_vendas)]
tmb_tf = tmb[tmb["email_norm"].isin(tf_e_vendas)]

fat_hm_total  = hm["valor"].sum()
fat_tmb_total = tmb["valor"].sum()
fat_total     = fat_hm_total + fat_tmb_total
fat_tf_hm     = hm_tf["valor"].sum()
fat_tf_tmb    = tmb_tf["valor"].sum()
fat_tf_total  = fat_tf_hm + fat_tf_tmb

print(f"\n  TF -> Lead CRM: {len(tf_e_crm):,} ({len(tf_e_crm)/len(tf_emails)*100:.1f}%)")
print(f"  TF -> Compra:   {len(tf_e_vendas):,} ({len(tf_e_vendas)/len(tf_emails)*100:.1f}%)")
print(f"  Faturamento TF: R$ {fat_tf_total:,.2f} ({fat_tf_total/fat_total*100:.1f}% do total)")

# ============================================================================
# HELPERS HTML
# ============================================================================

def row_perc(label, n_total, val_comp, val_ncomp, invert=False):
    bar_c = f'<div style="height:8px;background:#667eea;border-radius:3px;width:{min(val_comp,100):.0f}%"></div>'
    bar_n = f'<div style="height:8px;background:#ccc;border-radius:3px;width:{min(val_ncomp,100):.0f}%"></div>'
    diff  = val_comp - val_ncomp
    diff_str   = f'+{diff:.0f}pp' if diff >= 0 else f'{diff:.0f}pp'
    diff_color = "#28a745" if (diff > 0) != invert else "#dc3545"
    return (
        f"<tr><td>{label}</td>"
        f"<td style='text-align:right'><strong>{val_comp:.1f}%</strong><br>{bar_c}</td>"
        f"<td style='text-align:right'>{val_ncomp:.1f}%<br>{bar_n}</td>"
        f"<td style='text-align:right;color:{diff_color};font-weight:bold'>{diff_str}</td></tr>"
    )

def pct(df, col, val):
    if col not in df.columns: return 0
    return df[col].value_counts(normalize=True).get(val, 0) * 100

def pct_notnull(df, col):
    if col not in df.columns: return 0
    return df[col].notna().sum() / len(df) * 100

# ============================================================================
# CALCULAR MÉTRICAS
# ============================================================================

funil_tf        = len(tf_emails)
funil_leads     = len(tf_e_crm)
funil_compras   = len(tf_e_vendas)
funil_tx_lead       = funil_leads   / funil_tf * 100
funil_tx_venda_tf   = funil_compras / funil_tf * 100
funil_tx_venda_lead = len(crm_e_vendas) / len(crm_emails) * 100

# UTM sources dos compradores Typeform no CRM
utm_col   = next((c for c in crm.columns if "utm_source" in c.lower()), None)
utm_rows  = ""
if utm_col:
    crm_comp_tf = crm[crm["email_norm"].isin(tf_e_vendas)]
    utm_vc = crm_comp_tf[utm_col].value_counts().head(10)
    for src, cnt in utm_vc.items():
        plat = "YouTube" if str(src).startswith("yt") else ("Meta/FB" if str(src).startswith("fb") else "Outros")
        badge_color = "#ff0000" if plat == "YouTube" else ("#1877f2" if plat == "Meta/FB" else "#666")
        badge = f'<span style="background:{badge_color};color:white;padding:1px 6px;border-radius:10px;font-size:11px">{plat}</span>'
        utm_rows += f"<tr><td>{badge} {src}</td><td style='text-align:right'>{cnt}</td></tr>"

# Perfil demográfico
rows_genero = ""
for v in ["Masculino", "Feminino"]:
    rows_genero += row_perc(v, len(tf), pct(tf_comp, "Qual é o seu gênero?", v),
                             pct(tf_ncomp, "Qual é o seu gênero?", v))

rows_situacao = ""
for v in ["Desempregado(a)", "Funcionário(a) de empresa privada", "Autônomo(a)", "Funcionário(a) público"]:
    rows_situacao += row_perc(v, len(tf),
                               pct(tf_comp, "Qual a sua situação profissional atualmente?", v),
                               pct(tf_ncomp, "Qual a sua situação profissional atualmente?", v))

rows_nivel = ""
for v in ["Estou do zero", "Sou Iniciante", "Sou Intermediário(a)", "Sou Avançado(a)"]:
    rows_nivel += row_perc(v, len(tf),
                            pct(tf_comp, "Em relação aos estudos para concursos públicos, você se considera?", v),
                            pct(tf_ncomp, "Em relação aos estudos para concursos públicos, você se considera?", v))

rows_idade = ""
for v in ["18 a 22 anos", "23 a 27 anos", "28 a 32 anos", "33 a 37 anos", "38 a 45 anos"]:
    rows_idade += row_perc(v, len(tf), pct(tf_comp, "Qual a sua idade?", v),
                            pct(tf_ncomp, "Qual a sua idade?", v))

# Obstáculos (colunas presentes no CSV FEV)
obstaculos = [
    ("Não sei estudar do jeito certo",   "Não sei estudar do jeito certo (falta de técnicas de estudos)"),
    ("Não sei montar um cronograma",     "Não sei montar um cronograma de estudos"),
    ("Procrastinação",                   "Procrastinação (não conseguir estudar)"),
    ("Estou há muito tempo sem estudar", "Estou há muito tempo sem estudar"),
    ("Pouco tempo disponível",           "Pouco tempo disponível pra me dedicar aos estudos"),
    ("Medo de esquecer no dia da prova", "Medo de esquecer tudo no dia da prova"),
    ("Medo de estudar e não passar",     "Medo de estudar muito e não conseguir passar"),
    ("Sem dinheiro para curso",          "Não tenho dinheiro para investir em um curso"),
    ("Medo de não sair o concurso",      "Medo de não sair o concurso em 2025"),
]
rows_obst = ""
for label, col in obstaculos:
    if col in tf.columns:
        pc = pct_notnull(tf_comp, col)
        pn = pct_notnull(tf_ncomp, col)
        rows_obst += row_perc(label, len(tf), pc, pn, invert=(label == "Sem dinheiro para curso"))

# Graton
graton_col = "Você já assistiu a algum vídeo ou Aula do Felipe Graton?"
graton_c   = pct(tf_comp,  graton_col, 1)
graton_n   = pct(tf_ncomp, graton_col, 1)
graton_0c  = pct(tf_comp,  graton_col, 0)
graton_0n  = pct(tf_ncomp, graton_col, 0)

# Dados demográficos dinâmicos
genero_col = "Qual é o seu gênero?"
fem_pct    = pct(tf, genero_col, "Feminino")
masc_pct   = pct(tf, genero_col, "Masculino")

idade_col  = "Qual a sua idade?"
jovem_pct  = pct(tf, idade_col, "18 a 22 anos") + pct(tf, idade_col, "23 a 27 anos")

escol_col  = "Qual o seu grau de escolaridade?"
nivel_medio = pct(tf, escol_col, "Ensino Médio Completo") + pct(tf, escol_col, "Ensino Médio Incompleto") \
            + pct(tf, escol_col, "Nível Médio")
if nivel_medio == 0:
    nivel_medio = tf[escol_col].value_counts(normalize=True).iloc[0] * 100 if escol_col in tf.columns else 0
    nivel_medio_label = tf[escol_col].value_counts().index[0] if escol_col in tf.columns else "N/A"
else:
    nivel_medio_label = "Nível Médio"

prof_col    = "Qual a sua situação profissional atualmente?"
desemp_pct  = pct(tf, prof_col, "Desempregado(a)")

nivel_col   = "Em relação aos estudos para concursos públicos, você se considera?"
zero_pct    = pct(tf, nivel_col, "Estou do zero")
inic_pct    = pct(tf, nivel_col, "Sou Iniciante")

commit_col  = "Você se Compromete a estudar pelo menos 2 horas por dia para ser Aprovado(a) no próximo concurso do Banco do Brasil?"
commit_sim  = 0
if commit_col in tf.columns:
    commit_sim = tf[commit_col].notna().sum() / len(tf) * 100

# Top estados
rows_estados = ""
top_estados = tf_comp["De qual estado você é?"].value_counts().head(10)
for estado, cnt in top_estados.items():
    pct_estado = cnt / len(tf_comp) * 100
    rows_estados += f"<tr><td>{estado}</td><td style='text-align:right'>{cnt}</td><td style='text-align:right'>{pct_estado:.1f}%</td></tr>"

rows_estados_geral = ""
top_estados_g = tf["De qual estado você é?"].value_counts().head(10)
for estado, cnt in top_estados_g.items():
    pct_estado = cnt / len(tf) * 100
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
            <a href="INDEX_[PBB-FEV-26].html">
                <img src="{LOGO_PATH}" alt="Brabo Concursos">
            </a>
        </div>
        <div class="header-title">
            <h1>📋 Análise Typeform — Pesquisa de Captação</h1>
            <p>Confronto: Pesquisa × Leads CRM × Campanhas × Vendas</p>
            <p>Campanha {CAMPAIGN_CODE} | Período: Fevereiro de 2026</p>
        </div>
    </div>

    <div class="content">

        <!-- RESUMO EXECUTIVO -->
        <h2>📊 Resumo Executivo</h2>
        <div class="section-intro">
            Esta análise cruza as <strong>{len(tf):,} respostas da pesquisa Typeform</strong> realizada durante a captação do {CAMPAIGN_CODE} com
            os leads do CRM Active Campaign, as campanhas do Meta Ads e Google Ads, e as vendas da Hotmart e TMB —
            revelando o perfil dos respondentes, a taxa de conversão por segmento e oportunidades de otimização.
        </div>
        <div style="margin:16px 0;">
            <div class="metric-box">
                <div class="label">Respostas Typeform</div>
                <div class="value">{len(tf):,}</div>
                <div class="sub">Emails únicos</div>
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
                <div class="num" style="color:#4285f4">{len(tf):,}</div>
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
            <strong>💡 Insight:</strong> Campanhas de captação quente (YouTube e Facebook) dominam entre os compradores que responderam a pesquisa.
            O segmento <em>quente</em> tem maior propensão de conversão após a pesquisa.
        </div>

        <!-- PERFIL DEMOGRAFICO GERAL -->
        <h2>👤 Perfil Demográfico — Todos os Respondentes ({len(tf):,})</h2>
        <div class="grid">
            <div class="card">
                <h3>Gênero</h3>
                <p><strong>{fem_pct:.1f}%</strong> Feminino — <strong>{masc_pct:.1f}%</strong> Masculino</p>
                <div style="margin-top:8px;height:10px;background:#eee;border-radius:5px;overflow:hidden;">
                    <div style="height:100%;width:{fem_pct:.1f}%;background:linear-gradient(90deg,#f093fb,#f5576c);border-radius:5px;"></div>
                </div>
            </div>
            <div class="card">
                <h3>Faixa Etária</h3>
                <p><strong>{jovem_pct:.1f}%</strong> têm entre 18 e 27 anos</p>
                <p style="font-size:12px;color:#666;margin-top:4px">{pct(tf, idade_col, '18 a 22 anos'):.1f}% (18–22) + {pct(tf, idade_col, '23 a 27 anos'):.1f}% (23–27)</p>
            </div>
            <div class="card">
                <h3>Situação Profissional</h3>
                <p><strong>{desemp_pct:.1f}%</strong> Desempregado(a)</p>
                <p style="font-size:12px;color:#666;margin-top:4px">{pct(tf, prof_col, 'Funcionário(a) de empresa privada'):.1f}% Empresa privada | {pct(tf, prof_col, 'Autônomo(a)'):.1f}% Autônomo(a)</p>
            </div>
            <div class="card">
                <h3>Nível nos Estudos</h3>
                <p><strong>{zero_pct:.1f}%</strong> do zero | <strong>{inic_pct:.1f}%</strong> Iniciante</p>
                <p style="font-size:12px;color:#666;margin-top:4px">{zero_pct+inic_pct:.1f}% são iniciantes ou do zero</p>
            </div>
        </div>

        <h3>Top 10 Estados — Respondentes Typeform</h3>
        <table>
            <tr><th>Estado</th><th style="text-align:right">Respondentes</th><th style="text-align:right">% do Total</th></tr>
            {rows_estados_geral}
        </table>

        <!-- PERFIL DOS COMPRADORES vs NÃO COMPRADORES -->
        <h2>🎯 Compradores vs. Não-Compradores — Diferenças de Perfil</h2>
        <div class="section-intro">
            Comparação entre os <strong>{len(tf_comp)}</strong> respondentes que compraram
            e os <strong>{len(tf_ncomp):,}</strong> que não compraram.
        </div>

        <h3>Gênero</h3>
        <table>
            <tr><th>Gênero</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Diferença</th></tr>
            {rows_genero}
        </table>
        <div class="insight-box">
            <strong>📌 Insight:</strong> Observe a diferença de gênero entre compradores e não-compradores.
            Segmentos com maior taxa de conversão indicam onde concentrar criativos personalizados.
        </div>

        <h3>Situação Profissional</h3>
        <table>
            <tr><th>Situação</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Diferença</th></tr>
            {rows_situacao}
        </table>
        <div class="insight-box">
            <strong>📌 Insight:</strong> Empregados em empresa privada tendem a investir mais por terem renda regular
            e desejo de transição de carreira. Desempregados podem ter barreira financeira real.
        </div>

        <h3>Nível de Estudos</h3>
        <table>
            <tr><th>Nível</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Diferença</th></tr>
            {rows_nivel}
        </table>
        <div class="insight-box">
            <strong>📌 Insight:</strong> Pessoas com alguma consciência do processo de estudo (Iniciante)
            tendem a perceber melhor o valor do produto e converter mais.
        </div>

        <h3>Faixa Etária</h3>
        <table>
            <tr><th>Faixa Etária</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Diferença</th></tr>
            {rows_idade}
        </table>
        <div class="insight-box">
            <strong>📌 Insight:</strong> Faixas com maior urgência de mudança de carreira (23–37 anos) costumam converter mais.
            18–22 anos têm maior participação geral mas menor taxa de conversão por barreira financeira.
        </div>

        <!-- CONHECIMENTO DO GRATON -->
        <h2>🎥 Familiaridade com o Professor (Felipe Graton)</h2>
        <table>
            <tr><th>Já assistiu Felipe Graton?</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Diferença</th></tr>
            <tr>
                <td>Sim (já conhecia)</td>
                <td style="text-align:right"><strong>{graton_c:.1f}%</strong><br><div style="height:8px;background:#28a745;border-radius:3px;width:{min(graton_c,100):.0f}%"></div></td>
                <td style="text-align:right">{graton_n:.1f}%<br><div style="height:8px;background:#ccc;border-radius:3px;width:{min(graton_n,100):.0f}%"></div></td>
                <td style="text-align:right;color:{'#28a745' if graton_c >= graton_n else '#dc3545'};font-weight:bold">{graton_c-graton_n:+.1f}pp</td>
            </tr>
            <tr>
                <td>Não (novo seguidor)</td>
                <td style="text-align:right"><strong>{graton_0c:.1f}%</strong></td>
                <td style="text-align:right">{graton_0n:.1f}%</td>
                <td style="text-align:right;color:{'#28a745' if graton_0c >= graton_0n else '#dc3545'};font-weight:bold">{graton_0c-graton_0n:+.1f}pp</td>
            </tr>
        </table>
        <div class="success-box">
            <strong>✅ Insight crítico:</strong> Quem <em>já conhecia</em> o Felipe Graton converte mais.
            Isso confirma que branding e conteúdo anterior aumentam diretamente a conversão.
            Ampliar reach de conteúdo orgânico e remarketing de vídeo pode elevar a taxa geral.
        </div>

        <!-- OBSTACULOS DOS COMPRADORES -->
        <h2>🚧 Obstáculos Declarados — Compradores vs. Não-Compradores</h2>
        <div class="section-intro">
            Percentual de respondentes que marcaram cada obstáculo. Dores mais presentes nos compradores
            indicam o que o produto resolve efetivamente.
        </div>
        <table>
            <tr><th>Obstáculo</th><th style="text-align:right">Compradores</th><th style="text-align:right">Não Compradores</th><th style="text-align:right">Diferença</th></tr>
            {rows_obst}
        </table>
        <div class="grid">
            <div class="insight-box">
                <strong>📌 Compradores têm mais:</strong><br>
                • <strong>Não sei estudar do jeito certo</strong> — dor que o produto resolve diretamente<br>
                • <strong>Não sei montar cronograma</strong> — mesma lógica<br>
                • <strong>Procrastinação</strong> — buscam estrutura e compromisso externo<br>
                • <strong>Há muito tempo sem estudar</strong> — insegurança que gera urgência
            </div>
            <div class="recommendation-box">
                <strong>💡 Compradores têm MENOS:</strong><br>
                • <strong>Sem dinheiro para curso</strong> — barreira financeira removida é condição de compra<br>
                • <strong>Medo de não sair o concurso</strong> — menos bloqueados por incerteza externa<br>
                • <strong>Medo de estudar e não passar</strong> — mais focados em ação, não em resultado
            </div>
        </div>

        <!-- ESTADOS DOS COMPRADORES -->
        <h2>🗺️ Estados dos Compradores (via Typeform)</h2>
        <div class="grid">
            <div>
                <table>
                    <tr><th>Estado</th><th style="text-align:right">Compradores</th><th style="text-align:right">% do total</th></tr>
                    {rows_estados}
                </table>
            </div>
            <div class="card">
                <h3>Comparativo regional</h3>
                <p style="margin-bottom:8px">SP tende a ter mais respondentes <strong>e</strong> mais compradores — consistência esperada.</p>
                <p><strong>Estados com alta taxa de conversão por capita</strong> (muitos compradores relativo ao volume de respostas)
                indicam onde concentrar segmentação geográfica com lances mais agressivos.</p>
            </div>
        </div>

        <!-- RECOMENDACOES ACIONAVEIS -->
        <h2>🎯 Recomendações Acionáveis</h2>

        <div class="alert-box">
            <strong>⚠️ 1. Verificar cobertura da pesquisa vs leads CRM</strong><br>
            {len(tf):,} responderam o Typeform e {len(tf_e_crm):,} foram identificados no CRM ({funil_tx_lead:.1f}%).
            {f"Atenção: {len(tf_emails)-len(tf_e_crm):,} respondentes NÃO estão no CRM — verificar integração." if len(tf_emails) > len(tf_e_crm) else "Cobertura OK."}
        </div>

        <div class="recommendation-box">
            <strong>💡 2. Remarketing baseado no perfil de maior conversão</strong><br>
            Criar públicos personalizados no Meta Ads e Google Ads baseados nos segmentos de maior taxa de conversão
            identificados nesta análise (gênero, faixa etária, situação profissional).
        </div>

        <div class="recommendation-box">
            <strong>💡 3. Sequência diferenciada por nível de estudos</strong><br>
            Separar fluxos de nurturing para "do zero" vs "iniciante" — o iniciante converte mais rapidamente
            com foco em barreiras técnicas; o "do zero" precisa de mais contexto e urgência.
        </div>

        <div class="recommendation-box">
            <strong>💡 4. Ampliar branding do professor antes da próxima captação</strong><br>
            Quem já conhece Felipe Graton tem maior propensão de compra. Investir em conteúdo orgânico
            (YouTube, Reels) nos meses anteriores ao lançamento é estratégico.
        </div>

        <div class="recommendation-box">
            <strong>💡 5. Copy focado nas dores de metodologia e cronograma</strong><br>
            "Não sei estudar do jeito certo" e "não sei montar cronograma" são os dois pilares
            das dores dos compradores. Esses devem ser os principais ângulos de copy.
        </div>

        <div class="success-box">
            <strong>✅ 6. Segmentação geográfica agressiva nos estados de maior conversão</strong><br>
            Identificar os estados com melhor taxa comprador/respondente e aumentar lances nesses locais
            nas próximas campanhas para maximizar o ROAS regional.
        </div>

        <!-- DADOS DE REFERÊNCIA -->
        <h2>📁 Bases de Dados Utilizadas</h2>
        <table>
            <tr><th>Fonte</th><th style="text-align:right">Registros</th><th>Arquivo</th></tr>
            <tr><td>Pesquisa Typeform</td><td style="text-align:right">{len(tf):,}</td><td><code>typeform-pbb-fev-26.csv</code></td></tr>
            <tr><td>Leads CRM (Active Campaign)</td><td style="text-align:right">{len(crm):,}</td><td><code>PBB-FEV-26-16h-12-05-26.csv</code></td></tr>
            <tr><td>Vendas Hotmart</td><td style="text-align:right">{len(hm):,}</td><td><code>hotmart-pbb-fev-26.csv</code> | R$ {fat_hm_total:,.2f}</td></tr>
            <tr><td>Vendas TMB (Efetivado)</td><td style="text-align:right">{len(tmb):,}</td><td><code>tmb-pbb-fev-26.csv</code> | R$ {fat_tmb_total:,.2f}</td></tr>
        </table>

        <div class="footer">
            <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
            <p><a href="INDEX_[PBB-FEV-26].html" style="color:#667eea;text-decoration:none;font-weight:bold">← Voltar para INDEX</a></p>
        </div>
    </div>
</div>
</body>
</html>
"""

output_path = ANALISES_PATH / "ANALISE_TYPEFORM_[PBB-FEV-26].html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nArquivo gerado: {output_path}")
print(f"Tamanho: {os.path.getsize(output_path)//1024} KB")
print("=" * 80)
