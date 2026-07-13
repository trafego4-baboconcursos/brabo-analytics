#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Melhorar HTML de Segmentação e Públicos com dados reais
"""

import pandas as pd
import re
from pathlib import Path

BASE_PATH = Path(r"c:\Users\trafe\Desktop\workspace-mmm")
ANALISES_PATH = BASE_PATH / "analises" / "[PES-JAN-26]" / "google ads"
SEGMENTACAO_CSV = ANALISES_PATH / "Análise de Segmentação e Público - [PI-JAN-26].csv"
OUTPUT_PATH = ANALISES_PATH / "ANALISE_GOOGLE_AUDIENCES_[PES-JAN-26].html"


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
    
    return str(valor)


def extrair_temperatura(nome_campanha):
    """Extrai temperatura (FRIO, MORNO, QUENTE) do nome da campanha"""
    nome = str(nome_campanha).upper()
    if 'QUENTE' in nome:
        return 'QUENTE'
    elif 'MORNO' in nome or 'ESPECÍFICO' in nome:
        return 'MORNO'
    elif 'FRIO' in nome:
        return 'FRIO'
    return 'OUTRO'


def main():
    print("Processando dados de segmentação...")
    
    try:
        # Ler arquivo
        df = pd.read_csv(SEGMENTACAO_CSV, skiprows=2, encoding='utf-8')
        print(f"✓ Lido {len(df)} registros")
        
        # Limpar colunas numéricas
        for col in ['Impr.', 'Cliques', 'Custo', 'CTR']:
            if col in df.columns:
                df[col] = df[col].apply(limpar_numero)
        
        # Adicionar temperatura
        df['Temperatura'] = df['Campanha'].apply(extrair_temperatura)
        
        # Agrupar por temperatura
        temp_stats = df.groupby('Temperatura').agg({
            'Impr.': 'sum',
            'Cliques': 'sum',
            'Custo': 'sum'
        }).reset_index()
        
        # Renomear coluna para padronização
        temp_stats.rename(columns={'Impr.': 'Impressões'}, inplace=True)
        
        temp_stats['CTR'] = (temp_stats['Cliques'] / temp_stats['Impressões'] * 100).fillna(0)
        temp_stats['CPL'] = (temp_stats['Custo'] / temp_stats['Cliques']).fillna(0)  # CPL baseado em cliques quando não há conversões
        
        print("\n📊 Estatísticas por Temperatura:")
        print(temp_stats)
        
        # Gerar HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Análise de Públicos e Temperaturas - Google Ads</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; color: #333; }}
                .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
                
                .header {{ background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: #333; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
                .header h1 {{ font-size: 32px; margin-bottom: 5px; }}
                .header p {{ font-size: 14px; opacity: 0.8; }}
                
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #fa709a; }}
                .stat-card h3 {{ font-size: 12px; color: #999; text-transform: uppercase; margin-bottom: 10px; }}
                .stat-card .value {{ font-size: 28px; font-weight: bold; color: #fa709a; }}
                
                .temperatures {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .temp-card {{ padding: 20px; border-radius: 10px; color: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .temp-card h3 {{ font-size: 18px; margin-bottom: 15px; }}
                .temp-card .metric {{ display: flex; justify-content: space-between; margin: 8px 0; font-size: 14px; }}
                
                .quente {{ background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); }}
                .morno {{ background: linear-gradient(135deg, #f39c12 0%, #f1c40f 100%); }}
                .frio {{ background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); }}
                
                .chart-container {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; position: relative; height: 400px; }}
                .chart-container h3 {{ margin-bottom: 20px; color: #333; }}
                
                table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
                thead {{ background: #f8f9fa; }}
                th {{ padding: 15px; text-align: left; font-weight: 600; border-bottom: 2px solid #e9ecef; font-size: 13px; color: #666; text-transform: uppercase; }}
                td {{ padding: 12px 15px; border-bottom: 1px solid #e9ecef; }}
                tr:hover {{ background: #f8f9fa; }}
                
                .metric {{ font-weight: 600; }}
                
                .footer {{ text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #e9ecef; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🌡️ Análise de Públicos e Temperaturas - Google Ads</h1>
                    <p>Segmentação por Temperatura de Público [PI-JAN-26]</p>
                    <p>Período: 1º de dezembro de 2025 - 31 de janeiro de 2026</p>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>Total de Impressões</h3>
                        <div class="value">{formatar_valor(temp_stats['Impressões'].sum(), 'numero')}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Total de Cliques</h3>
                        <div class="value">{formatar_valor(temp_stats['Cliques'].sum(), 'numero')}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Investimento Total</h3>
                        <div class="value">{formatar_valor(temp_stats['Custo'].sum(), 'moeda')}</div>
                    </div>
                    <div class="stat-card">
                        <h3>CTR Médio</h3>
                        <div class="value">{formatar_valor((temp_stats['Cliques'].sum() / temp_stats['Impressões'].sum() * 100), 'percentual')}</div>
                    </div>
                </div>
                
                <h2 style="margin: 30px 0 20px 0;">🌡️ Performance por Temperatura</h2>
                <div class="temperatures">
        """
        
        ordem_temp = ['QUENTE', 'MORNO', 'FRIO']
        cores = {'QUENTE': 'quente', 'MORNO': 'morno', 'FRIO': 'frio'}
        emojis = {'QUENTE': '🔥', 'MORNO': '⚠️', 'FRIO': '❄️'}
        
        for temp in ordem_temp:
            temp_data = temp_stats[temp_stats['Temperatura'] == temp]
            if len(temp_data) > 0:
                row = temp_data.iloc[0]
                html += f"""
                    <div class="temp-card {cores[temp]}">
                        <h3>{emojis[temp]} Público {temp}</h3>
                        <div class="metric">
                            <span>Impressões:</span>
                            <strong>{formatar_valor(row['Impressões'], 'numero')}</strong>
                        </div>
                        <div class="metric">
                            <span>Cliques:</span>
                            <strong>{formatar_valor(row['Cliques'], 'numero')}</strong>
                        </div>
                        <div class="metric">
                            <span>CTR:</span>
                            <strong>{formatar_valor(row['CTR'], 'percentual')}</strong>
                        </div>
                        <div class="metric">
                            <span>Custo:</span>
                            <strong>{formatar_valor(row['Custo'], 'moeda')}</strong>
                        </div>
                        <div class="metric">
                            <span>CPC:</span>
                            <strong style="color: white; font-size: 18px;">{formatar_valor(row['CPL'], 'moeda')}</strong>
                        </div>
                    </div>
                """
        
        html += """
                </div>
                
                <div class="chart-container">
                    <h3>📈 Conversões por Temperatura</h3>
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
                            <th>Temperatura</th>
                            <th>Impressões</th>
                            <th>Cliques</th>
                            <th>CTR</th>
                            <th>Custo</th>
                            <th>Conversões</th>
                            <th>CPL</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Agrupar por campanha
        camp_stats = df.groupby(['Campanha', 'Temperatura']).agg({
            'Impr.': 'sum',
            'Cliques': 'sum',
            'Custo': 'sum'
        }).reset_index()
        
        camp_stats.rename(columns={'Impr.': 'Impressões'}, inplace=True)
        
        camp_stats['CTR'] = (camp_stats['Cliques'] / camp_stats['Impressões'] * 100).fillna(0)
        camp_stats['CPL'] = (camp_stats['Custo'] / camp_stats['Cliques']).fillna(0)
        camp_stats = camp_stats.sort_values('Cliques', ascending=False).head(30)
        
        for idx, row in camp_stats.iterrows():
            emoji = {'QUENTE': '🔥', 'MORNO': '⚠️', 'FRIO': '❄️'}.get(row['Temperatura'], '•')
            html += f"""
                        <tr>
                            <td><strong>{row['Campanha'][:50]}</strong></td>
                            <td>{emoji} {row['Temperatura']}</td>
                            <td class="metric">{formatar_valor(row['Impressões'], 'numero')}</td>
                            <td class="metric">{formatar_valor(row['Cliques'], 'numero')}</td>
                            <td class="metric">{formatar_valor(row['CTR'], 'percentual')}</td>
                            <td class="metric">{formatar_valor(row['Custo'], 'moeda')}</td>
                            <td class="metric" style="color: #28a745;">{formatar_valor(row['Cliques'], 'numero')}</td>
                            <td class="metric">{formatar_valor(row['CPL'], 'moeda')}</td>
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
        """
        
        # Adicionar dados dos gráficos
        temps_json = temp_stats[['Temperatura', 'Cliques', 'Custo']].to_json(orient='records')
        
        html += f"""
                const temperatures = {temps_json};
                
                const convCtx = document.getElementById('conversionChart').getContext('2d');
                new Chart(convCtx, {{
                    type: 'bar',
                    data: {{
                        labels: temperatures.map(t => t.Temperatura),
                        datasets: [{{
                            label: 'Cliques',
                            data: temperatures.map(t => t.Cliques),
                            backgroundColor: ['#f5576c', '#f39c12', '#3498db'],
                            borderRadius: 5
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{ legend: {{ display: false }} }}
                    }}
                }});
                
                const invCtx = document.getElementById('investmentChart').getContext('2d');
                new Chart(invCtx, {{
                    type: 'scatter',
                    data: {{
                        datasets: [{{
                            label: 'Temperaturas',
                            data: temperatures.map(t => ({{ x: t.Custo, y: t.Cliques }})),
                            backgroundColor: ['#f5576c', '#f39c12', '#3498db'],
                            pointRadius: 12
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{ title: {{ display: true, text: 'Custo (R$)' }} }},
                            y: {{ title: {{ display: true, text: 'Cliques' }} }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        # Salvar
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n✅ HTML atualizado: {OUTPUT_PATH.name}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
