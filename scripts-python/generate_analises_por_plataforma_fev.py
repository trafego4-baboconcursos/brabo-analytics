#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de Análises por Plataforma - PBB-FEV-26
Gera 3 relatórios:
1. ANALISE_FACEBOOK (utm_source fb-)
2. ANALISE_YOUTUBE (utm_source yt-)  
3. ANALISE_CONSOLIDADA (fb- + yt-)
"""

import pandas as pd
from pathlib import Path
import csv

print("=" * 100)
print("GERADOR DE ANALISES POR PLATAFORMA - PBB-FEV-26")
print("=" * 100)

# ========== CARREGAR LEADS DO CRM ==========
print("\n[1/5] Carregando leads do CRM...")

def encontrar_csv_leads_fev():
    base = Path(r'analises/[PBB-FEV-26]')
    candidatos = []
    for pasta in [base / 'active-campaing', base / 'Active Campaign', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-fev-26' in f.name.lower() or 'lead' in f.name.lower())
    return max(candidatos, key=lambda f: f.stat().st_mtime)

leads_file = encontrar_csv_leads_fev()
df_leads = pd.read_csv(leads_file, sep=',', encoding='utf-8', quoting=csv.QUOTE_MINIMAL, low_memory=False)

print(f"   Arquivo: {leads_file.name}")
print(f"   Total de leads: {len(df_leads):,}")

# Preparar dados
df_leads['Email'] = df_leads['Email'].str.strip().str.lower()
df_leads['utm_source_clean'] = df_leads['*Utm_source'].fillna('').astype(str).str.strip().str.lower()

# Extrair criativo
df_leads['criativo'] = df_leads['*Utm_content'].astype(str).apply(
    lambda x: x.split(' - ')[0].strip().upper() if isinstance(x, str) and ' - ' in x else str(x).strip().upper()
)

# Filtrar por plataforma
df_leads_facebook = df_leads[df_leads['utm_source_clean'].str.startswith('fb-', na=False)].copy()
df_leads_youtube  = df_leads[df_leads['utm_source_clean'].str.startswith('yt-', na=False)].copy()
df_leads_consolidado = pd.concat([df_leads_facebook, df_leads_youtube], ignore_index=True)

print(f"\n   Distribuição por plataforma:")
print(f"   - Facebook (fb-): {len(df_leads_facebook):,} leads ({len(df_leads_facebook)/len(df_leads)*100:.1f}%)")
print(f"   - YouTube (yt-):  {len(df_leads_youtube):,} leads ({len(df_leads_youtube)/len(df_leads)*100:.1f}%)")
print(f"   - Consolidado:    {len(df_leads_consolidado):,} leads ({len(df_leads_consolidado)/len(df_leads)*100:.1f}%)")

# ========== CARREGAR VENDAS ==========
print("\n[2/5] Carregando vendas...")

vendas_path = Path(r'analises/[PBB-FEV-26]/vendas')

# Hotmart
df_hotmart = pd.read_csv(vendas_path / 'hotmart-pbb-fev-26.csv', sep=';', encoding='utf-8')
df_hotmart['email'] = df_hotmart['Email do(a) Comprador(a)'].astype(str).str.strip().str.lower()
df_hotmart['valor_num'] = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce')
vendas_hotmart = df_hotmart[df_hotmart['valor_num'] > 0]

# TMB FEV-26: utf-8, Status == 'Efetivado', colunas diferentes
df_tmb_raw = pd.read_csv(vendas_path / 'tmb-pbb-fev-26.csv', sep=';', encoding='utf-8')
if 'Status' in df_tmb_raw.columns:
    df_tmb = df_tmb_raw[df_tmb_raw['Status'].astype(str).str.strip() == 'Efetivado'].copy()
else:
    df_tmb = df_tmb_raw.copy()
df_tmb['email'] = df_tmb['Cliente Email'].astype(str).str.strip().str.lower()
df_tmb['valor_num'] = pd.to_numeric(
    df_tmb['Ticket (R$)'].astype(str).str.replace(',', '.'), errors='coerce'
)
vendas_tmb = df_tmb[df_tmb['valor_num'] > 0]

print(f"   Hotmart: {len(vendas_hotmart)} vendas = R$ {vendas_hotmart['valor_num'].sum():,.2f}")
print(f"   TMB:     {len(vendas_tmb)} vendas = R$ {vendas_tmb['valor_num'].sum():,.2f}")
print(f"   TOTAL:   {len(vendas_hotmart) + len(vendas_tmb)} vendas = R$ {(vendas_hotmart['valor_num'].sum() + vendas_tmb['valor_num'].sum()):,.2f}")

# ========== CARREGAR INVESTIMENTOS FACEBOOK ==========
print("\n[3/5] Carregando investimentos Facebook (Meta Ads)...")

df_meta = pd.read_csv(
    r'analises/[PBB-FEV-26]/meta ads/MA-Campanhas-Completas-PBB-FEV-26.csv',
    sep=',', encoding='utf-8'
)
df_meta['codigo_ad'] = df_meta['Nome do anúncio'].astype(str).apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)
df_meta['valor_gasto'] = pd.to_numeric(
    df_meta['Valor usado (BRL)'].astype(str).str.replace(',', '.'),
    errors='coerce'
).fillna(0)

investimentos_facebook = df_meta.groupby('codigo_ad')['valor_gasto'].sum()
print(f"   Total investido Facebook: R$ {investimentos_facebook.sum():,.2f}")
print(f"   Anúncios com investimento: {len(investimentos_facebook[investimentos_facebook > 0])}")

# ========== CARREGAR INVESTIMENTOS YOUTUBE ==========
print("\n[4/5] Carregando investimentos YouTube (Google Ads)...")

df_youtube = pd.read_csv(
    r'analises/[PBB-FEV-26]/google ads/Performance dos anúncios-pbb-fev-26.csv',
    sep=',',
    encoding='utf-8',
    skiprows=2
)
df_youtube['codigo_ad'] = df_youtube['Nome do anúncio'].astype(str).apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)
df_youtube['custo_num'] = pd.to_numeric(
    df_youtube['Custo'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

investimentos_youtube = df_youtube.groupby('codigo_ad')['custo_num'].sum()
print(f"   Total investido YouTube: R$ {investimentos_youtube.sum():,.2f}")
print(f"   Anúncios com investimento: {len(investimentos_youtube[investimentos_youtube > 0])}")

# ========== GERAR ANÁLISES ==========
print("\n[5/5] Gerando análises...")

def gerar_analise_plataforma(nome_plataforma, df_leads_filtrado, investimentos_dict, vendas_h, vendas_t):
    """Gera análise para uma plataforma específica"""

    print(f"\n   >>> {nome_plataforma}")

    leads_por_criativo = df_leads_filtrado.groupby('criativo').size()

    resultados = []

    for criativo, investimento in investimentos_dict.items():
        if investimento == 0:
            continue

        num_leads = leads_por_criativo.get(criativo, 0)
        emails_criativo = df_leads_filtrado[df_leads_filtrado['criativo'] == criativo]['Email'].unique()

        vendas_h_criativo = vendas_h[vendas_h['email'].isin(emails_criativo)]
        num_vendas_h  = len(vendas_h_criativo)
        valor_vendas_h = vendas_h_criativo['valor_num'].sum()

        vendas_t_criativo = vendas_t[vendas_t['email'].isin(emails_criativo)]
        num_vendas_t  = len(vendas_t_criativo)
        valor_vendas_t = vendas_t_criativo['valor_num'].sum()

        num_vendas  = num_vendas_h + num_vendas_t
        faturamento = valor_vendas_h + valor_vendas_t

        cpl           = investimento / num_leads   if num_leads   > 0 else 0
        custo_venda   = investimento / num_vendas  if num_vendas  > 0 else 0
        roas          = faturamento  / investimento if investimento > 0 else 0
        taxa_conv     = (num_vendas  / num_leads * 100) if num_leads > 0 else 0

        resultados.append({
            'criativo': criativo,
            'investimento': investimento,
            'leads': num_leads,
            'vendas': num_vendas,
            'faturamento': faturamento,
            'cpl': cpl,
            'custo_por_venda': custo_venda,
            'roas': roas,
            'taxa_conversao': taxa_conv,
        })

    df_resultado = pd.DataFrame(resultados)

    if len(df_resultado) > 0:
        df_resultado = df_resultado.sort_values('vendas', ascending=False)

        print(f"       Criativos analisados: {len(df_resultado)}")
        print(f"       Investimento total:   R$ {df_resultado['investimento'].sum():,.2f}")
        print(f"       Leads total:          {df_resultado['leads'].sum():,}")
        print(f"       Vendas total:         {int(df_resultado['vendas'].sum())}")
        print(f"       Faturamento total:    R$ {df_resultado['faturamento'].sum():,.2f}")
        print(f"       ROAS médio:           {(df_resultado['faturamento'].sum() / df_resultado['investimento'].sum()):.2f}x")

        output_file = f"analises/[PBB-FEV-26]/ANALISE_{nome_plataforma}_[PBB-FEV-26].csv"
        df_resultado.to_csv(output_file, index=False, encoding='utf-8')
        print(f"       Arquivo salvo: {output_file}")

    return df_resultado

# FACEBOOK
df_fb = gerar_analise_plataforma(
    "FACEBOOK",
    df_leads_facebook,
    investimentos_facebook.to_dict(),
    vendas_hotmart,
    vendas_tmb
)

# YOUTUBE
df_yt = gerar_analise_plataforma(
    "YOUTUBE",
    df_leads_youtube,
    investimentos_youtube.to_dict(),
    vendas_hotmart,
    vendas_tmb
)

# CONSOLIDADO
investimentos_consolidado = {}
for criativo in set(list(investimentos_facebook.index) + list(investimentos_youtube.index)):
    inv_fb = investimentos_facebook.get(criativo, 0)
    inv_yt = investimentos_youtube.get(criativo, 0)
    investimentos_consolidado[criativo] = inv_fb + inv_yt

df_cons = gerar_analise_plataforma(
    "CONSOLIDADA",
    df_leads_consolidado,
    investimentos_consolidado,
    vendas_hotmart,
    vendas_tmb
)

print("\n" + "=" * 100)
print("CONCLUIDO! 3 análises geradas:")
print("   1. ANALISE_FACEBOOK_[PBB-FEV-26].csv")
print("   2. ANALISE_YOUTUBE_[PBB-FEV-26].csv")
print("   3. ANALISE_CONSOLIDADA_[PBB-FEV-26].csv")
print("=" * 100)
