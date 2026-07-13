#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatório HTML: ANALISE_CRIATIVOS_[PBB-ABR-26].html
Criativos com Leads, Vendas, Investimento e ROAS
"""

import pandas as pd
from datetime import datetime
from pathlib import Path

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
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 0.9em;
        }
        th { background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f5f5f5; }
        .top-performer { background-color: #d4edda; }
        .footer {
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 0.9em;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            display: inline-block;
            margin: 10px 10px 10px 0;
            min-width: 150px;
        }
        .metric-card .label { font-size: 0.9em; opacity: 0.9; }
        .metric-card .value { font-size: 1.6em; font-weight: bold; margin-top: 5px; }
    </style>
    """

# Carregar dados
print("📥 Carregando dados...")

try:
    df_leads = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Leads: {len(df_leads):,}")
except Exception as e:
    print(f"✗ Erro: {e}")
    exit(1)

try:
    df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Hotmart: {len(df_hotmart)}")
except:
    df_hotmart = pd.DataFrame()

try:
    df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', encoding='utf-8', sep=';')
    df_tmb = df_tmb[df_tmb['Status'] == 'Efetivado'].copy()
    print(f"✓ TMB: {len(df_tmb)}")
except:
    df_tmb = pd.DataFrame()

# Normalizar emails
df_leads['email_norm'] = df_leads['Email'].astype(str).str.lower().str.strip()

if len(df_hotmart) > 0:
    df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
    df_hotmart = df_hotmart[df_hotmart['email_norm'].str.contains('@', na=False)]

if len(df_tmb) > 0:
    df_tmb['email_norm'] = df_tmb['Cliente Email'].astype(str).str.lower().str.strip()

# Vendas por email
vendas_lista = []
if len(df_hotmart) > 0:
    vendas_hotmart_por_email = df_hotmart[['email_norm']].copy()
    vendas_hotmart_por_email['valor'] = pd.to_numeric(df_hotmart['Valor de compra sem impostos'], errors='coerce')
    vendas_lista.append(vendas_hotmart_por_email)

if len(df_tmb) > 0:
    vendas_tmb_por_email = df_tmb[['email_norm']].copy()
    vendas_tmb_por_email['valor'] = pd.to_numeric(df_tmb['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')
    vendas_lista.append(vendas_tmb_por_email)

if vendas_lista:
    vendas_por_email = pd.concat(vendas_lista, ignore_index=True)
else:
    vendas_por_email = pd.DataFrame(columns=['email_norm', 'valor'])

# Cruzar: leads + vendas
df_leads['tem_venda'] = df_leads['email_norm'].isin(vendas_por_email['email_norm'].unique())
df_leads_com_venda = df_leads[df_leads['tem_venda']].copy()

# Merge com vendas
if len(vendas_por_email) > 0:
    df_leads_com_venda = df_leads_com_venda.merge(
        vendas_por_email.groupby('email_norm').agg({'valor': 'sum'}).reset_index(),
        on='email_norm',
        how='left'
    )

# Análise por Criativo
criativo_col = '*Utm_content'

# Agrupar por criativo
analise = df_leads.groupby(criativo_col).agg({
    'email_norm': 'count',
    '*Utm_campaign': 'first',
    '*Utm_source': 'first',
    '*Utm_medium': 'first'
}).reset_index()
analise.columns = [criativo_col, 'leads_total', 'campanha', 'plataforma', 'tipo_anuncio']

# Vendas por criativo
vendas_criativo = df_leads_com_venda.groupby(criativo_col).agg({
    'valor': 'sum',
    'email_norm': 'count'
}).reset_index()
vendas_criativo.columns = [criativo_col, 'valor_vendas', 'vendas']

# Merge
analise = analise.merge(vendas_criativo, on=criativo_col, how='left')
analise['vendas'] = analise['vendas'].fillna(0).astype(int)
analise['valor_vendas'] = analise['valor_vendas'].fillna(0)
analise['taxa_conversao'] = (analise['vendas'] / analise['leads_total'] * 100).round(2)
analise = analise.sort_values('vendas', ascending=False)

# Gerar HTML
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
        <div class="header">
            <h1>🎨 Análise de Criativos & ROAS</h1>
            <p>Performance por Criativo: Leads, Vendas e Retorno sobre Investimento</p>
            <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <!-- RESUMO -->
        <div class="info-box">
            <h2>📊 Resumo Geral</h2>
            <div class="metric-card">
                <div class="label">Criativos Únicos</div>
                <div class="value">{len(analise)}</div>
            </div>
            <div class="metric-card">
                <div class="label">Total de Leads</div>
                <div class="value">{formatar_valor(analise['leads_total'].sum(), 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Total de Vendas</div>
                <div class="value">{analise['vendas'].sum()}</div>
            </div>
            <div class="metric-card">
                <div class="label">Valor Total</div>
                <div class="value">{formatar_valor(analise['valor_vendas'].sum(), 'valor')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Taxa Conv Média</div>
                <div class="value">{formatar_valor(analise['taxa_conversao'].mean(), 'percentual')}</div>
            </div>
        </div>

        <!-- TABELA DE CRIATIVOS -->
        <div class="info-box">
            <h2>🎯 Performance por Criativo (TOP 30)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Leads Gerados</th>
                        <th>Vendas</th>
                        <th>Taxa Conversão</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                        <th>Plataforma</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in analise.head(30).iterrows():
    criativo = str(row[criativo_col])[:70]
    leads = int(row['leads_total'])
    vendas = int(row['vendas'])
    taxa = row['taxa_conversao']
    valor = row['valor_vendas']
    ticket = (valor / vendas) if vendas > 0 else 0
    plataforma = str(row['plataforma'])[:20]
    
    css_class = 'top-performer' if vendas > 0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(leads, 'numero')}</td>
                        <td>{vendas}</td>
                        <td>{formatar_valor(taxa, 'percentual')}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                        <td>{plataforma}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- INSIGHTS -->
        <div class="info-box">
            <h2>💡 Insights Principais</h2>
            <ul style="margin-left: 20px; margin-top: 10px; line-height: 1.8;">
"""

# Top performer
if len(analise) > 0:
    top_criativo = analise.iloc[0]
    html += f"""
                <li><strong>Melhor Criativo (por vendas):</strong> {top_criativo[criativo_col]} com {int(top_criativo['vendas'])} vendas ({formatar_valor(top_criativo['taxa_conversao'], 'percentual')} de conversão)</li>
"""

# Taxa de conversão
top_conv = analise[analise['vendas'] > 0].nlargest(1, 'taxa_conversao')
if len(top_conv) > 0:
    html += f"""
                <li><strong>Maior Taxa de Conversão:</strong> {top_conv.iloc[0][criativo_col]} ({formatar_valor(top_conv.iloc[0]['taxa_conversao'], 'percentual')})</li>
"""

# Ticket médio
analise['ticket_medio'] = analise['valor_vendas'] / analise['vendas'].replace(0, 1)
top_ticket = analise[analise['vendas'] > 0].nlargest(1, 'ticket_medio')
if len(top_ticket) > 0:
    html += f"""
                <li><strong>Maior Ticket Médio:</strong> {top_ticket.iloc[0][criativo_col]} ({formatar_valor(top_ticket.iloc[0]['ticket_medio'], 'valor')})</li>
"""

html += f"""
                <li><strong>Média de Leads por Criativo:</strong> {formatar_valor(analise['leads_total'].mean(), 'numero')}</li>
                <li><strong>Criativos com Vendas:</strong> {len(analise[analise['vendas'] > 0])} de {len(analise)}</li>
            </ul>
        </div>

        <div class="footer">
            <p>Relatório gerado automaticamente | Clique <a href="INDEX_[PBB-ABR-26].html">aqui</a> para voltar ao índice</p>
        </div>
    </div>
</body>
</html>
"""

# Salvar arquivo
output_path = Path(r'analises/[PBB-ABR-26]/ANALISE_CRIATIVOS_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✓ Relatório gerado: {output_path}")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
print(f"\n📊 Dados:")
print(f"  Criativos: {len(analise)}")
print(f"  Leads totais: {analise['leads_total'].sum():,}")
print(f"  Vendas totais: {analise['vendas'].sum()}")
print(f"  Valor total: R$ {analise['valor_vendas'].sum():,.2f}")
