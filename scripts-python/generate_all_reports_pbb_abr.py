#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador Completo de Relatórios para PBB-ABR-26
Cria todos os 8 arquivos HTML de análise - Adaptado de PBB-FEV-26
"""

import pandas as pd
import numpy as np
from pathlib import Path
import os
import re
import runpy
import unicodedata
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURAÇÕES E SETUP
# ============================================================================

BASE_PATH = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
CAMPAIGN_NAME = "PBB-ABR-26"
CAMPAIGN_CODE = "PBB-ABR-26"
ANALISES_PATH = BASE_PATH / "analises" / "[PBB-ABR-26]"
GOOGLE_ADS_PATH = ANALISES_PATH / "Google Ads"
META_ADS_PATH = ANALISES_PATH / "Meta Ads"
ACTIVE_CAMPAIGN_PATH = ANALISES_PATH / "Active Campaign"
VENDAS_PATH = ANALISES_PATH / "Vendas"

# URLs de recursos
LOGO_PATH = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"

print("\n" + "="*100)
print(f"🚀 GERADOR DE RELATÓRIOS COMPLETO - {CAMPAIGN_CODE}")
print("="*100)

def limpar_numero(valor):
    """Converte string com formato brasileiro (1.234,56) para float.
    Inteiros usam ponto como separador de milhar: 28.299 -> 28299
    Decimais usam virgula: 8085,67 -> 8085.67
    """
    if pd.isna(valor) or str(valor).strip() in ('', '--', '-'):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    # Remove R$, espacos
    s = re.sub(r'[R$\s]', '', s)
    # Formato 1.234,56
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        # Formato inteiro 28.299
        s = s.replace('.', '')
    s = re.sub(r'[^\d.-]', '', s)
    try:
        return float(s) if s else 0.0
    except:
        return 0.0


def limpar_contagem_google(valor):
    """Converte contagens exportadas com milhar BR (114.586 / 6.349,00) em float."""
    if pd.isna(valor) or str(valor).strip() in ('', '--', '-'):
        return 0.0
    if isinstance(valor, (int, float)):
        numero = float(valor)
        if not float(numero).is_integer():
            escalado = numero * 1000
            if abs(escalado - round(escalado)) < 1e-6:
                return float(round(escalado))
        return numero
    s = str(valor).strip().replace('.', '').replace(',', '.')
    s = re.sub(r'[^\d.-]', '', s)
    try:
        return float(s) if s else 0.0
    except:
        return 0.0


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


def normalizar_texto(valor):
    if pd.isna(valor):
        return ''
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('pag.', 'pag').replace('pág.', 'pag').replace('pág', 'pag')
    texto = re.sub(r'\[[^\]]*\]', ' ', texto)
    texto = re.sub(r'[^a-z0-9]+', ' ', texto)
    return ' '.join(texto.split())


def classificar_clima(valor):
    texto = normalizar_texto(valor)
    if 'quente' in texto:
        return 'Quente'
    if 'frio' in texto:
        return 'Frio'
    if 'especific' in texto:
        return 'Específico'
    return 'Outros'


def detectar_plataforma_source(valor):
    texto = normalizar_texto(valor)
    if any(chave in texto for chave in ['fb', 'facebook', 'meta']):
        return 'meta'
    if any(chave in texto for chave in ['yt', 'youtube', 'google', 'gads', 'adwords']):
        return 'google'
    return 'outros'


def encontrar_coluna(df, termos):
    termos_l = [termo.lower() for termo in termos]
    for coluna in df.columns:
        col_l = coluna.lower()
        if all(termo in col_l for termo in termos_l):
            return coluna
    return None


def primeiro_texto_valido(series):
    for valor in series:
        texto = str(valor).strip()
        if texto and texto.lower() not in {'nan', 'none'}:
            return texto
    return '-'


def render_clima_boxes(df_clima, gradient):
    if df_clima.empty:
        return '<div class="problem-box">Não foi possível atribuir vendas por clima com os dados atuais do CRM.</div>'

    boxes = []
    for _, row in df_clima.iterrows():
        boxes.append(
            f"<div class=\"metric-box\" style=\"background: {gradient};\">"
            f"<div class=\"label\">Clima {row['clima']}</div>"
            f"<div class=\"value\">{formatar_valor(row['vendas'], 'numero')}</div>"
            f"<div style=\"font-size:12px;opacity:.9;margin-top:6px;\">{formatar_valor(row['valor_total'], 'moeda')}</div>"
            "</div>"
        )
    return ''.join(boxes)


def render_clima_bars(df_clima, bar_color):
    if df_clima.empty:
        return '<div class="problem-box">Não foi possível atribuir vendas por clima com os dados atuais do CRM.</div>'

    _df = df_clima.copy().sort_values('vendas', ascending=False)
    max_vendas = max(float(_df['vendas'].max()), 1.0)
    rows = []
    for _, row in _df.iterrows():
        vendas = float(row['vendas'])
        largura = max((vendas / max_vendas) * 100, 4)
        rows.append(
            f"""
            <div class=\"clima-bar-row\">
                <div class=\"clima-bar-head\">
                    <div>
                        <div class=\"clima-bar-title\">Clima {row['clima']}</div>
                        <div class=\"clima-bar-subtitle\">{formatar_valor(row['valor_total'], 'moeda')}</div>
                    </div>
                    <div class=\"clima-bar-number\">{formatar_valor(vendas, 'numero')}</div>
                </div>
                <div class=\"clima-bar-track\">
                    <div class=\"clima-bar-fill\" style=\"width:{largura:.1f}%; background:{bar_color};\"></div>
                </div>
            </div>
            """
        )
    return ''.join(rows)


def get_css_base():
    """Retorna CSS base para todos os relatórios"""
    return """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 20px auto;
            background: white;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            border-radius: 8px;
        }
        
        .header {
            background: white;
            color: #333;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            flex-wrap: wrap;
            border-bottom: 1px solid #eee;
        }
        
        .header-logo {
            margin-right: 30px;
        }
        
        .header-logo img {
            max-width: 120px;
            height: auto;
        }
        
        .header-logo a:hover img {
            transform: scale(1.05);
            transition: transform 0.3s ease;
        }
        
        .header-title h1 {
            font-size: 32px;
            margin-bottom: 10px;
            color: #333;
        }
        
        .header-title p {
            font-size: 14px;
            color: #666;
            margin: 5px 0;
        }
        
        .content {
            padding: 40px;
            max-width: 100%;
            margin: 0 auto;
        }
        
        .metric-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
            display: inline-block;
            min-width: 200px;
            margin-right: 15px;
        }
        
        .metric-box .label {
            font-size: 12px;
            text-transform: uppercase;
            opacity: 0.9;
            margin-bottom: 5px;
        }
        
        .metric-box .value {
            font-size: 24px;
            font-weight: bold;
        }
        
        .recommendation-box {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        
        .problem-box {
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        
        .success-box {
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }
        
        table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        
        table td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        
        table tr:hover {
            background: #f5f5f5;
        }
        
        h2 {
            margin-top: 30px;
            margin-bottom: 15px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        h3 {
            margin-top: 20px;
            margin-bottom: 10px;
            color: #555;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
            border-top: 1px solid #eee;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
            }
            .header {
                padding: 20px 15px;
                flex-direction: column;
            }
            .header-logo {
                margin-right: 0;
                margin-bottom: 20px;
            }
            .content {
                padding: 20px;
            }
        }
    </style>
    """


print("\n📊 Carregando dados...")

# Carregar Google Ads Campanhas
try:
    df_ga_campanhas = pd.read_csv(GOOGLE_ADS_PATH / "Performance da campanha-pbb-abr-26.csv", encoding='utf-8', skiprows=2)
    print("✓ Google Ads Campanhas carregado")
except Exception as e:
    df_ga_campanhas = None
    print(f"✗ Erro ao carregar Google Ads Campanhas: {e}")

# Carregar Google Ads Anúncios
try:
    df_ga_ads = pd.read_csv(GOOGLE_ADS_PATH / "Performance dos anúncios-pbb-abr-26.csv", encoding='utf-8', skiprows=2)
    print("✓ Google Ads Anúncios carregado")
except Exception as e:
    df_ga_ads = None
    print(f"✗ Erro ao carregar Google Ads Anúncios: {e}")

# Carregar Google Ads Públicos
try:
    df_ga_audiences = pd.read_csv(GOOGLE_ADS_PATH / "Públicos-alvo-pbb-abr-26.csv", encoding='utf-8', skiprows=2)
    print("✓ Google Ads Públicos carregado")
except Exception as e:
    df_ga_audiences = None
    print(f"✗ Erro ao carregar Google Ads Públicos: {e}")

# Carregar Meta Ads
try:
    df_meta = pd.read_csv(META_ADS_PATH / "MA-Campanhas-completas-PBB-ABR-26.csv", encoding='utf-8')
    print("✓ Meta Ads carregado")
except Exception as e:
    df_meta = None
    print(f"✗ Erro ao carregar Meta Ads: {e}")

# Carregar Leads
try:
    leads_candidates = []

    if ACTIVE_CAMPAIGN_PATH.exists():
        leads_candidates.extend(ACTIVE_CAMPAIGN_PATH.glob("*.csv"))

    if not leads_candidates:
        active_campaign_alt = ANALISES_PATH / "Active Campaign"
        if active_campaign_alt.exists():
            leads_candidates.extend(active_campaign_alt.glob("*.csv"))

    if not leads_candidates:
        leads_candidates.extend(
            f for f in ANALISES_PATH.rglob("*.csv")
            if "lead" in f.name.lower() or "pbb-abr-26" in f.name.lower() or "banco do brasil" in f.name.lower()
        )

    leads_file = max(leads_candidates, key=lambda f: f.stat().st_mtime) if leads_candidates else None

    if leads_file:
        last_error = None
        for enc in ["utf-8", "utf-8-sig", "latin1"]:
            try:
                df_leads = pd.read_csv(leads_file, encoding=enc)
                print(f"✓ Leads carregado de {leads_file.name}")
                break
            except Exception as e:
                last_error = e
                df_leads = None

        if df_leads is None and last_error is not None:
            raise last_error
    else:
        df_leads = None
        print("✗ Arquivo de leads não encontrado")
except Exception as e:
    df_leads = None
    print(f"✗ Erro ao carregar Leads: {e}")

# Carregar Vendas
try:
    _hm_raw_all = pd.read_csv(VENDAS_PATH / 'hotmart pbb-abr-26.csv', sep=';', encoding='utf-8')
    _tipo_col = next((c for c in _hm_raw_all.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
    _par_col_hm = 'Quantidade total de parcelas'
    _cob_col_hm = 'Quantidade de cobranças'
    _hm_norm = _hm_raw_all[_hm_raw_all[_tipo_col].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
    _hm_norm['valor_num'] = pd.to_numeric(_hm_norm['Faturamento líquido do(a) Produtor(a)'].astype(str), errors='coerce').fillna(0)
    _hm_ri = _hm_raw_all[
        (_hm_raw_all[_tipo_col].astype(str).str.strip() == 'Recuperador Inteligente') &
        (pd.to_numeric(_hm_raw_all[_cob_col_hm], errors='coerce').fillna(0) == 1)
    ].copy()
    _hm_ri[_par_col_hm] = pd.to_numeric(_hm_ri[_par_col_hm], errors='coerce').fillna(1)
    _hm_ri['valor_num'] = pd.to_numeric(_hm_ri['Faturamento líquido do(a) Produtor(a)'].astype(str), errors='coerce').fillna(0) * _hm_ri[_par_col_hm]
    df_hotmart = pd.concat([_hm_norm, _hm_ri], ignore_index=True)
    df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
    df_hotmart['origem_venda'] = 'Hotmart'
    print('✓ Vendas Hotmart carregadas')
except Exception as e:
    df_hotmart = None
    print(f'✗ Erro ao carregar Vendas Hotmart: {e}')

try:
    df_tmb = pd.read_csv(VENDAS_PATH / 'tmb pbb-abr-26.csv', sep=';', encoding='utf-8')
    # Inclui todos os rows (oficial conta todos os 170)
    df_tmb['email'] = df_tmb['E-mail do Cliente'].astype(str).str.strip().str.lower()
    df_tmb['valor_num'] = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce').fillna(0)
    df_tmb['origem_venda'] = 'TMB'
    print('✓ Vendas TMB carregadas')
except Exception as e:
    df_tmb = None
    print(f'✗ Erro ao carregar Vendas TMB: {e}')

df_sales = None
sales_by_clima = {'meta': pd.DataFrame(), 'google': pd.DataFrame()}
sales_by_publico = {'meta': {}, 'google': {}}

if df_leads is not None and ((df_hotmart is not None and len(df_hotmart) > 0) or (df_tmb is not None and len(df_tmb) > 0)):
    _email_col = next((c for c in df_leads.columns if 'email' in c.lower()), None)
    _utm_source_col = encontrar_coluna(df_leads, ['utm_source'])
    _utm_medium_col = encontrar_coluna(df_leads, ['utm_medium'])

    if _email_col and _utm_source_col and _utm_medium_col:
        _lead_attr = df_leads[[_email_col, _utm_source_col, _utm_medium_col]].copy()
        _lead_attr.columns = ['email', 'utm_source', 'utm_medium']
        _lead_attr['email'] = _lead_attr['email'].astype(str).str.strip().str.lower()
        _lead_attr['utm_source'] = _lead_attr['utm_source'].astype(str).fillna('')
        _lead_attr['utm_medium'] = _lead_attr['utm_medium'].astype(str).fillna('')
        _lead_attr = _lead_attr[_lead_attr['email'].str.strip() != '']
        _lead_attr = _lead_attr.drop_duplicates('email', keep='last')

        _sales_frames = []
        if df_hotmart is not None and len(df_hotmart) > 0:
            _sales_frames.append(df_hotmart[['email', 'valor_num', 'origem_venda']].copy())
        if df_tmb is not None and len(df_tmb) > 0:
            _sales_frames.append(df_tmb[['email', 'valor_num', 'origem_venda']].copy())

        if _sales_frames:
            df_sales = pd.concat(_sales_frames, ignore_index=True)
            df_sales['email'] = df_sales['email'].astype(str).str.strip().str.lower()
            df_sales = df_sales[df_sales['email'].str.strip() != '']
            df_sales = df_sales.merge(_lead_attr, on='email', how='left')
            df_sales['plataforma'] = df_sales['utm_source'].apply(detectar_plataforma_source)
            df_sales['clima'] = df_sales['utm_source'].apply(classificar_clima)
            df_sales['publico_norm'] = df_sales['utm_medium'].apply(normalizar_texto)

            for _plat in ['meta', 'google']:
                _plat_sales = df_sales[df_sales['plataforma'] == _plat].copy()
                if len(_plat_sales) == 0:
                    continue
                _clima = (
                    _plat_sales.groupby('clima', dropna=False)
                    .agg(vendas=('email', 'size'), valor_total=('valor_num', 'sum'))
                    .reset_index()
                    .sort_values(['vendas', 'valor_total'], ascending=False)
                )
                sales_by_clima[_plat] = _clima
                sales_by_publico[_plat] = _plat_sales.groupby('publico_norm').size().to_dict()

# ============================================================================
# GERAR TODOS OS 8 RELATÓRIOS HTML
# ============================================================================

print("\n" + "="*100)
print("📄 GERANDO RELATÓRIOS HTML")
print("="*100)

# 1. INDEX
print("\n📄 [1/8] Gerando INDEX_[PBB-ABR-26].html...")

html_index = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análises PBB-ABR-26 - Felipe Graton Banco do Brasil</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>📊 Campanha PBB-ABR-26</h1>
                <p>Felipe Graton Banco do Brasil - Captação</p>
                <p>Período: Abril de 2026</p>
            </div>
        </div>
        
        <div class="content">
            <h2>📈 Resumo da Campanha</h2>
            <div style="margin: 20px 0;">
                <div class="metric-box">
                    <div class="label">Período</div>
                    <div class="value">Abr/2026</div>
                </div>
                <div class="metric-box">
                    <div class="label">Status</div>
                    <div class="value">Ativo</div>
                </div>
            </div>
            
            <h2>🎯 Análises Disponíveis</h2>
            <div class="grid">
                <div class="card">
                    <h3>🧭 Funil Completo</h3>
                    <p>Leitura macro do funil com distribuição por etapa, verba e conversões entre Meta e Google.</p>
                    <a href="ANALISE_FUNIL_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>

                <div class="card">
                    <h3>📱 Meta Ads</h3>
                    <p>Visão consolidada de Meta Ads com Facebook, respostas de pesquisa atribuídas e criativos de captação.</p>
                    <a href="ANALISE_META_ADS_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>🔍 Google Ads</h3>
                    <p>Visão consolidada de Google Ads com YouTube, respostas de pesquisa atribuídas e criativos de captação.</p>
                    <a href="ANALISE_GOOGLE_ADS_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>👥 Públicos Meta Ads</h3>
                    <p>Análise detalhada dos públicos Meta Ads com segmentação demográfica.</p>
                    <a href="ANALISE_META_AUDIENCES_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>👥 Públicos Google Ads</h3>
                    <p>Segmentação e performance dos públicos do Google Ads.</p>
                    <a href="ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>📋 Leads vs Campanhas</h3>
                    <p>Confronto entre leads do CRM e dados das plataformas de anúncios.</p>
                    <a href="ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>

                <div class="card">
                    <h3>📝 Typeform</h3>
                    <p>Distribuição das respostas de pesquisa e leitura das origens atribuídas a partir do CRM.</p>
                    <a href="ANALISE_TYPEFORM_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>🎨 Análise de Criativos</h3>
                    <p>Performance dos criativos e anúncios.</p>
                    <a href="ANALISE_ANUNCIOS_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>💡 Insights e Recomendações</h3>
                    <p>Consolidação de insights acionáveis com recomendações prioritárias.</p>
                    <a href="INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>📘 Facebook — Performance</h3>
                    <p>Análise detalhada por campanha, conjunto e criativo do Facebook Ads.</p>
                    <a href="ANALISE_FACEBOOK_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>▶️ YouTube — Performance</h3>
                    <p>Análise de campanhas de vídeo e tráfego do YouTube Ads.</p>
                    <a href="ANALISE_YOUTUBE_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
                
                <div class="card">
                    <h3>📊 Consolidado Multi-plataforma</h3>
                    <p>Visão unificada de Facebook e YouTube com comparativo lado a lado.</p>
                    <a href="ANALISE_CONSOLIDADA_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
                </div>
            </div>
            
            <div class="footer">
                <p>Análises geradas em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "INDEX_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_index)
print("✓ INDEX criado")

# 2. META ADS
print("\n📄 [2/8] Gerando ANALISE_META_ADS_[PBB-ABR-26].html...")

# Pre-processar Meta Ads: agrupar por campanha
_meta_camp_rows = ""
_meta_total_inv = _meta_total_cliques = _meta_total_impr = _meta_total_leads = _meta_total_alcance = 0.0
_meta_total_vendas = 0
_meta_n_camp = 0

if df_meta is not None and len(df_meta) > 0:
    _df = df_meta.copy()
    for col in ['Valor usado (BRL)', 'Impressões', 'Alcance', 'Leads', 'Cliques no link']:
        if col in _df.columns:
            _df[col] = pd.to_numeric(
                _df[col].astype(str).str.replace(',', '.').str.replace(r'[^\d.]', '', regex=True),
                errors='coerce'
            ).fillna(0)

    _meta_sales_map = {}
    if 'Nome da campanha' in _df.columns and 'Nome do conjunto de anúncios' in _df.columns:
        _meta_sales_base = _df[['Nome da campanha', 'Nome do conjunto de anúncios']].dropna().drop_duplicates().copy()
        _meta_sales_base['vendas_publico'] = _meta_sales_base['Nome do conjunto de anúncios'].apply(
            lambda nome: sales_by_publico['meta'].get(normalizar_texto(nome), 0)
        )
        _meta_sales_map = _meta_sales_base.groupby('Nome da campanha')['vendas_publico'].sum().to_dict()

    if 'Nome da campanha' in _df.columns:
        _agg = {c: 'sum' for c in ['Valor usado (BRL)', 'Impressões', 'Alcance', 'Leads', 'Cliques no link'] if c in _df.columns}
        _grp = _df.groupby('Nome da campanha').agg(_agg).reset_index()
        _grp = _grp.sort_values('Valor usado (BRL)', ascending=False)
        _grp['vendas'] = _grp['Nome da campanha'].map(_meta_sales_map).fillna(0)
        _meta_n_camp = len(_grp)
        _meta_total_inv = _grp['Valor usado (BRL)'].sum() if 'Valor usado (BRL)' in _grp.columns else 0
        _meta_total_impr = _grp['Impressões'].sum() if 'Impressões' in _grp.columns else 0
        _meta_total_alcance = _grp['Alcance'].sum() if 'Alcance' in _grp.columns else 0
        _meta_total_leads = _grp['Leads'].sum() if 'Leads' in _grp.columns else 0
        _meta_total_cliques = _grp['Cliques no link'].sum() if 'Cliques no link' in _grp.columns else 0
        _meta_total_vendas = int(_grp['vendas'].sum())

        for _, r in _grp.iterrows():
            cliques = r.get('Cliques no link', 0)
            impr = r.get('Impressões', 0)
            ctr_link = (cliques / impr * 100) if impr > 0 else 0
            _meta_camp_rows += (
                f"<tr><td>{str(r.get('Nome da campanha', '')).strip()}</td>"
                f"<td style='text-align:right'>{formatar_valor(cliques,'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(impr,'numero')}</td>"
                f"<td style='text-align:right'>{ctr_link:.2f}%</td>"
                f"<td style='text-align:right'>{formatar_valor(r.get('Leads',0),'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(r.get('vendas',0),'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(r.get('Valor usado (BRL)',0),'moeda')}</td></tr>"
            )

_meta_cpl = (_meta_total_inv / _meta_total_leads) if _meta_total_leads > 0 else 0
_meta_cpc = (_meta_total_inv / _meta_total_cliques) if _meta_total_cliques > 0 else 0
_meta_cpv = (_meta_total_inv / _meta_total_vendas) if _meta_total_vendas > 0 else 0
_meta_n_ads = len(df_meta['Nome do anúncio'].dropna().unique()) if df_meta is not None and 'Nome do anúncio' in df_meta.columns else 0

html_meta = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Meta Ads - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>📱 Análise Performance Meta Ads</h1>
                <p>Campanha {CAMPAIGN_CODE}</p>
                <p>Período: Abril de 2026</p>
            </div>
        </div>
        
        <div class="content">
            <h2>📊 Resumo Executivo</h2>
            <div style="margin: 20px 0; display:flex; flex-wrap:wrap; gap:12px;">
                <div class="metric-box">
                    <div class="label">Cliques no Link</div>
                    <div class="value">{formatar_valor(_meta_total_cliques, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Impressões</div>
                    <div class="value">{formatar_valor(_meta_total_impr, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Investimento Total</div>
                    <div class="value">{formatar_valor(_meta_total_inv, 'moeda')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Leads</div>
                    <div class="value">{formatar_valor(_meta_total_leads, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Vendas</div>
                    <div class="value">{formatar_valor(_meta_total_vendas, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">CPL Médio</div>
                    <div class="value">{formatar_valor(_meta_cpl, 'moeda')}</div>
                </div>
            </div>

            <h2>📋 Performance por Campanha ({_meta_n_camp} campanhas)</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th>Campanha</th>
                    <th style="text-align:right">Cliques</th>
                    <th style="text-align:right">Impressões</th>
                    <th style="text-align:right">CTR Link</th>
                    <th style="text-align:right">Leads</th>
                    <th style="text-align:right">Vendas</th>
                    <th style="text-align:right">Investimento</th>
                </tr>
                {_meta_camp_rows if _meta_camp_rows else '<tr><td colspan="7">Dados não disponíveis.</td></tr>'}
                <tr style="font-weight:bold;background:#e8e8ff;">
                    <td><strong>TOTAL</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_meta_total_cliques, 'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_meta_total_impr, 'numero')}</strong></td>
                    <td></td>
                    <td style="text-align:right"><strong>{formatar_valor(_meta_total_leads, 'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_meta_total_vendas, 'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_meta_total_inv, 'moeda')}</strong></td>
                </tr>
            </table>
            </div>

            <h2>📁 Dados da Base Meta</h2>
            <div class="success-box">
                <strong>✅ Base Meta consolidada</strong><br>
                {_meta_n_ads:,} anúncios únicos e {formatar_valor(_meta_total_alcance, 'numero')} de alcance somado disponíveis para leitura detalhada.
                Consulte os cruzamentos de públicos e criativos nas análises complementares da campanha.
            </div>
            <div class="recommendation-box">
                <strong>💡 Ação recomendada</strong><br>
                Compare o CPV de Meta com o de Google e preserve verba nas campanhas que já combinam clique, lead e venda atribuída.
                Ver também: <a href="ANALISE_META_AUDIENCES_[PBB-ABR-26].html" style="color:#856404">ANALISE_META_AUDIENCES →</a>
                | <a href="ANALISE_ANUNCIOS_[PBB-ABR-26].html" style="color:#856404">ANALISE_ANUNCIOS →</a>
            </div>
            <div class="success-box">
                <strong>📌 Leitura executiva</strong><br>
                O Meta fecha com <strong>{formatar_valor(_meta_total_vendas, 'numero')} vendas atribuídas</strong>,
                <strong>{formatar_valor(_meta_total_leads, 'numero')} leads</strong> e CPV médio de <strong>{formatar_valor(_meta_cpv, 'moeda')}</strong>.
                Use essa página para decidir redistribuição entre campanhas e a página de públicos para aprofundar quais conjuntos sustentam essas vendas.
            </div>
            
            <div class="footer">
                <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
                <p><a href="INDEX_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "ANALISE_META_ADS_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_meta)
print("✓ Meta Ads análise criada")

# 3. GOOGLE ADS - com dados reais de campanhas
print("\n📄 [3/8] Gerando ANALISE_GOOGLE_ADS_[PBB-ABR-26].html...")

# Pre-processar dados de campanhas GA
_ga_camp_rows = ""
_ga_total_custo = _ga_total_cliques = _ga_total_impr = _ga_total_conv = 0.0
if df_ga_campanhas is not None and len(df_ga_campanhas) > 0:
    _df = df_ga_campanhas.copy()
    if 'Campanha' in _df.columns:
        _camp_raw = _df['Campanha'].astype(str).str.lower()
        _df = _df[
            _camp_raw.str.contains('[ga]', regex=False)
            & (
                _camp_raw.str.contains('captação', regex=False)
                | _camp_raw.str.contains('captacao', regex=False)
            )
        ].copy()
    for col in ['Cliques', 'Impr.']:
        if col in _df.columns:
            _df[col] = _df[col].apply(limpar_contagem_google)
    for col in ['Custo', 'Conversões', 'CPC méd.']:
        if col in _df.columns:
            _df[col] = _df[col].apply(limpar_contagem_google if col == 'Conversões' else limpar_numero)
    if 'Custo' in _df.columns:
        _df = _df.sort_values('Custo', ascending=False)
        _ga_total_custo = _df['Custo'].sum()
    if 'Cliques' in _df.columns:
        _ga_total_cliques = _df['Cliques'].sum()
    if 'Impr.' in _df.columns:
        _ga_total_impr = _df['Impr.'].sum()
    if 'Conversões' in _df.columns:
        _ga_total_conv = _df['Conversões'].sum()
    for _, r in _df.iterrows():
        _ga_camp_rows += (
            f"<tr><td>{str(r.get('Campanha','')).strip()}</td>"
            f"<td>{str(r.get('Estado da campanha','')).strip()}</td>"
            f"<td style='text-align:right'>{formatar_valor(r.get('Cliques',0),'numero')}</td>"
            f"<td style='text-align:right'>{formatar_valor(r.get('Impr.',0),'numero')}</td>"
            f"<td style='text-align:right'>{str(r.get('CTR','')).strip()}</td>"
            f"<td style='text-align:right'>{formatar_valor(r.get('Custo',0),'moeda')}</td>"
            f"<td style='text-align:right'>{formatar_valor(r.get('Conversões',0),'numero')}</td></tr>"
        )

_cpa_ga = (_ga_total_custo / _ga_total_conv) if _ga_total_conv > 0 else 0
_cpc_ga = (_ga_total_custo / _ga_total_cliques) if _ga_total_cliques > 0 else 0
_ga_n_camp = len(df_ga_campanhas) if df_ga_campanhas is not None else 0
_ga_n_ads = len(df_ga_ads) if df_ga_ads is not None else 0

html_google = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Google Ads - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>🔍 Análise Performance Google Ads</h1>
                <p>Campanha {CAMPAIGN_CODE} | Período: Abril de 2026</p>
            </div>
        </div>

        <div class="content">
            <h2>📊 Resumo Executivo</h2>
            <div style="margin: 20px 0; display:flex; flex-wrap:wrap; gap:12px;">
                <div class="metric-box" style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
                    <div class="label">Total Cliques</div>
                    <div class="value">{formatar_valor(_ga_total_cliques, 'numero')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
                    <div class="label">Total Impressões</div>
                    <div class="value">{formatar_valor(_ga_total_impr, 'numero')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
                    <div class="label">Custo Total</div>
                    <div class="value">{formatar_valor(_ga_total_custo, 'moeda')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
                    <div class="label">Conversões</div>
                    <div class="value">{formatar_valor(_ga_total_conv, 'numero')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
                    <div class="label">CPA</div>
                    <div class="value">{formatar_valor(_cpa_ga, 'moeda')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
                    <div class="label">CPC Médio</div>
                    <div class="value">{formatar_valor(_cpc_ga, 'moeda')}</div>
                </div>
            </div>

            <h2>📋 Performance por Campanha ({_ga_n_camp} registros)</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th>Campanha</th><th>Status</th>
                    <th style="text-align:right">Cliques</th>
                    <th style="text-align:right">Impressões</th>
                    <th style="text-align:right">CTR</th>
                    <th style="text-align:right">Custo</th>
                    <th style="text-align:right">Conversões</th>
                </tr>
                {_ga_camp_rows}
                <tr style="font-weight:bold;background:#e8f0fe;">
                    <td colspan="2"><strong>TOTAL</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ga_total_cliques, 'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ga_total_impr, 'numero')}</strong></td>
                    <td></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ga_total_custo, 'moeda')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ga_total_conv, 'decimal')}</strong></td>
                </tr>
            </table>
            </div>

            <h2>📁 Dados de Anúncios</h2>
            <div class="success-box">
                <strong>✅ Base de anúncios carregada</strong><br>
                {_ga_n_ads:,} linhas de performance de anúncios disponíveis para análise detalhada.
                Consulte os dados brutos em <code>Performance dos anúncios-pbb-abr-26.csv</code>.
            </div>
            <div class="recommendation-box">
                <strong>💡 Ação recomendada</strong><br>
                Compare CPA do Google Ads com o CPA do Meta Ads para orientar realocação de budget entre plataformas.
                Ver também: <a href="ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html" style="color:#856404">ANALISE_GOOGLE_AUDIENCES →</a>
            </div>

            <div class="footer">
                <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
                <p><a href="INDEX_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "ANALISE_GOOGLE_ADS_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_google)
print("✓ Google Ads análise criada")

# 4. LEADS CONFRONTO - com dados reais do CRM
print("\n📄 [4/8] Gerando ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html...")

# Pre-processar CRM: distribuição por utm_source
_leads_total = len(df_leads) if df_leads is not None else 0
_leads_com_utm = 0
_utm_dist_rows = ""
_plataforma_dist_rows = ""

if df_leads is not None and len(df_leads) > 0:
    # Detectar coluna UTM source (case-insensitive)
    _utm_col = next((c for c in df_leads.columns if 'utm_source' in c.lower()), None)
    _email_col = next((c for c in df_leads.columns if 'email' in c.lower()), None)

    if _utm_col:
        _df_utm = df_leads[df_leads[_utm_col].notna() & (df_leads[_utm_col].astype(str).str.strip() != '')]
        _leads_com_utm = len(_df_utm)
        _leads_sem_utm = _leads_total - _leads_com_utm
        _pct_utm = (_leads_com_utm / _leads_total * 100) if _leads_total > 0 else 0

        # Top utm_source
        _top_utm = df_leads[_utm_col].fillna('(sem UTM)').value_counts().head(15)
        for src, cnt in _top_utm.items():
            pct = cnt / _leads_total * 100
            _utm_dist_rows += (
                f"<tr><td>{src}</td>"
                f"<td style='text-align:right'>{cnt:,}</td>"
                f"<td style='text-align:right'>{pct:.1f}%</td></tr>"
            )

        # Agrupar por plataforma (fb, google, yt, etc.)
        def _detect_plat(s):
            s = str(s).lower()
            if s.startswith('fb') or 'facebook' in s or 'meta' in s: return 'Meta / Facebook'
            if s.startswith('yt') or 'youtube' in s: return 'YouTube'
            if 'google' in s or 'gdn' in s: return 'Google'
            if s == '(sem utm)' or s == 'nan': return 'Sem UTM'
            return 'Outros'
        _plat_dist = df_leads[_utm_col].fillna('(sem utm)').apply(_detect_plat).value_counts()
        for plat, cnt in _plat_dist.items():
            pct = cnt / _leads_total * 100
            _plataforma_dist_rows += (
                f"<tr><td>{plat}</td>"
                f"<td style='text-align:right'>{cnt:,}</td>"
                f"<td style='text-align:right'>{pct:.1f}%</td></tr>"
            )
    else:
        _leads_com_utm = 0
        _utm_dist_rows = "<tr><td colspan='3'>Coluna utm_source não encontrada no CRM.</td></tr>"

_pct_utm_str = f"{(_leads_com_utm / _leads_total * 100):.1f}%" if _leads_total > 0 else "—"
_meta_rows_cnt = len(df_meta) if df_meta is not None else 0
_ga_rows_cnt = len(df_ga_campanhas) if df_ga_campanhas is not None else 0
_leads_sem_utm = _leads_total - _leads_com_utm if _leads_total > 0 else 0

_top_platform_name = "—"
_top_platform_leads = 0
_top_platform_pct = 0.0
if df_leads is not None and len(df_leads) > 0 and _utm_col:
    _plat_series = df_leads[_utm_col].fillna('(sem utm)').apply(_detect_plat).value_counts()
    if len(_plat_series) > 0:
        _top_platform_name = str(_plat_series.index[0])
        _top_platform_leads = int(_plat_series.iloc[0])
        _top_platform_pct = (_top_platform_leads / _leads_total * 100) if _leads_total > 0 else 0.0

_top_utm_name = "—"
_top_utm_leads = 0
_top_utm_pct = 0.0
if df_leads is not None and len(df_leads) > 0 and _utm_col:
    _utm_series = df_leads[_utm_col].fillna('(sem UTM)').value_counts()
    if len(_utm_series) > 0:
        _top_utm_name = str(_utm_series.index[0])
        _top_utm_leads = int(_utm_series.iloc[0])
        _top_utm_pct = (_top_utm_leads / _leads_total * 100) if _leads_total > 0 else 0.0

_google_crm_leads = 0
_meta_crm_leads = 0
_youtube_crm_leads = 0
if df_leads is not None and len(df_leads) > 0 and _utm_col:
    _source_series = df_leads[_utm_col].fillna('(sem utm)').apply(_detect_plat)
    _meta_crm_leads = int((_source_series == 'Meta / Facebook').sum())
    _youtube_crm_leads = int((_source_series == 'YouTube').sum())
    _google_crm_leads = int((_source_series == 'Google').sum())

html_leads = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confronto Leads CRM vs Campanhas - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body style="background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);">
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>📋 Confronto: Leads CRM vs Campanhas</h1>
                <p>Comparativo de dados entre plataformas e CRM</p>
                <p>Campanha {CAMPAIGN_CODE}</p>
            </div>
        </div>

        <div class="content">
            <h2>📊 Visão Geral dos Dados</h2>
            <div style="margin: 20px 0; display:flex; flex-wrap:wrap; gap:12px;">
                <div class="metric-box" style="background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);">
                    <div class="label">Total Leads no CRM</div>
                    <div class="value">{_leads_total:,}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);">
                    <div class="label">Leads com UTM</div>
                    <div class="value">{_leads_com_utm:,}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);">
                    <div class="label">% com Rastreamento</div>
                    <div class="value">{_pct_utm_str}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);">
                    <div class="label">Linhas Meta Ads</div>
                    <div class="value">{_meta_rows_cnt:,}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #eb5757 0%, #ff9500 100%);">
                    <div class="label">Linhas GA Campanhas</div>
                    <div class="value">{_ga_rows_cnt:,}</div>
                </div>
            </div>

            <h2>🌐 Distribuição por Plataforma (CRM)</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr><th>Plataforma</th><th style="text-align:right">Leads</th><th style="text-align:right">% do Total</th></tr>
                {_plataforma_dist_rows if _plataforma_dist_rows else '<tr><td colspan="3">Dados de UTM não disponíveis.</td></tr>'}
                <tr style="font-weight:bold;background:#ffeeba;">
                    <td><strong>TOTAL</strong></td>
                    <td style="text-align:right"><strong>{_leads_total:,}</strong></td>
                    <td style="text-align:right"><strong>100%</strong></td>
                </tr>
            </table>
            </div>

            <h2>🔗 Distribuição por utm_source (Top 15)</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr><th>utm_source</th><th style="text-align:right">Leads</th><th style="text-align:right">% do Total</th></tr>
                {_utm_dist_rows if _utm_dist_rows else '<tr><td colspan="3">Coluna utm_source não localizada.</td></tr>'}
            </table>
            </div>

            <div class="recommendation-box">
                <strong>💡 Leitura CRM</strong><br>
                A base mostra <strong>{_pct_utm_str}</strong> de cobertura de rastreamento, com <strong>{_leads_sem_utm:,} leads sem UTM</strong>. Para CRM, isso significa que a operação já tem boa visibilidade de origem, mas ainda carrega uma faixa de receita e resposta comercial que pode ficar sem atribuição confiável.
            </div>

            <div class="success-box">
                <strong>✅ Diagnóstico de canal</strong><br>
                O CRM está concentrado em <strong>{_top_platform_name}</strong>, que responde por <strong>{_top_platform_leads:,} leads</strong> ({_top_platform_pct:.1f}% da base). No detalhamento por origem, a principal linha é <strong>{_top_utm_name}</strong>, com <strong>{_top_utm_leads:,} leads</strong> ({_top_utm_pct:.1f}%). Isso é útil para priorizar playbooks comerciais, SLA de atendimento e segmentação de réguas por origem dominante.
            </div>

            <div class="problem-box">
                <strong>⚠️ Ponto de atenção de CRM</strong><br>
                Há uma assimetria forte entre canais dentro do CRM: <strong>Meta/Facebook = {_meta_crm_leads:,} leads</strong>, <strong>YouTube = {_youtube_crm_leads:,} leads</strong> e <strong>Google = {_google_crm_leads:,} leads</strong>. Antes de concluir que Google não converte, vale auditar naming, parâmetros de URL, regras de redirect e persistência de UTM, porque baixa participação no CRM também pode indicar perda de atribuição.
            </div>

            <div class="recommendation-box">
                <strong>🧭 Recomendações de um profissional de CRM</strong><br>
                1. Tratar os <strong>{_leads_sem_utm:,} leads sem UTM</strong> como backlog de governança: revisar formulários, páginas intermediárias, redirecionamentos e sobrescrita de parâmetros.<br>
                2. Criar uma taxonomia fixa de <em>utm_source</em> e <em>utm_medium</em> por canal, clima e público para evitar fragmentação de bases e facilitar réguas, scoring e análise de cohort.<br>
                3. Separar as automações comerciais por macro-origem dominante: Meta/Facebook, YouTube e Google, com abordagem, cadência e copy diferentes conforme intenção e maturidade do lead.<br>
                4. Cruzar periodicamente este relatório com vendas e Typeform para medir não só volume de entrada, mas também qualidade do lead por origem, recuperando canais que trazem menos volume e mais resposta comercial.
            </div>

            <div class="footer">
                <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
                <p><a href="INDEX_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_leads)
print("✓ Análise de Leads criada")

# 5. ANUNCIOS
print("\n📄 [5/8] Gerando ANALISE_ANUNCIOS_[PBB-ABR-26].html...")
_cwd_original = Path.cwd()
try:
    os.chdir(BASE_PATH)
    runpy.run_path(str(BASE_PATH / "scripts-python" / "generate_analise_anuncios_FINAL.py"), run_name="__main__")
finally:
    os.chdir(_cwd_original)
print("✓ Análise de Anúncios criada")

# 6. META AUDIENCES - com dados reais agrupados por conjunto de anúncios
print("\n📄 [6/8] Gerando ANALISE_META_AUDIENCES_[PBB-ABR-26].html...")

# Pre-processar Meta Ads: agrupar por conjunto de anúncios
_ma_conj_rows = ""
_ma_total_inv = _ma_total_impressoes = _ma_total_alcance = _ma_total_leads = _ma_total_cliques = 0.0
_ma_n_conj = 0
_ma_clima_chart = render_clima_bars(sales_by_clima['meta'], 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)')
_ma_top_publico_nome = 'n/d'
_ma_top_publico_campanha = '-'
_ma_top_publico_vendas = 0
_ma_top_publico_cpl = 0.0
_ma_alerta_publico_nome = 'n/d'
_ma_alerta_publico_campanha = '-'
_ma_alerta_publico_leads = 0
_ma_top_clima_nome = 'n/d'
_ma_top_clima_vendas = 0
_ma_top_clima_valor = 0.0
_ma_top_clima_part = 0.0

if not sales_by_clima['meta'].empty:
    _ma_clima_df = sales_by_clima['meta'].copy().sort_values('vendas', ascending=False).reset_index(drop=True)
    _ma_top_clima = _ma_clima_df.iloc[0]
    _ma_top_clima_nome = str(_ma_top_clima['clima'])
    _ma_top_clima_vendas = int(_ma_top_clima['vendas'])
    _ma_top_clima_valor = float(_ma_top_clima['valor_total'])
    _ma_top_clima_total = float(_ma_clima_df['vendas'].sum())
    _ma_top_clima_part = (_ma_top_clima_vendas / _ma_top_clima_total * 100) if _ma_top_clima_total else 0.0

if df_meta is not None and len(df_meta) > 0:
    _df = df_meta.copy()
    # Normalizar colunas numéricas
    for col in ['Valor usado (BRL)', 'Impressões', 'Alcance', 'Leads', 'Cliques no link']:
        if col in _df.columns:
            _df[col] = pd.to_numeric(
                _df[col].astype(str).str.replace(',', '.').str.replace(r'[^\d.]', '', regex=True),
                errors='coerce'
            ).fillna(0)
    # Agrupar por conjunto de anúncios
    _agg_cols = {c: 'sum' for c in ['Valor usado (BRL)', 'Impressões', 'Alcance', 'Leads', 'Cliques no link'] if c in _df.columns}
    if 'Nome da campanha' in _df.columns:
        _agg_cols['Nome da campanha'] = primeiro_texto_valido
    if 'Nome do conjunto de anúncios' in _df.columns and _agg_cols:
        _grp = _df.groupby('Nome do conjunto de anúncios').agg(_agg_cols).reset_index()
        _grp = _grp.sort_values('Valor usado (BRL)', ascending=False)
        _grp['vendas_publico'] = _grp['Nome do conjunto de anúncios'].apply(
            lambda nome: sales_by_publico['meta'].get(normalizar_texto(nome), 0)
        )
        _grp['cpl_calc'] = _grp.apply(
            lambda row: (row.get('Valor usado (BRL)', 0) / row.get('Leads', 0)) if row.get('Leads', 0) > 0 else 0,
            axis=1
        )
        _ma_n_conj = len(_grp)
        _ma_total_inv = _grp['Valor usado (BRL)'].sum() if 'Valor usado (BRL)' in _grp.columns else 0
        _ma_total_impressoes = _grp['Impressões'].sum() if 'Impressões' in _grp.columns else 0
        _ma_total_alcance = _grp['Alcance'].sum() if 'Alcance' in _grp.columns else 0
        _ma_total_leads = _grp['Leads'].sum() if 'Leads' in _grp.columns else 0
        _ma_total_cliques = _grp['Cliques no link'].sum() if 'Cliques no link' in _grp.columns else 0

        _ma_top_publico_df = _grp[_grp['vendas_publico'] > 0].sort_values(['vendas_publico', 'Leads'], ascending=[False, False])
        if not _ma_top_publico_df.empty:
            _ma_top_publico = _ma_top_publico_df.iloc[0]
            _ma_top_publico_nome = str(_ma_top_publico['Nome do conjunto de anúncios'])
            _ma_top_publico_campanha = str(_ma_top_publico.get('Nome da campanha', '-'))
            _ma_top_publico_vendas = int(_ma_top_publico['vendas_publico'])
            _ma_top_publico_cpl = float(_ma_top_publico['cpl_calc'])

        _ma_alerta_publico_df = _grp[_grp['vendas_publico'] == 0].sort_values(['Leads', 'Valor usado (BRL)'], ascending=[False, False])
        if not _ma_alerta_publico_df.empty:
            _ma_alerta_publico = _ma_alerta_publico_df.iloc[0]
            _ma_alerta_publico_nome = str(_ma_alerta_publico['Nome do conjunto de anúncios'])
            _ma_alerta_publico_campanha = str(_ma_alerta_publico.get('Nome da campanha', '-'))
            _ma_alerta_publico_leads = int(_ma_alerta_publico.get('Leads', 0))

        for _, r in _grp.iterrows():
            inv = r.get('Valor usado (BRL)', 0)
            leads = r.get('Leads', 0)
            cpl = (inv / leads) if leads > 0 else 0
            publico_norm = normalizar_texto(r['Nome do conjunto de anúncios'])
            vendas_publico = sales_by_publico['meta'].get(publico_norm, 0)
            campanha_nome = str(r.get('Nome da campanha', '-')).strip() or '-'
            _ma_conj_rows += (
                f"<tr><td>{str(r['Nome do conjunto de anúncios'])[:60]}</td>"
                f"<td>{campanha_nome[:70]}</td>"
                f"<td style='text-align:right'>{formatar_valor(inv,'moeda')}</td>"
                f"<td style='text-align:right'>{formatar_valor(r.get('Impressões',0),'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(r.get('Alcance',0),'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(leads,'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(vendas_publico,'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(cpl,'moeda')}</td>"
                f"<td style='text-align:right'>{formatar_valor(r.get('Cliques no link',0),'numero')}</td></tr>"
            )

_ma_cpl_total = (_ma_total_inv / _ma_total_leads) if _ma_total_leads > 0 else 0

html_meta_audiences = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Meta Audiences - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>👥 Análise de Públicos — Meta Ads</h1>
                <p>Performance por conjunto de anúncios | {CAMPAIGN_CODE}</p>
            </div>
        </div>

        <div class="content">
            <h2>📊 Resumo Executivo</h2>
            <div style="margin: 20px 0; display:flex; flex-wrap:wrap; gap:12px;">
                <div class="metric-box">
                    <div class="label">Conjuntos de Anúncios</div>
                    <div class="value">{_ma_n_conj}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Investimento Total</div>
                    <div class="value">{formatar_valor(_ma_total_inv, 'moeda')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Impressões</div>
                    <div class="value">{formatar_valor(_ma_total_impressoes, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Alcance Total</div>
                    <div class="value">{formatar_valor(_ma_total_alcance, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Leads (Meta)</div>
                    <div class="value">{formatar_valor(_ma_total_leads, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">CPL Médio</div>
                    <div class="value">{formatar_valor(_ma_cpl_total, 'moeda')}</div>
                </div>
            </div>

            <h2>🌡️ Vendas por Clima</h2>
            <div style="margin: 20px 0; background:#f8faff; border:1px solid #dbe4ff; border-radius:12px; padding:20px;">
                <style>
                    .clima-bar-row {{ margin-bottom: 18px; }}
                    .clima-bar-row:last-child {{ margin-bottom: 0; }}
                    .clima-bar-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:8px; }}
                    .clima-bar-title {{ font-size:14px; font-weight:700; color:#2d3748; }}
                    .clima-bar-subtitle {{ font-size:12px; color:#667085; margin-top:2px; }}
                    .clima-bar-number {{ font-size:18px; font-weight:800; color:#3b4cca; min-width:56px; text-align:right; }}
                    .clima-bar-track {{ width:100%; height:16px; background:#e7ecff; border-radius:999px; overflow:hidden; }}
                    .clima-bar-fill {{ height:100%; border-radius:999px; box-shadow: inset 0 -1px 0 rgba(255,255,255,.25); }}
                </style>
                {_ma_clima_chart}
            </div>

            <h2>📋 Performance por Conjunto de Anúncios ({_ma_n_conj} conjuntos) — Top por Investimento</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th>Conjunto de Anúncios</th>
                    <th>Campanha</th>
                    <th style="text-align:right">Investimento</th>
                    <th style="text-align:right">Impressões</th>
                    <th style="text-align:right">Alcance</th>
                    <th style="text-align:right">Leads</th>
                    <th style="text-align:right">Vendas</th>
                    <th style="text-align:right">CPL</th>
                    <th style="text-align:right">Cliques</th>
                </tr>
                {_ma_conj_rows if _ma_conj_rows else '<tr><td colspan="9">Dados não disponíveis.</td></tr>'}
                <tr style="font-weight:bold;background:#e8e8ff;">
                    <td><strong>TOTAL</strong></td>
                    <td><strong>-</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ma_total_inv,'moeda')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ma_total_impressoes,'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ma_total_alcance,'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ma_total_leads,'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(sales_by_clima['meta']['vendas'].sum() if not sales_by_clima['meta'].empty else 0,'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ma_cpl_total,'moeda')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ma_total_cliques,'numero')}</strong></td>
                </tr>
            </table>
            </div>

            <div class="recommendation-box">
                <strong>💡 Ação recomendada</strong><br>
                Identifique conjuntos com CPL acima da média e priorize alocação nos conjuntos com menor CPL e maior volume de leads.
                Combine com a análise de criativos: <a href="ANALISE_ANUNCIOS_[PBB-ABR-26].html" style="color:#856404">ANALISE_ANUNCIOS →</a>
            </div>

            <div class="success-box">
                <strong>🌡️ Leitura de clima</strong><br>
                O clima <strong>{_ma_top_clima_nome}</strong> concentra <strong>{formatar_valor(_ma_top_clima_vendas, 'numero')} vendas</strong>
                ({_ma_top_clima_part:.1f}% das vendas atribuídas de Meta), somando <strong>{formatar_valor(_ma_top_clima_valor, 'moeda')}</strong>.
                A recomendação é preservar verba, criativos e cadência comercial para esse bloco enquanto ele seguir liderando conversão real, usando os demais climas como faixas de teste e expansão.
            </div>

            <div class="recommendation-box">
                <strong>👥 Leitura de audiência</strong><br>
                O conjunto <strong>{_ma_top_publico_nome}</strong>, na campanha <strong>{_ma_top_publico_campanha}</strong>, é hoje a principal audiência convertedora,
                com <strong>{formatar_valor(_ma_top_publico_vendas, 'numero')} vendas</strong> e CPL de <strong>{formatar_valor(_ma_top_publico_cpl, 'moeda')}</strong>.
                Esse é o melhor candidato para replicação de criativo, ampliação de orçamento e criação de variações próximas de público.
            </div>

            <div class="problem-box">
                <strong>⚠️ Ponto de atenção</strong><br>
                O conjunto <strong>{_ma_alerta_publico_nome}</strong>, na campanha <strong>{_ma_alerta_publico_campanha}</strong>, acumulou
                <strong>{formatar_valor(_ma_alerta_publico_leads, 'numero')} leads</strong> sem vendas atribuídas nesta leitura.
                Vale revisar aderência da oferta, qualidade do tráfego e alinhamento entre promessa do anúncio, landing page e follow-up comercial antes de seguir escalando esse público.
            </div>

            <div class="footer">
                <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
                <p><a href="INDEX_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "ANALISE_META_AUDIENCES_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_meta_audiences)
print("✓ Meta Audiences análise criada")

# 7. GOOGLE AUDIENCES - com dados reais de públicos
print("\n📄 [7/8] Gerando ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html...")

# Pre-processar GA Audiences: agrupar por segmento
_gaud_rows = ""
_gaud_total_cliques = _gaud_total_impr = _gaud_total_custo = 0.0
_gaud_n_seg = 0
_gaud_n_campanhas = 0
_gaud_clima_chart = render_clima_bars(sales_by_clima['google'], 'linear-gradient(90deg, #4285f4 0%, #34a853 100%)')
_gaud_top_publico_nome = 'n/d'
_gaud_top_publico_campanha = '-'
_gaud_top_publico_vendas = 0
_gaud_top_publico_cpc = 0.0
_gaud_alerta_publico_nome = 'n/d'
_gaud_alerta_publico_campanha = '-'
_gaud_alerta_publico_cliques = 0
_gaud_top_clima_nome = 'n/d'
_gaud_top_clima_vendas = 0
_gaud_top_clima_valor = 0.0
_gaud_top_clima_part = 0.0

if not sales_by_clima['google'].empty:
    _gaud_clima_df = sales_by_clima['google'].copy().sort_values('vendas', ascending=False).reset_index(drop=True)
    _gaud_top_clima = _gaud_clima_df.iloc[0]
    _gaud_top_clima_nome = str(_gaud_top_clima['clima'])
    _gaud_top_clima_vendas = int(_gaud_top_clima['vendas'])
    _gaud_top_clima_valor = float(_gaud_top_clima['valor_total'])
    _gaud_top_clima_total = float(_gaud_clima_df['vendas'].sum())
    _gaud_top_clima_part = (_gaud_top_clima_vendas / _gaud_top_clima_total * 100) if _gaud_top_clima_total else 0.0

if df_ga_audiences is not None and len(df_ga_audiences) > 0:
    _df = df_ga_audiences.copy()
    for col in ['Cliques', 'Impr.']:
        if col in _df.columns:
            _df[col] = _df[col].apply(limpar_numero)
    if 'Custo' in _df.columns:
        _df['Custo'] = _df['Custo'].apply(limpar_numero)
    if 'CPM médio' in _df.columns:
        _df['CPM médio'] = _df['CPM médio'].apply(limpar_numero)

    _seg_col = 'Grupo de anúncios'
    if _seg_col in _df.columns:
        _agg = {c: 'sum' for c in ['Cliques', 'Impr.', 'Custo'] if c in _df.columns}
        if 'Campanha' in _df.columns:
            _agg['Campanha'] = primeiro_texto_valido
        _grp = _df.groupby(_seg_col).agg(_agg).reset_index()
        _grp = _grp.sort_values('Custo', ascending=False)
        _grp['vendas_publico'] = _grp[_seg_col].apply(
            lambda nome: sales_by_publico['google'].get(normalizar_texto(nome), 0)
        )
        _grp['ctr_calc'] = _grp.apply(
            lambda row: (row.get('Cliques', 0) / row.get('Impr.', 0) * 100) if row.get('Impr.', 0) > 0 else 0,
            axis=1
        )
        _grp['cpc_calc'] = _grp.apply(
            lambda row: (row.get('Custo', 0) / row.get('Cliques', 0)) if row.get('Cliques', 0) > 0 else 0,
            axis=1
        )
        _gaud_n_seg = len(_grp)
        _gaud_n_campanhas = _df['Campanha'].nunique() if 'Campanha' in _df.columns else 0
        _gaud_total_cliques = _df['Cliques'].sum() if 'Cliques' in _df.columns else 0
        _gaud_total_impr = _df['Impr.'].sum() if 'Impr.' in _df.columns else 0
        _gaud_total_custo = _df['Custo'].sum() if 'Custo' in _df.columns else 0

        _gaud_top_publico_df = _grp[_grp['vendas_publico'] > 0].sort_values(['vendas_publico', 'Cliques'], ascending=[False, False])
        if not _gaud_top_publico_df.empty:
            _gaud_top_publico = _gaud_top_publico_df.iloc[0]
            _gaud_top_publico_nome = str(_gaud_top_publico[_seg_col])
            _gaud_top_publico_campanha = str(_gaud_top_publico.get('Campanha', '-'))
            _gaud_top_publico_vendas = int(_gaud_top_publico['vendas_publico'])
            _gaud_top_publico_cpc = float(_gaud_top_publico['cpc_calc'])

        _gaud_alerta_publico_df = _grp[_grp['vendas_publico'] == 0].sort_values(['Cliques', 'Custo'], ascending=[False, False])
        if not _gaud_alerta_publico_df.empty:
            _gaud_alerta_publico = _gaud_alerta_publico_df.iloc[0]
            _gaud_alerta_publico_nome = str(_gaud_alerta_publico[_seg_col])
            _gaud_alerta_publico_campanha = str(_gaud_alerta_publico.get('Campanha', '-'))
            _gaud_alerta_publico_cliques = int(_gaud_alerta_publico.get('Cliques', 0))

        for _, r in _grp.iterrows():
            cliques = r.get('Cliques', 0)
            impr = r.get('Impr.', 0)
            custo = r.get('Custo', 0)
            ctr_calc = (cliques / impr * 100) if impr > 0 else 0
            cpc = (custo / cliques) if cliques > 0 else 0
            vendas_publico = r.get('vendas_publico', 0)
            campanha_nome = str(r.get('Campanha', '-')).strip() or '-'
            _gaud_rows += (
                f"<tr><td>{str(r[_seg_col])[:70]}</td>"
                f"<td>{campanha_nome[:70]}</td>"
                f"<td style='text-align:right'>{formatar_valor(custo,'moeda')}</td>"
                f"<td style='text-align:right'>{formatar_valor(impr,'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(cliques,'numero')}</td>"
                f"<td style='text-align:right'>{formatar_valor(vendas_publico,'numero')}</td>"
                f"<td style='text-align:right'>{ctr_calc:.2f}%</td>"
                f"<td style='text-align:right'>{formatar_valor(cpc,'moeda')}</td></tr>"
            )

_gaud_cpc_total = (_gaud_total_custo / _gaud_total_cliques) if _gaud_total_cliques > 0 else 0

html_google_audiences = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Google Audiences - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body style="background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);">
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>👥 Análise de Públicos — Google Ads</h1>
                <p>Top segmentos por cliques e custo | {CAMPAIGN_CODE}</p>
            </div>
        </div>

        <div class="content">
            <h2>📊 Resumo Executivo</h2>
            <div style="margin: 20px 0; display:flex; flex-wrap:wrap; gap:12px;">
                <div class="metric-box">
                    <div class="label">Grupos de Anúncios</div>
                    <div class="value">{_gaud_n_seg}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Campanhas</div>
                    <div class="value">{_gaud_n_campanhas}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Custo Total</div>
                    <div class="value">{formatar_valor(_gaud_total_custo, 'moeda')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Impressões</div>
                    <div class="value">{formatar_valor(_gaud_total_impr, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">Cliques</div>
                    <div class="value">{formatar_valor(_gaud_total_cliques, 'numero')}</div>
                </div>
                <div class="metric-box">
                    <div class="label">CPC Médio</div>
                    <div class="value">{formatar_valor(_gaud_cpc_total, 'moeda')}</div>
                </div>
            </div>

            <h2>🌡️ Vendas por Clima</h2>
            <div style="margin: 20px 0; background:#f8faff; border:1px solid #dbe4ff; border-radius:12px; padding:20px;">
                <style>
                    .clima-bar-row {{ margin-bottom: 18px; }}
                    .clima-bar-row:last-child {{ margin-bottom: 0; }}
                    .clima-bar-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:8px; }}
                    .clima-bar-title {{ font-size:14px; font-weight:700; color:#2d3748; }}
                    .clima-bar-subtitle {{ font-size:12px; color:#667085; margin-top:2px; }}
                    .clima-bar-number {{ font-size:18px; font-weight:800; color:#2d6cdf; min-width:56px; text-align:right; }}
                    .clima-bar-track {{ width:100%; height:16px; background:#e7ecff; border-radius:999px; overflow:hidden; }}
                    .clima-bar-fill {{ height:100%; border-radius:999px; box-shadow: inset 0 -1px 0 rgba(255,255,255,.25); }}
                </style>
                {_gaud_clima_chart}
            </div>

            <h2>📋 Performance por Grupo de Anúncios ({_gaud_n_seg} grupos) — Top por Custo</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th>Grupo de anúncios</th>
                    <th>Campanha</th>
                    <th style="text-align:right">Custo</th>
                    <th style="text-align:right">Impressões</th>
                    <th style="text-align:right">Cliques</th>
                    <th style="text-align:right">Vendas</th>
                    <th style="text-align:right">CTR</th>
                    <th style="text-align:right">CPC</th>
                </tr>
                {_gaud_rows if _gaud_rows else '<tr><td colspan="8">Dados não disponíveis.</td></tr>'}
                <tr style="font-weight:bold;background:#e8f0fe;">
                    <td><strong>TOTAL GERAL</strong></td>
                    <td><strong>-</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_gaud_total_custo,'moeda')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_gaud_total_impr,'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_gaud_total_cliques,'numero')}</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(sales_by_clima['google']['vendas'].sum() if not sales_by_clima['google'].empty else 0,'numero')}</strong></td>
                    <td></td>
                    <td style="text-align:right"><strong>{formatar_valor(_gaud_cpc_total,'moeda')}</strong></td>
                </tr>
            </table>
            </div>

            <div class="recommendation-box">
                <strong>💡 Ação recomendada</strong><br>
                Identifique grupos com CPC acima da média e preserve orçamento nos grupos que combinam volume de cliques com vendas atribuídas.
                Combine com a análise criativa do canal: <a href="ANALISE_GOOGLE_ANUNCIOS_[PBB-ABR-26].html" style="color:#856404">ANALISE_GOOGLE_ANUNCIOS →</a>
            </div>

            <div class="success-box">
                <strong>🌡️ Leitura de clima</strong><br>
                O clima <strong>{_gaud_top_clima_nome}</strong> concentra <strong>{formatar_valor(_gaud_top_clima_vendas, 'numero')} vendas</strong>
                ({_gaud_top_clima_part:.1f}% das vendas atribuídas de Google), somando <strong>{formatar_valor(_gaud_top_clima_valor, 'moeda')}</strong>.
                A recomendação é manter esse bloco como referência de escala e usar os demais climas como frentes de teste controlado até provarem conversão real com custo sustentável.
            </div>

            <div class="recommendation-box">
                <strong>👥 Leitura de audiência</strong><br>
                O grupo <strong>{_gaud_top_publico_nome}</strong>, na campanha <strong>{_gaud_top_publico_campanha}</strong>, é hoje a principal audiência convertedora,
                com <strong>{formatar_valor(_gaud_top_publico_vendas, 'numero')} vendas</strong> e CPC de <strong>{formatar_valor(_gaud_top_publico_cpc, 'moeda')}</strong>.
                Esse é o melhor candidato para expansão, novas variações de anúncio e reforço de investimento no Google.
            </div>

            <div class="problem-box">
                <strong>⚠️ Ponto de atenção</strong><br>
                O grupo <strong>{_gaud_alerta_publico_nome}</strong>, na campanha <strong>{_gaud_alerta_publico_campanha}</strong>, acumulou
                <strong>{formatar_valor(_gaud_alerta_publico_cliques, 'numero')} cliques</strong> sem vendas atribuídas nesta leitura.
                Vale revisar aderência da audiência, intenção de busca, promessa do anúncio e qualidade da página antes de seguir escalando esse grupo.
            </div>

            <div class="footer">
                <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
                <p><a href="INDEX_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_google_audiences)
print("✓ Google Audiences análise criada")

# 8. VENDAS - cruzamento CRM + Typeform + Hotmart + TMB
print("\n📄 [8/9] Gerando ANALISE_VENDAS_[PBB-ABR-26].html...")
_cwd_original = Path.cwd()
try:
    os.chdir(BASE_PATH)
    runpy.run_path(str(BASE_PATH / "scripts-python" / "generate_analise_vendas_abr_final.py"), run_name="__main__")
finally:
    os.chdir(_cwd_original)
print("✓ Análise de Vendas criada")

# 9. INSIGHTS - com dados reais das plataformas
print("\n📄 [9/9] Gerando INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html...")

# Calcular métricas consolidadas para insights
_ins_meta_inv = _ma_total_inv if df_meta is not None else 0
_ins_meta_leads = _ma_total_leads if df_meta is not None else 0
_ins_meta_cliques = _ma_total_cliques if df_meta is not None else 0
_ins_ga_inv = _ga_total_custo if df_ga_campanhas is not None else 0
_ins_ga_cliques = _ga_total_cliques if df_ga_campanhas is not None else 0
_ins_ga_conv = _ga_total_conv if df_ga_campanhas is not None else 0
_ins_total_inv = _ins_meta_inv + _ins_ga_inv
_ins_total_leads_crm = _leads_total if df_leads is not None else 0
_ins_meta_pct = (_ins_meta_inv / _ins_total_inv * 100) if _ins_total_inv > 0 else 0
_ins_ga_pct = (_ins_ga_inv / _ins_total_inv * 100) if _ins_total_inv > 0 else 0
_ins_cpl_meta = (_ins_meta_inv / _ins_meta_leads) if _ins_meta_leads > 0 else 0
_ins_cpl_ga = (_ins_ga_inv / _ins_ga_conv) if _ins_ga_conv > 0 else 0
_ins_cpc_meta = (_ins_meta_inv / _ins_meta_cliques) if _ins_meta_cliques > 0 else 0
_ins_cpc_ga = (_ins_ga_inv / _ins_ga_cliques) if _ins_ga_cliques > 0 else 0

html_insights = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Insights e Recomendações - {CAMPAIGN_CODE}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PBB-ABR-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>💡 Insights e Recomendações</h1>
                <p>Análise consolidada multi-plataforma | {CAMPAIGN_CODE}</p>
            </div>
        </div>

        <div class="content">
            <h2>📊 Visão Geral da Campanha</h2>
            <div style="margin: 20px 0; display:flex; flex-wrap:wrap; gap:12px;">
                <div class="metric-box" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                    <div class="label">Investimento Total</div>
                    <div class="value">{formatar_valor(_ins_total_inv, 'moeda')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                    <div class="label">Meta Ads</div>
                    <div class="value">{formatar_valor(_ins_meta_inv, 'moeda')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                    <div class="label">Google Ads</div>
                    <div class="value">{formatar_valor(_ins_ga_inv, 'moeda')}</div>
                </div>
                <div class="metric-box" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                    <div class="label">Total Leads (CRM)</div>
                    <div class="value">{_ins_total_leads_crm:,}</div>
                </div>
            </div>

            <h2>⚖️ Comparativo entre Plataformas</h2>
            <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th>Plataforma</th>
                    <th style="text-align:right">Investimento</th>
                    <th style="text-align:right">% do Budget</th>
                    <th style="text-align:right">Cliques</th>
                    <th style="text-align:right">CPC</th>
                    <th style="text-align:right">Leads/Conv.</th>
                    <th style="text-align:right">CPL</th>
                </tr>
                <tr>
                    <td>📱 Meta Ads (Facebook/Instagram)</td>
                    <td style="text-align:right">{formatar_valor(_ins_meta_inv,'moeda')}</td>
                    <td style="text-align:right">{_ins_meta_pct:.1f}%</td>
                    <td style="text-align:right">{formatar_valor(_ins_meta_cliques,'numero')}</td>
                    <td style="text-align:right">{formatar_valor(_ins_cpc_meta,'moeda')}</td>
                    <td style="text-align:right">{formatar_valor(_ins_meta_leads,'numero')}</td>
                    <td style="text-align:right">{formatar_valor(_ins_cpl_meta,'moeda')}</td>
                </tr>
                <tr>
                    <td>🔍 Google Ads</td>
                    <td style="text-align:right">{formatar_valor(_ins_ga_inv,'moeda')}</td>
                    <td style="text-align:right">{_ins_ga_pct:.1f}%</td>
                    <td style="text-align:right">{formatar_valor(_ins_ga_cliques,'numero')}</td>
                    <td style="text-align:right">{formatar_valor(_ins_cpc_ga,'moeda')}</td>
                    <td style="text-align:right">{formatar_valor(_ins_ga_conv,'decimal')}</td>
                    <td style="text-align:right">{formatar_valor(_ins_cpl_ga,'moeda')}</td>
                </tr>
                <tr style="font-weight:bold;background:#fce4ec;">
                    <td><strong>TOTAL</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ins_total_inv,'moeda')}</strong></td>
                    <td style="text-align:right"><strong>100%</strong></td>
                    <td style="text-align:right"><strong>{formatar_valor(_ins_meta_cliques + _ins_ga_cliques,'numero')}</strong></td>
                    <td></td>
                    <td></td>
                    <td></td>
                </tr>
            </table>
            </div>

            <h2>🎯 Recomendações Prioritárias</h2>
            <div class="recommendation-box">
                <strong>1. Escalar criativos de maior conversão</strong><br>
                Utilize os dados de ANALISE_ANUNCIOS para identificar os 2-3 criativos com menor CPL e aumente o orçamento desses conjuntos em 20-30%.
                <br><a href="ANALISE_ANUNCIOS_[PBB-ABR-26].html" style="color:#856404">→ Ver Análise de Anúncios</a>
            </div>
            <div class="recommendation-box">
                <strong>2. Otimizar distribuição entre plataformas</strong><br>
                {'Meta Ads representa ' + f"{_ins_meta_pct:.0f}%" + ' do budget. ' if _ins_total_inv > 0 else ''}
                Compare CPL entre plataformas e realoque verba para a que tiver menor custo por lead qualificado.
                <br><a href="ANALISE_META_AUDIENCES_[PBB-ABR-26].html" style="color:#856404">→ Ver Públicos Meta</a> |
                <a href="ANALISE_GOOGLE_ADS_[PBB-ABR-26].html" style="color:#856404">→ Ver Google Ads</a>
            </div>
            <div class="recommendation-box">
                <strong>3. Fechar gap de atribuição</strong><br>
                Leads sem UTM representam receita não atribuída. Padronize parâmetros de URL nas landing pages e verifique a integração CRM.
                <br><a href="ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html" style="color:#856404">→ Ver Confronto de Leads</a>
            </div>
            <div class="recommendation-box">
                <strong>4. Revisar públicos de baixo desempenho</strong><br>
                Exclua segmentos de públicos com CTR abaixo de 0,5% e CPC muito acima da média para reduzir custo de mídia sem perda de volume.
                <br><a href="ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html" style="color:#856404">→ Ver Públicos Google</a>
            </div>
            <div class="success-box">
                <strong>✅ Fontes de dados utilizadas</strong><br>
                Meta Ads: <code>MA-Campanhas-completas-PBB-ABR-26.csv</code> ({len(df_meta) if df_meta is not None else 0:,} linhas) |
                Google Ads Campanhas: <code>Performance da campanha-pbb-abr-26.csv</code> ({len(df_ga_campanhas) if df_ga_campanhas is not None else 0:,} linhas) |
                CRM: <code>Active Campaign</code> ({_ins_total_leads_crm:,} leads)
            </div>

            <div class="footer">
                <p>Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
                <p><a href="INDEX_[PBB-ABR-26].html" style="color: #667eea; text-decoration: none; font-weight: bold;">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

with open(ANALISES_PATH / "INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html", "w", encoding="utf-8") as f:
    f.write(html_insights)
print("✓ Insights e Recomendações criada")

print("\n" + "="*100)
print("✓ Geração de relatórios concluída!")
print("="*100 + "\n")
