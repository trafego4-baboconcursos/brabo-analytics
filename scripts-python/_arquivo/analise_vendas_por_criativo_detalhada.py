#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VENDAS POR CRIATIVO
Associa leads do Active Campaign com vendas usando UTMs
Analisa performance por utm_content (criativo)
"""

import pandas as pd
import glob
from datetime import datetime
from pathlib import Path
import csv

print("=" * 120)
print("ANALISE: VENDAS POR CRIATIVO (UTM_CONTENT)")
print("=" * 120)

# ===== CARREGAR DADOS =====
print("\n1. Carregando dados...")

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

# Leads do Active Campaign
leads_file = encontrar_csv_leads_abr()
df_crm = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)

# Normalizar emails do CRM
df_crm['email_norm'] = df_crm['Email'].astype(str).str.strip().str.lower()

# Vendas Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
# Valores já estão em reais
df_hotmart['valor_num'] = df_hotmart['Faturamento bruto (sem impostos)']
df_hotmart['plataforma'] = 'Hotmart'

# Vendas TMB
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
# NÃO FILTRAR - usar TODAS as 183 vendas
df_tmb['email_norm'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
# Valores já estão em reais
df_tmb['valor_num'] = df_tmb['Ticket do pedido']
df_tmb['plataforma'] = 'TMB'

print(f"   Active Campaign: {len(df_crm):,} leads ({leads_file.name})")
print(f"   Hotmart: {len(df_hotmart):,} vendas")
print(f"   TMB: {len(df_tmb):,} vendas")

# ===== MATCH EMAILS =====
print("\n2. Associando vendas com leads...")

# Combinar vendas
df_vendas = pd.concat([
    df_hotmart[['email_norm', 'valor_num', 'plataforma']],
    df_tmb[['email_norm', 'valor_num', 'plataforma']]
], ignore_index=True)

# Merge com CRM
df_merged = df_vendas.merge(
    df_crm[['email_norm', '*Utm_content', '*Utm_campaign', '*Utm_source', '*Utm_medium']],
    on='email_norm',
    how='left'
)

vendas_com_utm = df_merged[df_merged['*Utm_content'].notna()]
vendas_sem_utm = df_merged[df_merged['*Utm_content'].isna()]
vendas_sem_utm_count = len(vendas_sem_utm)
vendas_sem_utm_valor = vendas_sem_utm['valor_num'].sum()

print(f"   Vendas com UTM (rastreadas): {len(vendas_com_utm):,} = R$ {vendas_com_utm['valor_num'].sum():,.2f}")
print(f"   Vendas SEM UTM (nao rastreadas): {vendas_sem_utm_count:,} = R$ {vendas_sem_utm_valor:,.2f}")
print(f"   Taxa de rastreamento: {(len(vendas_com_utm)/len(df_vendas)*100):.1f}%")

# ===== AGRUPAR POR CRIATIVO =====
print("\n3. Agrupando por criativo (utm_content)...")

# Apenas vendas rastreadas
df_vendas_utm = df_merged[df_merged['*Utm_content'].notna()].copy()

# Agrupar por criativo
criativos = df_vendas_utm.groupby('*Utm_content').agg({
    'valor_num': ['count', 'sum', 'mean'],
    'plataforma': lambda x: list(x.value_counts().index)
}).reset_index()

criativos.columns = ['Criativo', 'Vendas', 'Valor_Total', 'Ticket_Medio', 'Plataformas']
criativos = criativos.sort_values('Vendas', ascending=False)

# Adicionar info de leads
leads_por_criativo = df_crm[df_crm['*Utm_content'].notna()].groupby('*Utm_content').size().reset_index(name='Leads')
criativos = criativos.merge(leads_por_criativo, left_on='Criativo', right_on='*Utm_content', how='left')
criativos.drop('*Utm_content', axis=1, inplace=True)

criativos['Taxa_Conversao'] = (criativos['Vendas'] / criativos['Leads'] * 100)
criativos = criativos.sort_values('Vendas', ascending=False)

print("\n4. TOP 20 CRIATIVOS POR VENDAS:")
print("-" * 120)
print(f"{'Rank':<5} {'Criativo':<40} {'Leads':<10} {'Vendas':<10} {'Conv%':<8} {'Ticket':<15} {'Total Vendido':<18}")
print("-" * 120)

for idx, row in criativos.head(20).iterrows():
    rank = list(criativos.head(20).index).index(idx) + 1
    print(f"{rank:<5} {row['Criativo']:<40} {row['Leads']:<10,.0f} {row['Vendas']:<10,.0f} "
          f"{row['Taxa_Conversao']:<8.2f}% R$ {row['Ticket_Medio']:<13,.2f} R$ {row['Valor_Total']:<16,.2f}")

# ===== ESTATISTICAS GERAIS =====
print("\n5. ESTATISTICAS GERAIS:")
print("-" * 120)
print(f"   Total de Criativos: {len(criativos)}")
print(f"   Total de Leads (com criativo): {criativos['Leads'].sum():,.0f}")
print(f"   Total de Vendas (rastreadas por criativo): {criativos['Vendas'].sum():,.0f}")
print(f"   Valor Vendido (rastreado): R$ {criativos['Valor_Total'].sum():,.2f}")
print(f"   Vendas SEM UTM: {vendas_sem_utm_count:,.0f}")
print(f"   Valor Vendido (SEM UTM): R$ {vendas_sem_utm_valor:,.2f}")
print(f"   ──────────────────────────────────────────")
print(f"   TOTAL DE VENDAS: {criativos['Vendas'].sum() + vendas_sem_utm_count:,.0f}")
print(f"   TOTAL GERAL: R$ {criativos['Valor_Total'].sum() + vendas_sem_utm_valor:,.2f}")
print(f"   ──────────────────────────────────────────")
print(f"   Ticket Medio Geral: R$ {(criativos['Valor_Total'].sum() + vendas_sem_utm_valor) / (criativos['Vendas'].sum() + vendas_sem_utm_count):,.2f}")
print(f"   Taxa de Conversao Media (rastreadas): {criativos['Taxa_Conversao'].mean():.2f}%")
print(f"   Taxa de Conversao Mediana (rastreadas): {criativos['Taxa_Conversao'].median():.2f}%")

# ===== BEST & WORST PERFORMERS =====
print("\n6. PERFORMANCE EXTREMOS:")
print("-" * 120)

best_3 = criativos.nlargest(3, 'Vendas')
worst_3 = criativos.nsmallest(3, 'Vendas')

print("\n   🏆 TOP 3 MELHORES PERFORMERS:")
for idx, (_, row) in enumerate(best_3.iterrows(), 1):
    print(f"      {idx}. {row['Criativo']}: {row['Vendas']:.0f} vendas "
          f"(Taxa: {row['Taxa_Conversao']:.2f}% | Ticket: R$ {row['Ticket_Medio']:,.2f})")

print("\n   ❌ TOP 3 PIORES PERFORMERS (COM LEADS):")
worst_com_leads = criativos[criativos['Leads'] > 50].nsmallest(3, 'Taxa_Conversao')
for idx, (_, row) in enumerate(worst_com_leads.iterrows(), 1):
    print(f"      {idx}. {row['Criativo']}: {row['Vendas']:.0f} vendas de {row['Leads']:.0f} leads "
          f"(Taxa: {row['Taxa_Conversao']:.2f}%)")

# ===== EXPORTAR DADOS DETALHADOS =====
print("\n7. Exportando dados detalhados...")

# Criar relatório HTML
html_content = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vendas por Criativo - PBB-ABR-26</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #2196F3;
            padding-bottom: 10px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-box {{
            background: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #2196F3;
            border-radius: 4px;
        }}
        .stat-box strong {{
            display: block;
            color: #666;
            font-size: 12px;
            margin-bottom: 5px;
        }}
        .stat-box .value {{
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background: #2196F3;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .rank-1 {{ background: #fff3cd !important; font-weight: bold; }}
        .rank-2 {{ background: #fff8e1 !important; }}
        .rank-3 {{ background: #fffbee !important; }}
        .high {{ color: #4caf50; font-weight: bold; }}
        .low {{ color: #f44336; font-weight: bold; }}
        .medium {{ color: #ff9800; }}
        .text-right {{ text-align: right; }}
        .currency {{ font-family: 'Courier New', monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; align-items: center; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #eee;">
            <a href="INDEX_[PBB-ABR-26].html" style="margin-right: 20px;">
                <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos" style="max-width: 100px; height: auto;">
            </a>
            <div>
                <h1>📊 Vendas por Criativo - PBB-ABR-26</h1>
                <p><em>Análise gerada em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</em></p>
            </div>
        </div>
        
        <h2>📈 Estatísticas Gerais</h2>
        <div class="stats">
            <div class="stat-box">
                <strong>Total de Criativos</strong>
                <div class="value">{len(criativos)}</div>
            </div>
            <div class="stat-box">
                <strong>Total de Leads</strong>
                <div class="value">{criativos['Leads'].sum():,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>Total de Vendas (Rastreadas)</strong>
                <div class="value">{criativos['Vendas'].sum():,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>Vendas NÃO Rastreadas</strong>
                <div class="value">{vendas_sem_utm_count:,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>TOTAL DE VENDAS</strong>
                <div class="value">{criativos['Vendas'].sum() + vendas_sem_utm_count:,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>Valor Rastreado</strong>
                <div class="value">R$ {criativos['Valor_Total'].sum():,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>Valor NÃO Rastreado</strong>
                <div class="value">R$ {vendas_sem_utm_valor:,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>💰 TOTAL GERAL</strong>
                <div class="value">R$ {criativos['Valor_Total'].sum() + vendas_sem_utm_valor:,.0f}</div>
            </div>
            <div class="stat-box">
                <strong>Taxa Média de Conversão</strong>
                <div class="value">{criativos['Taxa_Conversao'].mean():.2f}%</div>
            </div>
            <div class="stat-box">
                <strong>Ticket Médio</strong>
                <div class="value">R$ {(criativos['Valor_Total'].sum() + vendas_sem_utm_valor) / (criativos['Vendas'].sum() + vendas_sem_utm_count):,.0f}</div>
            </div>
        </div>
        
        <h2>🎯 Performance de Criativos</h2>
        <table>
            <thead>
                <tr>
                    <th>Posição</th>
                    <th>Criativo (utm_content)</th>
                    <th class="text-right">Leads</th>
                    <th class="text-right">Vendas</th>
                    <th class="text-right">Taxa Conv.</th>
                    <th class="text-right">Ticket Médio</th>
                    <th class="text-right">Total Vendido</th>
                </tr>
            </thead>
            <tbody>
"""

for idx, (_, row) in enumerate(criativos.iterrows(), 1):
    rank_class = ""
    if idx <= 3:
        rank_class = f"rank-{idx}"
    
    conv_class = "high" if row['Taxa_Conversao'] > 1 else ("low" if row['Taxa_Conversao'] < 0.5 else "medium")
    
    html_content += f"""
                <tr class="{rank_class}">
                    <td><strong>{idx}</strong></td>
                    <td>{row['Criativo']}</td>
                    <td class="text-right">{row['Leads']:,.0f}</td>
                    <td class="text-right"><strong>{row['Vendas']:,.0f}</strong></td>
                    <td class="text-right"><span class="{conv_class}">{row['Taxa_Conversao']:.2f}%</span></td>
                    <td class="text-right currency">R$ {row['Ticket_Medio']:,.2f}</td>
                    <td class="text-right currency">R$ {row['Valor_Total']:,.2f}</td>
                </tr>
"""

# Adicionar linha "Não Rastreado"
# Adicionar linha "Não Rastreado"
html_content += f"""
                <tr style="background: #f0f0f0 !important; font-weight: bold; border-top: 2px solid #999;">
                    <td><strong>-</strong></td>
                    <td><strong>⚠️ NÃO RASTREADO (sem UTM)</strong></td>
                    <td class="text-right">-</td>
                    <td class="text-right"><strong>{vendas_sem_utm_count:,.0f}</strong></td>
                    <td class="text-right">-</td>
                    <td class="text-right currency">R$ {vendas_sem_utm_valor / vendas_sem_utm_count:,.2f}</td>
                    <td class="text-right currency">R$ {vendas_sem_utm_valor:,.2f}</td>
                </tr>
                <tr style="background: #e3f2fd !important; font-weight: bold; border-top: 2px solid #2196F3;">
                    <td colspan="2"><strong>TOTAL GERAL</strong></td>
                    <td class="text-right"><strong>{criativos['Leads'].sum():,.0f}</strong></td>
                    <td class="text-right"><strong>{criativos['Vendas'].sum() + vendas_sem_utm_count:,.0f}</strong></td>
                    <td class="text-right"><strong>{((criativos['Vendas'].sum() + vendas_sem_utm_count) / criativos['Leads'].sum() * 100):.2f}%</strong></td>
                    <td class="text-right currency"><strong>R$ {(criativos['Valor_Total'].sum() + vendas_sem_utm_valor) / (criativos['Vendas'].sum() + vendas_sem_utm_count):,.2f}</strong></td>
                    <td class="text-right currency"><strong>R$ {criativos['Valor_Total'].sum() + vendas_sem_utm_valor:,.2f}</strong></td>
                </tr>
            </tbody>
        </table>
        
        <h2>💡 Insights e Recomendações</h2>
        <ul>
"""

# Gerar insights
best = criativos.iloc[0]
worst_valid = criativos[criativos['Leads'] > 50].iloc[-1] if len(criativos[criativos['Leads'] > 50]) > 0 else None

html_content += f"""
            <li><strong>🏆 Top Performer:</strong> {best['Criativo']} com {best['Vendas']:.0f} vendas 
                (Taxa: {best['Taxa_Conversao']:.2f}%) - <strong>Replicar estratégia!</strong></li>
"""

if worst_valid is not None:
    html_content += f"""
            <li><strong>⚠️ Baixo Performance:</strong> {worst_valid['Criativo']} com taxa de {worst_valid['Taxa_Conversao']:.2f}% 
                e {worst_valid['Leads']:.0f} leads - <strong>Revisar ou pausar</strong></li>
"""

html_content += f"""
            <li><strong>📊 Taxa Média:</strong> {criativos['Taxa_Conversao'].mean():.2f}% - 
                Criativos acima dessa média estão com boa performance</li>
            <li><strong>💰 Ticket Médio:</strong> R$ {criativos['Ticket_Medio'].mean():,.2f} - 
                Varia bastante por criativo</li>
            <li><strong>⚠️ Vendas não rastreadas:</strong> {vendas_sem_utm_count:,.0f} vendas (R$ {vendas_sem_utm_valor:,.2f}) sem UTM atribuído</li>
        </ul>
    </div>
    <div style="text-align: center; padding: 20px; margin-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px;">
        <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
        <p><a href="INDEX_[PBB-ABR-26].html" style="color: #2196F3; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
    </div>
</body>
</html>
"""

# Salvar HTML
output_path = r'analises/[PBB-ABR-26]/VENDAS_POR_CRIATIVO_[PBB-ABR-26].html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"   ✓ Relatório salvo: {output_path}")

# Salvar CSV com dados completos
csv_path = r'analises/[PBB-ABR-26]/VENDAS_POR_CRIATIVO_[PBB-ABR-26].csv'
criativos_export = criativos.copy()
criativos_export['Valor_Total'] = criativos_export['Valor_Total'].apply(lambda x: f"R$ {x:,.2f}")
criativos_export['Ticket_Medio'] = criativos_export['Ticket_Medio'].apply(lambda x: f"R$ {x:,.2f}")
criativos_export['Taxa_Conversao'] = criativos_export['Taxa_Conversao'].apply(lambda x: f"{x:.2f}%")
criativos_export.to_csv(csv_path, index=False, encoding='utf-8', sep=';')

print(f"   ✓ Dados exportados: {csv_path}")

print("\n" + "=" * 120)
print("✅ Análise concluída com sucesso!")
print("=" * 120)
