#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE_ANUNCIOS_[PBB-ABR-26].html - VERSÃO FINAL CORRIGIDA
Mostra TODAS as 571 vendas (R$ 657.836,09) incluindo não rastreadas
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime
from pathlib import Path
import csv


def normalizar_criativo(valor):
    texto = str(valor).strip()
    return texto.split(' - ')[0].strip().upper() if ' - ' in texto else texto.strip().upper()


def criativo_valido(valor):
    texto = str(valor).strip().upper()
    if texto in {'', 'NAN', 'NONE', '{{AD.NAME}}', 'LINK_IN_BIO'}:
        return False
    if '{{' in texto or '}}' in texto:
        return False
    if texto.isdigit() and len(texto) >= 8:
        return False
    return True


def classificar_origem_macro(utm_source):
    texto = str(utm_source).strip().lower()
    if 'engaj' in texto:
        return 'Engajamento'
    if 'capta' in texto:
        return 'Captação'
    return 'Outros'

def extrair_codigo_ad(nome):
    """Extrai código base do anúncio (ex: 'AD092 - Dois...' → 'AD092')"""
    txt = str(nome).strip()
    codigo = txt.split(' - ')[0].strip().upper() if ' - ' in txt else txt.strip().upper()
    return codigo if re.match(r'^AD\d{2,3}$', codigo) else None

def limpar_brl(valor):
    """Converte string BRL para float (ex: '8.085,67' → 8085.67)"""
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
print("📊 ANÁLISE DE ANÚNCIOS PBB-ABR-26 - VERSÃO FINAL CORRIGIDA")
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
df_leads_criativo['criativo'] = df_leads_criativo['criativo_original'].apply(normalizar_criativo)
df_leads_criativo['origem_macro'] = df_leads_criativo['*Utm_source'].apply(classificar_origem_macro)

print(f"   ✓ Total leads: {len(df_leads):,}")
print(f"   ✓ Leads com criativo (UTM): {len(df_leads_criativo):,}")
print(f"   ✓ Arquivo: {leads_file.name}")

# ========== CARREGAR VENDAS (TODAS) ==========
print("\n2️⃣ Carregando VENDAS (TODAS)...")

# Hotmart — Parcelado/À vista líquido direto; RI cobrança=1 × parcelas
_hm_raw_an = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart pbb-abr-26.csv', sep=';', encoding='utf-8')
_tipo_col_an = next((c for c in _hm_raw_an.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
_par_col_an = 'Quantidade total de parcelas'
_cob_col_an = 'Quantidade de cobranças'
_an_norm = _hm_raw_an[_hm_raw_an[_tipo_col_an].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
_an_norm['valor_num'] = pd.to_numeric(_an_norm['Faturamento líquido do(a) Produtor(a)'].astype(str), errors='coerce').fillna(0)
_an_ri = _hm_raw_an[
    (_hm_raw_an[_tipo_col_an].astype(str).str.strip() == 'Recuperador Inteligente') &
    (pd.to_numeric(_hm_raw_an[_cob_col_an], errors='coerce').fillna(0) == 1)
].copy()
_an_ri[_par_col_an] = pd.to_numeric(_an_ri[_par_col_an], errors='coerce').fillna(1)
_an_ri['valor_num'] = pd.to_numeric(_an_ri['Faturamento líquido do(a) Produtor(a)'].astype(str), errors='coerce').fillna(0) * _an_ri[_par_col_an]
df_hotmart = pd.concat([_an_norm, _an_ri], ignore_index=True)
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()

# TMB — todos os rows
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb pbb-abr-26.csv', sep=';', encoding='utf-8')
# Inclui todos (oficial conta todos os 170)
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

# ========== CARREGAR INVESTIMENTO META + GOOGLE ==========
print("\n2.5 Carregando investimento por anúncio...")
ANALISES_BASE = Path(r'analises/[PBB-ABR-26]')
try:
    meta_ads_inv = pd.read_csv(ANALISES_BASE / 'Meta Ads' / 'MA-Campanhas-Completas-PBB-ABR-26.csv', encoding='utf-8', low_memory=False)
    meta_ads_inv['_ad_code'] = meta_ads_inv['Nome do anúncio'].apply(extrair_codigo_ad)
    meta_ads_inv['_invest'] = meta_ads_inv['Valor usado (BRL)'].apply(limpar_brl)
    invest_meta = meta_ads_inv[meta_ads_inv['_ad_code'].notna()].groupby('_ad_code')['_invest'].sum().to_dict()
except Exception as e:
    print(f"   ⚠ Meta Ads: {e}")
    invest_meta = {}
try:
    p_gads = ANALISES_BASE / 'Google Ads' / 'Performance dos an\u00fancios-pbb-abr-26.csv'
    gads_inv = pd.read_csv(p_gads, encoding='utf-8', skiprows=2)
    gads_inv['_ad_code'] = gads_inv['Nome do anúncio'].apply(extrair_codigo_ad)
    gads_inv['_invest'] = gads_inv['Custo'].apply(limpar_brl)
    invest_google = gads_inv[gads_inv['_ad_code'].notna()].groupby('_ad_code')['_invest'].sum().to_dict()
except Exception as e:
    print(f"   ⚠ Google Ads: {e}")
    invest_google = {}
invest_total_meta = sum(invest_meta.values())
invest_total_google = sum(invest_google.values())
invest_total_geral = invest_total_meta + invest_total_google
print(f"   ✓ Meta: R$ {invest_total_meta:,.2f} | Google: R$ {invest_total_google:,.2f} | TOTAL: R$ {invest_total_geral:,.2f}")

# ========== SEPARAR VENDAS RASTREADAS vs NÃO RASTREADAS ==========
print("\n3️⃣ Classificando vendas (rastreadas vs não rastreadas)...")

emails_com_utm = set(df_leads_criativo['Email'].unique())

# Vendas rastreadas (com UTM)
vendas_rastreadas_h = df_hotmart[df_hotmart['email'].isin(emails_com_utm)]
vendas_rastreadas_t = df_tmb[df_tmb['email'].isin(emails_com_utm)]

# Vendas NÃO rastreadas (sem UTM)
vendas_nao_rastreadas_h = df_hotmart[~df_hotmart['email'].isin(emails_com_utm)]
vendas_nao_rastreadas_t = df_tmb[~df_tmb['email'].isin(emails_com_utm)]

total_rastreadas = len(vendas_rastreadas_h) + len(vendas_rastreadas_t)
valor_rastreadas = vendas_rastreadas_h['valor_num'].sum() + vendas_rastreadas_t['valor_num'].sum()

total_nao_rastreadas = len(vendas_nao_rastreadas_h) + len(vendas_nao_rastreadas_t)
valor_nao_rastreadas = vendas_nao_rastreadas_h['valor_num'].sum() + vendas_nao_rastreadas_t['valor_num'].sum()

print(f"   ✓ Rastreadas (com UTM): {total_rastreadas} vendas = R$ {valor_rastreadas:,.2f}")
print(f"   ✓ Não rastreadas: {total_nao_rastreadas} vendas = R$ {valor_nao_rastreadas:,.2f}")

# ========== ANÁLISE POR CRIATIVO (apenas rastreadas) ==========
print("\n4️⃣ Processando análise por criativo...")

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
origem_por_criativo = (
    df_leads_criativo.groupby(['criativo', 'origem_macro']).size().reset_index(name='leads_origem')
    .sort_values(['criativo', 'leads_origem'], ascending=[True, False])
    .drop_duplicates('criativo')
    .set_index('criativo')['origem_macro']
)
criativo_stats['origem_macro'] = criativo_stats['criativo'].map(origem_por_criativo).fillna('Outros')

criativo_stats = criativo_stats[
    (criativo_stats['vendas'] > 0) & criativo_stats['criativo'].apply(criativo_valido)
].sort_values('vendas', ascending=False)

# Adicionar investimento, ROAS e CPA por criativo
criativo_stats['investimento'] = criativo_stats['criativo'].apply(
    lambda c: invest_meta.get(c, 0) + invest_google.get(c, 0)
)
criativo_stats['roas'] = criativo_stats.apply(
    lambda r: round(r['valor_total'] / r['investimento'], 2) if r['investimento'] > 0 else None, axis=1
)
criativo_stats['cpa'] = criativo_stats.apply(
    lambda r: round(r['investimento'] / r['vendas'], 0) if r['vendas'] > 0 and r['investimento'] > 0 else None, axis=1
)

# Ads com investimento mas sem vendas rastreadas
ads_com_venda = set(criativo_stats['criativo'].unique())
todos_invest = {k: invest_meta.get(k, 0) + invest_google.get(k, 0)
                for k in set(list(invest_meta.keys()) + list(invest_google.keys()))}
ads_sem_retorno = {k: v for k, v in todos_invest.items() if k not in ads_com_venda and v > 0}
ads_sem_retorno = dict(sorted(ads_sem_retorno.items(), key=lambda x: x[1], reverse=True))
total_budget_waste = sum(ads_sem_retorno.values())

# Top por ROAS (min 2 vendas)
top_roas_df = criativo_stats[
    criativo_stats['roas'].notna() & (criativo_stats['vendas'] >= 2)
].sort_values('roas', ascending=False).head(10)

top_n = min(50, len(criativo_stats))
perc_rastreadas = (total_rastreadas / total_vendas * 100) if total_vendas else 0
perc_nao_rastreadas = (total_nao_rastreadas / total_vendas * 100) if total_vendas else 0
ticket_medio = (valor_total_geral / total_vendas) if total_vendas else 0
taxa_rastreamento_leads = (len(df_leads_criativo) / len(df_leads) * 100) if len(df_leads) else 0
top3_vendas = int(criativo_stats.head(3)['vendas'].sum()) if not criativo_stats.empty else 0
top3_valor = float(criativo_stats.head(3)['valor_total'].sum()) if not criativo_stats.empty else 0
top3_part_vendas = (top3_vendas / total_rastreadas * 100) if total_rastreadas else 0
top3_part_valor = (top3_valor / valor_rastreadas * 100) if valor_rastreadas else 0
roas_geral = criativo_stats['valor_total'].sum() / criativo_stats['investimento'].sum() if criativo_stats['investimento'].sum() > 0 else 0
cap_df = criativo_stats[criativo_stats['origem_macro'] == 'Captação'].copy()
eng_df = criativo_stats[criativo_stats['origem_macro'] == 'Engajamento'].copy()
cap_vendas = int(cap_df['vendas'].sum()) if not cap_df.empty else 0
cap_valor = float(cap_df['valor_total'].sum()) if not cap_df.empty else 0
eng_vendas = int(eng_df['vendas'].sum()) if not eng_df.empty else 0
eng_valor = float(eng_df['valor_total'].sum()) if not eng_df.empty else 0


def render_tabela_categoria(titulo, descricao, df_categoria):
    if df_categoria.empty:
        return f"""
        <div class=\"info-box\">
            <h2>{titulo}</h2>
            <p>{descricao}</p>
            <div class=\"alert\"><strong>Sem registros:</strong> não há vendas rastreadas para esta categoria com criativos válidos.</div>
        </div>
        """

    top_local = min(50, len(df_categoria))
    linhas = []
    for pos, (_, row) in enumerate(df_categoria.head(50).iterrows(), start=1):
        linhas.append(f"""
                    <tr>
                        <td>{pos}º</td>
                        <td><strong>{row['criativo']}</strong></td>
                        <td class=\"numero\">{formatar_valor(row['leads_total'], 'numero')}</td>
                        <td class=\"numero\">{int(row['vendas'])}</td>
                        <td class=\"numero\">{formatar_valor(row['taxa_conversao'], 'percentual')}</td>
                        <td class=\"numero\">{formatar_valor(row['valor_total'])}</td>
                        <td class=\"numero\">{formatar_valor(row['valor_por_lead'])}</td>
                    </tr>
        """)

    return f"""
        <div class=\"info-box\">
            <h2>{titulo}</h2>
            <p>{descricao} | <strong>Criativos com vendas:</strong> {len(df_categoria)} | <strong>Vendas rastreadas:</strong> {int(df_categoria['vendas'].sum())} | <strong>Valor total:</strong> {formatar_valor(df_categoria['valor_total'].sum())}</p>
            <table>
                <thead>
                    <tr>
                        <th>Posição</th>
                        <th>Criativo</th>
                        <th class=\"numero\">Leads</th>
                        <th class=\"numero\">Vendas</th>
                        <th class=\"numero\">Taxa Conv.</th>
                        <th class=\"numero\">Valor Total</th>
                        <th class=\"numero\">Valor/Lead</th>
                    </tr>
                </thead>
                <tbody>
{''.join(linhas)}
                </tbody>
            </table>
        </div>
    """

print(f"   ✓ Criativos únicos com vendas: {len(criativo_stats)}")
print(f"   ✓ Top 10 criativos:")
for idx, row in criativo_stats.head(10).iterrows():
    print(f"      {row['criativo']}: {int(row['vendas'])} vendas | R$ {row['valor_total']:,.2f}")

# ========== GERAR HTML ==========
print("\n5️⃣ Gerando HTML...")


html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Anúncios - PBB-ABR-26</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .header h1 {{ color: #667eea; margin-bottom: 10px; font-size: 2.5em; }}
        .header p {{ color: #666; font-size: 1.1em; }}
        
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }}
        .metric-card.destaque {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
        .metric-card .label {{ font-size: 0.9em; opacity: 0.8; margin-bottom: 10px; }}
        .metric-card.destaque .label {{ opacity: 1; font-weight: 600; }}
        .metric-card .value {{ font-size: 2.5em; font-weight: bold; }}
        .metric-card .subtext {{ font-size: 0.85em; margin-top: 10px; opacity: 0.7; }}
        
        .info-box {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .info-box h2 {{ color: #667eea; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        .info-box h3 {{ color: #764ba2; margin: 20px 0 10px 0; font-size: 1.3em; }}
        
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin-top: 15px; font-size: 0.9em; }}
        th {{ background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .numero {{ text-align: right; font-family: 'Courier New', monospace; }}
        .destaque-row {{ background-color: #fff3cd !important; font-weight: 600; }}
        
        .alert {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .alert strong {{ color: #856404; }}
        .closing-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; margin-top: 24px; }}
        .closing-card {{ background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 22px; box-shadow: 0 8px 20px rgba(102,126,234,0.08); }}
        .closing-card h3 {{ color: #4c51bf; margin-bottom: 12px; font-size: 1.2em; }}
        .closing-card p {{ color: #4a5568; margin-bottom: 10px; line-height: 1.65; }}
        .closing-card p:last-child {{ margin-bottom: 0; }}
        .pill-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
        .pill {{ display: inline-flex; align-items: center; padding: 6px 10px; border-radius: 999px; font-size: 0.82em; font-weight: 700; }}
        .pill.ok {{ background: #e6fffa; color: #0f766e; }}
        .pill.warn {{ background: #fff7ed; color: #c2410c; }}
        .footer-note {{ color: #718096; font-size: 0.9em; margin-top: 18px; line-height: 1.6; }}
        @media (max-width: 900px) {{ .closing-grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Análise de Anúncios - PBB-ABR-26</h1>
            <p>Período da campanha: Abril 2026 | Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card destaque">
                <div class="label">📈 VENDAS TOTAIS (CRM)</div>
                <div class="value">{total_vendas}</div>
                <div class="subtext">Hotmart: {total_hotmart} | TMB: {total_tmb}</div>
            </div>
            <div class="metric-card destaque">
                <div class="label">💰 VALOR TOTAL</div>
                <div class="value">{formatar_valor(valor_total_geral)}</div>
                <div class="subtext">Ticket médio: {formatar_valor(valor_total_geral/total_vendas)}</div>
            </div>
            <div class="metric-card">
                <div class="label">✅ Vendas Rastreadas</div>
                <div class="value">{total_rastreadas}</div>
                <div class="subtext">{formatar_valor(valor_rastreadas)}</div>
            </div>
            <div class="metric-card">
                <div class="label">❌ Vendas Não Rastreadas</div>
                <div class="value">{total_nao_rastreadas}</div>
                <div class="subtext">{formatar_valor(valor_nao_rastreadas)}</div>
            </div>
            <div class="metric-card">
                <div class="label">🎯 Total de Leads</div>
                <div class="value">{formatar_valor(len(df_leads), 'numero')}</div>
                <div class="subtext">Com UTM: {formatar_valor(len(df_leads_criativo), 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">📱 Criativos Únicos</div>
                <div class="value">{len(criativo_stats)}</div>
                <div class="subtext">Com vendas</div>
            </div>
            <div class="metric-card destaque">
                <div class="label">💸 INVESTIMENTO TOTAL</div>
                <div class="value">{formatar_valor(invest_total_geral)}</div>
                <div class="subtext">Meta: {formatar_valor(invest_total_meta)} | Google: {formatar_valor(invest_total_google)}</div>
            </div>
            <div class="metric-card destaque">
                <div class="label">📊 ROAS RASTREADO</div>
                <div class="value">{roas_geral:.2f}x</div>
                <div class="subtext">Receita atribuída ÷ Investimento</div>
            </div>
        </div>

        <div class="alert">
            <strong>⚠️ Importante:</strong> Das {total_vendas} vendas totais, {total_rastreadas} ({perc_rastreadas:.1f}%) foram rastreadas por criativo através de UTM. 
            As {total_nao_rastreadas} vendas não rastreadas ({perc_nao_rastreadas:.1f}%) não possuem UTM_content nos leads.
        </div>

        <div class="info-box">
            <h2>🏆 Fechamento por Categoria</h2>
            <p><strong>Criativos válidos com vendas:</strong> {len(criativo_stats)} | <strong>Vendas rastreadas consideradas:</strong> {int(criativo_stats['vendas'].sum())} | <strong>Valor rastreado considerado:</strong> {formatar_valor(criativo_stats['valor_total'].sum())}</p>
            <div class="pill-row">
                <span class="pill ok">Captação: {cap_vendas} vendas | {formatar_valor(cap_valor)}</span>
                <span class="pill warn">Engajamento: {eng_vendas} vendas | {formatar_valor(eng_valor)}</span>
            </div>
        </div>
"""

html += render_tabela_categoria(
    f"🎯 Top {min(50, len(cap_df))} Criativos de Captação por Vendas" if len(cap_df) else "🎯 Criativos de Captação",
    "Recorte dos criativos ligados a campanhas de captação via UTM_source",
    cap_df,
)

html += render_tabela_categoria(
    f"🔁 Top {min(50, len(eng_df))} Criativos de Engajamento por Vendas" if len(eng_df) else "🔁 Criativos de Engajamento",
    "Recorte dos criativos ligados a campanhas de engajamento via UTM_source",
    eng_df,
)

# ── Seção: Top por ROAS ──
if not top_roas_df.empty:
    linhas_roas = []
    for i, (_, r) in enumerate(top_roas_df.iterrows(), 1):
        cor = '#22c55e' if r['roas'] >= 2 else ('#f59e0b' if r['roas'] >= 1 else '#ef4444')
        cpa_str = f"R$ {int(r['cpa']):,}".replace(',', '.') if r.get('cpa') is not None and r['cpa'] == r['cpa'] else '-'
        linhas_roas.append(f"""
            <tr>
                <td><strong>{i}º</strong></td>
                <td><strong>{r['criativo']}</strong></td>
                <td class="numero">{int(r['vendas'])}</td>
                <td class="numero">{formatar_valor(r['valor_total'])}</td>
                <td class="numero">{formatar_valor(r['investimento'])}</td>
                <td class="numero"><span style="color:{cor};font-weight:700">{r['roas']:.2f}x</span></td>
                <td class="numero">{cpa_str}</td>
                <td class="numero">{formatar_valor(r['taxa_conversao'], 'percentual')}</td>
            </tr>""")
    html += f"""
        <div class="info-box">
            <h2>🏆 Top {len(top_roas_df)} Anúncios por ROAS (mín. 2 vendas)</h2>
            <p>Anúncios com melhor retorno sobre investimento, considerando receita atribuída via CRM</p>
            <table>
                <thead>
                    <tr>
                        <th>Pos.</th><th>Criativo</th>
                        <th class="numero">Vendas</th><th class="numero">Receita</th>
                        <th class="numero">Investimento</th><th class="numero">ROAS</th>
                        <th class="numero">CPA</th><th class="numero">Conv.%</th>
                    </tr>
                </thead>
                <tbody>{''.join(linhas_roas)}</tbody>
            </table>
        </div>
    """

# ── Seção: Budget sem retorno ──
if ads_sem_retorno:
    linhas_waste = []
    for ad, inv in list(ads_sem_retorno.items())[:20]:
        linhas_waste.append(f"""
            <tr>
                <td><strong>{ad}</strong></td>
                <td class="numero" style="color:#ef4444;font-weight:700">{formatar_valor(inv)}</td>
                <td class="numero">0</td>
            </tr>""")
    html += f"""
        <div class="info-box">
            <h2>💸 Budget sem Retorno Rastreado ({len(ads_sem_retorno)} ads — R$ {total_budget_waste:,.2f})</h2>
            <p>Anúncios com investimento registrado mas sem vendas atribuídas via CRM. Podem ter contribuído para vendas não rastreadas.</p>
            <table>
                <thead>
                    <tr><th>Criativo</th><th class="numero">Investimento</th><th class="numero">Vendas atribuídas</th></tr>
                </thead>
                <tbody>{''.join(linhas_waste)}</tbody>
            </table>
        </div>
    """

html += f"""
        <div class="info-box">
            <h2>📋 Resumo Consolidado</h2>
            <table>
                <thead>
                    <tr>
                        <th>Categoria</th>
                        <th class="numero">Quantidade</th>
                        <th class="numero">Valor Total</th>
                        <th class="numero">% Vendas</th>
                        <th class="numero">% Valor</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Hotmart (Total)</strong></td>
                        <td class="numero">{total_hotmart}</td>
                        <td class="numero">{formatar_valor(valor_total_hotmart)}</td>
                        <td class="numero">{formatar_valor(total_hotmart/total_vendas*100, 'percentual')}</td>
                        <td class="numero">{formatar_valor(valor_total_hotmart/valor_total_geral*100, 'percentual')}</td>
                    </tr>
                    <tr>
                        <td><strong>TMB (Total)</strong></td>
                        <td class="numero">{total_tmb}</td>
                        <td class="numero">{formatar_valor(valor_total_tmb)}</td>
                        <td class="numero">{formatar_valor(total_tmb/total_vendas*100, 'percentual')}</td>
                        <td class="numero">{formatar_valor(valor_total_tmb/valor_total_geral*100, 'percentual')}</td>
                    </tr>
                    <tr class="destaque-row">
                        <td><strong>TOTAL GERAL</strong></td>
                        <td class="numero"><strong>{total_vendas}</strong></td>
                        <td class="numero"><strong>{formatar_valor(valor_total_geral)}</strong></td>
                        <td class="numero"><strong>100.00%</strong></td>
                        <td class="numero"><strong>100.00%</strong></td>
                    </tr>
                </tbody>
            </table>

            <div class="closing-grid">
                <div class="closing-card">
                    <h3>Leitura final</h3>
                    <p>O relatório fecha com <strong>{formatar_valor(perc_rastreadas, 'percentual')}</strong> das vendas atribuídas a criativos específicos e <strong>{formatar_valor(ticket_medio)}</strong> de ticket médio consolidado.</p>
                    <p>Os 3 criativos líderes concentram <strong>{top3_vendas}</strong> vendas rastreadas e <strong>{formatar_valor(top3_valor)}</strong> em receita, o que representa <strong>{formatar_valor(top3_part_vendas, 'percentual')}</strong> das vendas rastreadas e <strong>{formatar_valor(top3_part_valor, 'percentual')}</strong> do valor rastreado.</p>
                    <div class="pill-row">
                        <span class="pill ok">{total_rastreadas} vendas com criativo</span>
                        <span class="pill warn">{total_nao_rastreadas} vendas sem criativo</span>
                    </div>
                </div>
                <div class="closing-card">
                    <h3>Como ler este fechamento</h3>
                    <p>Os criativos do ranking consideram apenas vendas com correspondência entre email do CRM e lead com <strong>UTM_content</strong>. Por isso, a soma da tabela não pretende bater com 100% do faturamento total.</p>
                    <p>A cobertura atual de leads com criativo é de <strong>{formatar_valor(taxa_rastreamento_leads, 'percentual')}</strong>. O saldo sem UTM deve ser lido como lacuna operacional de rastreamento, não como ausência de performance.</p>
                    <p class="footer-note">Uso recomendado: combine este fechamento com as páginas de Meta, Google e Criativos para decidir escala, pausar peças com baixa conversão e priorizar os anúncios que concentram valor por lead e vendas rastreadas.</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

output_file = r'analises/[PBB-ABR-26]/ANALISE_ANUNCIOS_[PBB-ABR-26].html'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ ANÁLISE CONCLUÍDA COM SUCESSO!")
print(f"   📄 Arquivo: {output_file}")
print(f"   📊 Total de vendas: {total_vendas} = R$ {valor_total_geral:,.2f}")
print(f"   ✅ Rastreadas: {total_rastreadas} = R$ {valor_rastreadas:,.2f}")
print(f"   ❌ Não rastreadas: {total_nao_rastreadas} = R$ {valor_nao_rastreadas:,.2f}")
print("=" * 100)
