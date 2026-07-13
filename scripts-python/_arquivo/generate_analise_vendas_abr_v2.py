#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de Vendas - PBB-ABR-26
Atualizado com novo arquivo de leads
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
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { color: #667eea; margin-bottom: 10px; font-size: 2.5em; }
        .header p { color: #666; font-size: 1.1em; }
        .card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-card .label { font-size: 0.9em; opacity: 0.9; margin-bottom: 10px; }
        .metric-card .value { font-size: 2em; font-weight: bold; }
        .info-box { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .info-box h2 { color: #667eea; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
        th { background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f5f5f5; }
        .footer { text-align: center; color: #666; padding: 20px; font-size: 0.9em; }
    </style>
    """

print("📥 Carregando dados de abril (com novo arquivo)...")

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

# Novo arquivo de leads - usar quoting para lidar com commas dentro de campos
leads_file = encontrar_csv_leads_abr()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL)

print(f"✓ Leads carregados: {len(df_leads)} ({leads_file.name})")

# Normalizar emails
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()

# Vendas - Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()

# Vendas - TMB
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
# Filtrar apenas pedidos efetivados
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()

print(f"✓ Hotmart: {len(df_hotmart)} vendas")
print(f"✓ TMB: {len(df_tmb)} vendas")

# CONSOLIDAR VENDAS
total_vendas = len(df_hotmart) + len(df_tmb)
total_valor_vendas = 0

# Valor Hotmart
if 'Faturamento bruto (sem impostos)' in df_hotmart.columns:
    df_hotmart['valor_num'] = pd.to_numeric(
        df_hotmart['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
        errors='coerce'
    )
    total_valor_vendas += df_hotmart['valor_num'].sum()
else:
    print("⚠️ Coluna de valor não encontrada em Hotmart")

# Valor TMB
if 'Ticket do pedido' in df_tmb.columns:
    df_tmb['valor_num'] = pd.to_numeric(
        df_tmb['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
        errors='coerce'
    )
    total_valor_vendas += df_tmb['valor_num'].sum()
elif 'Valor Total' in df_tmb.columns:
    df_tmb['valor_num'] = pd.to_numeric(
        df_tmb['Valor Total'].astype(str).str.replace('.', '').str.replace(',', '.'),
        errors='coerce'
    )
    total_valor_vendas += df_tmb['valor_num'].sum()

# ATRIBUIÇÃO: Cruzar leads com vendas
leads_vendidos = 0
vendas_atribuidas = 0

for email in df_hotmart['email'].unique():
    if pd.notna(email) and '@' in str(email):
        if email in df_leads['Email'].values:
            leads_vendidos += 1
            vendas_atribuidas += len(df_hotmart[df_hotmart['email'] == email])

for email in df_tmb['email'].unique():
    if pd.notna(email) and '@' in str(email):
        if email in df_leads['Email'].values:
            leads_vendidos += len(df_tmb[df_tmb['email'] == email])
            vendas_atribuidas += len(df_tmb[df_tmb['email'] == email])

taxa_conversao = (total_vendas / len(df_leads)) * 100 if len(df_leads) > 0 else 0

# Gerar HTML
html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Vendas - PBB-ABR-26</title>
    {get_css_base()}
</head>
<body>
    <div class="container">
        <div class="header" style="display: flex; align-items: center; gap: 20px;">
            <a href="INDEX_[PBB-ABR-26].html" style="flex-shrink: 0;">
                <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos" style="max-width: 100px; height: auto;">
            </a>
            <div>
                <h1>💰 Análise de Vendas - PBB-ABR-26</h1>
                <p>Cruzamento de leads com vendas (Hotmart + TMB)</p>
                <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
        </div>

        <div class="card-grid">
            <div class="metric-card">
                <div class="label">Total de Leads</div>
                <div class="value">{formatar_valor(len(df_leads), 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Total de Vendas</div>
                <div class="value">{formatar_valor(total_vendas, 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Taxa de Conversão</div>
                <div class="value">{formatar_valor(taxa_conversao, 'percentual')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Valor Total</div>
                <div class="value">{formatar_valor(total_valor_vendas, 'valor')}</div>
            </div>
        </div>

        <div class="info-box">
            <h2>📊 Detalhamento por Plataforma</h2>
            <table>
                <thead>
                    <tr>
                        <th>Plataforma</th>
                        <th>Quantidade Vendas</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Hotmart</strong></td>
                        <td>{len(df_hotmart)}</td>
                        <td>{formatar_valor(df_hotmart['valor_num'].sum(), 'valor')}</td>
                        <td>{formatar_valor(df_hotmart['valor_num'].sum() / len(df_hotmart) if len(df_hotmart) > 0 else 0, 'valor')}</td>
                    </tr>
                    <tr>
                        <td><strong>TMB</strong></td>
                        <td>{len(df_tmb)}</td>
                        <td>{formatar_valor(df_tmb['valor_num'].sum(), 'valor')}</td>
                        <td>{formatar_valor(df_tmb['valor_num'].sum() / len(df_tmb) if len(df_tmb) > 0 else 0, 'valor')}</td>
                    </tr>
                    <tr style="background: #f0f0f0;">
                        <td><strong>TOTAL</strong></td>
                        <td><strong>{total_vendas}</strong></td>
                        <td><strong>{formatar_valor(total_valor_vendas, 'valor')}</strong></td>
                        <td><strong>{formatar_valor(total_valor_vendas / total_vendas if total_vendas > 0 else 0, 'valor')}</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Relatório gerado automaticamente | <a href="INDEX_[PBB-ABR-26].html">voltar ao índice</a></p>
        </div>
    </div>
</body>
</html>
"""

output_path = Path(r'analises/[PBB-ABR-26]/ANALISE_VENDAS_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅ Análise de vendas gerada: {output_path}")
print(f"   Total de vendas: {total_vendas}")
print(f"   Valor: {formatar_valor(total_valor_vendas, 'valor')}")
print(f"   Taxa de conversão: {formatar_valor(taxa_conversao, 'percentual')}")
