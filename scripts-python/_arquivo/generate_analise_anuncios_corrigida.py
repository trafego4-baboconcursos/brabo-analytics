#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE_ANUNCIOS_[PBB-ABR-26].html CORRIGIDA
Recalcula vendas a partir dos CSVs (Hotmart + TMB) via email matching
Usa dados do Excel apenas para investimento por criativo
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
print("📊 ANÁLISE DE ANÚNCIOS PBB-ABR-26 - CORRIGIDA")
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
print(f"   ✓ Leads com criativo: {len(df_leads_criativo):,}")
print(f"   ✓ Arquivo: {leads_file.name}")

# ========== CARREGAR VENDAS ==========
print("\n2️⃣ Carregando VENDAS...")

# Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

# TMB (apenas "Efetivado")
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

print(f"   ✓ Hotmart: {len(df_hotmart):,} vendas")
print(f"   ✓ TMB: {len(df_tmb):,} vendas")
print(f"   ✓ TOTAL: {len(df_hotmart) + len(df_tmb):,} vendas")

# ========== CARREGAR DADOS DO EXCEL (apenas investimento) ==========
print("\n3️⃣ Carregando INVESTIMENTO do Excel...")

import glob
xlsx_files = glob.glob(r'C:\Users\trafe\OneDrive\Desktop\workspace-mmm\*PBB-ABR*.xlsx')
if not xlsx_files:
    raise FileNotFoundError("Excel não encontrado")

xlsx_path = xlsx_files[0]
df_excel = pd.read_excel(xlsx_path, sheet_name='Anúncios PBB-ABR-26', header=None)

print(f"   ✓ Arquivo: {Path(xlsx_path).name}")

# ========== PROCESSAR ANÁLISE ==========
print("\n4️⃣ Processando análise por criativo...")

dados = []
for i in range(2, len(df_excel)):
    row = df_excel.iloc[i]
    if pd.notna(row[0]) and row[0] not in ['Anuncio', 'TOTAL', 'NaN']:
        try:
            criativo = str(row[0])
            invest_excel = float(row[1]) if pd.notna(row[1]) else 0
            leads_excel = float(row[3]) if pd.notna(row[3]) else 0
            
            # Buscar leads REAIS do CSV
            leads_reais = len(df_leads_criativo[df_leads_criativo['criativo'] == criativo])
            
            # Buscar vendas do CRM via email matching
            emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo]['Email'].unique()
            vendas_hotmart = len(df_hotmart[df_hotmart['email'].isin(emails_criativo)])
            vendas_tmb = len(df_tmb[df_tmb['email'].isin(emails_criativo)])
            vendas_total = vendas_hotmart + vendas_tmb
            
            # Calcular valores
            valor_hotmart = df_hotmart[df_hotmart['email'].isin(emails_criativo)]['valor_num'].sum()
            valor_tmb = df_tmb[df_tmb['email'].isin(emails_criativo)]['valor_num'].sum()
            valor_total = valor_hotmart + valor_tmb
            
            # Métricas
            taxa_conv = (vendas_total / leads_reais * 100) if leads_reais > 0 else 0
            cpl = invest_excel / leads_reais if leads_reais > 0 else 0
            custo_venda = invest_excel / vendas_total if vendas_total > 0 else 0
            roas = (valor_total / invest_excel * 100) if invest_excel > 0 else 0
            
            dados.append({
                'criativo': criativo,
                'invest': invest_excel,
                'leads_excel': leads_excel,
                'leads_reais': leads_reais,
                'vendas': vendas_total,
                'vendas_hotmart': vendas_hotmart,
                'vendas_tmb': vendas_tmb,
                'valor': valor_total,
                'taxa_conv': taxa_conv,
                'cpl': cpl,
                'custo_venda': custo_venda,
                'roas': roas,
            })
        except Exception as e:
            pass

df_analise = pd.DataFrame(dados)
df_analise = df_analise.sort_values('vendas', ascending=False)

print(f"\n   ✓ Criativos processados: {len(df_analise)}")
print(f"   ✓ Investimento total: R$ {df_analise['invest'].sum():,.2f}")
print(f"   ✓ Leads (Excel): {df_analise['leads_excel'].sum():,.0f}")
print(f"   ✓ Leads (Real/CRM): {df_analise['leads_reais'].sum():,.0f}")
print(f"   ✓ VENDAS TOTAL: {int(df_analise['vendas'].sum())}")

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
                <p>Performance consolidada com dados recalculados do CRM</p>
                <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
        </div>

        <!-- RESUMO GERAL -->
        <div class="info-box">
            <h2>📈 Resumo Geral</h2>
            <div class="metric-card">
                <div class="label">Criativos</div>
                <div class="value">{len(df_analise)}</div>
            </div>
            <div class="metric-card">
                <div class="label">Investimento</div>
                <div class="value">{formatar_valor(df_analise['invest'].sum(), 'valor')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Leads</div>
                <div class="value">{formatar_valor(df_analise['leads_reais'].sum(), 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Vendas</div>
                <div class="value" style="color: #FFD700; font-weight: bold;">{int(df_analise['vendas'].sum())}</div>
            </div>
            <div class="metric-card">
                <div class="label">CPL Médio</div>
                <div class="value">{formatar_valor((df_analise['invest'].sum() / df_analise['leads_reais'].sum()) if df_analise['leads_reais'].sum() > 0 else 0, 'valor')}</div>
            </div>
            <div class="metric-card">
                <div class="label">ROAS Médio</div>
                <div class="value">{formatar_valor(df_analise['roas'].mean(), 'percentual')}</div>
            </div>
        </div>

        <!-- TOP 20 CRIATIVOS -->
        <div class="info-box">
            <h2>🏆 Top 20 Criativos por Vendas</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Investimento</th>
                        <th>Leads</th>
                        <th>CPL</th>
                        <th>Vendas</th>
                        <th>Taxa Conv</th>
                        <th>Custo/Venda</th>
                        <th>ROAS</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in df_analise.head(20).iterrows():
    criativo = str(row['criativo'])[:70]
    css_class = 'top-performer' if row['vendas'] > 0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(row['invest'], 'valor')}</td>
                        <td>{formatar_valor(row['leads_reais'], 'numero')}</td>
                        <td>{formatar_valor(row['cpl'], 'valor')}</td>
                        <td><strong>{int(row['vendas'])}</strong></td>
                        <td>{formatar_valor(row['taxa_conv'], 'percentual')}</td>
                        <td>{formatar_valor(row['custo_venda'], 'valor')}</td>
                        <td>{formatar_valor(row['roas'], 'percentual')}</td>
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
                <li><strong>🥇 Melhor Criativo:</strong> {df_analise.iloc[0]['criativo'][:60]} com <strong>{int(df_analise.iloc[0]['vendas'])} vendas</strong></li>
                <li><strong>📊 Taxa de Conversão Média:</strong> {formatar_valor(df_analise[df_analise['vendas'] > 0]['taxa_conv'].mean(), 'percentual')}</li>
                <li><strong>💰 Maior ROAS:</strong> {formatar_valor(df_analise[df_analise['roas'] > 0]['roas'].max(), 'percentual')}</li>
                <li><strong>💵 Menor CPL:</strong> {formatar_valor(df_analise[df_analise['leads_reais'] > 0]['cpl'].min(), 'valor')}</li>
                <li><strong>📈 Criativos com Vendas:</strong> {len(df_analise[df_analise['vendas'] > 0])} de {len(df_analise)} ({len(df_analise[df_analise['vendas'] > 0])/len(df_analise)*100:.1f}%)</li>
                <li><strong>🎯 Hotmart:</strong> {int(df_analise['vendas_hotmart'].sum())} vendas | <strong>TMB:</strong> {int(df_analise['vendas_tmb'].sum())} vendas</li>
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
print("✅ ANÁLISE CONCLUÍDA COM SUCESSO - VENDAS CORRIGIDAS!")
print("=" * 100)
