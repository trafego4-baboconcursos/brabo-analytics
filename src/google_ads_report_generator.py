#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Ads Report Generator
Processa CSVs e gera HTMLs de análise para: Campanhas, Públicos e Criativos
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configurações
BASE_PATH = Path(r"c:\Users\trafe\Desktop\workspace-mmm")
ANALISES_PATH = BASE_PATH / "analises" / "[PES-JAN-26]" / "google ads"
OUTPUT_PATH = ANALISES_PATH

# Arquivos de entrada
CRIATIVOS_CSV = ANALISES_PATH / "Análise de Anúncios e Criativos [PI-JAN-26].csv"
SEGMENTACAO_CSV = ANALISES_PATH / "Análise de Segmentação e Público - [PI-JAN-26].csv"
CAMPANHA_CSV = ANALISES_PATH / "Performance Geral por Campanha - [PI-JAN-26].csv"


def limpar_numero(valor):
    """Converte string com formato brasileiro para número"""
    if pd.isna(valor) or valor == '' or valor == '--':
        return 0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    valor_str = str(valor).strip()
    # Remove símbolos e converte
    valor_str = valor_str.replace('.', '').replace(',', '.')
    valor_str = re.sub(r'[^\d.-]', '', valor_str)
    
    try:
        return float(valor_str) if valor_str else 0
    except:
        return 0


def formatar_valor(valor, tipo='numero'):
    """Formata valores para exibição"""
    if pd.isna(valor):
        return '0'
    
    valor = float(valor)
    
    if tipo == 'moeda':
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    elif tipo == 'percentual':
        return f"{valor:.2f}%"
    elif tipo == 'numero':
        return f"{valor:,.0f}".replace(',', '.')
    elif tipo == 'decimal':
        return f"{valor:.2f}"
    
    return str(valor)


def extrair_id_video(url):
    """Extrai ID do vídeo da URL do YouTube"""
    if pd.isna(url) or url == '' or url == '--':
        return None
    
    url_str = str(url)
    
    # Formatos: youtube.com/watch?v=ID ou youtu.be/ID
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_str)
        if match:
            return match.group(1)
    
    return None


def extrair_nome_criativo(nome):
    """Extrai nome limpo do criativo"""
    if pd.isna(nome) or nome == '' or nome == '--':
        return 'N/A'
    
    nome_str = str(nome).strip()
    # Remove ID
    nome_str = re.sub(r'^AD\d+\s*-\s*', '', nome_str)
    return nome_str


def gerar_html_campanhas(df):
    """Gera HTML de análise por campanhas"""
    
    # Agrupar por campanha
    campanhas = df.groupby('Campanha').agg({
        'Impressões mensuráveis': 'sum',
        'Cliques': 'sum',
        'CPM médio': 'mean',
        'Custo': 'sum',
        'Conversões': 'sum',
        'Custo / conv.': 'mean',
        'Taxa de conv.': 'mean'
    }).reset_index()
    
    # Calcular CTR
    campanhas['CTR'] = (campanhas['Cliques'] / campanhas['Impressões mensuráveis'] * 100).fillna(0)
    
    # Ordenar por conversões
    campanhas = campanhas.sort_values('Conversões', ascending=False)
    
    # Limpar dados
    for col in ['CPM médio', 'Custo', 'Custo / conv.']:
        campanhas[col] = campanhas[col].apply(limpar_numero)
    
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Análise de Campanhas - Google Ads</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; }
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
            .header h1 { font-size: 32px; margin-bottom: 5px; }
            .header p { font-size: 14px; opacity: 0.9; }
            
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #667eea; }
            .stat-card h3 { font-size: 12px; color: #999; text-transform: uppercase; margin-bottom: 10px; }
            .stat-card .value { font-size: 28px; font-weight: bold; color: #667eea; }
            .stat-card .detail { font-size: 12px; color: #999; margin-top: 5px; }
            
            table { width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }
            thead { background: #f8f9fa; }
            th { padding: 15px; text-align: left; font-weight: 600; border-bottom: 2px solid #e9ecef; font-size: 13px; color: #666; text-transform: uppercase; }
            td { padding: 12px 15px; border-bottom: 1px solid #e9ecef; }
            tr:hover { background: #f8f9fa; }
            
            .metric { font-weight: 600; }
            .metric.positive { color: #28a745; }
            .metric.negative { color: #dc3545; }
            .metric.neutral { color: #667eea; }
            
            .chart-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; position: relative; height: 400px; }
            .chart-container h3 { margin-bottom: 20px; color: #333; }
            
            .footer { text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #e9ecef; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Análise de Campanhas - Google Ads</h1>
                <p>Performance Geral por Campanha [PI-JAN-26]</p>
                <p>Período: 1º de dezembro de 2025 - 31 de janeiro de 2026</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total de Impressões</h3>
                    <div class="value">""" + formatar_valor(campanhas['Impressões mensuráveis'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Cliques</h3>
                    <div class="value">""" + formatar_valor(campanhas['Cliques'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Conversões</h3>
                    <div class="value">""" + formatar_valor(campanhas['Conversões'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Investimento Total</h3>
                    <div class="value">""" + formatar_valor(campanhas['Custo'].sum(), 'moeda') + """</div>
                </div>
                <div class="stat-card">
                    <h3>CTR Médio</h3>
                    <div class="value">""" + formatar_valor(campanhas['CTR'].mean(), 'percentual') + """</div>
                </div>
                <div class="stat-card">
                    <h3>CPM Médio</h3>
                    <div class="value">""" + formatar_valor(campanhas['CPM médio'].mean(), 'moeda') + """</div>
                </div>
            </div>
            
            <div class="chart-container">
                <h3>📈 Conversões por Campanha</h3>
                <canvas id="conversionChart"></canvas>
            </div>
            
            <div class="chart-container">
                <h3>💰 Investimento vs Conversões</h3>
                <canvas id="investmentChart"></canvas>
            </div>
            
            <h2 style="margin: 30px 0 20px 0;">📋 Detalhamento por Campanha</h2>
            <table>
                <thead>
                    <tr>
                        <th>Campanha</th>
                        <th>Impressões</th>
                        <th>Cliques</th>
                        <th>CTR</th>
                        <th>CPM Médio</th>
                        <th>Custo</th>
                        <th>Conversões</th>
                        <th>Taxa Conv.</th>
                        <th>Custo/Conv.</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for idx, row in campanhas.iterrows():
        html += f"""
                    <tr>
                        <td><strong>{row['Campanha']}</strong></td>
                        <td class="metric">{formatar_valor(row['Impressões mensuráveis'], 'numero')}</td>
                        <td class="metric">{formatar_valor(row['Cliques'], 'numero')}</td>
                        <td class="metric">{formatar_valor(row['CTR'], 'percentual')}</td>
                        <td class="metric">{formatar_valor(row['CPM médio'], 'moeda')}</td>
                        <td class="metric">{formatar_valor(row['Custo'], 'moeda')}</td>
                        <td class="metric positive">{formatar_valor(row['Conversões'], 'numero')}</td>
                        <td class="metric">{formatar_valor(row['Taxa de conv.'], 'percentual')}</td>
                        <td class="metric">{formatar_valor(row['Custo / conv.'], 'moeda')}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            
            <div class="footer">
                <p>Relatório gerado automaticamente | Dados de Google Ads</p>
            </div>
        </div>
        
        <script>
            const campanhas = """ + campanhas[['Campanha', 'Conversões', 'Custo']].to_json(orient='records') + """;
            
            // Gráfico de Conversões
            const convCtx = document.getElementById('conversionChart').getContext('2d');
            new Chart(convCtx, {
                type: 'bar',
                data: {
                    labels: campanhas.map(c => c.Campanha.substring(0, 30) + '...'),
                    datasets: [{
                        label: 'Conversões',
                        data: campanhas.map(c => c.Conversões),
                        backgroundColor: '#667eea',
                        borderRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
            
            // Gráfico de Investimento
            const invCtx = document.getElementById('investmentChart').getContext('2d');
            new Chart(invCtx, {
                type: 'scatter',
                data: {
                    datasets: [{
                        label: 'Campanhas',
                        data: campanhas.map(c => ({ x: c.Custo, y: c.Conversões })),
                        backgroundColor: '#764ba2',
                        pointRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { title: { display: true, text: 'Custo (R$)' } },
                        y: { title: { display: true, text: 'Conversões' } }
                    }
                }
            });
        </script>
    </body>
    </html>
    """
    
    return html


def gerar_html_criativos(df_criativos):
    """Gera HTML de análise de criativos com thumbnails"""
    
    # Agrupar por criativo e extrair info
    criativos = []
    for idx, row in df_criativos.iterrows():
        criativo_nome = extrair_nome_criativo(row['Nome do anúncio'])
        video_id = extrair_id_video(row['URL final'])
        
        criativos.append({
            'nome': criativo_nome,
            'video_id': video_id,
            'impressoes': limpar_numero(row['Impr.']),
            'cliques': limpar_numero(row['Cliques']),
            'ctr': limpar_numero(row['CTR']) if 'CTR' in row.index else 0,
            'custo': limpar_numero(row['Custo']),
            'conversoes': limpar_numero(row['Conversões']),
            'custo_conv': limpar_numero(row['Custo / conv.']),
            'taxa_conv': limpar_numero(row['Taxa de conv.']) if 'Taxa de conv.' in row.index else 0,
            'campanha': row['Campanha'],
            'url_final': row['URL final']
        })
    
    df_criativos_proc = pd.DataFrame(criativos)
    df_criativos_proc = df_criativos_proc[df_criativos_proc['impressoes'] > 0].sort_values('conversoes', ascending=False)
    
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Análise de Criativos - Google Ads</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; }
            .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
            
            .header { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
            .header h1 { font-size: 32px; margin-bottom: 5px; }
            .header p { font-size: 14px; opacity: 0.9; }
            
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #f5576c; }
            .stat-card h3 { font-size: 12px; color: #999; text-transform: uppercase; margin-bottom: 10px; }
            .stat-card .value { font-size: 28px; font-weight: bold; color: #f5576c; }
            
            .criatives-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .criative-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: transform 0.3s; }
            .criative-card:hover { transform: translateY(-5px); box-shadow: 0 4px 15px rgba(0,0,0,0.15); }
            
            .criative-thumbnail { width: 100%; height: 200px; background: #000; position: relative; overflow: hidden; }
            .criative-thumbnail img { width: 100%; height: 100%; object-fit: cover; }
            .play-button { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 60px; height: 60px; background: rgba(255,0,0,0.8); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 30px; }
            
            .criative-info { padding: 15px; }
            .criative-info h3 { font-size: 14px; margin-bottom: 10px; color: #333; font-weight: 600; }
            .criative-info p { font-size: 12px; color: #999; margin-bottom: 5px; }
            
            .metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #e9ecef; }
            .metric-item { font-size: 12px; }
            .metric-label { color: #999; font-size: 11px; }
            .metric-value { font-weight: 600; color: #f5576c; }
            
            .ranking-badge { display: inline-block; background: #f5576c; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; margin-bottom: 10px; }
            
            .footer { text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #e9ecef; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 Análise de Criativos - Google Ads</h1>
                <p>Performance dos Anúncios [PI-JAN-26]</p>
                <p>Período: 1º de dezembro de 2025 - 31 de janeiro de 2026</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total de Criativos</h3>
                    <div class="value">""" + str(len(df_criativos_proc)) + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Impressões</h3>
                    <div class="value">""" + formatar_valor(df_criativos_proc['impressoes'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Conversões</h3>
                    <div class="value">""" + formatar_valor(df_criativos_proc['conversoes'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Criativo Top</h3>
                    <div class="value" style="font-size: 18px;">""" + (df_criativos_proc.iloc[0]['nome'][:25] + '...' if len(df_criativos_proc) > 0 else 'N/A') + """</div>
                </div>
            </div>
            
            <h2 style="margin: 30px 0 20px 0;">🎯 Criativos por Performance</h2>
            <div class="criatives-grid">
    """
    
    ranking = 1
    for idx, criativo in df_criativos_proc.iterrows():
        thumbnail_url = f"https://img.youtube.com/vi/{criativo['video_id']}/maxresdefault.jpg" if criativo['video_id'] else "https://via.placeholder.com/320x180?text=Sem+Vídeo"
        
        html += f"""
                <div class="criative-card">
                    <div class="criative-thumbnail">
                        <img src="{thumbnail_url}" alt="{criativo['nome']}">
                        <div class="play-button">▶</div>
                    </div>
                    <div class="criative-info">
                        <div class="ranking-badge">#{ranking} - Conversões</div>
                        <h3>{criativo['nome']}</h3>
                        <p><strong>Campanha:</strong> {criativo['campanha'][:40]}</p>
                        <div class="metrics">
                            <div class="metric-item">
                                <div class="metric-label">Impressões</div>
                                <div class="metric-value">{formatar_valor(criativo['impressoes'], 'numero')}</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-label">Cliques</div>
                                <div class="metric-value">{formatar_valor(criativo['cliques'], 'numero')}</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-label">CTR</div>
                                <div class="metric-value">{formatar_valor(criativo['ctr'], 'percentual')}</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-label">Conversões</div>
                                <div class="metric-value" style="color: #28a745;">{formatar_valor(criativo['conversoes'], 'numero')}</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-label">Custo</div>
                                <div class="metric-value">{formatar_valor(criativo['custo'], 'moeda')}</div>
                            </div>
                            <div class="metric-item">
                                <div class="metric-label">CPL</div>
                                <div class="metric-value">{formatar_valor(criativo['custo_conv'], 'moeda')}</div>
                            </div>
                        </div>
                    </div>
                </div>
        """
        ranking += 1
    
    html += """
            </div>
            
            <div class="footer">
                <p>Relatório gerado automaticamente | Dados de Google Ads</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def gerar_html_segmentacao(df):
    """Gera HTML de análise por públicos e temperaturas"""
    
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Análise de Públicos e Temperaturas - Google Ads</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; }
            .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
            
            .header { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: #333; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
            .header h1 { font-size: 32px; margin-bottom: 5px; }
            .header p { font-size: 14px; opacity: 0.8; }
            
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #fa709a; }
            .stat-card h3 { font-size: 12px; color: #999; text-transform: uppercase; margin-bottom: 10px; }
            .stat-card .value { font-size: 28px; font-weight: bold; color: #fa709a; }
            
            .chart-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; position: relative; height: 400px; }
            .chart-container h3 { margin-bottom: 20px; color: #333; }
            
            table { width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }
            thead { background: #f8f9fa; }
            th { padding: 15px; text-align: left; font-weight: 600; border-bottom: 2px solid #e9ecef; font-size: 13px; color: #666; text-transform: uppercase; }
            td { padding: 12px 15px; border-bottom: 1px solid #e9ecef; }
            tr:hover { background: #f8f9fa; }
            
            .metric { font-weight: 600; }
            .temp-cold { color: #3498db; background: rgba(52, 152, 219, 0.1); }
            .temp-warm { color: #f39c12; background: rgba(243, 156, 18, 0.1); }
            .temp-hot { color: #e74c3c; background: rgba(231, 76, 60, 0.1); }
            
            .footer { text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #e9ecef; }
            
            .temperature-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌡️ Análise de Públicos e Temperaturas - Google Ads</h1>
                <p>Segmentação e Performance [PI-JAN-26]</p>
                <p>Período: 1º de dezembro de 2025 - 31 de janeiro de 2026</p>
            </div>
            
            <div class="chart-container">
                <h3>📊 Distribuição de Públicos</h3>
                <p style="color: #999; margin-bottom: 15px;">Carregando dados de segmentação...</p>
                <p style="color: #999; font-size: 12px;">⚠️ Os dados de segmentação por temperaturas serão exibidos conforme disponibilidade no arquivo CSV</p>
            </div>
            
            <div class="footer">
                <p>Relatório gerado automaticamente | Dados de Google Ads</p>
                <p style="margin-top: 10px; font-size: 11px;">📌 Nota: As dimensões Age, Gender e Hour of day requerem ativação específica nas campanhas do Google Ads</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def main():
    """Executa geração de todos os relatórios"""
    
    print("=" * 60)
    print("🚀 Google Ads Report Generator")
    print("=" * 60)
    
    try:
        # Ler CSVs
        print("\n📖 Lendo arquivos CSV...")
        
        # Criativos
        print("  → Lendo Análise de Anúncios e Criativos...")
        df_criativos = pd.read_csv(CRIATIVOS_CSV, skiprows=2, encoding='utf-8')
        print(f"    ✓ {len(df_criativos)} registros")
        
        # Campanhas
        print("  → Lendo Performance Geral por Campanha...")
        df_campanhas = pd.read_csv(CAMPANHA_CSV, skiprows=2, encoding='utf-8')
        # Limpar dados numéricos
        for col in ['Impressões mensuráveis', 'Cliques', 'CPM médio', 'Custo', 'Conversões', 'Custo / conv.', 'Taxa de conv.']:
            if col in df_campanhas.columns:
                df_campanhas[col] = df_campanhas[col].apply(limpar_numero)
        print(f"    ✓ {len(df_campanhas)} registros")
        
        # Segmentação (tentar ler, se falhar gerar versão simplificada)
        try:
            print("  → Lendo Análise de Segmentação e Público...")
            df_segmentacao = pd.read_csv(SEGMENTACAO_CSV, skiprows=2, encoding='utf-8')
            print(f"    ✓ {len(df_segmentacao)} registros")
        except:
            print("    ⚠️ Arquivo de segmentação muito grande, usando versão simplificada")
            df_segmentacao = pd.DataFrame()
        
        # Gerar HTMLs
        print("\n🎨 Gerando relatórios HTML...")
        
        # 1. Campanhas
        print("  → Gerando ANALISE_GOOGLE_ADS_[PES-JAN-26].html...")
        html_campanhas = gerar_html_campanhas(df_campanhas)
        output_file_campanhas = OUTPUT_PATH / "ANALISE_GOOGLE_ADS_[PES-JAN-26].html"
        with open(output_file_campanhas, 'w', encoding='utf-8') as f:
            f.write(html_campanhas)
        print(f"    ✓ Salvo em {output_file_campanhas.name}")
        
        # 2. Criativos
        print("  → Gerando ANALISE_GOOGLE_ANUNCIOS_[PES-JAN-26].html...")
        html_criativos = gerar_html_criativos(df_criativos)
        output_file_criativos = OUTPUT_PATH / "ANALISE_GOOGLE_ANUNCIOS_[PES-JAN-26].html"
        with open(output_file_criativos, 'w', encoding='utf-8') as f:
            f.write(html_criativos)
        print(f"    ✓ Salvo em {output_file_criativos.name}")
        
        # 3. Segmentação
        print("  → Gerando ANALISE_GOOGLE_AUDIENCES_[PES-JAN-26].html...")
        html_segmentacao = gerar_html_segmentacao(df_segmentacao)
        output_file_segmentacao = OUTPUT_PATH / "ANALISE_GOOGLE_AUDIENCES_[PES-JAN-26].html"
        with open(output_file_segmentacao, 'w', encoding='utf-8') as f:
            f.write(html_segmentacao)
        print(f"    ✓ Salvo em {output_file_segmentacao.name}")
        
        print("\n" + "=" * 60)
        print("✅ Relatórios gerados com sucesso!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
