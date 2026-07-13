#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE_CRIATIVOS_[PBB-ABR-26].html - VERSÃO FINAL CORRIGIDA
Mostra análise por criativo com totais corretos
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime
from pathlib import Path
import csv

def formatar_valor(valor, tipo='valor'):
    """Formata número conforme tipo"""
    try:
        if pd.isna(valor) or valor is None or valor == '':
            return "-"
        v = float(valor)
        if tipo == 'valor':
            return f"R$ {v:,.2f}".replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
        elif tipo == 'percentual':
            return f"{v:.2f}%"
        elif tipo == 'numero':
            return f"{int(v):,}".replace(',', '.')
        else:
            return str(v)
    except:
        return str(valor)

print("=" * 100)
print("📊 ANÁLISE DE CRIATIVOS PBB-ABR-26 - VERSÃO FINAL CORRIGIDA")
print("=" * 100)

# ========== CARREGAR LEADS ==========
print("\n1️⃣ Carregando LEADS...")

def encontrar_csv_leads_abr():
    base = Path(r'analises/[PBB-ABR-26]')
    candidatos = []
    for pasta in [base / 'Active Campaign', base / 'active-campaing', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-abr-26' in f.name.lower() or 'lead' in f.name.lower())
    if not candidatos:
        raise FileNotFoundError('Arquivo de leads PBB-ABR-26 não encontrado')
    return max(candidatos, key=lambda f: f.stat().st_mtime)

leads_file = encontrar_csv_leads_abr()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()
df_leads_criativo = df_leads[df_leads['*Utm_content'].notna()].copy()
# Extrair código base do criativo (antes do " - " se houver)
df_leads_criativo['criativo_original'] = df_leads_criativo['*Utm_content'].astype(str).str.strip()
df_leads_criativo['criativo'] = df_leads_criativo['criativo_original'].apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)

print(f"   ✓ Total leads: {len(df_leads):,}")
print(f"   ✓ Leads com criativo (UTM): {len(df_leads_criativo):,}")

# ========== CARREGAR VENDAS ==========
print("\n2️⃣ Carregando VENDAS...")

def encontrar_csv_vendas(nome_base):
    base = Path(r'analises/[PBB-ABR-26]/Vendas')
    if not base.exists():
        raise FileNotFoundError(f"Diretório de Vendas não encontrado: {base}")
    candidatos = list(base.glob('*.csv'))
    for f in candidatos:
        f_nome = f.name.lower()
        if nome_base.lower() in f_nome:
            return f
    raise FileNotFoundError(f"Arquivo de vendas contendo '{nome_base}' não encontrado em {base}")

# Hotmart - excluindo Recuperador Inteligente (parcelas de lancamentos anteriores)
hotmart_file = encontrar_csv_vendas('hotmart')
df_hotmart = pd.read_csv(hotmart_file, sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
_tipo_col = next((c for c in df_hotmart.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
if _tipo_col:
    df_hotmart = df_hotmart[df_hotmart[_tipo_col].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
df_hotmart['valor_num'] = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce').fillna(0)

# TMB - Apenas vendas "Vigente" (não canceladas)
tmb_file = encontrar_csv_vendas('tmb')
df_tmb = pd.read_csv(tmb_file, sep=';', encoding='utf-8')
# Encontrar coluna de situação (pode ter encoding problems)
col_situacao = [c for c in df_tmb.columns if 'Situa' in c][0] if any('Situa' in c for c in df_tmb.columns) else None
if col_situacao:
    df_tmb = df_tmb[df_tmb[col_situacao] == 'Vigente']
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce').fillna(0)

total_hotmart = len(df_hotmart)
total_tmb = len(df_tmb)
total_vendas = total_hotmart + total_tmb
valor_total_hotmart = df_hotmart['valor_num'].sum()
valor_total_tmb = df_tmb['valor_num'].sum()
valor_total_geral = valor_total_hotmart + valor_total_tmb

print(f"   ✓ Hotmart: {total_hotmart:,} vendas = R$ {valor_total_hotmart:,.2f}")
print(f"   ✓ TMB: {total_tmb:,} vendas = R$ {valor_total_tmb:,.2f}")
print(f"   ✓ TOTAL: {total_vendas:,} vendas = R$ {valor_total_geral:,.2f}")

# ========== INVESTIMENTO META + GOOGLE ==========
def _extrair_codigo_ad(nome):
    txt = str(nome).strip()
    codigo = txt.split(' - ')[0].strip().upper() if ' - ' in txt else txt.strip().upper()
    return codigo if re.match(r'^AD\d{2,3}$', codigo) else None

def _limpar_brl(valor):
    if pd.isna(valor) or str(valor).strip() in ('--', '', 'None'):
        return 0.0
    txt = str(valor).strip().replace('R$', '').strip()
    if ',' in txt and '.' in txt:
        txt = txt.replace('.', '').replace(',', '.')
    elif ',' in txt:
        txt = txt.replace(',', '.')
    try:
        return float(txt)
    except:
        return 0.0

ANALISES_BASE = Path(r'analises/[PBB-ABR-26]')
try:
    _meta = pd.read_csv(ANALISES_BASE / 'Meta Ads' / 'MA-Campanhas-Completas-PBB-ABR-26.csv', encoding='utf-8', low_memory=False)
    _meta['_c'] = _meta['Nome do anúncio'].apply(_extrair_codigo_ad)
    _meta['_v'] = _meta['Valor usado (BRL)'].apply(_limpar_brl)
    invest_meta = _meta[_meta['_c'].notna()].groupby('_c')['_v'].sum().to_dict()
except Exception:
    invest_meta = {}
try:
    _gads = pd.read_csv(ANALISES_BASE / 'Google Ads' / 'Performance dos an\u00fancios-pbb-abr-26.csv', encoding='utf-8', skiprows=2)
    _gads['_c'] = _gads['Nome do anúncio'].apply(_extrair_codigo_ad)
    _gads['_v'] = _gads['Custo'].apply(_limpar_brl)
    invest_google = _gads[_gads['_c'].notna()].groupby('_c')['_v'].sum().to_dict()
except Exception:
    invest_google = {}
print("\n3️⃣ Classificando vendas...")

emails_com_utm = set(df_leads_criativo['Email'].unique())

vendas_rastreadas_h = df_hotmart[df_hotmart['email'].isin(emails_com_utm)]
vendas_rastreadas_t = df_tmb[df_tmb['email'].isin(emails_com_utm)]

vendas_nao_rastreadas_h = df_hotmart[~df_hotmart['email'].isin(emails_com_utm)]
vendas_nao_rastreadas_t = df_tmb[~df_tmb['email'].isin(emails_com_utm)]

total_rastreadas = len(vendas_rastreadas_h) + len(vendas_rastreadas_t)
valor_rastreadas = vendas_rastreadas_h['valor_num'].sum() + vendas_rastreadas_t['valor_num'].sum()

total_nao_rastreadas = len(vendas_nao_rastreadas_h) + len(vendas_nao_rastreadas_t)
valor_nao_rastreadas = vendas_nao_rastreadas_h['valor_num'].sum() + vendas_nao_rastreadas_t['valor_num'].sum()

print(f"   ✓ Rastreadas: {total_rastreadas} = R$ {valor_rastreadas:,.2f}")
print(f"   ✓ Não rastreadas: {total_nao_rastreadas} = R$ {valor_nao_rastreadas:,.2f}")

# ========== ANÁLISE POR CRIATIVO ==========
print("\n4️⃣ Analisando por criativo...")

criativo_stats = df_leads_criativo.groupby('criativo').agg({
    'Email': 'count'
}).rename(columns={'Email': 'leads_total'}).reset_index()

def contar_vendas_criativo(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    vendas_h = len(vendas_rastreadas_h[vendas_rastreadas_h['email'].isin(emails_criativo)])
    vendas_t = len(vendas_rastreadas_t[vendas_rastreadas_t['email'].isin(emails_criativo)])
    return vendas_h + vendas_t

def somar_valores_criativo(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    valor = vendas_rastreadas_h[vendas_rastreadas_h['email'].isin(emails_criativo)]['valor_num'].sum()
    valor += vendas_rastreadas_t[vendas_rastreadas_t['email'].isin(emails_criativo)]['valor_num'].sum()
    return valor

criativo_stats['vendas'] = criativo_stats['criativo'].apply(contar_vendas_criativo)
criativo_stats['valor_total'] = criativo_stats['criativo'].apply(somar_valores_criativo)
criativo_stats['taxa_conversao'] = (criativo_stats['vendas'] / criativo_stats['leads_total'] * 100).round(2)
criativo_stats['valor_por_lead'] = (criativo_stats['valor_total'] / criativo_stats['leads_total']).round(2)
criativo_stats['ticket_medio'] = (criativo_stats['valor_total'] / (criativo_stats['vendas'] + 0.001)).round(2)

criativo_stats['investimento'] = criativo_stats['criativo'].apply(
    lambda c: invest_meta.get(c, 0) + invest_google.get(c, 0)
)
criativo_stats['roas'] = criativo_stats.apply(
    lambda r: round(r['valor_total'] / r['investimento'], 2) if r['investimento'] > 0 else None, axis=1
)
criativo_stats['cpa'] = criativo_stats.apply(
    lambda r: round(r['investimento'] / r['vendas'], 0) if r['vendas'] > 0 and r['investimento'] > 0 else None, axis=1
)

criativo_stats = criativo_stats[criativo_stats['vendas'] > 0].sort_values('vendas', ascending=False)

print(f"   ✓ Criativos com vendas: {len(criativo_stats)}")

# ========== GERAR HTML ==========
print("\n5️⃣ Gerando HTML...")

html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Criativos - PBB-ABR-26</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        .header {{ background: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .header h1 {{ color: #667eea; margin-bottom: 10px; font-size: 2.5em; }}
        .header p {{ color: #666; font-size: 1.1em; }}
        
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }}
        .metric-card.destaque {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
        .metric-card .label {{ font-size: 0.85em; opacity: 0.8; margin-bottom: 10px; }}
        .metric-card.destaque .label {{ opacity: 1; font-weight: 600; }}
        .metric-card .value {{ font-size: 2.2em; font-weight: bold; }}
        .metric-card .subtext {{ font-size: 0.8em; margin-top: 8px; opacity: 0.7; }}
        
        .info-box {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .info-box h2 {{ color: #667eea; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin-top: 15px; font-size: 0.85em; }}
        th {{ background-color: #667eea; color: white; padding: 12px 8px; text-align: left; font-weight: 600; font-size: 0.9em; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .numero {{ text-align: right; font-family: 'Courier New', monospace; }}
        .top3 {{ background-color: #fff3cd !important; }}
        
        .alert {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .alert strong {{ color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎨 Análise de Criativos - PBB-ABR-26</h1>
            <p>Análise detalhada por criativo (UTM_content) | Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card destaque">
                <div class="label">📈 VENDAS TOTAIS</div>
                <div class="value">{total_vendas}</div>
                <div class="subtext">Hotmart + TMB</div>
            </div>
            <div class="metric-card destaque">
                <div class="label">💰 VALOR TOTAL</div>
                <div class="value">{formatar_valor(valor_total_geral).replace('R$ ', '').split(',')[0]}</div>
                <div class="subtext">{formatar_valor(valor_total_geral)}</div>
            </div>
            <div class="metric-card">
                <div class="label">✅ Rastreadas</div>
                <div class="value">{total_rastreadas}</div>
                <div class="subtext">{formatar_valor(valor_rastreadas)}</div>
            </div>
            <div class="metric-card">
                <div class="label">❌ Não Rastreadas</div>
                <div class="value">{total_nao_rastreadas}</div>
                <div class="subtext">{formatar_valor(valor_nao_rastreadas)}</div>
            </div>
            <div class="metric-card">
                <div class="label">🎯 Criativos Ativos</div>
                <div class="value">{len(criativo_stats)}</div>
                <div class="subtext">Com vendas</div>
            </div>
            <div class="metric-card">
                <div class="label">📊 Taxa Conv. Média</div>
                <div class="value">{formatar_valor(total_rastreadas/len(df_leads_criativo)*100, 'percentual')}</div>
                <div class="subtext">Rastreadas/Leads</div>
            </div>
        </div>

        <div class="alert">
            <strong>📋 Resumo:</strong> Das {total_vendas} vendas totais ({formatar_valor(valor_total_geral)}), 
            {total_rastreadas} vendas ({total_rastreadas/total_vendas*100:.1f}%) foram rastreadas por criativo através de UTM_content. 
            As {total_nao_rastreadas} vendas não rastreadas ({total_nao_rastreadas/total_vendas*100:.1f}%) não possuem UTM_content nos leads.
        </div>

        <div class="info-box">
            <h2>🏆 Top 50 Criativos por Performance</h2>
            <p><strong>Ordenado por:</strong> Número de vendas (decrescente) | <strong>Total de criativos com vendas:</strong> {len(criativo_stats)}</p>
            <table>
                <thead>
                    <tr>
                        <th>Pos</th>
                        <th>Criativo</th>
                        <th class="numero">Leads</th>
                        <th class="numero">Vendas</th>
                        <th class="numero">Conv.%</th>
                        <th class="numero">Receita</th>
                        <th class="numero">Investimento</th>
                        <th class="numero">ROAS</th>
                        <th class="numero">CPA</th>
                        <th class="numero">R$/Lead</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in criativo_stats.head(50).iterrows():
    pos = criativo_stats.index.get_loc(idx) + 1
    row_class = 'top3' if pos <= 3 else ''
    invest_str = formatar_valor(row['investimento']) if row.get('investimento', 0) > 0 else '-'
    roas_val = row.get('roas')
    if roas_val is not None and roas_val == roas_val:  # not NaN
        cor = '#22c55e' if roas_val >= 2 else ('#f59e0b' if roas_val >= 1 else '#ef4444')
        roas_str = f'<span style="color:{cor};font-weight:700">{roas_val:.2f}x</span>'
    else:
        roas_str = '-'
    cpa_val = row.get('cpa')
    cpa_str = f"R$ {int(cpa_val):,}".replace(',', '.') if cpa_val is not None and cpa_val == cpa_val else '-'
    html += f"""
                    <tr class="{row_class}">
                        <td><strong>{pos}\u00ba</strong></td>
                        <td><strong>{row['criativo']}</strong></td>
                        <td class="numero">{formatar_valor(row['leads_total'], 'numero')}</td>
                        <td class="numero"><strong>{int(row['vendas'])}</strong></td>
                        <td class="numero">{formatar_valor(row['taxa_conversao'], 'percentual')}</td>
                        <td class="numero">{formatar_valor(row['valor_total'])}</td>
                        <td class="numero">{invest_str}</td>
                        <td class="numero">{roas_str}</td>
                        <td class="numero">{cpa_str}</td>
                        <td class="numero">{formatar_valor(row['valor_por_lead'])}</td>
                    </tr>
"""

html += f"""
                </tbody>
            </table>
        </div>

        <div class="info-box">
            <h2>📊 Consolidado Final</h2>
            <table>
                <thead>
                    <tr>
                        <th>Categoria</th>
                        <th class="numero">Vendas</th>
                        <th class="numero">Valor</th>
                        <th class="numero">% Vendas</th>
                        <th class="numero">% Valor</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Vendas Rastreadas (com UTM)</strong></td>
                        <td class="numero">{total_rastreadas}</td>
                        <td class="numero">{formatar_valor(valor_rastreadas)}</td>
                        <td class="numero">{formatar_valor(total_rastreadas/total_vendas*100, 'percentual')}</td>
                        <td class="numero">{formatar_valor(valor_rastreadas/valor_total_geral*100, 'percentual')}</td>
                    </tr>
                    <tr>
                        <td><strong>Vendas Não Rastreadas (sem UTM)</strong></td>
                        <td class="numero">{total_nao_rastreadas}</td>
                        <td class="numero">{formatar_valor(valor_nao_rastreadas)}</td>
                        <td class="numero">{formatar_valor(total_nao_rastreadas/total_vendas*100, 'percentual')}</td>
                        <td class="numero">{formatar_valor(valor_nao_rastreadas/valor_total_geral*100, 'percentual')}</td>
                    </tr>
                    <tr style="background-color: #e7f3ff; font-weight: bold;">
                        <td><strong>TOTAL GERAL</strong></td>
                        <td class="numero"><strong>{total_vendas}</strong></td>
                        <td class="numero"><strong>{formatar_valor(valor_total_geral)}</strong></td>
                        <td class="numero"><strong>100.00%</strong></td>
                        <td class="numero"><strong>100.00%</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

output_file = r'analises/[PBB-ABR-26]/ANALISE_CRIATIVOS_[PBB-ABR-26].html'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ ANÁLISE CONCLUÍDA!")
print(f"   📄 Arquivo: {output_file}")
print(f"   📊 Vendas totais: {total_vendas} = {formatar_valor(valor_total_geral)}")
print(f"   ✅ Rastreadas: {total_rastreadas} ({total_rastreadas/total_vendas*100:.1f}%)")
print(f"   ❌ Não rastreadas: {total_nao_rastreadas} ({total_nao_rastreadas/total_vendas*100:.1f}%)")
print("=" * 100)
