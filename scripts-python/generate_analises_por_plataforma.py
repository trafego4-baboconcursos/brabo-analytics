#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de Análises por Plataforma - PBB-ABR-26
Gera 3 relatórios:
1. ANALISE_FACEBOOK (utm_source fb-)
2. ANALISE_YOUTUBE (utm_source yt-)  
3. ANALISE_CONSOLIDADA (fb- + yt-)
"""

import pandas as pd
from pathlib import Path
import csv
import unicodedata

print("=" * 100)
print("GERADOR DE ANALISES POR PLATAFORMA - PBB-ABR-26")
print("=" * 100)


def normalizar_texto(valor):
    if pd.isna(valor):
        return ''
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    return texto


def read_csv_safe(filepath, sep=',', skiprows=0, **kwargs):
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']:
        try:
            return pd.read_csv(filepath, sep=sep, skiprows=skiprows, encoding=enc, **kwargs)
        except Exception:
            continue
    return pd.read_csv(filepath, sep=sep, skiprows=skiprows, **kwargs)


def find_column(df, possible_names):
    def normalize_str(s):
        import unicodedata
        s = str(s).strip().lower()
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
        return s
    
    normalized_possibilities = [normalize_str(n) for n in possible_names]
    
    # 1. Tentar correspondência exata ou normalizada
    for col in df.columns:
        col_norm = normalize_str(col)
        if col_norm in normalized_possibilities:
            return col
            
    # 2. Tentar correspondência por substrings básicas
    for col in df.columns:
        col_norm = col.lower()
        for pos in possible_names:
            pos_norm = pos.lower()
            if 'an' in pos_norm and 'nc' in pos_norm:
                if ('an' in col_norm and 'nc' in col_norm) or 'ad' in col_norm:
                    return col
            elif 'camp' in pos_norm:
                if 'camp' in col_norm or 'campaign' in col_norm:
                    return col
            elif 'cust' in pos_norm:
                if 'cust' in col_norm or 'cost' in col_norm or 'valor' in col_norm or 'gasto' in col_norm:
                    return col
                    
    # 3. Fallback
    for col in df.columns:
        col_norm = normalize_str(col)
        for pos_norm in normalized_possibilities:
            if pos_norm in col_norm or col_norm in pos_norm:
                return col
                
    return possible_names[0]


def eh_captacao(valor):
    texto = normalizar_texto(valor)
    return 'capta' in texto or ('cadastro' in texto and 'capta' in texto)

# ========== CARREGAR LEADS DO CRM ==========
print("\n[1/5] Carregando leads do CRM...")

def encontrar_csv_leads_abr():
    base = Path(r'analises/[PBB-ABR-26]')
    candidatos = []
    for pasta in [base / 'Active Campaign', base / 'active-campaing', base / 'Active campaign']:
        if pasta.exists():
            candidatos.extend(pasta.glob('*.csv'))
    if not candidatos:
        candidatos.extend(f for f in base.rglob('*.csv') if 'pbb-abr-26' in f.name.lower() or 'lead' in f.name.lower())
    return max(candidatos, key=lambda f: f.stat().st_mtime)

leads_file = encontrar_csv_leads_abr()
df_leads = read_csv_safe(leads_file, sep=',', quoting=csv.QUOTE_MINIMAL, low_memory=False)

print(f"   Arquivo: {leads_file.name}")
print(f"   Total de leads: {len(df_leads):,}")

# Preparar dados
col_email = find_column(df_leads, ['Email', 'E-mail', 'email'])
df_leads['Email'] = df_leads[col_email].str.strip().str.lower()
col_utm_source = find_column(df_leads, ['*Utm_source', 'Utm_source', 'utm_source', 'Source'])
df_leads['utm_source_clean'] = df_leads[col_utm_source].fillna('').astype(str).str.strip().str.lower()

# Extrair criativo
col_utm_content = find_column(df_leads, ['*Utm_content', 'Utm_content', 'utm_content', 'Content'])
df_leads['criativo'] = df_leads[col_utm_content].astype(str).apply(
    lambda x: x.split(' - ')[0].strip().upper() if isinstance(x, str) and ' - ' in x else str(x).strip().upper()
)

# Filtrar por plataforma
df_leads_facebook = df_leads[
    df_leads['utm_source_clean'].str.startswith('fb-', na=False)
    & df_leads['utm_source_clean'].apply(eh_captacao)
].copy()
df_leads_youtube = df_leads[
    df_leads['utm_source_clean'].str.startswith('yt-', na=False)
    & df_leads['utm_source_clean'].apply(eh_captacao)
].copy()
df_leads_consolidado = pd.concat([df_leads_facebook, df_leads_youtube], ignore_index=True)

print(f"\n   Distribuicao por plataforma:")
print(f"   - Facebook (fb-): {len(df_leads_facebook):,} leads ({len(df_leads_facebook)/len(df_leads)*100:.1f}%)")
print(f"   - YouTube (yt-):  {len(df_leads_youtube):,} leads ({len(df_leads_youtube)/len(df_leads)*100:.1f}%)")
print(f"   - Consolidado:    {len(df_leads_consolidado):,} leads ({len(df_leads_consolidado)/len(df_leads)*100:.1f}%)")

# ========== CARREGAR VENDAS ==========
print("\n[2/5] Carregando vendas do CRM...")

def encontrar_csv_vendas(nome_base):
    base = Path(r'analises/[PBB-ABR-26]/Vendas')
    if not base.exists():
        raise FileNotFoundError(f"Diretório de Vendas não encontrado: {base}")
    candidatos = list(base.glob('*.csv'))
    for f in candidatos:
        if nome_base.lower() in f.name.lower():
            return f
    raise FileNotFoundError(f"Arquivo de vendas contendo '{nome_base}' não encontrado em {base}")

# Hotmart - excluindo Recuperador Inteligente (parcelas de lancamentos anteriores)
hotmart_file = encontrar_csv_vendas('hotmart')
df_hotmart = read_csv_safe(hotmart_file, sep=';')
col_h_email = find_column(df_hotmart, ['Email do(a) Comprador(a)', 'Email do comprador', 'Email', 'Comprador Email'])
df_hotmart['email'] = df_hotmart[col_h_email].astype(str).str.strip().str.lower()
_tipo_col = next((c for c in df_hotmart.columns if 'tipo' in c.lower() and 'cobran' in c.lower()), None)
if _tipo_col:
    df_hotmart = df_hotmart[df_hotmart[_tipo_col].astype(str).str.strip() != 'Recuperador Inteligente'].copy()
col_h_valor = find_column(df_hotmart, ['Faturamento bruto (sem impostos)', 'Faturamento bruto', 'Preco', 'Preço', 'Valor'])
df_hotmart['valor_num'] = pd.to_numeric(df_hotmart[col_h_valor], errors='coerce')
vendas_hotmart = df_hotmart[df_hotmart['valor_num'] > 0]

# TMB
tmb_file = encontrar_csv_vendas('tmb')
df_tmb = read_csv_safe(tmb_file, sep=';')
col_situacao = [c for c in df_tmb.columns if 'situa' in c.lower()][0]
df_tmb = df_tmb[df_tmb[col_situacao] == 'Vigente']
col_t_email = find_column(df_tmb, ['E-mail do Cliente', 'Email do cliente', 'Email', 'E-mail'])
df_tmb['email'] = df_tmb[col_t_email].str.strip().str.lower()
col_t_valor = find_column(df_tmb, ['Ticket do pedido', 'Ticket', 'Valor', 'Preco'])
df_tmb['valor_num'] = pd.to_numeric(df_tmb[col_t_valor], errors='coerce')
vendas_tmb = df_tmb[df_tmb['valor_num'] > 0]

print(f"   Hotmart: {len(vendas_hotmart)} vendas = R$ {vendas_hotmart['valor_num'].sum():,.2f}")
print(f"   TMB: {len(vendas_tmb)} vendas = R$ {vendas_tmb['valor_num'].sum():,.2f}")
print(f"   TOTAL: {len(vendas_hotmart) + len(vendas_tmb)} vendas = R$ {(vendas_hotmart['valor_num'].sum() + vendas_tmb['valor_num'].sum()):,.2f}")

# ========== CARREGAR INVESTIMENTOS FACEBOOK ==========
print("\n[3/5] Carregando investimentos Facebook (Meta Ads)...")

def encontrar_csv_meta():
    base = Path(r'analises/[PBB-ABR-26]/Meta Ads')
    if not base.exists():
        raise FileNotFoundError(f"Diretório de Meta Ads não encontrado: {base}")
    candidatos = list(base.glob('*.csv'))
    if candidatos:
        return candidatos[0]
    raise FileNotFoundError(f"Arquivo de Meta Ads não encontrado em {base}")

meta_file = encontrar_csv_meta()
df_meta = read_csv_safe(meta_file, sep=',')
col_meta_ad = find_column(df_meta, ['Nome do anúncio', 'Nome do anuncio', 'Ad name', 'Ad Name'])
df_meta['codigo_ad'] = df_meta[col_meta_ad].astype(str).apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)
col_meta_camp = find_column(df_meta, ['Nome da campanha', 'Campanha', 'Campaign name'])
if col_meta_camp in df_meta.columns:
    df_meta = df_meta[df_meta[col_meta_camp].apply(eh_captacao)].copy()
col_meta_gasto = find_column(df_meta, ['Valor usado (BRL)', 'Valor usado', 'Valor gasto', 'Custo', 'Amount spent (BRL)'])
df_meta['valor_gasto'] = pd.to_numeric(
    df_meta[col_meta_gasto].astype(str).str.replace(',', '.'),
    errors='coerce'
).fillna(0)

investimentos_facebook = df_meta.groupby('codigo_ad')['valor_gasto'].sum()
print(f"   Total investido Facebook: R$ {investimentos_facebook.sum():,.2f}")
print(f"   Anuncios com investimento: {len(investimentos_facebook[investimentos_facebook > 0])}")

# ========== CARREGAR INVESTIMENTOS YOUTUBE ==========
print("\n[4/5] Carregando investimentos YouTube (Google Ads)...")

def encontrar_csv_google_anuncios():
    base = Path(r'analises/[PBB-ABR-26]/Google Ads')
    if not base.exists():
        raise FileNotFoundError(f"Diretório de Google Ads não encontrado: {base}")
    for f in base.glob('*.csv'):
        if 'anuncios' in f.name.lower():
            return f
    raise FileNotFoundError(f"Arquivo de anúncios do Google Ads não encontrado em {base}")

youtube_file = encontrar_csv_google_anuncios()
df_youtube = read_csv_safe(youtube_file, sep=',', skiprows=2)
col_yt_ad = find_column(df_youtube, ['Nome do anúncio', 'Nome do anuncio', 'Ad name', 'Ad Name'])
df_youtube['codigo_ad'] = df_youtube[col_yt_ad].astype(str).apply(
    lambda x: x.split(' - ')[0].strip().upper() if ' - ' in x else x.strip().upper()
)
col_yt_camp = find_column(df_youtube, ['Campanha', 'Nome da campanha', 'Campaign'])
df_youtube = df_youtube[df_youtube[col_yt_camp].apply(eh_captacao)].copy()
col_yt_custo = find_column(df_youtube, ['Custo', 'Cost', 'Valor usado', 'Valor gasto'])
df_youtube['custo_num'] = pd.to_numeric(
    df_youtube[col_yt_custo].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

investimentos_youtube = df_youtube.groupby('codigo_ad')['custo_num'].sum()
print(f"   Total investido YouTube: R$ {investimentos_youtube.sum():,.2f}")
print(f"   Anuncios com investimento: {len(investimentos_youtube[investimentos_youtube > 0])}")

# ========== GERAR ANÁLISES ==========
print("\n[5/5] Gerando analises...")

def gerar_analise_plataforma(nome_plataforma, df_leads_filtrado, investimentos_dict, vendas_h, vendas_t):
    """Gera análise para uma plataforma específica"""
    
    print(f"\n   >>> {nome_plataforma}")
    
    # Agrupar leads por criativo
    leads_por_criativo = df_leads_filtrado.groupby('criativo').size()
    
    # Para cada criativo com investimento, calcular métricas
    resultados = []
    
    for criativo, investimento in investimentos_dict.items():
        if investimento == 0:
            continue
        
        # Leads
        num_leads = leads_por_criativo.get(criativo, 0)
        
        # Emails deste criativo
        emails_criativo = df_leads_filtrado[df_leads_filtrado['criativo'] == criativo]['Email'].unique()
        
        # Vendas Hotmart
        vendas_h_criativo = vendas_h[vendas_h['email'].isin(emails_criativo)]
        num_vendas_h = len(vendas_h_criativo)
        valor_vendas_h = vendas_h_criativo['valor_num'].sum()
        
        # Vendas TMB
        vendas_t_criativo = vendas_t[vendas_t['email'].isin(emails_criativo)]
        num_vendas_t = len(vendas_t_criativo)
        valor_vendas_t = vendas_t_criativo['valor_num'].sum()
        
        # Totais
        num_vendas = num_vendas_h + num_vendas_t
        faturamento = valor_vendas_h + valor_vendas_t
        
        # Métricas
        cpl = investimento / num_leads if num_leads > 0 else 0
        custo_por_venda = investimento / num_vendas if num_vendas > 0 else 0
        roas = faturamento / investimento if investimento > 0 else 0
        taxa_conversao = (num_vendas / num_leads * 100) if num_leads > 0 else 0
        
        resultados.append({
            'criativo': criativo,
            'investimento': investimento,
            'leads': num_leads,
            'vendas': num_vendas,
            'faturamento': faturamento,
            'cpl': cpl,
            'custo_por_venda': custo_por_venda,
            'roas': roas,
            'taxa_conversao': taxa_conversao
        })
    
    # Criar DataFrame
    df_resultado = pd.DataFrame(resultados)
    
    if len(df_resultado) > 0:
        df_resultado = df_resultado.sort_values('vendas', ascending=False)
        
        print(f"       Criativos analisados: {len(df_resultado)}")
        print(f"       Investimento total: R$ {df_resultado['investimento'].sum():,.2f}")
        print(f"       Leads total: {df_resultado['leads'].sum():,}")
        print(f"       Vendas total: {int(df_resultado['vendas'].sum())}")
        print(f"       Faturamento total: R$ {df_resultado['faturamento'].sum():,.2f}")
        print(f"       ROAS medio: {(df_resultado['faturamento'].sum() / df_resultado['investimento'].sum()):.2f}x")
        
        # Salvar CSV
        output_file = f"analises/[PBB-ABR-26]/ANALISE_{nome_plataforma}_[PBB-ABR-26].csv"
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
print("CONCLUIDO! 3 analises geradas:")
print("   1. ANALISE_FACEBOOK_[PBB-ABR-26].csv")
print("   2. ANALISE_YOUTUBE_[PBB-ABR-26].csv")
print("   3. ANALISE_CONSOLIDADA_[PBB-ABR-26].csv")
print("=" * 100)
