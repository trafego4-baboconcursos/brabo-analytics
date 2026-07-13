#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE_ANUNCIOS_[PBB-ABR-26].html CORRIGIDA v2
Recalcula tudo a partir dos leads CSV e CRM (Hotmart + TMB)
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
print("📊 ANÁLISE DE ANÚNCIOS PBB-ABR-26 - CORRIGIDA v2")
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
df_leads_criativo['criativo'] = df_leads_criativo['*Utm_content'].astype(str).str.strip()

print(f"   ✓ Total leads: {len(df_leads):,}")
print(f"   ✓ Leads com criativo (UTM): {len(df_leads_criativo):,}")
print(f"   ✓ Arquivo: {leads_file.name}")

# ========== CARREGAR VENDAS ==========
print("\n2️⃣ Carregando VENDAS...")

# Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
# Valores já estão em formato correto (usa . como decimal) - não remover .
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str),
    errors='coerce'
).fillna(0)

# TMB (apenas "Efetivado")
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
# Valores já estão em formato correto (usa . como decimal) - não remover .
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str),
    errors='coerce'
).fillna(0)

total_hotmart = len(df_hotmart)
total_tmb = len(df_tmb)
total_vendas_crm = total_hotmart + total_tmb

print(f"   ✓ Hotmart: {total_hotmart:,} vendas")
print(f"   ✓ TMB: {total_tmb:,} vendas")
print(f"   ✓ TOTAL CRM: {total_vendas_crm:,} vendas")

# ========== ANÁLISE POR CRIATIVO ==========
print("\n3️⃣ Processando análise por criativo...")

# Agrupar leads por criativo
criativo_stats = df_leads_criativo.groupby('criativo').agg({
    'Email': 'count'
}).rename(columns={'Email': 'leads_total'}).reset_index()

# Calcular vendas por criativo
def contar_vendas_criativo(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    vendas_h = len(df_hotmart[df_hotmart['email'].isin(emails_criativo)])
    vendas_t = len(df_tmb[df_tmb['email'].isin(emails_criativo)])
    return vendas_h + vendas_t

def somar_valores_criativo(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    valor = df_hotmart[df_hotmart['email'].isin(emails_criativo)]['valor_num'].sum()
    valor += df_tmb[df_tmb['email'].isin(emails_criativo)]['valor_num'].sum()
    return valor

criativo_stats['vendas'] = criativo_stats['criativo'].apply(contar_vendas_criativo)
criativo_stats['valor_total'] = criativo_stats['criativo'].apply(somar_valores_criativo)
criativo_stats['taxa_conversao'] = (criativo_stats['vendas'] / criativo_stats['leads_total'] * 100).round(2)
criativo_stats['cpl'] = (criativo_stats['valor_total'] / criativo_stats['leads_total']).round(2)
criativo_stats['custo_venda_medio'] = (100 / (criativo_stats['taxa_conversao'] + 0.01)).round(2)  # Placeholder

criativo_stats = criativo_stats.sort_values('vendas', ascending=False)

print(f"   ✓ Criativos únicos com leads: {len(criativo_stats)}")
print(f"   ✓ Total de vendas (agrupado): {int(criativo_stats['vendas'].sum())}")
print(f"   ✓ Valor total de vendas: R$ {criativo_stats['valor_total'].sum():,.2f}")

# ========== GERAR HTML ==========
print("\n4️⃣ Gerando HTML...")

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
        .header {{ background: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 20px; }}
        .header h1 {{ color: #667eea; margin-bottom: 10px; font-size: 2.5em; }}
        .header p {{ color: #666; font-size: 1.1em; }}
        .info-box {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .info-box h2 {{ color: #667eea; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin-top: 15px; font-size: 0.85em; }}
        th {{ background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .top-performer {{ background-color: #d4edda; }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 15px; border-radius: 8px;
            text-align: center; display: inline-block;
            margin: 10px 10px 10px 0; min-width: 130px;
        }}
        .metric-card .label {{ font-size: 0.9em; opacity: 0.9; }}
        .metric-card .value {{ font-size: 1.6em; font-weight: bold; margin-top: 5px; }}
        .footer {{ text-align: center; color: #666; padding: 20px; font-size: 0.9em; }}
        .logo {{ max-width: 100px; height: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="INDEX_[PBB-ABR-26].html" style="flex-shrink: 0;">
                <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos" class="logo">
            </a>
            <div>
                <h1>📊 Análise de Anúncios - PBB-ABR-26</h1>
                <p>Performance por criativo com dados corrigidos do CRM</p>
                <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
        </div>

        <!-- RESUMO GERAL -->
        <div class="info-box">
            <h2>📈 Resumo Geral</h2>
            <div class="metric-card">
                <div class="label">Criativos</div>
                <div class="value">{len(criativo_stats)}</div>
            </div>
            <div class="metric-card">
                <div class="label">Leads (UTM)</div>
                <div class="value">{formatar_valor(criativo_stats['leads_total'].sum(), 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Vendas CRM</div>
                <div class="value" style="color: #FFD700; font-weight: bold;">{total_vendas_crm}</div>
            </div>
            <div class="metric-card">
                <div class="label">Hotmart</div>
                <div class="value">{total_hotmart}</div>
            </div>
            <div class="metric-card">
                <div class="label">TMB</div>
                <div class="value">{total_tmb}</div>
            </div>
            <div class="metric-card">
                <div class="label">Valor Total</div>
                <div class="value">{formatar_valor(criativo_stats['valor_total'].sum(), 'valor')}</div>
            </div>
        </div>

        <!-- TOP 20 CRIATIVOS -->
        <div class="info-box">
            <h2>🏆 Top 20 Criativos por Vendas</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Leads</th>
                        <th>Vendas</th>
                        <th>Valor Total</th>
                        <th>Taxa Conv %</th>
                        <th>CPL</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in criativo_stats.head(20).iterrows():
    criativo = str(row['criativo'])[:70]
    css_class = 'top-performer' if row['vendas'] > 0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(row['leads_total'], 'numero')}</td>
                        <td><strong>{int(row['vendas'])}</strong></td>
                        <td>{formatar_valor(row['valor_total'], 'valor')}</td>
                        <td>{formatar_valor(row['taxa_conversao'], 'percentual')}</td>
                        <td>{formatar_valor(row['cpl'], 'valor')}</td>
                    </tr>
"""

html += f"""
                </tbody>
            </table>
        </div>

        <!-- INSIGHTS -->
        <div class="info-box">
            <h2>💡 Insights Principais</h2>
            <ul style="margin-left: 20px; margin-top: 10px; line-height: 1.8;">
                <li><strong>🥇 Melhor Criativo:</strong> {criativo_stats.iloc[0]['criativo'][:60]} com <strong>{int(criativo_stats.iloc[0]['vendas'])} vendas</strong></li>
                <li><strong>📊 Taxa de Conversão Média:</strong> {formatar_valor(criativo_stats[criativo_stats['vendas'] > 0]['taxa_conversao'].mean(), 'percentual')}</li>
                <li><strong>💰 Maior Valor por Venda:</strong> {formatar_valor(criativo_stats['valor_total'].max(), 'valor')} (Top 1)</li>
                <li><strong>💵 Menor CPL:</strong> {formatar_valor(criativo_stats[criativo_stats['leads_total'] > 0]['cpl'].min(), 'valor')}</li>
                <li><strong>📈 Criativos com Vendas:</strong> {len(criativo_stats[criativo_stats['vendas'] > 0])} de {len(criativo_stats)} ({len(criativo_stats[criativo_stats['vendas'] > 0])/len(criativo_stats)*100:.1f}%)</li>
                <li><strong>🎯 Distribuição:</strong> Hotmart: {total_hotmart} vendas | TMB: {total_tmb} vendas</li>
            </ul>
        </div>

        <div class="footer">
            <p>Relatório gerado automaticamente com dados recalculados do CRM | <a href="INDEX_[PBB-ABR-26].html">Voltar ao índice</a></p>
        </div>
    </div>
</body>
</html>
"""

# ========== SALVAR ==========
output_path = Path(r'analises/[PBB-ABR-26]/ANALISE_ANUNCIOS_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"   ✓ HTML salvo: {output_path}")
print(f"   ✓ Tamanho: {output_path.stat().st_size / 1024:.1f} KB")

print("\n" + "=" * 100)
print("✅ ANÁLISE CONCLUÍDA COM SUCESSO!")
print(f"   Total de vendas: {total_vendas_crm}")
print(f"   Criativos com UTM: {len(criativo_stats)}")
print("=" * 100)
