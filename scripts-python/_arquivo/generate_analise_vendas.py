#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatório HTML: ANALISE_VENDAS_[PBB-FEV-26].html
Cruzamento de Leads x Vendas com ROAS
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

def limpar_numero(valor):
    """Converte string com formato português (1.234,56) para float"""
    if pd.isna(valor) or valor == '':
        return 0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    valor = str(valor).strip()
    if not valor or valor == 'nan':
        return 0
    
    # Remover símbolos
    valor = valor.replace('R$', '').replace(' ', '').strip()
    # Converter formato português
    valor = valor.replace('.', '').replace(',', '.')
    try:
        return float(valor)
    except:
        return 0

def formatar_valor(valor, tipo='valor'):
    """Formata número conforme tipo"""
    try:
        if tipo == 'valor':
            return f"R$ {valor:,.2f}".replace(',', 'COMMA').replace('.', ',').replace('COMMA', '.')
        elif tipo == 'percentual':
            return f"{valor:.2f}%"
        elif tipo == 'numero':
            return f"{int(valor):,}".replace(',', '.')
        else:
            return str(valor)
    except:
        return str(valor)

def get_css_base():
    """Retorna CSS base para todos os relatórios"""
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
        .header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { color: #667eea; margin-bottom: 10px; font-size: 2.5em; }
        .header p { color: #666; font-size: 1.1em; }
        .info-box {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .info-box h2 { color: #667eea; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid #667eea; padding-bottom: 10px; }
        .info-box h3 { color: #764ba2; margin-top: 20px; margin-bottom: 10px; font-size: 1.3em; }
        .metric-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-card .label { font-size: 0.9em; opacity: 0.9; margin-bottom: 5px; }
        .metric-card .value { font-size: 1.8em; font-weight: bold; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th { background-color: #667eea; color: white; padding: 15px; text-align: left; font-weight: 600; }
        td { padding: 12px 15px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f5f5f5; }
        .top-performer { background-color: #d4edda; font-weight: bold; }
        .footer {
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 0.9em;
        }
        .chart-container { margin: 20px 0; }
    </style>
    """

# Carregar dados
print("📥 Carregando dados...")
df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')
df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')

# Normalizar emails
df_leads['email_normalizado'] = df_leads['Email'].astype(str).str.lower().str.strip()
df_hotmart['email_normalizado'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
df_hotmart = df_hotmart[df_hotmart['email_normalizado'] != 'nan']
df_hotmart = df_hotmart[df_hotmart['email_normalizado'].str.contains('@', na=False)]

# Encontrar vendas
emails_com_venda = set(df_hotmart['email_normalizado'].unique())
df_leads['tem_venda'] = df_leads['email_normalizado'].isin(emails_com_venda)

# Cruzar informações
leads_com_venda = df_leads[df_leads['tem_venda']].copy()
leads_com_venda = leads_com_venda.merge(
    df_hotmart[['email_normalizado', 'Valor de compra sem impostos', 'Data da transação', 'Produto']],
    on='email_normalizado',
    how='left'
)

# Converter valor
valor_col = leads_com_venda['Valor de compra sem impostos']
valor_col_str = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
leads_com_venda['valor_venda'] = pd.to_numeric(valor_col_str, errors='coerce')

# Calcular métricas
total_leads = len(df_leads)
total_vendas = len(leads_com_venda)
taxa_conversao = (total_vendas / total_leads * 100) if total_leads > 0 else 0
valor_total = leads_com_venda['valor_venda'].sum()
ticket_medio = leads_com_venda['valor_venda'].mean() if total_vendas > 0 else 0

# Análise por campanha
campanha_col = '*Utm_campaign'
campanha_stats = leads_com_venda.groupby(campanha_col).agg({
    'valor_venda': ['count', 'sum', 'mean'],
    'email_normalizado': 'count'
}).round(2)
campanha_stats.columns = ['vendas', 'valor_total', 'ticket_medio', 'total_linhas']
campanha_stats = campanha_stats.sort_values('valor_total', ascending=False)

# Análise por fonte/plataforma
source_col = '*Utm_source'
total_leads_source = df_leads.groupby(source_col).size()
vendas_source = leads_com_venda.groupby(source_col).agg({
    'valor_venda': ['count', 'sum', 'mean']
})

# Análise por médium
medium_col = '*Utm_medium'
total_leads_medium = df_leads.groupby(medium_col).size()
vendas_medium = leads_com_venda.groupby(medium_col).agg({
    'valor_venda': ['count', 'sum', 'mean']
})

# Gerar HTML
html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Vendas - PBB-FEV-26</title>
    {get_css_base()}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Análise de Vendas & ROAS</h1>
            <p>Cruzamento: Active Campaign Leads × Hotmart Sales | PBB-FEV-26</p>
            <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <!-- MÉTRICAS PRINCIPAIS -->
        <div class="info-box">
            <h2>📈 Métricas Principais</h2>
            <div class="metric-row">
                <div class="metric-card">
                    <div class="label">Total de Leads</div>
                    <div class="value">{formatar_valor(total_leads, 'numero')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Vendas Geradas</div>
                    <div class="value">{total_vendas}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Taxa de Conversão</div>
                    <div class="value">{formatar_valor(taxa_conversao, 'percentual')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Valor Total em Vendas</div>
                    <div class="value">{formatar_valor(valor_total, 'valor')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Ticket Médio</div>
                    <div class="value">{formatar_valor(ticket_medio, 'valor')}</div>
                </div>
            </div>
        </div>

        <!-- ANÁLISE POR CAMPANHA -->
        <div class="info-box">
            <h2>🎯 Desempenho por Campanha</h2>
            <table>
                <thead>
                    <tr>
                        <th>Campanha</th>
                        <th>Leads com Venda</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                    </tr>
                </thead>
                <tbody>
"""

for campanha, row in campanha_stats.iterrows():
    vendas = int(row['vendas'])
    valor = row['valor_total']
    ticket = row['ticket_medio']
    
    html += f"""
                    <tr>
                        <td><strong>{campanha}</strong></td>
                        <td>{vendas}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- ANÁLISE POR FONTE (UTM_SOURCE) -->
        <div class="info-box">
            <h2>📱 Desempenho por Plataforma</h2>
            <table>
                <thead>
                    <tr>
                        <th>Plataforma</th>
                        <th>Leads Totais</th>
                        <th>Vendas</th>
                        <th>Taxa Conversão</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                    </tr>
                </thead>
                <tbody>
"""

# Construir dados por fonte
sources = [s for s in df_leads[source_col].unique() if not pd.isna(s)]
for source in sorted(sources):
    
    total = total_leads_source.get(source, 0)
    
    if source in vendas_source.index:
        vendas = int(vendas_source.loc[source, ('valor_venda', 'count')])
        valor = vendas_source.loc[source, ('valor_venda', 'sum')]
        ticket = vendas_source.loc[source, ('valor_venda', 'mean')]
    else:
        vendas = 0
        valor = 0
        ticket = 0
    
    taxa = (vendas / total * 100) if total > 0 else 0
    
    css_class = 'top-performer' if taxa > 1.0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{source}</strong></td>
                        <td>{formatar_valor(total, 'numero')}</td>
                        <td>{vendas}</td>
                        <td>{formatar_valor(taxa, 'percentual')}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- ANÁLISE POR TIPO DE ANÚNCIO (UTM_MEDIUM) -->
        <div class="info-box">
            <h2>📹 Desempenho por Tipo de Anúncio</h2>
            <table>
                <thead>
                    <tr>
                        <th>Tipo de Anúncio</th>
                        <th>Leads Totais</th>
                        <th>Vendas</th>
                        <th>Taxa Conversão</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                    </tr>
                </thead>
                <tbody>
"""

# Construir dados por médium
mediums = [m for m in df_leads[medium_col].unique() if not pd.isna(m)]
for medium in sorted(mediums):
    
    total = total_leads_medium.get(medium, 0)
    
    if medium in vendas_medium.index:
        vendas = int(vendas_medium.loc[medium, ('valor_venda', 'count')])
        valor = vendas_medium.loc[medium, ('valor_venda', 'sum')]
        ticket = vendas_medium.loc[medium, ('valor_venda', 'mean')]
    else:
        vendas = 0
        valor = 0
        ticket = 0
    
    taxa = (vendas / total * 100) if total > 0 else 0
    
    css_class = 'top-performer' if taxa > 1.0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{medium}</strong></td>
                        <td>{formatar_valor(total, 'numero')}</td>
                        <td>{vendas}</td>
                        <td>{formatar_valor(taxa, 'percentual')}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- INSIGHTS -->
        <div class="info-box">
            <h2>💡 Insights & Recomendações</h2>
            <h3>🔍 Descobertas Principais</h3>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li><strong>Taxa de Conversão Geral:</strong> {:.2f}% dos leads se converteram em vendas</li>
                <li><strong>Valor Gerado:</strong> R$ {:.2f} em receita total</li>
                <li><strong>Ticket Médio:</strong> R$ {:.2f} por cliente</li>
                <li><strong>Campanha Principal:</strong> {} com as maiores vendas e receita</li>
            </ul>
        </div>

        <div class="footer">
            <p>Relatório gerado automaticamente | Clique <a href="INDEX_[PBB-FEV-26].html">aqui</a> para voltar ao índice</p>
        </div>
    </div>
</body>
</html>
""".format(
    taxa_conversao,
    valor_total,
    ticket_medio,
    campanha_stats.index[0] if len(campanha_stats) > 0 else 'N/A'
)

# Salvar arquivo
output_path = Path(r'analises/[PBB-FEV-26]/ANALISE_VENDAS_[PBB-FEV-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✓ Relatório gerado: {output_path}")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
