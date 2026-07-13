#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatório HTML: ANALISE_VENDAS_[PBB-ABR-26].html
Análise de leads vs vendas com atribuição por UTM
"""

import pandas as pd
from datetime import datetime
from pathlib import Path

def limpar_numero(valor):
    """Converte string em formato português (1.234,56) para float"""
    if pd.isna(valor):
        return 0
    valor = str(valor).strip()
    valor = valor.replace('.', '')  # Remove separador de milhares
    valor = valor.replace(',', '.')  # Substitui vírgula por ponto
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
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th { background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f5f5f5; }
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
        .warning-box {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .footer {
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 0.9em;
        }
    </style>
    """

# Carregar dados
print("📥 Carregando dados de abril...")

try:
    df_leads = pd.read_csv(r'analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Leads: {len(df_leads):,}")
except Exception as e:
    print(f"✗ Erro ao carregar leads: {e}")
    exit(1)

try:
    df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', encoding='utf-8', sep=';')
    print(f"✓ Hotmart: {len(df_hotmart):,}")
except Exception as e:
    print(f"✗ Erro ao carregar Hotmart: {e}")
    df_hotmart = pd.DataFrame()

try:
    df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', encoding='utf-8', sep=';')
    df_tmb = df_tmb[df_tmb['Status'] == 'Efetivado'].copy()
    print(f"✓ TMB (Efetivado): {len(df_tmb):,}")
except Exception as e:
    print(f"✗ Erro ao carregar TMB: {e}")
    df_tmb = pd.DataFrame()

# Normalizar emails
df_leads['email_norm'] = df_leads['Email'].astype(str).str.lower().str.strip()

if len(df_hotmart) > 0:
    df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
    df_hotmart = df_hotmart[df_hotmart['email_norm'].str.contains('@', na=False)]

if len(df_tmb) > 0:
    df_tmb['email_norm'] = df_tmb['Cliente Email'].astype(str).str.lower().str.strip()

# Combinar vendas
vendas_lista = []

if len(df_hotmart) > 0:
    vendas_hotmart = df_hotmart[['email_norm']].copy()
    vendas_hotmart['valor'] = pd.to_numeric(df_hotmart['Valor de compra sem impostos'], errors='coerce')
    vendas_hotmart['fonte'] = 'Hotmart'
    vendas_hotmart['*Utm_campaign'] = 'pbb-abr-26'
    vendas_lista.append(vendas_hotmart)

if len(df_tmb) > 0:
    vendas_tmb = df_tmb[['email_norm']].copy()
    vendas_tmb['valor'] = pd.to_numeric(df_tmb['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')
    vendas_tmb['fonte'] = 'TMB'
    # Tentar extrair campanha
    vendas_tmb['*Utm_campaign'] = 'pbb-abr-26'
    vendas_lista.append(vendas_tmb)

if vendas_lista:
    vendas_por_email = pd.concat(vendas_lista, ignore_index=True)
else:
    vendas_por_email = pd.DataFrame(columns=['email_norm', 'valor', 'fonte'])

# Análise de leads com venda
df_leads['tem_venda'] = df_leads['email_norm'].isin(vendas_por_email['email_norm'].unique())
total_leads = len(df_leads)
leads_com_venda = df_leads[df_leads['tem_venda']].copy()
total_com_venda = len(leads_com_venda)

# Merge com vendas para valores
vendas_agrupadas = vendas_por_email.groupby('email_norm').agg({'valor': 'sum', 'fonte': 'first', '*Utm_campaign': 'first'}).reset_index()

df_leads_venda = df_leads[df_leads['tem_venda']].merge(
    vendas_agrupadas,
    on='email_norm',
    how='left'
)

# Totais
total_vendas = len(vendas_agrupadas)
total_valor = vendas_agrupadas['valor'].sum()
taxa_conversao = (total_com_venda / total_leads * 100) if total_leads > 0 else 0
ticket_medio = (total_valor / total_vendas) if total_vendas > 0 else 0

# Por campanha
vendas_por_campanha = vendas_por_email.groupby('*Utm_campaign').agg({
    'email_norm': 'count',
    'valor': 'sum',
    'fonte': lambda x: ', '.join(x.unique())
}).reset_index()
vendas_por_campanha.columns = ['Campanha', 'Transações', 'Valor Total', 'Plataformas']

# Por método de pagamento
vendas_por_fonte = vendas_por_email.groupby('fonte').agg({
    'email_norm': 'count',
    'valor': 'sum'
}).reset_index()
vendas_por_fonte.columns = ['Método', 'Transações', 'Valor Total']

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
        <div class="header">
            <h1>💰 Análise de Vendas - PBB-ABR-26</h1>
            <p>Cruzamento de Leads com Vendas Reais (Hotmart + TMB)</p>
            <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <!-- RESUMO GERAL -->
        <div class="info-box">
            <h2>📊 Resumo Geral</h2>
            <div class="metric-card">
                <div class="label">Total de Leads</div>
                <div class="value">{formatar_valor(total_leads, 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Transações</div>
                <div class="value">{total_vendas}</div>
            </div>
            <div class="metric-card">
                <div class="label">Taxa Conversão</div>
                <div class="value">{formatar_valor(taxa_conversao, 'percentual')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Valor Total</div>
                <div class="value">{formatar_valor(total_valor, 'valor')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Ticket Médio</div>
                <div class="value">{formatar_valor(ticket_medio, 'valor')}</div>
            </div>
        </div>

        <!-- AVISO -->
        <div class="warning-box">
            <strong>⚠️ Importante:</strong> Este relatório inclui todas as transações com email correspondente na base de leads.
            {total_vendas - total_com_venda} transações podem não ter sido mapeadas corretamente.
        </div>

        <!-- MÉTODO DE PAGAMENTO -->
        <div class="info-box">
            <h2>💳 Breakdown por Método de Pagamento</h2>
            <table>
                <thead>
                    <tr>
                        <th>Método</th>
                        <th>Transações</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in vendas_por_fonte.iterrows():
    metodo = row['Método']
    trans = int(row['Transações'])
    valor = row['Valor Total']
    ticket = valor / trans if trans > 0 else 0
    
    html += f"""
                    <tr>
                        <td><strong>{metodo}</strong></td>
                        <td>{trans}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- PERFORMANCE POR CAMPANHA -->
        <div class="info-box">
            <h2>🎯 Performance por Campanha UTM</h2>
            <table>
                <thead>
                    <tr>
                        <th>Campanha</th>
                        <th>Transações</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                        <th>Plataformas</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in vendas_por_campanha.iterrows():
    campanha = str(row['Campanha'])[:50]
    trans = int(row['Transações'])
    valor = row['Valor Total']
    ticket = valor / trans if trans > 0 else 0
    plataformas = row['Plataformas']
    
    html += f"""
                    <tr>
                        <td><strong>{campanha}</strong></td>
                        <td>{trans}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                        <td>{plataformas}</td>
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
                <li><strong>Pessoas Convertidas:</strong> {total_com_venda:,} de {total_leads:,} leads ({formatar_valor(taxa_conversao, 'percentual')})</li>
                <li><strong>Valor Total Gerado:</strong> {formatar_valor(total_valor, 'valor')}</li>
                <li><strong>Ticket Médio:</strong> {formatar_valor(ticket_medio, 'valor')}</li>
                <li><strong>Métodos de Pagamento:</strong> {len(vendas_por_fonte)} plataformas ativas</li>
                <li><strong>Campanhas UTM Mapeadas:</strong> {len(vendas_por_campanha)} campanhas diferentes</li>
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
output_path = Path(r'analises/[PBB-ABR-26]/ANALISE_VENDAS_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✓ Relatório gerado: ANALISE_VENDAS_[PBB-ABR-26].html")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
print(f"\n📊 Dados:")
print(f"  Leads: {total_leads:,}")
print(f"  Vendas: {total_vendas}")
print(f"  Conversão: {formatar_valor(taxa_conversao, 'percentual')}")
print(f"  Valor Total: {formatar_valor(total_valor, 'valor')}")
print(f"  Ticket Médio: {formatar_valor(ticket_medio, 'valor')}")
