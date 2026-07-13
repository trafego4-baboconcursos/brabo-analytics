import pandas as pd
import os
from pathlib import Path

print("\n" + "=" * 100)
print("🔍 ANÁLISE DE UTMs POR PLATAFORMA - PBB-ABR-26")
print("=" * 100)

# ========== ENCONTRAR CSV DE LEADS ==========
def encontrar_csv_leads_abr():
    pasta_ac = Path(r'analises/[PBB-ABR-26]/Active Campaign')
    if not pasta_ac.exists():
        return None
    
    csvs = list(pasta_ac.glob('*.csv'))
    if not csvs:
        return None
    
    # Pegar o mais recente
    csv_mais_recente = max(csvs, key=lambda p: p.stat().st_mtime)
    return str(csv_mais_recente)

# ========== CARREGAR LEADS DO CRM ==========
csv_leads = encontrar_csv_leads_abr()
if not csv_leads:
    print("\n❌ Arquivo de leads não encontrado!")
    exit(1)

print(f"\n📁 Carregando: {os.path.basename(csv_leads)}")
df_leads = pd.read_csv(csv_leads, sep=',', encoding='utf-8')
print(f"   ✓ Total de leads: {len(df_leads):,}")

# ========== ANALISAR COLUNAS UTM ==========
print(f"\n📊 COLUNAS UTM DISPONÍVEIS:")
utm_cols = [col for col in df_leads.columns if 'utm' in col.lower() or 'source' in col.lower() or 'medium' in col.lower()]
for col in utm_cols:
    print(f"   • {col}")

# ========== ANALISAR UTM_SOURCE ==========
utm_source_col = '*Utm_source' if '*Utm_source' in df_leads.columns else 'utm_source'
utm_content_col = '*Utm_content' if '*Utm_content' in df_leads.columns else 'utm_content'

if utm_source_col in df_leads.columns:
    print(f"\n🎯 DISTRIBUIÇÃO POR UTM_SOURCE:")
    print("-" * 100)
    
    df_leads['utm_source_clean'] = df_leads[utm_source_col].fillna('(não informado)').astype(str).str.strip().str.lower()
    
    source_counts = df_leads['utm_source_clean'].value_counts()
    for source, count in source_counts.head(20).items():
        pct = (count / len(df_leads)) * 100
        print(f"   {source:30} → {count:6,} leads ({pct:5.2f}%)")
    
    # ========== FACEBOOK ==========
    df_facebook = df_leads[df_leads['utm_source_clean'].str.startswith('fb-', na=False)]
    print(f"\n📘 LEADS DO FACEBOOK (utm_source começa com 'fb-'):")
    print(f"   Total: {len(df_facebook):,} leads ({(len(df_facebook)/len(df_leads))*100:.2f}%)")
    
    if utm_content_col in df_leads.columns and len(df_facebook) > 0:
        df_facebook_criativo = df_facebook[df_facebook[utm_content_col].notna()].copy()
        df_facebook_criativo['criativo'] = df_facebook_criativo[utm_content_col].astype(str).apply(lambda x: x.split(' - ')[0].strip().upper() if isinstance(x, str) and ' - ' in x else str(x).strip().upper())
        criativos_fb = df_facebook_criativo['criativo'].value_counts()
        print(f"\n   Top 15 criativos Facebook:")
        for criativo, count in criativos_fb.head(15).items():
            if criativo not in ['NAN', '(NÃO INFORMADO)', '']:
                print(f"      {criativo:15} → {count:5,} leads")
    
    # ========== YOUTUBE ==========
    df_youtube = df_leads[df_leads['utm_source_clean'].str.startswith('yt-', na=False)]
    print(f"\n🎥 LEADS DO YOUTUBE (utm_source começa com 'yt-'):")
    print(f"   Total: {len(df_youtube):,} leads ({(len(df_youtube)/len(df_leads))*100:.2f}%)")
    
    if utm_content_col in df_leads.columns and len(df_youtube) > 0:
        df_youtube_criativo = df_youtube[df_youtube[utm_content_col].notna()].copy()
        df_youtube_criativo['criativo'] = df_youtube_criativo[utm_content_col].astype(str).apply(lambda x: x.split(' - ')[0].strip().upper() if isinstance(x, str) and ' - ' in x else str(x).strip().upper())
        criativos_yt = df_youtube_criativo['criativo'].value_counts()
        print(f"\n   Top 15 criativos YouTube:")
        for criativo, count in criativos_yt.head(15).items():
            if criativo not in ['NAN', '(NÃO INFORMADO)', '']:
                print(f"      {criativo:15} → {count:5,} leads")
    
    # ========== GOOGLE ADS (Search/Display) ==========
    df_google = df_leads[df_leads['utm_source_clean'].str.startswith('google', na=False) | df_leads['utm_source_clean'].str.contains('adwords|gads', na=False)]
    print(f"\n🔍 LEADS DO GOOGLE ADS:")
    print(f"   Total: {len(df_google):,} leads ({(len(df_google)/len(df_leads))*100:.2f}%)")
    
    # ========== OUTRAS FONTES ==========
    df_outras = df_leads[
        ~df_leads['utm_source_clean'].str.startswith('fb-', na=False) &
        ~df_leads['utm_source_clean'].str.startswith('yt-', na=False) &
        ~df_leads['utm_source_clean'].str.startswith('google', na=False) &
        (df_leads['utm_source_clean'] != '(não informado)')
    ]
    print(f"\n📌 OUTRAS FONTES:")
    print(f"   Total: {len(df_outras):,} leads ({(len(df_outras)/len(df_leads))*100:.2f}%)")
    
    if len(df_outras) > 0:
        outras_sources = df_outras['utm_source_clean'].value_counts()
        print(f"\n   Top 10:")
        for source, count in outras_sources.head(10).items():
            print(f"      {source:40} → {count:6,} leads")

# ========== ANALISAR AD093 ESPECIFICAMENTE ==========
if utm_content_col in df_leads.columns:
    print(f"\n🔍 PROCURANDO AD093 NAS UTMs:")
    print("-" * 100)
    
    # Criar coluna criativo para todos os leads com tratamento para NaN
    df_leads_com_criativo = df_leads[df_leads[utm_content_col].notna()].copy()
    df_leads_com_criativo['criativo'] = df_leads_com_criativo[utm_content_col].astype(str).apply(
        lambda x: x.split(' - ')[0].strip().upper() if isinstance(x, str) and ' - ' in x else str(x).strip().upper()
    )
    ad093_leads = df_leads_com_criativo[df_leads_com_criativo['criativo'] == 'AD093']
    
    print(f"   Total de leads com AD093: {len(ad093_leads):,}")
    
    if len(ad093_leads) > 0 and utm_source_col in df_leads.columns:
        print(f"\n   Distribuição por plataforma:")
        ad093_by_source = ad093_leads['utm_source_clean'].value_counts()
        for source, count in ad093_by_source.items():
            print(f"      {source:20} → {count:5,} leads")

print("\n" + "=" * 100)
