#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de HTMLs por Plataforma - PBB-ABR-26
Gera 3 relatórios HTML:
1. ANALISE_FACEBOOK_[PBB-ABR-26].html
2. ANALISE_YOUTUBE_[PBB-ABR-26].html  
3. ANALISE_CONSOLIDADA_[PBB-ABR-26].html
"""

import pandas as pd
from datetime import datetime


CAMPAIGN_CODE = "PES-MAI-26"
CAMPAIGN_FOLDER = "[PES-MAI-26]"
PERIOD_LABEL = "Abril a Maio de 2026"


def adaptar_html_campaign(html):
    nav_start = "<!-- BRABO-NAV -->"
    nav_end = "<!-- /BRABO-NAV -->"
    nav_block = None
    if nav_start in html and nav_end in html:
        before_nav, rest = html.split(nav_start, 1)
        nav_body, after_nav = rest.split(nav_end, 1)
        nav_block = nav_start + nav_body + nav_end
        html = before_nav + "__BRABO_NAV__" + after_nav
    replacements = {
        "[PBB-ABR-26]": CAMPAIGN_FOLDER,
        "PBB-ABR-26": CAMPAIGN_CODE,
        "Abril 2026": PERIOD_LABEL,
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    if nav_block is not None:
        html = html.replace("__BRABO_NAV__", nav_block)
    return html

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

def gerar_html_plataforma(nome_plataforma, df_dados, cor_primaria, cor_secundaria):
    """Gera HTML para uma plataforma específica"""
    df_metricas = df_dados.copy()
    if nome_plataforma.upper().startswith("YOUTUBE") and "criativo" in df_metricas.columns:
        df_metricas = df_metricas[~df_metricas["criativo"].astype(str).isin(["SEARCH", "PMAX", "DISPLAY"])].copy()
    
    # Métricas gerais
    total_investimento = df_metricas['investimento'].sum()
    total_leads = int(df_metricas['leads'].sum())
    total_vendas = int(df_metricas['vendas'].sum())
    total_faturamento = df_metricas['faturamento'].sum()
    roas_medio = total_faturamento / total_investimento if total_investimento > 0 else 0
    cpl_medio = total_investimento / total_leads if total_leads > 0 else 0
    custo_venda_medio = total_investimento / total_vendas if total_vendas > 0 else 0
    taxa_conversao_media = (total_vendas / total_leads * 100) if total_leads > 0 else 0
    
    # Ordenar por vendas
    df_sorted = df_dados.sort_values('vendas', ascending=False).reset_index(drop=True)
    
    # Top performers
    top_roas = df_metricas[df_metricas['vendas'] > 0].nlargest(5, 'roas')
    top_vendas = df_metricas[df_metricas['vendas'] > 0].nlargest(5, 'vendas')
    pior_roas = df_metricas[df_metricas['vendas'] > 0].nsmallest(5, 'roas')
    
    html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise {nome_plataforma} - PBB-ABR-26</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, {cor_primaria} 0%, {cor_secundaria} 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1800px; margin: 0 auto; }}
        .header {{ background: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .header h1 {{ color: {cor_primaria}; margin-bottom: 10px; font-size: 2.5em; }}
        .header .subtitle {{ color: #666; font-size: 1.1em; margin-bottom: 5px; }}
        .header .timestamp {{ color: #999; font-size: 0.9em; }}
        
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }}
        .metric-card.destaque {{ background: linear-gradient(135deg, {cor_primaria} 0%, {cor_secundaria} 100%); color: white; }}
        .metric-card .label {{ font-size: 0.85em; opacity: 0.8; margin-bottom: 10px; }}
        .metric-card.destaque .label {{ opacity: 1; font-weight: 600; }}
        .metric-card .value {{ font-size: 2.2em; font-weight: bold; }}
        .metric-card .subtext {{ font-size: 0.8em; margin-top: 8px; opacity: 0.7; }}
        
        .info-box {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .info-box h2 {{ color: {cor_primaria}; margin-bottom: 20px; font-size: 1.8em; border-bottom: 3px solid {cor_primaria}; padding-bottom: 10px; }}
        
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin-top: 15px; font-size: 0.85em; }}
        th {{ background-color: {cor_primaria}; color: white; padding: 12px 8px; text-align: left; font-weight: 600; font-size: 0.9em; position: sticky; top: 0; z-index: 10; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .numero {{ text-align: right; font-family: 'Courier New', monospace; }}
        .top3 {{ background-color: #fff3cd !important; }}
        .positivo {{ color: #28a745; font-weight: bold; }}
        .negativo {{ color: #dc3545; font-weight: bold; }}
        
        .highlights {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .highlight-box {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .highlight-box h3 {{ color: {cor_primaria}; margin-bottom: 15px; font-size: 1.2em; }}
        .highlight-item {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        .highlight-item:last-child {{ border-bottom: none; }}
        .highlight-item .criativo {{ font-weight: bold; color: #333; }}
        .highlight-item .value {{ float: right; color: {cor_primaria}; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Análise {nome_plataforma}</h1>
            <div class="subtitle">Campanha: PBB-ABR-26 | Período: Abril 2026</div>
            <div class="timestamp">Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}</div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card destaque">
                <div class="label">💰 INVESTIMENTO TOTAL</div>
                <div class="value">{formatar_valor(total_investimento).replace('R$ ', '')}</div>
                <div class="subtext">{formatar_valor(total_investimento)}</div>
            </div>
            <div class="metric-card destaque">
                <div class="label">💵 FATURAMENTO CRM</div>
                <div class="value">{formatar_valor(total_faturamento).replace('R$ ', '')}</div>
                <div class="subtext">{formatar_valor(total_faturamento)}</div>
            </div>
            <div class="metric-card">
                <div class="label">📊 ROAS Médio</div>
                <div class="value">{roas_medio:.2f}x</div>
                <div class="subtext">Retorno sobre investimento</div>
            </div>
            <div class="metric-card">
                <div class="label">📈 Total de Vendas</div>
                <div class="value">{formatar_valor(total_vendas, 'numero')}</div>
                <div class="subtext">Vendas rastreadas via UTM</div>
            </div>
            <div class="metric-card">
                <div class="label">👥 Total de Leads</div>
                <div class="value">{formatar_valor(total_leads, 'numero')}</div>
                <div class="subtext">Leads capturados no CRM</div>
            </div>
            <div class="metric-card">
                <div class="label">💸 Custo por Lead</div>
                <div class="value">{formatar_valor(cpl_medio)}</div>
                <div class="subtext">CPL médio</div>
            </div>
        </div>
        
        <div class="highlights">
            <div class="highlight-box">
                <h3>🏆 Top 5 por ROAS</h3>
"""
    
    for idx, row in top_roas.iterrows():
        html += f"""
                <div class="highlight-item">
                    <span class="criativo">{row['criativo']}</span>
                    <span class="value">{row['roas']:.2f}x</span>
                    <br><small style="color: #666;">{int(row['vendas'])} vendas | {formatar_valor(row['investimento'])}</small>
                </div>
"""
    
    html += f"""
            </div>
            
            <div class="highlight-box">
                <h3>📈 Top 5 por Vendas</h3>
"""
    
    for idx, row in top_vendas.iterrows():
        html += f"""
                <div class="highlight-item">
                    <span class="criativo">{row['criativo']}</span>
                    <span class="value">{int(row['vendas'])} vendas</span>
                    <br><small style="color: #666;">ROAS {row['roas']:.2f}x | {formatar_valor(row['faturamento'])}</small>
                </div>
"""
    
    html += f"""
            </div>
            
            <div class="highlight-box">
                <h3>⚠️ Piores ROAS (atenção)</h3>
"""
    
    for idx, row in pior_roas.iterrows():
        html += f"""
                <div class="highlight-item">
                    <span class="criativo">{row['criativo']}</span>
                    <span class="value negativo">{row['roas']:.2f}x</span>
                    <br><small style="color: #666;">{int(row['vendas'])} vendas | {formatar_valor(row['investimento'])}</small>
                </div>
"""
    
    html += f"""
            </div>
        </div>
        
        <div class="info-box">
            <h2>📋 Desempenho Detalhado por Criativo</h2>
            <table>
                <thead>
                    <tr>
                        <th style="width: 8%;">#</th>
                        <th style="width: 12%;">Criativo</th>
                        <th style="width: 13%;">Investimento</th>
                        <th style="width: 8%;">Leads</th>
                        <th style="width: 8%;">Vendas</th>
                        <th style="width: 13%;">Faturamento</th>
                        <th style="width: 8%;">ROAS</th>
                        <th style="width: 10%;">CPL</th>
                        <th style="width: 10%;">Custo/Venda</th>
                        <th style="width: 10%;">Taxa Conv.</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for idx, row in df_sorted.iterrows():
        row_class = 'top3' if idx < 3 and row['vendas'] > 0 else ''
        roas_class = 'positivo' if row['roas'] >= 2.0 else ('negativo' if row['roas'] < 1.0 and row['vendas'] > 0 else '')
        
        html += f"""
                    <tr class="{row_class}">
                        <td class="numero">{idx + 1}</td>
                        <td><strong>{row['criativo']}</strong></td>
                        <td class="numero">{formatar_valor(row['investimento'])}</td>
                        <td class="numero">{formatar_valor(row['leads'], 'numero')}</td>
                        <td class="numero"><strong>{int(row['vendas'])}</strong></td>
                        <td class="numero">{formatar_valor(row['faturamento'])}</td>
                        <td class="numero {roas_class}"><strong>{row['roas']:.2f}x</strong></td>
                        <td class="numero">{formatar_valor(row['cpl'])}</td>
                        <td class="numero">{formatar_valor(row['custo_por_venda']) if row['vendas'] > 0 else '-'}</td>
                        <td class="numero">{formatar_valor(row['taxa_conversao'], 'percentual')}</td>
                    </tr>
"""
    
    html += f"""
                </tbody>
            </table>
        </div>
        
        <div class="info-box">
            <h2>📊 Resumo Consolidado</h2>
            <table>
                <tbody>
                    <tr>
                        <td><strong>Total de Criativos Analisados</strong></td>
                        <td class="numero"><strong>{len(df_dados)}</strong></td>
                        <td>Criativos com investimento > R$ 0</td>
                    </tr>
                    <tr>
                        <td><strong>Criativos com Vendas</strong></td>
                        <td class="numero"><strong>{len(df_dados[df_dados['vendas'] > 0])}</strong></td>
                        <td>Criativos que geraram pelo menos 1 venda</td>
                    </tr>
                    <tr>
                        <td><strong>Investimento Total</strong></td>
                        <td class="numero"><strong>{formatar_valor(total_investimento)}</strong></td>
                        <td>Soma de todos os gastos na plataforma</td>
                    </tr>
                    <tr>
                        <td><strong>Faturamento Total</strong></td>
                        <td class="numero"><strong>{formatar_valor(total_faturamento)}</strong></td>
                        <td>Vendas rastreadas (Hotmart + TMB)</td>
                    </tr>
                    <tr>
                        <td><strong>ROAS Médio</strong></td>
                        <td class="numero"><strong>{roas_medio:.2f}x</strong></td>
                        <td>Faturamento / Investimento</td>
                    </tr>
                    <tr>
                        <td><strong>Vendas Rastreadas</strong></td>
                        <td class="numero"><strong>{total_vendas}</strong></td>
                        <td>Vendas com UTM_content identificado</td>
                    </tr>
                    <tr>
                        <td><strong>Custo por Venda Médio</strong></td>
                        <td class="numero"><strong>{formatar_valor(custo_venda_medio)}</strong></td>
                        <td>Investimento / Vendas</td>
                    </tr>
                    <tr>
                        <td><strong>Taxa de Conversão Média</strong></td>
                        <td class="numero"><strong>{formatar_valor(taxa_conversao_media, 'percentual')}</strong></td>
                        <td>Vendas / Leads</td>
                    </tr>
                    <tr>
                        <td><strong>Total de Leads</strong></td>
                        <td class="numero"><strong>{formatar_valor(total_leads, 'numero')}</strong></td>
                        <td>Leads capturados no CRM com UTM</td>
                    </tr>
                    <tr>
                        <td><strong>CPL Médio</strong></td>
                        <td class="numero"><strong>{formatar_valor(cpl_medio)}</strong></td>
                        <td>Investimento / Leads</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
    </div>
</body>
</html>
"""
    
    return html

# ========== GERAR OS 3 HTMLS ==========
print("\n" + "=" * 100)
print("GERADOR DE HTMLs POR PLATAFORMA - PBB-ABR-26")
print("=" * 100)

# Carregar CSVs
print("\n[1/3] Carregando dados...")
df_facebook = pd.read_csv(r'analises/[PES-MAI-26]/ANALISE_FACEBOOK_[PES-MAI-26].csv')
df_youtube = pd.read_csv(r'analises/[PES-MAI-26]/ANALISE_YOUTUBE_[PES-MAI-26].csv')
df_consolidada = pd.read_csv(r'analises/[PES-MAI-26]/ANALISE_CONSOLIDADA_[PES-MAI-26].csv')

print(f"   Facebook: {len(df_facebook)} criativos")
print(f"   YouTube: {len(df_youtube)} criativos")
print(f"   Consolidada: {len(df_consolidada)} criativos")

# Gerar HTMLs
print("\n[2/3] Gerando HTMLs...")

html_facebook = gerar_html_plataforma(
    "FACEBOOK - CAPTAÇÃO",
    df_facebook,
    "#1877f2",  # Azul Facebook
    "#0a4da3"
)

html_youtube = gerar_html_plataforma(
    "YOUTUBE - CAPTAÇÃO",
    df_youtube,
    "#ff0000",  # Vermelho YouTube
    "#c4302b"
)

html_consolidada = gerar_html_plataforma(
    "CONSOLIDADA DE CAPTAÇÃO (Facebook + YouTube)",
    df_consolidada,
    "#667eea",  # Roxo
    "#764ba2"
)

# Salvar arquivos
print("\n[3/3] Salvando arquivos...")

with open(r'analises/[PES-MAI-26]/ANALISE_FACEBOOK_[PES-MAI-26].html', 'w', encoding='utf-8') as f:
    f.write(adaptar_html_campaign(html_facebook))
print("   ✓ ANALISE_FACEBOOK_[PBB-ABR-26].html")

with open(r'analises/[PES-MAI-26]/ANALISE_YOUTUBE_[PES-MAI-26].html', 'w', encoding='utf-8') as f:
    f.write(adaptar_html_campaign(html_youtube))
print("   ✓ ANALISE_YOUTUBE_[PBB-ABR-26].html")

with open(r'analises/[PES-MAI-26]/ANALISE_CONSOLIDADA_[PES-MAI-26].html', 'w', encoding='utf-8') as f:
    f.write(adaptar_html_campaign(html_consolidada))
print("   ✓ ANALISE_CONSOLIDADA_[PBB-ABR-26].html")

print("\n" + "=" * 100)
print("CONCLUIDO! 3 HTMLs gerados com sucesso!")
print("=" * 100)
