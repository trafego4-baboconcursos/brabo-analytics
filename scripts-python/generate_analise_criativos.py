#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatório HTML: ANALISE_CRIATIVOS_[PBB-FEV-26].html
Criativos com Leads, Vendas, Investimento e ROAS
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
import re

def extrair_ad_code(texto):
    match = re.search(r'AD\d{3}', str(texto).upper())
    return match.group(0) if match else str(texto)

def encontrar_coluna(df, termos):
    termos = [termo.lower() for termo in termos]
    for coluna in df.columns:
        coluna_l = str(coluna).lower()
        if all(termo in coluna_l for termo in termos):
            return coluna
    return None

def encontrar_csv_leads_fev():
    base = Path(r'analises/[PBB-FEV-26]')
    candidatos = []
    for pasta in [base / 'active-campaing', base / 'Active Campaign', base / 'active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-fev-26' in f.name.lower() or 'lead' in f.name.lower())
    if not candidatos:
        raise FileNotFoundError('Arquivo de leads PBB-FEV-26 não encontrado')
    return max(candidatos, key=lambda f: f.stat().st_mtime)

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

leads_file = encontrar_csv_leads_fev()
df_leads = pd.read_csv(leads_file, encoding='utf-8', low_memory=False)

df_hotmart = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/hotmart pbb-fev-26.csv', encoding='utf-8', sep=';')
df_tmb = pd.read_csv(r'analises/[PBB-FEV-26]/vendas/tmb pbb-fev-26.csv', encoding='latin-1', sep=';')
_tmb_status_col = next((c for c in df_tmb.columns if 'situa' in c.lower() or 'status secund' in c.lower()), None)
if _tmb_status_col is not None:
    df_tmb_vendas = df_tmb[df_tmb[_tmb_status_col].astype(str).str.contains('Vigente', na=False)].copy()
else:
    df_tmb_vendas = df_tmb.copy()

# Normalizar emails
df_leads['email_norm'] = df_leads['Email'].astype(str).str.lower().str.strip()
df_hotmart['email_norm'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.lower().str.strip()
df_hotmart = df_hotmart[df_hotmart['email_norm'].str.contains('@', na=False)]

_tmb_email_col = encontrar_coluna(df_tmb_vendas, ['email']) or encontrar_coluna(df_tmb_vendas, ['e-mail'])
_tmb_ticket_col = encontrar_coluna(df_tmb_vendas, ['ticket'])
if _tmb_email_col is None or _tmb_ticket_col is None:
    raise KeyError(f'Não encontrei colunas de email/ticket no TMB: {list(df_tmb_vendas.columns)}')

df_tmb_vendas['email_norm'] = df_tmb_vendas[_tmb_email_col].astype(str).str.lower().str.strip()

# Vendas por email
vendas_hotmart_por_email = df_hotmart[['email_norm']].copy()
vendas_hotmart_por_email['valor'] = pd.to_numeric(df_hotmart['Valor de compra sem impostos'], errors='coerce')
vendas_hotmart_por_email['fonte'] = 'Hotmart'

vendas_tmb_por_email = df_tmb_vendas[['email_norm']].copy()
vendas_tmb_por_email['valor'] = pd.to_numeric(df_tmb_vendas[_tmb_ticket_col].astype(str).str.replace(',', '.'), errors='coerce')
vendas_tmb_por_email['fonte'] = 'TMB'

vendas_por_email = pd.concat([vendas_hotmart_por_email, vendas_tmb_por_email], ignore_index=True)

# Cruzar: leads + vendas
df_leads['tem_venda'] = df_leads['email_norm'].isin(vendas_por_email['email_norm'].unique())
df_leads_com_venda = df_leads[df_leads['tem_venda']].copy()

# Merge com vendas
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
analise['ad_code'] = analise[criativo_col].apply(extrair_ad_code)

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

# Calcular investimento por plataforma (Meta Ads)
try:
    df_meta = pd.read_csv(r'analises/[PBB-FEV-26]/meta ads/meta-pbb-fev-26.csv', encoding='utf-8')
    df_meta['valor_convertido'] = pd.to_numeric(df_meta['Valor usado (BRL)'].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
    df_meta['ad_code'] = df_meta['Nome do anúncio'].apply(extrair_ad_code)
    
    # Agrupar por código do anúncio
    investimento_meta = df_meta.groupby('ad_code').agg({
        'valor_convertido': 'sum',
        'Leads': 'sum'
    }).reset_index()
    investimento_meta.columns = ['ad_code', 'investimento', 'leads_meta']
except:
    investimento_meta = None
    print("⚠️  Não consegui carregar dados de Meta Ads para investimento")

if investimento_meta is not None:
    analise = analise.merge(investimento_meta, on='ad_code', how='left')
else:
    analise['investimento'] = 0
    analise['leads_meta'] = 0

analise['investimento'] = analise['investimento'].fillna(0)
analise['leads_meta'] = analise['leads_meta'].fillna(0)
analise['custo'] = analise.apply(lambda r: r['investimento'] / r['vendas'] if r['vendas'] > 0 else 0, axis=1)
analise['roas'] = analise.apply(lambda r: r['valor_vendas'] / r['investimento'] if r['investimento'] > 0 else 0, axis=1)

# Gerar HTML
html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Criativos - PBB-FEV-26</title>
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
                <div class="label">Investimento</div>
                <div class="value">{formatar_valor(analise['investimento'].sum(), 'valor')}</div>
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
                        <th>Investimento</th>
                        <th>Custo</th>
                        <th>Ticket Médio</th>
                        <th>ROAS</th>
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
    investimento = row['investimento']
    custo = row['custo']
    ticket = (valor / vendas) if vendas > 0 else 0
    roas = row['roas']
    plataforma = str(row['plataforma'])[:20]
    
    css_class = 'top-performer' if vendas > 0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(leads, 'numero')}</td>
                        <td>{vendas}</td>
                        <td>{formatar_valor(taxa, 'percentual')}</td>
                        <td>{formatar_valor(valor, 'valor')}</td>
                        <td>{formatar_valor(investimento, 'valor')}</td>
                        <td>{formatar_valor(custo, 'valor')}</td>
                        <td>{formatar_valor(ticket, 'valor')}</td>
                        <td>{formatar_valor(roas, 'decimal')}x</td>
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
                <li><strong>Custo médio por venda:</strong> {formatar_valor((analise['investimento'].sum() / analise['vendas'].sum()) if analise['vendas'].sum() > 0 else 0, 'valor')}</li>
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
output_path = Path(r'analises/[PBB-FEV-26]/ANALISE_CRIATIVOS_[PBB-FEV-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✓ Relatório gerado: {output_path}")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
print(f"\n📊 Dados:")
print(f"  Criativos: {len(analise)}")
print(f"  Leads totais: {analise['leads_total'].sum():,}")
print(f"  Vendas totais: {analise['vendas'].sum()}")
print(f"  Valor total: R$ {analise['valor_vendas'].sum():,.2f}")
