#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Ads Video Performance Report - Hook Rate Analysis
Processa dados de vídeos e calcula Hook Rate
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

# Arquivo de entrada
VIDEOS_CSV = ANALISES_PATH / "Análise de Vídeos - [PI-JAN-26].csv"


def limpar_numero(valor):
    """Converte string com formato brasileiro para número"""
    if pd.isna(valor) or valor == '' or valor == '--':
        return 0
    if isinstance(valor, (int, float)):
        return float(valor)
    
    valor_str = str(valor).strip()
    valor_str = valor_str.replace('.', '').replace(',', '.')
    valor_str = re.sub(r'[^\d.-]', '', valor_str)
    
    try:
        return float(valor_str) if valor_str else 0
    except:
        return 0


def formatar_valor(valor, tipo='numero'):
    """Formata valores para exibição"""
    if pd.isna(valor) or valor is None:
        return '0'
    
    valor = float(valor)
    
    if tipo == 'moeda':
        return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    elif tipo == 'percentual':
        return f"{valor:.2f}%"
    elif tipo == 'numero':
        if valor >= 1000:
            return f"{valor:,.0f}".replace(',', '.')
        return f"{valor:.0f}"
    elif tipo == 'decimal':
        return f"{valor:.2f}"
    
    return str(valor)


def extrair_id_video(url):
    """Extrai ID do vídeo da URL do YouTube"""
    if pd.isna(url) or url == '' or url == '--':
        return None
    
    url_str = str(url)
    
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
    nome_str = re.sub(r'^AD\d+\s*-\s*', '', nome_str)
    return nome_str


def gerar_html_videos(df_videos):
    """Gera HTML de análise de vídeos com Hook Rate"""
    
    # Limpar dados numéricos
    cols_numericas = ['Impr.', 'Visualizações do TrueView', 'Cliques', 'Custo', 'Conversões',
                      'Vídeo assistido até 25%', 'Vídeo assistido até 50%', 
                      'Vídeo assistido até 75%', 'Vídeo assistido até 100%',
                      'Taxa de visualização do TrueView']
    
    for col in cols_numericas:
        if col in df_videos.columns:
            df_videos[col] = df_videos[col].apply(limpar_numero)
    
    # Processar dados de vídeos
    videos = []
    for idx, row in df_videos.iterrows():
        criativo_nome = extrair_nome_criativo(row['Nome do anúncio'])
        video_id = extrair_id_video(row['URL final'])
        
        impressoes = limpar_numero(row['Impr.'])
        views = limpar_numero(row['Visualizações do TrueView'])
        views_25 = limpar_numero(row['Vídeo assistido até 25%'])
        
        # ⭐ HOOK RATE = (Vídeos que chegaram aos 25% / Total de Impressões) × 100
        # Alternativa: Se não tiver 25%, usar TrueView views como proxy
        hook_rate = (views_25 / impressoes * 100) if impressoes > 0 else 0
        
        # View Rate
        view_rate = limpar_numero(row['Taxa de visualização do TrueView'])
        
        videos.append({
            'nome': criativo_nome,
            'video_id': video_id,
            'impressoes': impressoes,
            'views': views,
            'view_rate': view_rate,
            'views_25': views_25,
            'views_50': limpar_numero(row['Vídeo assistido até 50%']),
            'views_75': limpar_numero(row['Vídeo assistido até 75%']),
            'views_100': limpar_numero(row['Vídeo assistido até 100%']),
            'hook_rate': hook_rate,
            'cliques': limpar_numero(row['Cliques']),
            'custo': limpar_numero(row['Custo']),
            'conversoes': limpar_numero(row['Conversões']),
            'campanha': row['Campanha'],
            'url_final': row['URL final']
        })
    
    df_videos_proc = pd.DataFrame(videos)
    df_videos_proc = df_videos_proc[df_videos_proc['impressoes'] > 0]
    
    # Agregar vídeos únicos por Hook Rate
    videos_unicos = df_videos_proc.groupby('nome').agg({
        'impressoes': 'sum',
        'views': 'sum',
        'views_25': 'sum',
        'views_50': 'sum',
        'views_75': 'sum',
        'views_100': 'sum',
        'cliques': 'sum',
        'custo': 'sum',
        'conversoes': 'sum',
        'campanha': lambda x: list(x.unique())
    }).reset_index()
    
    # Recalcular métricas
    videos_unicos['view_rate'] = (videos_unicos['views'] / videos_unicos['impressoes'] * 100).fillna(0)
    videos_unicos['hook_rate'] = (videos_unicos['views_25'] / videos_unicos['impressoes'] * 100).fillna(0)
    videos_unicos['completion_25_rate'] = (videos_unicos['views_25'] / videos_unicos['views'] * 100).fillna(0)
    videos_unicos['completion_100_rate'] = (videos_unicos['views_100'] / videos_unicos['views'] * 100).fillna(0)
    
    videos_unicos = videos_unicos.sort_values('hook_rate', ascending=False)
    
    df_videos_proc = df_videos_proc.sort_values('hook_rate', ascending=False)
    
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Análise de Vídeos com Hook Rate - Google Ads</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; }
            .container { max-width: 1800px; margin: 0 auto; padding: 20px; }
            
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
            .header h1 { font-size: 32px; margin-bottom: 5px; }
            .header p { font-size: 14px; opacity: 0.9; }
            
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #667eea; }
            .stat-card h3 { font-size: 12px; color: #999; text-transform: uppercase; margin-bottom: 10px; }
            .stat-card .value { font-size: 28px; font-weight: bold; color: #667eea; }
            
            /* ===== TABELA HOOK RATE ===== */
            .summary-section { margin-bottom: 40px; }
            .summary-section h2 { margin: 30px 0 20px 0; color: #333; font-size: 24px; }
            .summary-table { width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .summary-table thead { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            .summary-table th { padding: 15px; text-align: left; font-weight: 600; border-bottom: none; font-size: 12px; text-transform: uppercase; }
            .summary-table td { padding: 12px 15px; border-bottom: 1px solid #e9ecef; }
            .summary-table tr:hover { background: #f8f9fa; }
            .summary-table .rank { font-weight: 700; color: #667eea; font-size: 16px; width: 40px; text-align: center; }
            .summary-table .metric { font-weight: 600; color: #667eea; }
            .hook-rate-high { color: #28a745; font-weight: 700; }
            .hook-rate-medium { color: #ffc107; font-weight: 700; }
            .hook-rate-low { color: #dc3545; font-weight: 700; }
            
            .chart-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; position: relative; height: 400px; }
            .chart-container h3 { margin-bottom: 20px; color: #333; }
            
            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .metric-box { background: white; padding: 15px; border-radius: 8px; border-left: 3px solid #667eea; }
            .metric-box .label { font-size: 11px; color: #999; text-transform: uppercase; }
            .metric-box .value { font-size: 24px; font-weight: bold; color: #667eea; margin-top: 5px; }
            
            .footer { text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #e9ecef; }
            
            .info-box { background: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .info-box strong { color: #1976D2; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📺 Análise de Vídeos - Hook Rate [PI-JAN-26]</h1>
                <p>Performance de Vídeos YouTube com Análise de Hook Rate</p>
                <p>Período: 1º de dezembro de 2025 - 31 de janeiro de 2026</p>
            </div>
            
            <div class="info-box">
                <strong>🎯 Hook Rate:</strong> Porcentagem de pessoas que assistiram pelo menos 25% do vídeo em relação ao total de impressões. Métrica essencial para avaliar a eficácia do "gancho" (primeiros 3 segundos).
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total de Impressões</h3>
                    <div class="value">""" + formatar_valor(videos_unicos['impressoes'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Visualizações</h3>
                    <div class="value">""" + formatar_valor(videos_unicos['views'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Hook Rate Médio</h3>
                    <div class="value">""" + formatar_valor(videos_unicos['hook_rate'].mean(), 'percentual') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Visualizações até 100%</h3>
                    <div class="value">""" + formatar_valor(videos_unicos['views_100'].sum(), 'numero') + """</div>
                </div>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="label">View Rate Médio</div>
                    <div class="value">""" + formatar_valor(videos_unicos['view_rate'].mean(), 'percentual') + """</div>
                </div>
                <div class="metric-box">
                    <div class="label">Taxa Conclusão 25%</div>
                    <div class="value">""" + formatar_valor(videos_unicos['completion_25_rate'].mean(), 'percentual') + """</div>
                </div>
                <div class="metric-box">
                    <div class="label">Taxa Conclusão 100%</div>
                    <div class="value">""" + formatar_valor(videos_unicos['completion_100_rate'].mean(), 'percentual') + """</div>
                </div>
                <div class="metric-box">
                    <div class="label">Custo Total</div>
                    <div class="value">""" + formatar_valor(videos_unicos['custo'].sum(), 'moeda') + """</div>
                </div>
            </div>
            
            <!-- GRÁFICO HOOK RATE -->
            <div class="chart-container">
                <h3>📊 Hook Rate por Vídeo (Top 15)</h3>
                <canvas id="hookRateChart"></canvas>
            </div>
            
            <!-- GRÁFICO FUNIL DE VISUALIZAÇÃO -->
            <div class="chart-container">
                <h3>📈 Funil de Visualização (Média)</h3>
                <canvas id="funnelChart"></canvas>
            </div>
            
            <!-- TABELA HOOK RATE -->
            <div class="summary-section">
                <h2>🎯 Ranking de Vídeos - Hook Rate (% que assistiram até 25%)</h2>
                <table class="summary-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th style="max-width: 200px;">Vídeo</th>
                            <th>Impressões</th>
                            <th>Visualizações</th>
                            <th>View Rate</th>
                            <th>Hook Rate ⭐</th>
                            <th>até 50%</th>
                            <th>até 75%</th>
                            <th>até 100%</th>
                            <th>Custo</th>
                            <th>Conversões</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    ranking = 1
    for idx, video in videos_unicos.iterrows():
        # Colorir Hook Rate por desempenho
        if video['hook_rate'] >= 20:
            hook_class = 'hook-rate-high'
        elif video['hook_rate'] >= 10:
            hook_class = 'hook-rate-medium'
        else:
            hook_class = 'hook-rate-low'
        
        html += f"""
                        <tr>
                            <td class="rank">#{ranking}</td>
                            <td><strong>{video['nome'][:40]}</strong></td>
                            <td class="metric">{formatar_valor(video['impressoes'], 'numero')}</td>
                            <td class="metric">{formatar_valor(video['views'], 'numero')}</td>
                            <td class="metric">{formatar_valor(video['view_rate'], 'percentual')}</td>
                            <td class="{hook_class}">{formatar_valor(video['hook_rate'], 'percentual')}</td>
                            <td class="metric">{formatar_valor(video['views_50'], 'numero')}</td>
                            <td class="metric">{formatar_valor(video['views_75'], 'numero')}</td>
                            <td class="metric">{formatar_valor(video['views_100'], 'numero')}</td>
                            <td class="metric">{formatar_valor(video['custo'], 'moeda')}</td>
                            <td class="metric" style="color: #28a745;"><strong>{formatar_valor(video['conversoes'], 'numero')}</strong></td>
                        </tr>
        """
        ranking += 1
    
    html += """
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                <p>Relatório gerado automaticamente | Google Ads - Video Performance Data</p>
                <p style="margin-top: 10px; font-size: 11px;">🎯 <strong>Interpretação:</strong> Hook Rate > 15% é excelente | 10-15% é bom | < 10% precisa melhorar</p>
            </div>
        </div>
        
        <script>
            const videos = """ + videos_unicos.head(15).to_json(orient='records') + """;
            
            // Gráfico Hook Rate
            const hookCtx = document.getElementById('hookRateChart').getContext('2d');
            new Chart(hookCtx, {
                type: 'bar',
                data: {
                    labels: videos.map(v => v.nome.substring(0, 25) + '...'),
                    datasets: [{
                        label: 'Hook Rate (%)',
                        data: videos.map(v => v.hook_rate),
                        backgroundColor: videos.map(v => v.hook_rate >= 20 ? '#28a745' : (v.hook_rate >= 10 ? '#ffc107' : '#dc3545')),
                        borderRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });
            
            // Gráfico Funil
            const funnelCtx = document.getElementById('funnelChart').getContext('2d');
            const avgCompletion25 = """ + str(videos_unicos['completion_25_rate'].mean()) + """;
            const avgCompletion50 = """ + str((videos_unicos['views_50'].sum() / videos_unicos['views'].sum() * 100)) + """;
            const avgCompletion75 = """ + str((videos_unicos['views_75'].sum() / videos_unicos['views'].sum() * 100)) + """;
            const avgCompletion100 = """ + str(videos_unicos['completion_100_rate'].mean()) + """;
            
            new Chart(funnelCtx, {
                type: 'bar',
                data: {
                    labels: ['Até 25%', 'Até 50%', 'Até 75%', 'Até 100%'],
                    datasets: [{
                        label: 'Taxa de Conclusão (%)',
                        data: [avgCompletion25, avgCompletion50, avgCompletion75, avgCompletion100],
                        backgroundColor: ['#667eea', '#764ba2', '#f5576c', '#f093fb'],
                        borderRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });
        </script>
    </body>
    </html>
    """
    
    return html


def main():
    """Executa geração do relatório"""
    
    print("=" * 60)
    print("📺 Google Ads Video Performance Report - Hook Rate")
    print("=" * 60)
    
    try:
        # Ler CSV
        print("\n📖 Lendo arquivo CSV...")
        print("  → Lendo Análise de Vídeos...")
        df_videos = pd.read_csv(VIDEOS_CSV, skiprows=2, encoding='utf-8')
        print(f"    ✓ {len(df_videos)} registros")
        
        # Gerar HTML
        print("\n🎨 Gerando relatório HTML...")
        print("  → Gerando ANALISE_GOOGLE_VIDEOS_HOOK_RATE_[PES-JAN-26].html...")
        html_videos = gerar_html_videos(df_videos)
        output_file = OUTPUT_PATH / "ANALISE_GOOGLE_VIDEOS_HOOK_RATE_[PES-JAN-26].html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_videos)
        print(f"    ✓ Salvo em {output_file.name}")
        
        print("\n" + "=" * 60)
        print("✅ Relatório de Hook Rate gerado com sucesso!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
