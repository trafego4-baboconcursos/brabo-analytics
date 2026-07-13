#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatório HTML CORRIGIDO: ANALISE_VENDAS_[PBB-FEV-26].html
Inclui TODAS as vendas: Hotmart (crédito) + TMB (boleto)
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
    
    valor = valor.replace('R$', '').replace(' ', '').strip()
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
        .warning-box {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        ul { margin-left: 20px; margin-top: 10px; }
        li { margin: 5px 0; }
    </style>
    """

# Carregar dados
print("📥 Carregando dados...")

# Leads
df_leads = pd.read_csv(r'analises/[PBB-FEV-26]/active-campaing/peb-fev-26-leads-26-02-2026-8h-15min.csv', encoding='utf-8')

# Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart-pbb-fev-26.csv', encoding='utf-8', sep=';')
valor_col = df_hotmart['Valor de compra sem impostos']
valor_col_str = valor_col.astype(str).str.replace('.', '').str.replace(',', '.')
df_hotmart['valor_numerico'] = pd.to_numeric(valor_col_str, errors='coerce')
df_hotmart['email_normalizado'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
df_hotmart = df_hotmart[df_hotmart['email_normalizado'].str.contains('@', na=False)]

# TMB
df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb-pbb-fev-26.csv', encoding='utf-8', sep=';')
df_tmb['valor_numerico'] = pd.to_numeric(df_tmb['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce')
df_tmb_vendas = df_tmb[df_tmb['Status'] == 'Efetivado'].copy()
df_tmb_vendas['email_normalizado'] = df_tmb_vendas['Cliente Email'].astype(str).str.lower().str.strip()

# Normalizar leads
df_leads['email_normalizado'] = df_leads['Email'].astype(str).str.lower().str.strip()

# Encontrar vendas
emails_vendas_hotmart = set(df_hotmart['email_normalizado'].unique())
emails_vendas_tmb = set(df_tmb_vendas['email_normalizado'].unique())
emails_com_venda = emails_vendas_hotmart.union(emails_vendas_tmb)

df_leads['tem_venda'] = df_leads['email_normalizado'].isin(emails_com_venda)

# Calcular métricas
total_leads = len(df_leads)
total_vendas_hotmart = len(df_hotmart)
total_vendas_tmb = len(df_tmb_vendas)
total_vendas_pessoas = df_leads['tem_venda'].sum()
total_vendas_valor_hotmart = df_hotmart['valor_numerico'].sum()
total_vendas_valor_tmb = df_tmb_vendas['valor_numerico'].sum()
total_vendas_valor = total_vendas_valor_hotmart + total_vendas_valor_tmb
taxa_conversao = (total_vendas_pessoas / total_leads * 100) if total_leads > 0 else 0
ticket_medio = total_vendas_valor / (total_vendas_hotmart + total_vendas_tmb) if (total_vendas_hotmart + total_vendas_tmb) > 0 else 0

# Contar vendas com UTM
leads_hotmart = df_leads[df_leads['email_normalizado'].isin(emails_vendas_hotmart)].copy()
leads_tmb = df_leads[df_leads['email_normalizado'].isin(emails_vendas_tmb)].copy()
hotmart_com_utm = len(leads_hotmart.dropna(subset=['*Utm_campaign']))
tmb_com_utm = len(leads_tmb.dropna(subset=['*Utm_campaign']))
vendas_com_utm = hotmart_com_utm + tmb_com_utm
vendas_sem_utm = total_vendas_pessoas - vendas_com_utm

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
            <p>Cruzamento: Active Campaign Leads × Hotmart (Crédito) + TMB (Boleto)</p>
            <p style="color: #999; margin-top: 10px;">Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <!-- ATENÇÃO -->
        <div class="warning-box">
            <strong>⚠️ Importante:</strong> Este relatório inclui TODAS as vendas dos últimos 6 meses:
            <ul>
                <li><strong>Hotmart (Crédito):</strong> {total_vendas_hotmart} transações | R$ {formatar_valor(total_vendas_valor_hotmart, 'valor')}</li>
                <li><strong>TMB (Boleto):</strong> {total_vendas_tmb} transações | R$ {formatar_valor(total_vendas_valor_tmb, 'valor')}</li>
                <li><strong>Vendas vinculadas a Leads da Active Campaign:</strong> {total_vendas_pessoas} ({taxa_conversao:.2f}%)</li>
                <li><strong>Vendas SEM UTM mapeado:</strong> {vendas_sem_utm} (não foi possível vincular à campanha)</li>
            </ul>
        </div>

        <!-- MÉTRICAS PRINCIPAIS -->
        <div class="info-box">
            <h2>📈 Métricas Principais - TODAS AS VENDAS</h2>
            <div class="metric-row">
                <div class="metric-card">
                    <div class="label">Total de Leads</div>
                    <div class="value">{formatar_valor(total_leads, 'numero')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Total de Vendas</div>
                    <div class="value">{total_vendas_hotmart + total_vendas_tmb}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Taxa de Conversão</div>
                    <div class="value">{formatar_valor(taxa_conversao, 'percentual')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Valor Total em Vendas</div>
                    <div class="value">{formatar_valor(total_vendas_valor, 'valor')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Ticket Médio</div>
                    <div class="value">{formatar_valor(ticket_medio, 'valor')}</div>
                </div>
            </div>
        </div>

        <!-- BREAKDOWN POR PLATAFORMA -->
        <div class="info-box">
            <h2>💳 Vendas por Forma de Pagamento</h2>
            <table>
                <thead>
                    <tr>
                        <th>Plataforma</th>
                        <th>Quantidade</th>
                        <th>Valor Total</th>
                        <th>Ticket Médio</th>
                        <th>Leads Vinculados</th>
                        <th>Com UTM</th>
                        <th>Sem UTM</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>🎨 Hotmart (Cartão Crédito)</strong></td>
                        <td>{total_vendas_hotmart}</td>
                        <td>{formatar_valor(total_vendas_valor_hotmart, 'valor')}</td>
                        <td>{formatar_valor(total_vendas_valor_hotmart / total_vendas_hotmart if total_vendas_hotmart > 0 else 0, 'valor')}</td>
                        <td>{len(leads_hotmart)}</td>
                        <td>{hotmart_com_utm}</td>
                        <td>{len(leads_hotmart) - hotmart_com_utm}</td>
                    </tr>
                    <tr>
                        <td><strong>💰 TMB (Boleto)</strong></td>
                        <td>{total_vendas_tmb}</td>
                        <td>{formatar_valor(total_vendas_valor_tmb, 'valor')}</td>
                        <td>{formatar_valor(total_vendas_valor_tmb / total_vendas_tmb if total_vendas_tmb > 0 else 0, 'valor')}</td>
                        <td>{len(leads_tmb)}</td>
                        <td>{tmb_com_utm}</td>
                        <td>{len(leads_tmb) - tmb_com_utm}</td>
                    </tr>
                    <tr style="background-color: #f0f0f0; font-weight: bold;">
                        <td>TOTAL</td>
                        <td>{total_vendas_hotmart + total_vendas_tmb}</td>
                        <td>{formatar_valor(total_vendas_valor, 'valor')}</td>
                        <td>{formatar_valor(ticket_medio, 'valor')}</td>
                        <td>{total_vendas_pessoas}</td>
                        <td>{vendas_com_utm}</td>
                        <td>{vendas_sem_utm}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- ANÁLISE POR CAMPANHA (com UTM mapeado) -->
        <div class="info-box">
            <h2>🎯 Desempenho por Campanha (com UTM vinculado)</h2>
            <h3>Hotmart - Cartão de Crédito</h3>
            <table>
                <thead>
                    <tr>
                        <th>Campanha</th>
                        <th>Quantidade</th>
                        <th>% do Total Hotmart</th>
                    </tr>
                </thead>
                <tbody>
"""

# Hotmart por campanha
hotmart_com_utm_df = leads_hotmart.dropna(subset=['*Utm_campaign'])
if len(hotmart_com_utm_df) > 0:
    for campanha in sorted(hotmart_com_utm_df['*Utm_campaign'].unique()):
        if pd.isna(campanha):
            continue
        count = len(hotmart_com_utm_df[hotmart_com_utm_df['*Utm_campaign'] == campanha])
        perc = (count / hotmart_com_utm) * 100 if hotmart_com_utm > 0 else 0
        html += f"""
                    <tr>
                        <td>{campanha}</td>
                        <td>{count}</td>
                        <td>{formatar_valor(perc, 'percentual')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
            <h3>TMB - Boleto</h3>
            <table>
                <thead>
                    <tr>
                        <th>Campanha</th>
                        <th>Quantidade</th>
                        <th>% do Total TMB</th>
                    </tr>
                </thead>
                <tbody>
"""

# TMB por campanha
tmb_com_utm_df = leads_tmb.dropna(subset=['*Utm_campaign'])
if len(tmb_com_utm_df) > 0:
    for campanha in sorted(tmb_com_utm_df['*Utm_campaign'].unique()):
        if pd.isna(campanha):
            continue
        count = len(tmb_com_utm_df[tmb_com_utm_df['*Utm_campaign'] == campanha])
        perc = (count / tmb_com_utm) * 100 if tmb_com_utm > 0 else 0
        html += f"""
                    <tr>
                        <td>{campanha}</td>
                        <td>{count}</td>
                        <td>{formatar_valor(perc, 'percentual')}</td>
                    </tr>
"""

html += f"""
                </tbody>
            </table>
        </div>

        <!-- INSIGHTS -->
        <div class="info-box">
            <h2>💡 Insights & Análise</h2>
            <h3>🔍 Descobertas Principais</h3>
            <ul>
                <li><strong>Taxa de Conversão Geral:</strong> {taxa_conversao:.2f}% dos leads se converteram em vendas (340 de {total_leads:,})</li>
                <li><strong>Valor Gerado:</strong> R$ {formatar_valor(total_vendas_valor, 'valor')} em receita total</li>
                <li><strong>Ticket Médio Geral:</strong> R$ {formatar_valor(ticket_medio, 'valor')} por cliente</li>
                <li><strong>Hotmart tem {((total_vendas_valor_hotmart / total_vendas_valor) * 100):.1f}% da receita:</strong> Cartão de crédito é a principal forma de pagamento</li>
                <li><strong>UTM Tracking:</strong> {vendas_com_utm} vendas mapeadas para campanha ({vendas_sem_utm} sem UTM identificado)</li>
            </ul>
        </div>

        <div class="footer">
            <p>Relatório gerado automaticamente | Clique <a href="INDEX_[PBB-FEV-26].html">aqui</a> para voltar ao índice</p>
        </div>
    </div>
</body>
</html>
"""

# Salvar arquivo
output_path = Path(r'analises/[PBB-FEV-26]/ANALISE_VENDAS_[PBB-FEV-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✓ Relatório CORRIGIDO gerado: {output_path}")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
print(f"\n📊 Dados no relatório:")
print(f"  Valor total de vendas: R$ {total_vendas_valor:,.2f}")
print(f"  Hotmart: R$ {total_vendas_valor_hotmart:,.2f}")
print(f"  TMB: R$ {total_vendas_valor_tmb:,.2f}")
