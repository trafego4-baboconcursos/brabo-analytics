#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Ads Criativos Report - VERSÃO COM HOOK RATE
Integra dados de Hook Rate do relatório de vídeos
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
    if pd.isna(valor):
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


def gerar_html_criativos_com_hook(df_criativos, df_videos):
    """Gera HTML de análise de criativos com Hook Rate integrado"""
    
    # Limpar dados de vídeos
    cols_numericas_video = ['Impr.', 'Vídeo assistido até 25%']
    for col in cols_numericas_video:
        if col in df_videos.columns:
            df_videos[col] = df_videos[col].apply(limpar_numero)
    
    # Calcular Hook Rate por anúncio do CSV de vídeos
    df_videos['Hook Rate'] = (df_videos['Vídeo assistido até 25%'] / df_videos['Impr.'] * 100).fillna(0)
    
    # Criar dicionário de Hook Rate por Nome do anúncio
    hook_rate_dict = dict(zip(df_videos['Nome do anúncio'], df_videos['Hook Rate']))
    
    # Processar dados de criativos
    criativos = []
    for idx, row in df_criativos.iterrows():
        criativo_nome = extrair_nome_criativo(row['Nome do anúncio'])
        video_id = extrair_id_video(row['URL final'])
        
        # Extrair hook (título)
        hook = row['Título'] if pd.notna(row['Título']) and row['Título'] != '--' else ''
        
        # Pegar Hook Rate do dicionário
        hook_rate = hook_rate_dict.get(row['Nome do anúncio'], 0)
        
        criativos.append({
            'nome': criativo_nome,
            'hook': hook,
            'video_id': video_id,
            'impressoes': limpar_numero(row['Impr.']),
            'cliques': limpar_numero(row['Cliques']),
            'ctr': limpar_numero(row['CTR']) if 'CTR' in row.index else 0,
            'custo': limpar_numero(row['Custo']),
            'conversoes': limpar_numero(row['Conversões']),
            'custo_conv': limpar_numero(row['Custo / conv.']),
            'taxa_conv': limpar_numero(row['Taxa de conv.']) if 'Taxa de conv.' in row.index else 0,
            'hook_rate': hook_rate,
            'campanha': row['Campanha'],
            'url_final': row['URL final']
        })
    
    df_criativos_proc = pd.DataFrame(criativos)
    df_criativos_proc = df_criativos_proc[df_criativos_proc['impressoes'] > 0]
    
    # Agregar criativos únicos
    criativos_unicos = df_criativos_proc.groupby('nome').agg({
        'impressoes': 'sum',
        'cliques': 'sum',
        'custo': 'sum',
        'conversoes': 'sum',
        'hook': 'first',
        'hook_rate': 'mean',  # Média de Hook Rate
        'campanha': lambda x: list(x.unique())
    }).reset_index()
    
    criativos_unicos['ctr'] = (criativos_unicos['cliques'] / criativos_unicos['impressoes'] * 100).fillna(0)
    criativos_unicos['cpl'] = (criativos_unicos['custo'] / criativos_unicos['conversoes']).fillna(0)
    criativos_unicos = criativos_unicos.sort_values('conversoes', ascending=False)
    
    df_criativos_proc = df_criativos_proc.sort_values('conversoes', ascending=False)
    
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
            
            /* ===== TABELA RESUMIDA ===== */
            .summary-section { margin-bottom: 40px; }
            .summary-section h2 { margin: 30px 0 20px 0; color: #333; font-size: 24px; }
            .summary-table { width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .summary-table thead { background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); color: white; }
            .summary-table th { padding: 15px; text-align: left; font-weight: 600; border-bottom: none; font-size: 12px; text-transform: uppercase; }
            .summary-table td { padding: 12px 15px; border-bottom: 1px solid #e9ecef; }
            .summary-table tr:hover { background: #f8f9fa; }
            .summary-table .rank { font-weight: 700; color: #f5576c; font-size: 16px; width: 40px; text-align: center; }
            .summary-table .metric { font-weight: 600; color: #667eea; }
            .summary-table .campanhas-list { font-size: 11px; color: #999; max-width: 250px; }
            
            .hook-rate-high { color: #28a745; font-weight: 700; }
            .hook-rate-medium { color: #ffc107; font-weight: 700; }
            .hook-rate-low { color: #dc3545; font-weight: 700; }
            
            /* ===== CARDS DETALHADOS ===== */
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
            .hook-rate-badge { display: inline-block; background: #667eea; color: white; padding: 6px 12px; border-radius: 4px; font-size: 12px; margin: 8px 0; font-weight: 600; }
            
            .footer { text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #e9ecef; }
            
            .section-divider { height: 2px; background: linear-gradient(90deg, transparent, #f5576c, transparent); margin: 40px 0; }
            
            .info-box { background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .info-box strong { color: #856404; }
            
            /* ===== FILTROS ===== */
            .filter-section { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .filter-section h3 { margin-bottom: 15px; color: #333; font-size: 14px; font-weight: 600; }
            .filters-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .filter-input { padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
            .filter-input:focus { outline: none; border-color: #f5576c; box-shadow: 0 0 0 3px rgba(245, 87, 108, 0.1); }
            .btn-reset { padding: 10px 20px; background: #f5576c; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
            .btn-reset:hover { background: #e73f54; }
            .filter-result { font-size: 12px; color: #999; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 Análise de Criativos - Google Ads</h1>
                <p>Performance dos Anúncios com Hook Rate [PI-JAN-26]</p>
                <p>Período: 1º de dezembro de 2025 - 31 de janeiro de 2026</p>
            </div>
            
            <div class="info-box">
                <strong>📺 Novo:</strong> Agora com integração de Hook Rate! Veja qual % de espectadores ficou gancho no primeiros 25% do vídeo.
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total de Criativos Únicos</h3>
                    <div class="value">""" + str(len(criativos_unicos)) + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Impressões</h3>
                    <div class="value">""" + formatar_valor(criativos_unicos['impressoes'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Total de Conversões</h3>
                    <div class="value">""" + formatar_valor(criativos_unicos['conversoes'].sum(), 'numero') + """</div>
                </div>
                <div class="stat-card">
                    <h3>Hook Rate Médio</h3>
                    <div class="value">""" + formatar_valor(criativos_unicos['hook_rate'].mean(), 'percentual') + """</div>
                </div>
            </div>
            
            <!-- ===== SEÇÃO RESUMIDA ===== -->
            <div class="summary-section">
                <h2>📊 Resumo de Criativos Únicos - Ranking</h2>
                
                <!-- FILTROS -->
                <div class="filter-section">
                    <h3>🔍 Filtrar Tabela</h3>
                    <div class="filters-grid">
                        <div>
                            <input type="text" id="filterNome" class="filter-input" placeholder="Buscar por criativo...">
                        </div>
                        <div>
                            <select id="filterHookRate" class="filter-input">
                                <option value="">Hook Rate: Todos</option>
                                <option value="15">Hook Rate ≥ 15% (Excelente)</option>
                                <option value="8">Hook Rate 8-15% (Bom)</option>
                                <option value="0">Hook Rate < 8% (Precisa melhorar)</option>
                            </select>
                        </div>
                        <div>
                            <input type="number" id="filterConversoes" class="filter-input" placeholder="Conversões mínimas...">
                        </div>
                        <div>
                            <button class="btn-reset" onclick="resetarFiltros()">Limpar Filtros</button>
                        </div>
                    </div>
                    <div class="filter-result" id="filterResult"></div>
                </div>
                
                <table class="summary-table" id="tabelaRanking">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th style="max-width: 200px;">Criativo</th>
                            <th style="max-width: 250px;">Hook (Título)</th>
                            <th>Impressões</th>
                            <th>Cliques</th>
                            <th>CTR</th>
                            <th>🎯 Hook Rate</th>
                            <th>Custo</th>
                            <th>Conversões</th>
                            <th>CPL</th>
                            <th>Campanhas</th>
                        </tr>
                    </thead>
                    <tbody id="tabelaBody">
    """
    
    ranking = 1
    for idx, criativo in criativos_unicos.iterrows():
        campanhas_str = ', '.join(criativo['campanha'][:2])
        if len(criativo['campanha']) > 2:
            campanhas_str += f" (+{len(criativo['campanha'])-2})"
        
        # Colorir Hook Rate
        if criativo['hook_rate'] >= 15:
            hook_class = 'hook-rate-high'
        elif criativo['hook_rate'] >= 8:
            hook_class = 'hook-rate-medium'
        else:
            hook_class = 'hook-rate-low'
        
        html += f"""
                        <tr>
                            <td class="rank">#{ranking}</td>
                            <td><strong>{criativo['nome'][:40]}</strong></td>
                            <td><em>{criativo['hook'][:50] if criativo['hook'] and criativo['hook'] != '--' else '—'}</em></td>
                            <td class="metric">{formatar_valor(criativo['impressoes'], 'numero')}</td>
                            <td class="metric">{formatar_valor(criativo['cliques'], 'numero')}</td>
                            <td class="metric">{formatar_valor(criativo['ctr'], 'percentual')}</td>
                            <td class="{hook_class}">{formatar_valor(criativo['hook_rate'], 'percentual')}</td>
                            <td class="metric">{formatar_valor(criativo['custo'], 'moeda')}</td>
                            <td class="metric" style="color: #28a745; font-size: 14px;"><strong>{formatar_valor(criativo['conversoes'], 'numero')}</strong></td>
                            <td class="metric">{formatar_valor(criativo['cpl'], 'moeda')}</td>
                            <td class="campanhas-list" title="{', '.join(criativo['campanha'])}">{campanhas_str}</td>
                        </tr>
        """
        ranking += 1
    
    html += """
                    </tbody>
                </table>
            </div>
            
            <div class="section-divider"></div>
            
            <!-- ===== CARDS DETALHADOS ===== -->
            <h2 style="margin: 30px 0 20px 0;">🎯 Criativos - Análise Detalhada por Campanha</h2>
            <div class="criatives-grid">
    """
    
    ranking = 1
    for idx, criativo in df_criativos_proc.iterrows():
        thumbnail_url = f"https://img.youtube.com/vi/{criativo['video_id']}/maxresdefault.jpg" if criativo['video_id'] else "https://via.placeholder.com/320x180?text=Sem+Vídeo"
        
        # Colorir Hook Rate
        if criativo['hook_rate'] >= 15:
            hook_class = 'hook-rate-high'
        elif criativo['hook_rate'] >= 8:
            hook_class = 'hook-rate-medium'
        else:
            hook_class = 'hook-rate-low'
        
        html += f"""
                <div class="criative-card">
                    <div class="criative-thumbnail">
                        <img src="{thumbnail_url}" alt="{criativo['nome']}">
                        <div class="play-button">▶</div>
                    </div>
                    <div class="criative-info">
                        <div class="ranking-badge">Campanha: #{ranking}</div>
                        <h3>{criativo['nome']}</h3>
                        <div class="hook-rate-badge {hook_class}">🎯 Hook Rate: {formatar_valor(criativo['hook_rate'], 'percentual')}</div>
                        {f'<p><strong>Hook:</strong> <em>{criativo["hook"]}</em></p>' if criativo['hook'] and criativo['hook'] != '--' else ''}
                        <p><strong>Campanha:</strong> {criativo['campanha'][:45]}</p>
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
                <p style="margin-top: 10px; font-size: 11px;">📌 Hook Rate ≥15% = Excelente | 8-15% = Bom | <8% = Precisa melhorar</p>
            </div>
        </div>
        
        <script>
            // Dados da tabela
            const dadosRanking = """ + criativos_unicos.to_json(orient='records') + """;
            
            // Renderizar tabela inicial
            function renderizarTabela(dados) {
                const tbody = document.getElementById('tabelaBody');
                tbody.innerHTML = '';
                
                dados.forEach((criativo, index) => {
                    const hookClass = criativo.hook_rate >= 15 ? 'hook-rate-high' : (criativo.hook_rate >= 8 ? 'hook-rate-medium' : 'hook-rate-low');
                    const campanhas_str = criativo.campanha.slice(0, 2).join(', ') + (criativo.campanha.length > 2 ? ` (+${criativo.campanha.length-2})` : '');
                    const hookText = criativo.hook && criativo.hook !== '--' ? criativo.hook.substring(0, 50) : '—';
                    
                    const row = `
                        <tr>
                            <td class="rank">#${index + 1}</td>
                            <td><strong>${criativo.nome.substring(0, 40)}</strong></td>
                            <td><em>${hookText}</em></td>
                            <td class="metric">${criativo.impressoes.toLocaleString('pt-BR')}</td>
                            <td class="metric">${criativo.cliques.toLocaleString('pt-BR')}</td>
                            <td class="metric">${criativo.ctr.toFixed(2)}%</td>
                            <td class="${hookClass}">${criativo.hook_rate.toFixed(2)}%</td>
                            <td class="metric">R$ ${criativo.custo.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                            <td class="metric" style="color: #28a745; font-size: 14px;"><strong>${criativo.conversoes.toLocaleString('pt-BR')}</strong></td>
                            <td class="metric">R$ ${criativo.cpl.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                            <td class="campanhas-list" title="${criativo.campanha.join(', ')}">${campanhas_str}</td>
                        </tr>
                    `;
                    tbody.innerHTML += row;
                });
                
                document.getElementById('filterResult').textContent = `Mostrando ${dados.length} de ${dadosRanking.length} criativos`;
            }
            
            // Aplicar filtros
            function aplicarFiltros() {
                const nomeFiltro = document.getElementById('filterNome').value.toLowerCase();
                const hookRateFiltro = parseFloat(document.getElementById('filterHookRate').value) || null;
                const conversoesFiltro = parseFloat(document.getElementById('filterConversoes').value) || 0;
                
                const dadosFiltrados = dadosRanking.filter(criativo => {
                    // Filtro por nome
                    const nomeMatch = criativo.nome.toLowerCase().includes(nomeFiltro);
                    
                    // Filtro por Hook Rate
                    let hookMatch = true;
                    if (hookRateFiltro !== null) {
                        if (hookRateFiltro === 15) {
                            hookMatch = criativo.hook_rate >= 15;
                        } else if (hookRateFiltro === 8) {
                            hookMatch = criativo.hook_rate >= 8 && criativo.hook_rate < 15;
                        } else if (hookRateFiltro === 0) {
                            hookMatch = criativo.hook_rate < 8;
                        }
                    }
                    
                    // Filtro por conversões mínimas
                    const conversoesMatch = criativo.conversoes >= conversoesFiltro;
                    
                    return nomeMatch && hookMatch && conversoesMatch;
                });
                
                renderizarTabela(dadosFiltrados);
            }
            
            // Resetar filtros
            function resetarFiltros() {
                document.getElementById('filterNome').value = '';
                document.getElementById('filterHookRate').value = '';
                document.getElementById('filterConversoes').value = '';
                renderizarTabela(dadosRanking);
            }
            
            // Event listeners para filtros
            document.getElementById('filterNome').addEventListener('keyup', aplicarFiltros);
            document.getElementById('filterHookRate').addEventListener('change', aplicarFiltros);
            document.getElementById('filterConversoes').addEventListener('input', aplicarFiltros);
            
            // Renderizar tabela inicial
            renderizarTabela(dadosRanking);
    </body>
    </html>
    """
    
    return html


def main():
    """Executa geração do relatório"""
    
    print("=" * 60)
    print("🎬 Google Ads Criativos Report - COM HOOK RATE")
    print("=" * 60)
    
    try:
        # Ler CSVs
        print("\n📖 Lendo arquivos CSV...")
        print("  → Lendo Análise de Anúncios e Criativos...")
        df_criativos = pd.read_csv(CRIATIVOS_CSV, skiprows=2, encoding='utf-8')
        print(f"    ✓ {len(df_criativos)} registros")
        
        print("  → Lendo Análise de Vídeos...")
        df_videos = pd.read_csv(VIDEOS_CSV, skiprows=2, encoding='utf-8')
        print(f"    ✓ {len(df_videos)} registros")
        
        # Gerar HTML
        print("\n🎨 Gerando relatório HTML...")
        print("  → Integrando Hook Rate...")
        html_criativos = gerar_html_criativos_com_hook(df_criativos, df_videos)
        output_file_criativos = OUTPUT_PATH / "ANALISE_GOOGLE_ANUNCIOS_[PES-JAN-26].html"
        with open(output_file_criativos, 'w', encoding='utf-8') as f:
            f.write(html_criativos)
        print(f"    ✓ Salvo em {output_file_criativos.name}")
        
        print("\n" + "=" * 60)
        print("✅ Relatório atualizado com sucesso!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
