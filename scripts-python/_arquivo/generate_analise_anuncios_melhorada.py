#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera ANALISE_ANUNCIOS_[PBB-ABR-26].html melhorado
Consolida dados do Excel com extrações Google Ads e Facebook
"""

import pandas as pd
from datetime import datetime
from pathlib import Path

def formatar_valor(valor, tipo='valor'):
    """Formata número conforme tipo"""
    try:
        if pd.isna(valor):
            return "-"
        if tipo == 'valor':
            return f"R$ {float(valor):,.2f}".replace(',', 'COMMA').replace('.', ',').replace('COMMA', '.')
        elif tipo == 'percentual':
            return f"{float(valor):.2f}%"
        elif tipo == 'numero':
            return f"{int(float(valor)):,}".replace(',', '.')
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
            font-size: 0.85em;
        }
        th { background-color: #667eea; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px 12px; border-bottom: 1px solid #eee; }
        tr:hover { background-color: #f5f5f5; }
        .top-performer { background-color: #d4edda; }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            display: inline-block;
            margin: 10px 10px 10px 0;
            min-width: 130px;
        }
        .metric-card .label { font-size: 0.9em; opacity: 0.9; }
        .metric-card .value { font-size: 1.6em; font-weight: bold; margin-top: 5px; }
        .platform-section {
            border-left: 4px solid #667eea;
            padding-left: 20px;
            margin-top: 20px;
        }
        .facebook { border-left-color: #1877f2; }
        .google { border-left-color: #ea4335; }
        .footer {
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 0.9em;
        }
    </style>
    """

print("Carregando dados...")

# Ler abas principais
import glob
import csv as csv_module
xlsx_files = glob.glob(r'C:\Users\trafe\OneDrive\Desktop\workspace-mmm\*PBB-ABR*.xlsx')
if not xlsx_files:
    print("Arquivo nao encontrado!")
    exit(1)

xlsx_path = xlsx_files[0]
print(f"Arquivo encontrado: {xlsx_path}\n")

df_geral = pd.read_excel(xlsx_path, sheet_name='Anúncios PBB-ABR-26', header=None)
df_fb = pd.read_excel(xlsx_path, sheet_name='Anúncios FB PBB-ABR-26', header=None)
df_yt = pd.read_excel(xlsx_path, sheet_name='Anúncios YT PBB-ABR-26', header=None)
df_bm_raw = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')

print(f"  Geral: {len(df_geral)} linhas")
print(f"  FB: {len(df_fb)} linhas")
print(f"  YT: {len(df_yt)} linhas")
print(f"  BM Raw: {len(df_bm_raw)} linhas")

# =========== CARREGANDO DADOS DE VENDAS DOS CSVs ===========
# Leads
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
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv_module.QUOTE_MINIMAL, low_memory=False)
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()
df_leads_criativo = df_leads[df_leads['*Utm_content'].notna()].copy()
df_leads_criativo['criativo'] = df_leads_criativo['*Utm_content'].astype(str).str.strip()

# Vendas - Hotmart
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

# Vendas - TMB
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

print(f"✓ Leads: {len(df_leads)} ({leads_file.name})")
print(f"✓ Hotmart: {len(df_hotmart)} vendas")
print(f"✓ TMB: {len(df_tmb)} vendas")
print(f"✓ Total vendas (CRM): {len(df_hotmart) + len(df_tmb)}\n")

# Processar dados da aba geral (começa em linha 1 com headers em linha 1)
# Linha 0 = TOTAL, Linha 1 = Headers
# Colunas: 0=Anuncio, 1=Invest, 2=Miniatura, 3=Leads, 4=CPL, 5=Vendas (SERÁ RECALCULADA), 6=Custo/Venda, 7=ROAS
dados_geral = []
for i in range(2, len(df_geral)):
    row = df_geral.iloc[i]
    if pd.notna(row[0]) and row[0] not in ['Anuncio', 'TOTAL', 'NaN']:
        try:
            criativo = str(row[0])
            invest = float(row[1]) if pd.notna(row[1]) else 0
            leads = float(row[3]) if pd.notna(row[3]) else 0
            cpl = float(row[4]) if pd.notna(row[4]) else 0
            # NÃO USAR vendas da planilha (está errada)
            # Será recalculada abaixo
            
            # Facebook
            invest_fb = float(row[9]) if pd.notna(row[9]) else 0
            leads_fb = float(row[10]) if pd.notna(row[10]) else 0
            cpl_fb = float(row[11]) if pd.notna(row[11]) else 0
            vendas_fb = float(row[12]) if pd.notna(row[12]) else 0
            roas_fb = float(row[13]) if pd.notna(row[13]) else 0
            
            # Google/YT
            invest_yt = float(row[15]) if pd.notna(row[15]) else 0
            leads_yt = float(row[16]) if pd.notna(row[16]) else 0
            cpl_yt = float(row[17]) if pd.notna(row[17]) else 0
            vendas_yt = float(row[18]) if pd.notna(row[18]) else 0
            roas_yt = float(row[19]) if pd.notna(row[19]) else 0
            
            # Calcular vendas por criativo (email matching)
            emails_criativo = df_leads_criativo[df_leads_criativo['criativo'] == criativo]['Email'].unique()
            vendas_hotmart = len(df_hotmart[df_hotmart['email'].isin(emails_criativo)])
            vendas_tmb = len(df_tmb[df_tmb['email'].isin(emails_criativo)])
            vendas = vendas_hotmart + vendas_tmb
            valor_vendas = df_hotmart[df_hotmart['email'].isin(emails_criativo)]['valor_num'].sum() + \
                          df_tmb[df_tmb['email'].isin(emails_criativo)]['valor_num'].sum()
            
            custo_venda = invest / vendas if vendas > 0 else 0
            roas = (valor_vendas / invest * 100) if invest > 0 else 0
            
            dados_geral.append({
                'criativo': criativo,
                'invest': invest,
                'leads': leads,
                'cpl': cpl if cpl > 0 else (invest / leads if leads > 0 else 0),
                'vendas': vendas,
                'custo_venda': custo_venda,
                'roas': roas,
                'invest_fb': invest_fb,
                'leads_fb': leads_fb,
                'cpl_fb': cpl_fb,
                'vendas_fb': vendas_fb,
                'roas_fb': roas_fb,
                'invest_yt': invest_yt,
                'leads_yt': leads_yt,
                'cpl_yt': cpl_yt,
                'vendas_yt': vendas_yt,
                'roas_yt': roas_yt,
            })
        except Exception as e:
            pass

df_analise = pd.DataFrame(dados_geral)
print(f"Dados consolidados: {len(df_analise)} criativos")
print(f"  Investimento Total: R$ {df_analise['invest'].sum():,.2f}")
print(f"  Leads Total: {df_analise['leads'].sum():,.0f}")
print(f"  Vendas Total (RECALCULADAS): {int(df_analise['vendas'].sum())}")
print(f"  Diferença da planilha: {385 - int(df_analise['vendas'].sum())} vendas\n")

# Ordenar por vendas
df_analise = df_analise.sort_values('vendas', ascending=False)

# Gerar HTML
html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analise de Anuncios - PBB-ABR-26</title>
    {get_css_base()}
</head>
<body>
    <div class="container">
        <div class="header" style="display: flex; align-items: center; gap: 20px;">
            <a href="INDEX_[PBB-ABR-26].html" style="flex-shrink: 0;">
                <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos" style="max-width: 100px; height: auto;">
            </a>
            <div>
                <h1>Analise Consolidada de Anuncios</h1>
                <p>Performance por Criativo: Facebook Ads + Google Ads (YouTube)</p>
                <p style="color: #999; margin-top: 10px;">Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y as %H:%M')}</p>
            </div>
        </div>

        <!-- RESUMO GERAL -->
        <div class="info-box">
            <h2>Resumo Geral</h2>
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
                <div class="value">{formatar_valor(df_analise['leads'].sum(), 'numero')}</div>
            </div>
            <div class="metric-card">
                <div class="label">Vendas</div>
                <div class="value">{int(df_analise['vendas'].sum())}</div>
            </div>
            <div class="metric-card">
                <div class="label">CPL Medio</div>
                <div class="value">{formatar_valor((df_analise['invest'].sum() / df_analise['leads'].sum()) if df_analise['leads'].sum() > 0 else 0, 'valor')}</div>
            </div>
        </div>

        <!-- TOP 20 CRIATIVOS -->
        <div class="info-box">
            <h2>Top 20 Criativos por Vendas</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Investimento</th>
                        <th>Leads</th>
                        <th>CPL</th>
                        <th>Vendas</th>
                        <th>Custo/Venda</th>
                        <th>ROAS</th>
                        <th>Taxa Conv</th>
                    </tr>
                </thead>
                <tbody>
"""

for idx, row in df_analise.head(20).iterrows():
    criativo = str(row['criativo'])[:60]
    invest = row['invest']
    leads = row['leads']
    cpl = row['cpl']
    vendas = row['vendas']
    custo_venda = row['custo_venda']
    roas = row['roas']
    taxa_conv = (vendas / leads * 100) if leads > 0 else 0
    
    css_class = 'top-performer' if vendas > 0 else ''
    
    html += f"""
                    <tr class="{css_class}">
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(invest, 'valor')}</td>
                        <td>{formatar_valor(leads, 'numero')}</td>
                        <td>{formatar_valor(cpl, 'valor')}</td>
                        <td>{int(vendas)}</td>
                        <td>{formatar_valor(custo_venda, 'valor')}</td>
                        <td>{formatar_valor(roas, 'percentual')}</td>
                        <td>{formatar_valor(taxa_conv, 'percentual')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- FACEBOOK ADS -->
        <div class="info-box platform-section facebook">
            <h2>Facebook Ads Performance</h2>
            <div class="metric-card">
                <div class="label">Investimento FB</div>
                <div class="value">R$ {:.0f}</div>
            </div>
            <div class="metric-card">
                <div class="label">Leads FB</div>
                <div class="value">{:.0f}</div>
            </div>
            <div class="metric-card">
                <div class="label">CPL FB</div>
                <div class="value">R$ {:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="label">Vendas FB</div>
                <div class="value">{:.0f}</div>
            </div>
            <table style="margin-top: 20px;">
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Investimento FB</th>
                        <th>Leads FB</th>
                        <th>CPL FB</th>
                        <th>Vendas FB</th>
                        <th>ROAS FB</th>
                    </tr>
                </thead>
                <tbody>
""".format(
    df_analise['invest_fb'].sum(),
    df_analise['leads_fb'].sum(),
    (df_analise['invest_fb'].sum() / df_analise['leads_fb'].sum()) if df_analise['leads_fb'].sum() > 0 else 0,
    df_analise['vendas_fb'].sum()
)

for idx, row in df_analise[df_analise['invest_fb'] > 0].head(10).iterrows():
    criativo = str(row['criativo'])[:50]
    html += f"""
                    <tr>
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(row['invest_fb'], 'valor')}</td>
                        <td>{formatar_valor(row['leads_fb'], 'numero')}</td>
                        <td>{formatar_valor(row['cpl_fb'], 'valor')}</td>
                        <td>{int(row['vendas_fb'])}</td>
                        <td>{formatar_valor(row['roas_fb'], 'percentual')}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </div>

        <!-- GOOGLE ADS / YOUTUBE -->
        <div class="info-box platform-section google">
            <h2>Google Ads / YouTube Performance</h2>
            <div class="metric-card">
                <div class="label">Investimento YT</div>
                <div class="value">R$ {:.0f}</div>
            </div>
            <div class="metric-card">
                <div class="label">Leads YT</div>
                <div class="value">{:.0f}</div>
            </div>
            <div class="metric-card">
                <div class="label">CPL YT</div>
                <div class="value">R$ {:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="label">Vendas YT</div>
                <div class="value">{:.0f}</div>
            </div>
            <table style="margin-top: 20px;">
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Investimento YT</th>
                        <th>Leads YT</th>
                        <th>CPL YT</th>
                        <th>Vendas YT</th>
                        <th>ROAS YT</th>
                    </tr>
                </thead>
                <tbody>
""".format(
    df_analise['invest_yt'].sum(),
    df_analise['leads_yt'].sum(),
    (df_analise['invest_yt'].sum() / df_analise['leads_yt'].sum()) if df_analise['leads_yt'].sum() > 0 else 0,
    df_analise['vendas_yt'].sum()
)

for idx, row in df_analise[df_analise['invest_yt'] > 0].head(10).iterrows():
    criativo = str(row['criativo'])[:50]
    html += f"""
                    <tr>
                        <td><strong>{criativo}</strong></td>
                        <td>{formatar_valor(row['invest_yt'], 'valor')}</td>
                        <td>{formatar_valor(row['leads_yt'], 'numero')}</td>
                        <td>{formatar_valor(row['cpl_yt'], 'valor')}</td>
                        <td>{int(row['vendas_yt'])}</td>
                        <td>{formatar_valor(row['roas_yt'], 'percentual')}</td>
                    </tr>
"""

html += f"""
                </tbody>
            </table>
        </div>

        <!-- INSIGHTS -->
        <div class="info-box">
            <h2>Insights Principais</h2>
            <ul style="margin-left: 20px; margin-top: 10px; line-height: 1.8;">
                <li><strong>Melhor Criativo:</strong> {df_analise.iloc[0]['criativo'][:60]} com {int(df_analise.iloc[0]['vendas'])} vendas</li>
                <li><strong>Maior ROAS:</strong> {formatar_valor(df_analise['roas'].max(), 'percentual')}</li>
                <li><strong>Menor CPL:</strong> {formatar_valor(df_analise[df_analise['leads'] > 0]['cpl'].min(), 'valor')}</li>
                <li><strong>Criativos com Vendas:</strong> {len(df_analise[df_analise['vendas'] > 0])} de {len(df_analise)}</li>
                <li><strong>Comparacao:</strong> Facebook: {formatar_valor(df_analise['invest_fb'].sum(), 'valor')} em {int(df_analise['leads_fb'].sum())} leads | YouTube: {formatar_valor(df_analise['invest_yt'].sum(), 'valor')} em {int(df_analise['leads_yt'].sum())} leads</li>
            </ul>
        </div>

        <div class="footer">
            <p>Relatorio gerado automaticamente | Clique <a href="INDEX_[PBB-ABR-26].html">aqui</a> para voltar ao indice</p>
        </div>
    </div>
</body>
</html>
"""

# Salvar
output_path = Path(r'analises/[PBB-ABR-26]/ANALISE_ANUNCIOS_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nRelatorio gerado: {output_path}")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
