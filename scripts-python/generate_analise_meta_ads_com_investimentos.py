#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de investimentos Meta Ads por criativo
Cruza dados de investimento do Facebook com vendas do CRM
"""

import pandas as pd
import numpy as np
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
print("📊 ANÁLISE META ADS - PBB-ABR-26 (com investimentos)")
print("=" * 100)

# ========== CARREGAR DADOS META ADS ==========
print("\n1️⃣ Carregando dados Meta Ads...")

def encontrar_csv_meta():
    base = Path(r'analises/[PBB-ABR-26]/Meta Ads')
    if not base.exists():
        raise FileNotFoundError(f"Diretório de Meta Ads não encontrado: {base}")
    candidatos = list(base.glob('*.csv'))
    if candidatos:
        return candidatos[0]
    raise FileNotFoundError(f"Arquivo de Meta Ads não encontrado em {base}")

meta_file = encontrar_csv_meta()
df_meta = pd.read_csv(meta_file, sep=',', encoding='utf-8')

# Limpar nome do anúncio e extrair código
df_meta['nome_anuncio_original'] = df_meta['Nome do anúncio'].astype(str).str.strip()
df_meta['codigo_ad'] = df_meta['nome_anuncio_original'].apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)

# Converter valor usado (BRL) - pode vir como string com vírgula
df_meta['valor_gasto'] = pd.to_numeric(
    df_meta['Valor usado (BRL)'].astype(str).str.replace(',', '.'),
    errors='coerce'
).fillna(0)

# Converter outras métricas
df_meta['alcance'] = pd.to_numeric(df_meta['Alcance'], errors='coerce').fillna(0)
df_meta['impressoes'] = pd.to_numeric(df_meta['Impressões'], errors='coerce').fillna(0)
df_meta['cliques'] = pd.to_numeric(df_meta['Cliques (todos)'], errors='coerce').fillna(0)
df_meta['leads'] = pd.to_numeric(df_meta['Leads'], errors='coerce').fillna(0)

print(f"   ✓ Total de linhas: {len(df_meta):,}")
print(f"   ✓ Investimento total: R$ {df_meta['valor_gasto'].sum():,.2f}")
print(f"   ✓ Total de leads (Meta): {int(df_meta['leads'].sum()):,}")
print(f"   ✓ Total de cliques: {int(df_meta['cliques'].sum()):,}")

# ========== AGRUPAR POR CÓDIGO DO AD ==========
print("\n2️⃣ Agrupando por código do anúncio...")

meta_por_ad = df_meta.groupby('codigo_ad').agg({
    'valor_gasto': 'sum',
    'alcance': 'sum',
    'impressoes': 'sum',
    'cliques': 'sum',
    'leads': 'sum'
}).reset_index()

meta_por_ad = meta_por_ad[meta_por_ad['valor_gasto'] > 0].sort_values('valor_gasto', ascending=False)

print(f"   ✓ Anúncios únicos com investimento: {len(meta_por_ad)}")
print(f"\n   Top 10 anúncios por investimento:")
for idx, row in meta_por_ad.head(10).iterrows():
    print(f"      {row['codigo_ad']}: R$ {row['valor_gasto']:,.2f} | {int(row['leads'])} leads Meta")

# ========== CARREGAR VENDAS (CRM) ==========
print("\n3️⃣ Carregando vendas do CRM...")

def encontrar_csv_leads_abr():
    base = Path(r'analises/[PBB-ABR-26]')
    candidatos = []
    for pasta in [base / 'Active Campaign', base / 'active-campaing', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-abr-26' in f.name.lower() or 'lead' in f.name.lower())
    return max(candidatos, key=lambda f: f.stat().st_mtime)

leads_file = encontrar_csv_leads_abr()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()
df_leads_criativo = df_leads[df_leads['*Utm_content'].notna()].copy()
df_leads_criativo['criativo'] = df_leads_criativo['*Utm_content'].astype(str).str.strip().apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)

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

# Hotmart — Parcelado/À vista líquido direto; RI cobrança=1 × parcelas
hotmart_file = encontrar_csv_vendas('hotmart')
_hm_raw_meta = pd.read_csv(hotmart_file, sep=';', encoding='utf-8')
_tipo_col_m = next((c for c in _hm_raw_meta.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
_par_col_m = 'Quantidade total de parcelas'
_cob_col_m = 'Quantidade de cobranças'
_m_norm = _hm_raw_meta[_hm_raw_meta[_tipo_col_m].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
_m_norm['valor_num'] = pd.to_numeric(_m_norm['Faturamento líquido do(a) Produtor(a)'].astype(str), errors='coerce').fillna(0)
_m_ri = _hm_raw_meta[
    (_hm_raw_meta[_tipo_col_m].astype(str).str.strip() == 'Recuperador Inteligente') &
    (pd.to_numeric(_hm_raw_meta[_cob_col_m], errors='coerce').fillna(0) == 1)
].copy()
_m_ri[_par_col_m] = pd.to_numeric(_m_ri[_par_col_m], errors='coerce').fillna(1)
_m_ri['valor_num'] = pd.to_numeric(_m_ri['Faturamento líquido do(a) Produtor(a)'].astype(str), errors='coerce').fillna(0) * _m_ri[_par_col_m]
df_hotmart = pd.concat([_m_norm, _m_ri], ignore_index=True)
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()

# TMB
# TMB — todos os rows
tmb_file = encontrar_csv_vendas('tmb')
df_tmb = pd.read_csv(tmb_file, sep=';', encoding='utf-8')
# Inclui todos (oficial conta todos os 170)
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce').fillna(0)

emails_com_utm = set(df_leads_criativo['Email'].unique())
vendas_rastreadas_h = df_hotmart[df_hotmart['email'].isin(emails_com_utm)]
vendas_rastreadas_t = df_tmb[df_tmb['email'].isin(emails_com_utm)]

print(f"   ✓ Leads CRM: {len(df_leads):,}")
print(f"   ✓ Vendas rastreadas: {len(vendas_rastreadas_h) + len(vendas_rastreadas_t)}")

# ========== CRUZAR META ADS + VENDAS ==========
print("\n4️⃣ Cruzando Meta Ads + Vendas...")

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

def contar_leads_crm(criativo_name):
    return len(df_leads_criativo[df_leads_criativo['criativo'] == criativo_name])

# Adicionar métricas de vendas aos dados do Meta
meta_por_ad['vendas_crm'] = meta_por_ad['codigo_ad'].apply(contar_vendas_criativo)
meta_por_ad['faturamento_crm'] = meta_por_ad['codigo_ad'].apply(somar_valores_criativo)
meta_por_ad['leads_crm'] = meta_por_ad['codigo_ad'].apply(contar_leads_crm)

# Calcular métricas
meta_por_ad['cpl_meta'] = (meta_por_ad['valor_gasto'] / (meta_por_ad['leads'] + 0.001)).round(2)
meta_por_ad['cpl_crm'] = (meta_por_ad['valor_gasto'] / (meta_por_ad['leads_crm'] + 0.001)).round(2)
meta_por_ad['custo_por_venda'] = (meta_por_ad['valor_gasto'] / (meta_por_ad['vendas_crm'] + 0.001)).round(2)
meta_por_ad['roas'] = (meta_por_ad['faturamento_crm'] / (meta_por_ad['valor_gasto'] + 0.001)).round(2)
meta_por_ad['taxa_conversao'] = (meta_por_ad['vendas_crm'] / (meta_por_ad['leads_crm'] + 0.001) * 100).round(2)

meta_por_ad = meta_por_ad.sort_values('vendas_crm', ascending=False)

print(f"   ✓ Anúncios com vendas: {len(meta_por_ad[meta_por_ad['vendas_crm'] > 0])}")

# ========== GERAR HTML ==========
print("\n5️⃣ Gerando HTML...")

html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Meta Ads com Investimentos - PBB-ABR-26</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1800px; margin: 0 auto; }}
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
        
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin-top: 15px; font-size: 0.8em; }}
        th {{ background-color: #667eea; color: white; padding: 12px 6px; text-align: left; font-weight: 600; font-size: 0.9em; }}
        td {{ padding: 10px 6px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .numero {{ text-align: right; font-family: 'Courier New', monospace; }}
        .top3 {{ background-color: #fff3cd !important; }}
        .positivo {{ color: #28a745; font-weight: bold; }}
        .negativo {{ color: #dc3545; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 Análise Meta Ads - PBB-ABR-26</h1>
            <p>Investimentos por anúncio com cruzamento CRM | Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card destaque">
                <div class="label">💰 INVESTIMENTO TOTAL</div>
                <div class="value">{formatar_valor(meta_por_ad['valor_gasto'].sum()).replace('R$ ', '')}</div>
                <div class="subtext">{formatar_valor(meta_por_ad['valor_gasto'].sum())}</div>
            </div>
            <div class="metric-card destaque">
                <div class="label">💵 FATURAMENTO CRM</div>
                <div class="value">{formatar_valor(meta_por_ad['faturamento_crm'].sum()).replace('R$ ', '')}</div>
                <div class="subtext">{formatar_valor(meta_por_ad['faturamento_crm'].sum())}</div>
            </div>
            <div class="metric-card">
                <div class="label">📊 ROAS Geral</div>
                <div class="value">{(meta_por_ad['faturamento_crm'].sum() / max(meta_por_ad['valor_gasto'].sum(), 0.01)):.2f}</div>
                <div class="subtext">Retorno sobre investimento</div>
            </div>
            <div class="metric-card">
                <div class="label">📈 Vendas (CRM)</div>
                <div class="value">{int(meta_por_ad['vendas_crm'].sum())}</div>
                <div class="subtext">Rastreadas por UTM</div>
            </div>
            <div class="metric-card">
                <div class="label">🎯 Leads Meta</div>
                <div class="value">{formatar_valor(meta_por_ad['leads'].sum(), 'numero')}</div>
                <div class="subtext">Facebook Ads</div>
            </div>
            <div class="metric-card">
                <div class="label">🎯 Leads CRM</div>
                <div class="value">{formatar_valor(meta_por_ad['leads_crm'].sum(), 'numero')}</div>
                <div class="subtext">Active Campaign</div>
            </div>
        </div>

        <div class="info-box">
            <h2>🏆 Performance por Anúncio (ordenado por vendas)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Pos</th>
                        <th>Anúncio</th>
                        <th class="numero">Investimento</th>
                        <th class="numero">Vendas</th>
                        <th class="numero">Faturamento</th>
                        <th class="numero">ROAS</th>
                        <th class="numero">Custo/Venda</th>
                        <th class="numero">Leads Meta</th>
                        <th class="numero">Leads CRM</th>
                        <th class="numero">CPL Meta</th>
                        <th class="numero">CPL CRM</th>
                        <th class="numero">Taxa Conv.</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in meta_por_ad.iterrows():
    pos = meta_por_ad.index.get_loc(idx) + 1
    row_class = 'top3' if pos <= 3 and row['vendas_crm'] > 0 else ''
    roas_class = 'positivo' if row['roas'] >= 3 else ('negativo' if row['roas'] < 1 else '')
    
    html += f"""
                    <tr class="{row_class}">
                        <td><strong>{pos}º</strong></td>
                        <td><strong>{row['codigo_ad']}</strong></td>
                        <td class="numero">{formatar_valor(row['valor_gasto'])}</td>
                        <td class="numero"><strong>{int(row['vendas_crm'])}</strong></td>
                        <td class="numero">{formatar_valor(row['faturamento_crm'])}</td>
                        <td class="numero {roas_class}">{row['roas']:.2f}</td>
                        <td class="numero">{formatar_valor(row['custo_por_venda']) if row['vendas_crm'] > 0 else '-'}</td>
                        <td class="numero">{int(row['leads'])}</td>
                        <td class="numero">{int(row['leads_crm'])}</td>
                        <td class="numero">{formatar_valor(row['cpl_meta']) if row['leads'] > 0 else '-'}</td>
                        <td class="numero">{formatar_valor(row['cpl_crm']) if row['leads_crm'] > 0 else '-'}</td>
                        <td class="numero">{formatar_valor(row['taxa_conversao'], 'percentual') if row['leads_crm'] > 0 else '-'}</td>
                    </tr>
"""

html += f"""
                </tbody>
            </table>
        </div>

        <div class="info-box">
            <h2>📋 Resumo Consolidado</h2>
            <table>
                <thead>
                    <tr>
                        <th>Métrica</th>
                        <th class="numero">Valor</th>
                        <th>Observação</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Investimento Total Meta Ads</strong></td>
                        <td class="numero"><strong>{formatar_valor(meta_por_ad['valor_gasto'].sum())}</strong></td>
                        <td>Valor gasto (BRL) reportado pelo Facebook</td>
                    </tr>
                    <tr>
                        <td><strong>Faturamento CRM (rastreado)</strong></td>
                        <td class="numero"><strong>{formatar_valor(meta_por_ad['faturamento_crm'].sum())}</strong></td>
                        <td>Hotmart + TMB (vendas com UTM)</td>
                    </tr>
                    <tr>
                        <td><strong>ROAS Geral</strong></td>
                        <td class="numero"><strong>{(meta_por_ad['faturamento_crm'].sum() / max(meta_por_ad['valor_gasto'].sum(), 0.01)):.2f}</strong></td>
                        <td>Faturamento / Investimento</td>
                    </tr>
                    <tr>
                        <td><strong>Vendas Rastreadas</strong></td>
                        <td class="numero"><strong>{int(meta_por_ad['vendas_crm'].sum())}</strong></td>
                        <td>Vendas com UTM_content identificado</td>
                    </tr>
                    <tr>
                        <td><strong>Custo por Venda Médio</strong></td>
                        <td class="numero"><strong>{formatar_valor(meta_por_ad['valor_gasto'].sum() / max(meta_por_ad['vendas_crm'].sum(), 0.01))}</strong></td>
                        <td>Investimento / Vendas</td>
                    </tr>
                    <tr>
                        <td><strong>Leads Meta (Facebook)</strong></td>
                        <td class="numero"><strong>{formatar_valor(meta_por_ad['leads'].sum(), 'numero')}</strong></td>
                        <td>Reportado pelo Facebook Ads</td>
                    </tr>
                    <tr>
                        <td><strong>Leads CRM (Active Campaign)</strong></td>
                        <td class="numero"><strong>{formatar_valor(meta_por_ad['leads_crm'].sum(), 'numero')}</strong></td>
                        <td>Leads com UTM rastreados no CRM</td>
                    </tr>
                    <tr>
                        <td><strong>Taxa de Conversão Média</strong></td>
                        <td class="numero"><strong>{formatar_valor(meta_por_ad['vendas_crm'].sum() / max(meta_por_ad['leads_crm'].sum(), 0.01) * 100, 'percentual')}</strong></td>
                        <td>Vendas / Leads CRM</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

output_file = r'analises/[PBB-ABR-26]/ANALISE_META_ADS_[PBB-ABR-26].html'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ ANÁLISE CONCLUÍDA!")
print(f"   📄 Arquivo: {output_file}")
print(f"   💰 Investimento total: {formatar_valor(meta_por_ad['valor_gasto'].sum())}")
print(f"   💵 Faturamento CRM: {formatar_valor(meta_por_ad['faturamento_crm'].sum())}")
if meta_por_ad['valor_gasto'].sum() > 0:
    print(f"   📊 ROAS: {(meta_por_ad['faturamento_crm'].sum() / meta_por_ad['valor_gasto'].sum()):.2f}")
else:
    print(f"   📊 ROAS: N/A (sem investimento)")
print(f"   📈 Vendas: {int(meta_por_ad['vendas_crm'].sum())}")
print(f"   🎯 Anúncios analisados: {len(meta_por_ad)}")
print("=" * 100)
