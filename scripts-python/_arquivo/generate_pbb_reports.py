#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de Relatórios Completo para PBB-FEV-26
Regenera todos os arquivos HTML de análise
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configurações
BASE_PATH = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
CAMPAIGN_NAME = "PBB-FEV-26"
ANALISES_PATH = BASE_PATH / "analises" / "[PBB-FEV-26]"
GOOGLE_ADS_PATH = ANALISES_PATH / "google ads"
META_ADS_PATH = ANALISES_PATH / "meta ads"
ACTIVE_CAMPAIGN_PATH = ANALISES_PATH / "active-campaing"
VENDAS_PATH = ANALISES_PATH / "vendas"

print("\n" + "="*100)
print(f"🚀 GERADOR DE RELATÓRIOS - {CAMPAIGN_NAME}")
print("="*100)

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


def find_csv(path_obj, pattern):
    """Encontra arquivo CSV que corresponde ao padrão"""
    if not path_obj.exists():
        print(f"⚠️  Caminho não encontrado: {path_obj}")
        return None
    
    files = list(path_obj.glob("*.csv"))
    for f in files:
        if pattern.lower() in f.name.lower():
            print(f"✓ Encontrado: {f.name}")
            return f
    
    print(f"✗ CSV não encontrado para padrão: {pattern}")
    return None


# ============================================================================
# 1. ANÁLISE GOOGLE ADS - CAMPANHAS E ANÚNCIOS
# ============================================================================

print("\n📊 [1] Processando Google Ads - Campanhas...")

ga_campanha_csv = find_csv(GOOGLE_ADS_PATH, "Performance da campanha")
ga_ads_csv = find_csv(GOOGLE_ADS_PATH, "Performance dos anúncios")
ga_audiences_csv = find_csv(GOOGLE_ADS_PATH, "Públicos-alvo")

if ga_campanha_csv:
    try:
        df_ga_campanhas = pd.read_csv(ga_campanha_csv, encoding='utf-8', skiprows=2)
        print(f"  → Campanhas: {len(df_ga_campanhas)} linhas")
        
        # Limpar números
        for col in df_ga_campanhas.columns:
            if any(x in col.lower() for x in ['custo', 'cpc', 'cpa', 'impressões', 'cliques', 'conversões']):
                df_ga_campanhas[col] = df_ga_campanhas[col].apply(limpar_numero)
        
        print("  ✓ Google Ads Campanhas processado")
    except Exception as e:
        print(f"  ✗ Erro ao processar: {e}")


print("\n📊 [2] Processando Google Ads - Anúncios...")

if ga_ads_csv:
    try:
        df_ga_ads = pd.read_csv(ga_ads_csv, encoding='utf-8', skiprows=2)
        print(f"  → Anúncios: {len(df_ga_ads)} linhas")
        
        # Limpar números
        for col in df_ga_ads.columns:
            if any(x in col.lower() for x in ['custo', 'cpc', 'cpa', 'impressões', 'cliques', 'conversões']):
                df_ga_ads[col] = df_ga_ads[col].apply(limpar_numero)
        
        print("  ✓ Google Ads Anúncios processado")
    except Exception as e:
        print(f"  ✗ Erro ao processar: {e}")


print("\n📊 [2b] Processando Google Ads - Públicos...")

if ga_audiences_csv:
    try:
        df_ga_audiences = pd.read_csv(ga_audiences_csv, encoding='utf-8', skiprows=2)
        print(f"  → Públicos: {len(df_ga_audiences)} linhas")
        
        # Limpar números
        for col in df_ga_audiences.columns:
            if any(x in col.lower() for x in ['custo', 'cpc', 'cpa', 'impressões', 'cliques', 'conversões']):
                df_ga_audiences[col] = df_ga_audiences[col].apply(limpar_numero)
        
        print("  ✓ Google Ads Públicos processado")
    except Exception as e:
        print(f"  ✗ Erro ao processar: {e}")


# ============================================================================
# 2. ANÁLISE META ADS
# ============================================================================

print("\n📊 [3] Processando Meta Ads - Campanhas...")

ma_csv = find_csv(META_ADS_PATH, "campanhas")

if ma_csv:
    try:
        df_meta = pd.read_csv(ma_csv, encoding='utf-8')
        print(f"  → Meta Ads: {len(df_meta)} linhas")
        
        # Limpar números
        for col in df_meta.columns:
            if any(x in col.lower() for x in ['custo', 'cpc', 'cpa', 'impressões', 'cliques', 'conversões', 'leads', 'cpl']):
                df_meta[col] = df_meta[col].apply(limpar_numero)
        
        print("  ✓ Meta Ads processado")
    except Exception as e:
        print(f"  ✗ Erro ao processar: {e}")


# ============================================================================
# 3. ANÁLISE LEADS - ACTIVE CAMPAIGN
# ============================================================================

print("\n📊 [4] Processando Leads - Active Campaign...")

ac_csv = find_csv(ACTIVE_CAMPAIGN_PATH, "leads")

if ac_csv:
    try:
        df_leads = pd.read_csv(ac_csv, encoding='utf-8')
        print(f"  → Leads: {len(df_leads)} linhas")
        print("  ✓ Leads processado")
    except Exception as e:
        print(f"  ✗ Erro ao processar: {e}")


# ============================================================================
# 4. ANÁLISE VENDAS
# ============================================================================

print("\n📊 [5] Processando Vendas...")

hotmart_csv = find_csv(VENDAS_PATH, "hotmart")
tmb_csv = find_csv(VENDAS_PATH, "tmb")

if hotmart_csv:
    try:
        df_hotmart = pd.read_csv(hotmart_csv, encoding='utf-8')
        print(f"  → Hotmart: {len(df_hotmart)} linhas")
    except Exception as e:
        print(f"  ✗ Erro Hotmart: {e}")

if tmb_csv:
    try:
        df_tmb = pd.read_csv(tmb_csv, encoding='utf-8')
        print(f"  → TMB: {len(df_tmb)} linhas")
    except Exception as e:
        print(f"  ✗ Erro TMB: {e}")


# ============================================================================
# AGORA GERAR RELATÓRIOS HTML
# ============================================================================

print("\n" + "="*100)
print("📄 GERANDO RELATÓRIOS HTML")
print("="*100)

# Será implementado a seguir...

print("\n✓ Processamento concluído!")
print("="*100 + "\n")
