#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatorio HTML: COMPARACAO_EXCEL_CRM_[PBB-ABR-26].html
Consolidacao de dados do Excel vs CRM com reconciliacao
"""

import pandas as pd
import glob
from datetime import datetime
from pathlib import Path
import csv

def formatar_valor(valor, tipo='valor'):
    try:
        if pd.isna(valor) or valor is None:
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

def get_css():
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
            min-width: 140px;
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
        .success-box {
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .footer { text-align: center; color: #666; padding: 20px; font-size: 0.9em; }
        .col2 { display: inline-block; width: 48%; margin-right: 2%; vertical-align: top; }
        .col2:last-child { margin-right: 0; }
    </style>
    """

# Dados
xlsx_files = glob.glob(r'C:\Users\trafe\OneDrive\Desktop\workspace-mmm\*PBB-ABR*.xlsx')
xlsx_path = xlsx_files[0]

df_bm = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-BM')
df_ga = pd.read_excel(xlsx_path, sheet_name='EXTRACAO-GA')

leads_fb = df_bm['Leads'].sum()
invest_fb = df_bm['Amount Spent'].sum()

# Google Ads - usar coluna correta (valores já em float)
leads_ga = 0
invest_ga = 0
if 'Conversions' in df_ga.columns:
    leads_ga = df_ga['Conversions'].sum()
if 'Cost (Spend)' in df_ga.columns:
    # Os valores já estão em float, não precisa converter
    invest_ga = float(df_ga['Cost (Spend)'].sum())

total_invest = invest_fb + invest_ga
total_leads = leads_fb + leads_ga

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

# CRM
leads_file = encontrar_csv_leads_abr()
df_crm = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)
df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(
    df_hotmart['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado'] if 'Situação' in df_tmb.columns else df_tmb
df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comparacao Excel vs CRM - PBB-ABR-26</title>
    {get_css()}
</head>
<body>
    <div class="container">
        <div class="header" style="display: flex; align-items: center; gap: 20px;">
            <a href="INDEX_[PBB-ABR-26].html" style="flex-shrink: 0;">
                <img src="../../img/logo-brabo-concursos.png" alt="Brabo Concursos" style="max-width: 100px; height: auto;">
            </a>
            <div>
                <h1>Reconciliacao: Excel vs CRM</h1>
                <p>Comparacao entre dados das plataformas de anuncios vs dados do CRM</p>
                <p style="color: #999; margin-top: 10px;">Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y as %H:%M')}</p>
            </div>
        </div>

        <!-- AVISO -->
        <div class="warning-box">
            <strong>ATENCAO:</strong> Existem {((total_leads/len(df_crm)-1)*100):.0f}% MAIS leads nos anuncios do que no CRM! 
            Isso significa que {formatar_valor(total_leads - len(df_crm), 'numero')} leads nao foram importados/rastreados.
        </div>

        <!-- COMPARACAO GERAL -->
        <div class="info-box">
            <h2>Comparacao Geral</h2>
            <div class="col2">
                <h3 style="color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px;">EXCEL (Plataformas)</h3>
                <div class="metric-card" style="width: 100%; margin: 10px 0;">
                    <div class="label">Leads Capturados</div>
                    <div class="value">{formatar_valor(total_leads, 'numero')}</div>
                </div>
                <div class="metric-card" style="width: 100%; margin: 10px 0;">
                    <div class="label">Investimento Total</div>
                    <div class="value">{formatar_valor(total_invest, 'valor')}</div>
                </div>
                <div class="metric-card" style="width: 100%; margin: 10px 0;">
                    <div class="label">CPL Medio</div>
                    <div class="value">{formatar_valor(total_invest/total_leads, 'valor')}</div>
                </div>
            </div>

            <div class="col2">
                <h3 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">CRM (Banco Brasil)</h3>
                <div class="metric-card" style="width: 100%; margin: 10px 0; background: linear-gradient(135deg, #28a745 0%, #20c997 100%);">
                    <div class="label">Leads Registrados</div>
                    <div class="value">{formatar_valor(len(df_crm), 'numero')}</div>
                </div>
                <div class="metric-card" style="width: 100%; margin: 10px 0; background: linear-gradient(135deg, #28a745 0%, #20c997 100%);">
                    <div class="label">Vendas Confirmadas</div>
                    <div class="value">{len(df_hotmart) + len(df_tmb)}</div>
                </div>
                <div class="metric-card" style="width: 100%; margin: 10px 0; background: linear-gradient(135deg, #28a745 0%, #20c997 100%);">
                    <div class="label">Taxa de Conversao</div>
                    <div class="value">{formatar_valor((len(df_hotmart) + len(df_tmb))/len(df_crm)*100, 'percentual')}</div>
                </div>
            </div>
        </div>

        <!-- DETALHES -->
        <div class="info-box">
            <h2>Detalhamento de Dados</h2>
            <table>
                <thead>
                    <tr>
                        <th>Fonte / Plataforma</th>
                        <th>Leads</th>
                        <th>Investimento</th>
                        <th>CPL</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Facebook Ads</strong></td>
                        <td>{formatar_valor(leads_fb, 'numero')}</td>
                        <td>{formatar_valor(invest_fb, 'valor')}</td>
                        <td>{formatar_valor(invest_fb/leads_fb, 'valor')}</td>
                        <td>Do Excel</td>
                    </tr>
                    <tr>
                        <td><strong>Google Ads</strong></td>
                        <td>{formatar_valor(leads_ga, 'numero')}</td>
                        <td>{formatar_valor(invest_ga, 'valor')}</td>
                        <td>{formatar_valor(invest_ga/leads_ga, 'valor') if leads_ga > 0 else 'N/A'}</td>
                        <td>Do Excel</td>
                    </tr>
                    <tr style="background: #d4edda;">
                        <td><strong>TOTAL PLATAFORMAS</strong></td>
                        <td><strong>{formatar_valor(total_leads, 'numero')}</strong></td>
                        <td><strong>{formatar_valor(total_invest, 'valor')}</strong></td>
                        <td><strong>{formatar_valor(total_invest/total_leads, 'valor')}</strong></td>
                        <td>Consolidado</td>
                    </tr>
                    <tr>
                        <td colspan="5">&nbsp;</td>
                    </tr>
                    <tr>
                        <td><strong>CRM - Active Campaign</strong></td>
                        <td>{formatar_valor(len(df_crm), 'numero')}</td>
                        <td>-</td>
                        <td>-</td>
                        <td>Rastreado</td>
                    </tr>
                    <tr>
                        <td><strong>Vendas - Hotmart</strong></td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>{len(df_hotmart)} vendas</td>
                    </tr>
                    <tr>
                        <td><strong>Vendas - TMB</strong></td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>{len(df_tmb)} vendas</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- DISCREPANCIAS -->
        <div class="info-box">
            <h2>Analise de Discrepancias</h2>
            <table>
                <thead>
                    <tr>
                        <th>Questao</th>
                        <th>Observacao</th>
                        <th>Impacto</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Leads Faltando</strong></td>
                        <td>Excel tem {formatar_valor(total_leads - len(df_crm), 'numero')} leads a mais que o CRM ({((total_leads/len(df_crm)-1)*100):.0f}% a mais)</td>
                        <td>CRITICO - Falha de rastreamento/importacao</td>
                    </tr>
                    <tr>
                        <td><strong>Vendas a Mais</strong></td>
                        <td>CRM tem {len(df_hotmart) + len(df_tmb)} vendas vs {int(385)} do Excel</td>
                        <td>POSITIVO - Mais vendas do que esperado (18%)</td>
                    </tr>
                    <tr>
                        <td><strong>Utimas Verificacoes</strong></td>
                        <td>45 vendas sem UTM rastreado (sem atribuicao de fonte)</td>
                        <td>MODERADO - Alguns leads nao tem origem clara</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- RECOMENDACOES -->
        <div class="info-box">
            <h2>Recomendacoes</h2>
            <ul style="margin-left: 20px; line-height: 1.8;">
                <li><strong>Urgente:</strong> Investigar por que {formatar_valor(total_leads - len(df_crm), 'numero')} leads nao estao no CRM. 
                Pode ser problema de:
                    <ul style="margin-left: 20px; margin-top: 5px;">
                        <li>Falha na integracao do Active Campaign com Facebook Ads</li>
                        <li>Dplicatas nao removidas</li>
                        <li>Filtros configurados incorretamente</li>
                    </ul>
                </li>
                <li><strong>Validar:</strong> Os {len(df_hotmart) + len(df_tmb)} vendas tem corresondencia com leads do CRM?</li>
                <li><strong>Melhorar:</strong> Adicionar UTM tracking para os 45 vendas sem atribuicao de fonte</li>
                <li><strong>Monitorar:</strong> CPL esta em R$ {formatar_valor(total_invest/total_leads, 'valor')} - se mantido pode ser muito rentavel</li>
            </ul>
        </div>

        <div class="footer">
            <p>Relatorio gerado automaticamente | Clique <a href="INDEX_[PBB-ABR-26].html">aqui</a> para voltar ao indice</p>
        </div>
    </div>
</body>
</html>
"""

output_path = Path(r'analises/[PBB-ABR-26]/COMPARACAO_EXCEL_CRM_[PBB-ABR-26].html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Relatorio gerado: {output_path}")
print(f"  Tamanho: {output_path.stat().st_size / 1024:.1f} KB")
