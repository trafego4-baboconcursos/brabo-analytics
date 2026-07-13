#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de Criativos - PBB-ABR-26
Performance por criativo com dados atualizados
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import csv

def formatar_valor(valor, tipo='valor'):
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

def get_css_base():
    return """
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { color: #667eea; margin-bottom: 10px; font-size: 2.5em; }
        .header p { color: #666; font-size: 1.1em; }
        .info-box { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .info-box h2 { color: #667eea; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
        th { background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f5f5f5; }
        .top { background-color: #d4edda; }
        .footer { text-align: center; color: #666; padding: 20px; font-size: 0.9em; }
    </style>
    """

print("📥 Carregando dados...")

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

# Carregar leads (novo arquivo)
leads_file = encontrar_csv_leads_abr()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()

print(f"✓ Leads: {len(df_leads)} ({leads_file.name})")

# Vendas
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str),
    errors='coerce'
).fillna(0)

df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str),
    errors='coerce'
).fillna(0)

print(f"✓ Hotmart: {len(df_hotmart)} vendas")
print(f"✓ TMB: {len(df_tmb)} vendas")

# ANÁLISE POR CRIATIVO
df_leads_criativo = df_leads[df_leads['*Utm_content'].notna()].copy()
df_leads_criativo['criativo'] = df_leads_criativo['*Utm_content'].astype(str).str.strip()

# Agrupar por criativo
criativo_stats = df_leads_criativo.groupby('criativo').agg({
    'Email': 'count'
}).rename(columns={'Email': 'leads_total'}).reset_index()

# Contar vendas por criativo (via email do lead)
def contar_vendas_criativo(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    vendas = len(df_hotmart[df_hotmart['email'].isin(emails_criativo)])
    vendas += len(df_tmb[df_tmb['email'].isin(emails_criativo)])
    return vendas

def somar_valores_criativo(criativo_name):
    emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo_name]['Email'].unique()
    valor = df_hotmart[df_hotmart['email'].isin(emails_criativo)]['valor_num'].sum()
    valor += df_tmb[df_tmb['email'].isin(emails_criativo)]['valor_num'].sum()
    return valor

criativo_stats['vendas'] = criativo_stats['criativo'].apply(contar_vendas_criativo)
criativo_stats['valor_total'] = criativo_stats['criativo'].apply(somar_valores_criativo)
criativo_stats['taxa_conversao'] = (criativo_stats['vendas'] / criativo_stats['leads_total'] * 100).round(2)
criativo_stats['cpl'] = (criativo_stats['valor_total'] / criativo_stats['leads_total']).round(2)

# Ordenar por vendas
criativo_stats = criativo_stats.sort_values('vendas', ascending=False)

print(f"✓ Criativos únicos: {len(criativo_stats)}")

# Gerar tabela HTML
rows_html = ""
for idx, row in criativo_stats.head(50).iterrows():
    rows_html += f"""
    <tr class="{'top' if idx < 5 else ''}">
        <td><strong>{row['criativo']}</strong></td>
        <td>{formatar_valor(row['leads_total'], 'numero')}</td>
        <td>{formatar_valor(row['vendas'], 'numero')}</td>
        <td>{formatar_valor(row['valor_total'], 'valor')}</td>
        <td>{formatar_valor(row['taxa_conversao'], 'percentual')}</td>
        <td>{formatar_valor(row['cpl'], 'valor')}</td>
    </tr>
    """

html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Criativos - PBB-ABR-26</title>
    {get_css_base()}
</head>
<body>
    <div class="container">
        <div class="header" style="display: flex; align-items: center; gap: 20px;">
            <a href="INDEX_[PBB-ABR-26].html" style="flex-shrink: 0;">
                <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos" style="max-width: 100px; height: auto;">
            </a>
            <div>
                <h1>🎨 Análise de Criativos - PBB-ABR-26</h1>
                <p>Performance de cada criativo: leads, vendas, taxa de conversão e CPL</p>
                <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
        </div>

        <div class="info-box">
            <h2>🏆 Top 50 Criativos</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Leads</th>
                        <th>Vendas</th>
                        <th>Valor Total</th>
                        <th>Taxa de Conversão</th>
                        <th>CPL</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Total de criativos analisados: {len(criativo_stats)} | <a href="INDEX_[PBB-ABR-26].html">voltar ao índice</a></p>
        </div>
    </div>
</body>
</html>
"""

output_path = Path(r'analises/[PBB-ABR-26]/ANALISE_CRIATIVOS_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ Análise de criativos gerada: {output_path}")
print(f"   {len(criativo_stats)} criativos únicos")
print(f"   Top criativo: {criativo_stats.iloc[0]['criativo']} ({criativo_stats.iloc[0]['vendas']} vendas)")
