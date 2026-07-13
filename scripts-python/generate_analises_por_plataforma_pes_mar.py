#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de Analises por Plataforma - PES-MAR-26
Gera 3 CSVs:
1. ANALISE_FACEBOOK_[PES-MAR-26].csv
2. ANALISE_YOUTUBE_[PES-MAR-26].csv
3. ANALISE_CONSOLIDADA_[PES-MAR-26].csv
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

import pandas as pd


BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES = BASE / "analises" / "[PES-MAR-26]"
ACTIVE_CAMPAIGN = ANALISES / "Active Campaign"
GOOGLE_ADS = ANALISES / "Google Ads"
META_ADS = ANALISES / "Meta Ads"
VENDAS = ANALISES / "Vendas"


def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto


def eh_captacao(valor):
    texto = normalizar_texto(valor)
    if "pes-mar-26" not in texto:
        return False
    return "capta" in texto or "cadastro" in texto


def detectar_plataforma(utm_source, utm_campaign):
    source = normalizar_texto(utm_source)
    campaign = normalizar_texto(utm_campaign)
    if any(chave in source for chave in ["facebook", "fb", "meta", "instagram"]):
        return "facebook"
    if any(chave in source for chave in ["google", "youtube", "yt", "gads", "adwords"]):
        return "google"
    if "[ma]" in campaign:
        return "facebook"
    if "[ga]" in campaign:
        return "google"
    return "outros"


def extrair_codigo_criativo(valor):
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return ""
    match = re.search(r"\bAD\d+\b", texto, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return texto.upper()


def bucket_google_por_campanha(valor):
    texto = normalizar_texto(valor)
    if "search" in texto:
        return "SEARCH"
    if "p-max" in texto or "p max" in texto or "performance max" in texto:
        return "PMAX"
    if "display" in texto:
        return "DISPLAY"
    return ""


def campanha_google_video(valor):
    return bucket_google_por_campanha(valor) == ""


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
    
    for col in df.columns:
        col_norm = normalize_str(col)
        if col_norm in normalized_possibilities:
            return col
            
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
                    
    for col in df.columns:
        col_norm = normalize_str(col)
        for pos_norm in normalized_possibilities:
            if pos_norm in col_norm or col_norm in pos_norm:
                return col
                
    return possible_names[0]


def encontrar_csv_leads():
    arquivos = sorted(ACTIVE_CAMPAIGN.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {ACTIVE_CAMPAIGN}")
    return max(arquivos, key=lambda path: path.stat().st_mtime)


def carregar_vendas():
    colunas = ["email", "valor_num"]
    if not VENDAS.exists():
        return pd.DataFrame(columns=colunas), pd.DataFrame(columns=colunas)

    hotmart_files = sorted(VENDAS.glob("*hotmart*.csv"))
    tmb_files = sorted(VENDAS.glob("*tmb*.csv")) + sorted(VENDAS.glob("*pedido*.csv"))

    if hotmart_files:
        _p_raw = read_csv_safe(hotmart_files[0], sep=";")
        col_email = find_column(_p_raw, ["Email do(a) Comprador(a)", "Email", "Comprador Email"])
        _p_raw["email"] = _p_raw[col_email].astype(str).str.strip().str.lower()
        _p_raw = _p_raw[_p_raw["email"].str.contains("@", na=False)].copy()
        _p_tipo = next((c for c in _p_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
        col_valor = find_column(_p_raw, ["Faturamento líquido do(a) Produtor(a)", "Preço", "Preco", "Valor"])
        
        if _p_tipo:
            _p_par = "Quantidade total de parcelas"
            _p_cob = "Quantidade de cobranças"
            _p_norm = _p_raw[_p_raw[_p_tipo].astype(str).str.strip() != "Recuperador Inteligente"].copy()
            _p_norm["valor_num"] = pd.to_numeric(_p_norm[col_valor], errors="coerce").fillna(0)
            
            # Tratar caso existam recuperadores inteligentes
            if _p_par in _p_raw.columns and _p_cob in _p_raw.columns:
                _p_ri = _p_raw[
                    (_p_raw[_p_tipo].astype(str).str.strip() == "Recuperador Inteligente") &
                    (pd.to_numeric(_p_raw[_p_cob], errors="coerce").fillna(0) == 1)
                ].copy()
                _p_ri[_p_par] = pd.to_numeric(_p_ri[_p_par], errors="coerce").fillna(1)
                _p_ri["valor_num"] = pd.to_numeric(_p_ri[col_valor], errors="coerce").fillna(0) * _p_ri[_p_par]
                df_hotmart = pd.concat([_p_norm, _p_ri], ignore_index=True)
            else:
                df_hotmart = _p_norm
        else:
            df_hotmart = _p_raw.copy()
            df_hotmart["valor_num"] = pd.to_numeric(df_hotmart[col_valor], errors="coerce").fillna(0)
        vendas_hotmart = df_hotmart[df_hotmart["valor_num"] > 0][colunas].copy()
    else:
        vendas_hotmart = pd.DataFrame(columns=colunas)

    if tmb_files:
        df_tmb = read_csv_safe(tmb_files[0], sep=";")
        status_col = next((c for c in df_tmb.columns if "situa" in c.lower()), None)
        if status_col:
            status_norm = df_tmb[status_col].astype(str).str.strip().str.lower()
            df_tmb = df_tmb[status_norm.isin({"vigente", "efetivado", "paga", "vigente "})].copy()
        email_col = find_column(df_tmb, ["E-mail do Cliente", "Email do cliente", "Email", "E-mail"])
        valor_col = find_column(df_tmb, ["Ticket do pedido", "Ticket", "Valor", "Preco"])
        if email_col and valor_col:
            df_tmb["email"] = df_tmb[email_col].astype(str).str.strip().str.lower()
            df_tmb["valor_num"] = pd.to_numeric(
                df_tmb[valor_col].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            ).fillna(0)
            vendas_tmb = df_tmb[df_tmb["valor_num"] > 0][colunas].copy()
        else:
            vendas_tmb = pd.DataFrame(columns=colunas)
    else:
        vendas_tmb = pd.DataFrame(columns=colunas)

    return vendas_hotmart, vendas_tmb


def carregar_investimentos_meta():
    arquivos = sorted(META_ADS.glob("*.csv"))
    if not arquivos:
        return {}
    
    # Prevenir falha se arquivo estiver vazio ou corrompido
    try:
        df_meta = read_csv_safe(arquivos[0], sep=",")
    except Exception:
        return {}
        
    col_camp = find_column(df_meta, ["Nome da campanha", "Campanha", "Campaign"])
    if col_camp in df_meta.columns:
        df_meta = df_meta[df_meta[col_camp].apply(eh_captacao)].copy()
        
    col_ad = find_column(df_meta, ["Nome do anúncio", "Nome do anuncio", "Ad Name", "Ad name"])
    col_valor = find_column(df_meta, ["Valor usado (BRL)", "Valor usado", "Valor gasto", "Custo"])
    
    if col_ad not in df_meta.columns or col_valor not in df_meta.columns:
        return {}
        
    df_meta["codigo_ad"] = df_meta[col_ad].astype(str).apply(extrair_codigo_criativo)
    df_meta["valor_gasto"] = pd.to_numeric(
        df_meta[col_valor].astype(str).str.replace(",", "."),
        errors="coerce",
    ).fillna(0)
    return df_meta.groupby("codigo_ad")["valor_gasto"].sum().to_dict()


def carregar_investimentos_google():
    arquivos = sorted(GOOGLE_ADS.glob("Performance dos anúncios*.csv"))
    if not arquivos:
        return {}
    
    try:
        df_google = read_csv_safe(arquivos[0], sep=",", skiprows=2)
    except Exception:
        return {}
        
    col_camp = find_column(df_google, ["Campanha", "Nome da campanha", "Campaign"])
    if col_camp in df_google.columns:
        df_google = df_google[df_google[col_camp].apply(eh_captacao)].copy()
        df_google = df_google[df_google[col_camp].apply(campanha_google_video)].copy()
        
    col_custo = find_column(df_google, ["Custo", "Cost", "Valor usado", "Valor gasto"])
    if col_custo not in df_google.columns:
        return {}
        
    nome_col = find_column(df_google, ["Nome do anúncio", "Nome do anuncio", "Ad Name", "Ad name"])
    grupo_col = find_column(df_google, ["Grupo de anúncios", "Grupo de anuncios", "Ad Group", "Ad group"])
    custom_col = find_column(df_google, ["Parâmetro personalizado", "Parametro personalizado", "Custom parameter"])

    def codigo_google(row):
        campanha = str(row.get(col_camp, "")) if col_camp in row else ""
        nome = str(row.get(nome_col, "")) if nome_col in row else ""
        if nome and nome != "--":
            return extrair_codigo_criativo(nome)
        custom = str(row.get(custom_col, "")) if custom_col in row else ""
        match = re.search(r"AD\d+", custom, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
        bucket = bucket_google_por_campanha(campanha)
        if bucket:
            return bucket
        grupo = str(row.get(grupo_col, "")) if grupo_col in row else ""
        return grupo.upper()

    df_google["codigo_ad"] = df_google.apply(codigo_google, axis=1)
    df_google["custo_num"] = pd.to_numeric(
        df_google[col_custo].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)
    return df_google.groupby("codigo_ad")["custo_num"].sum().to_dict()


def carregar_investimentos_google_por_tipo():
    arquivos = sorted(GOOGLE_ADS.glob("Performance da campanha*.csv"))
    if not arquivos:
        return {}
        
    try:
        df_google = read_csv_safe(arquivos[0], sep=",", skiprows=2)
    except Exception:
        return {}
        
    col_camp = find_column(df_google, ["Campanha", "Nome da campanha", "Campaign"])
    if col_camp in df_google.columns:
        df_google = df_google[df_google[col_camp].apply(eh_captacao)].copy()
        
    col_custo = find_column(df_google, ["Custo", "Cost", "Valor usado", "Valor gasto"])
    if col_custo not in df_google.columns:
        return {}
        
    df_google["tipo_bucket"] = df_google[col_camp].astype(str).apply(bucket_google_por_campanha)
    df_google = df_google[df_google["tipo_bucket"] != ""].copy()
    df_google["custo_num"] = pd.to_numeric(
        df_google[col_custo].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)
    return df_google.groupby("tipo_bucket")["custo_num"].sum().to_dict()


def gerar_analise_plataforma(nome_plataforma, df_leads_filtrado, investimentos_dict, vendas_h, vendas_t):
    resultados = []
    leads_por_criativo = df_leads_filtrado.groupby("criativo").size()

    # Prevenir que fique vazio se investimentos estiver zerado (Opção 1)
    criativos_para_analisar = set(investimentos_dict.keys())
    if not criativos_para_analisar or sum(investimentos_dict.values()) == 0:
        criativos_para_analisar = set(leads_por_criativo.index)
        # Filtrar vazios e nulos
        criativos_para_analisar = {c for c in criativos_para_analisar if c and str(c).strip().upper() not in {"", "NAN"}}

    for criativo in sorted(criativos_para_analisar):
        investimento = investimentos_dict.get(criativo, 0.0)
        num_leads = int(leads_por_criativo.get(criativo, 0))
        
        # Ignorar criativos sem leads E sem investimento
        if num_leads == 0 and investimento == 0:
            continue

        emails_criativo = df_leads_filtrado[df_leads_filtrado["criativo"] == criativo]["Email"].unique()

        vendas_h_criativo = vendas_h[vendas_h["email"].isin(emails_criativo)] if not vendas_h.empty else vendas_h
        vendas_t_criativo = vendas_t[vendas_t["email"].isin(emails_criativo)] if not vendas_t.empty else vendas_t

        num_vendas_h = len(vendas_h_criativo)
        valor_vendas_h = vendas_h_criativo["valor_num"].sum() if not vendas_h_criativo.empty else 0
        num_vendas_t = len(vendas_t_criativo)
        valor_vendas_t = vendas_t_criativo["valor_num"].sum() if not vendas_t_criativo.empty else 0

        num_vendas = num_vendas_h + num_vendas_t
        faturamento = float(valor_vendas_h + valor_vendas_t)
        
        cpl = investimento / num_leads if num_leads > 0 else 0
        custo_por_venda = investimento / num_vendas if num_vendas > 0 else 0
        roas = faturamento / investimento if investimento > 0 else 0
        taxa_conversao = (num_vendas / num_leads * 100) if num_leads > 0 else 0

        resultados.append(
            {
                "criativo": criativo,
                "investimento": investimento,
                "leads": num_leads,
                "vendas": num_vendas,
                "faturamento": faturamento,
                "cpl": cpl,
                "custo_por_venda": custo_por_venda,
                "roas": roas,
                "taxa_conversao": taxa_conversao,
            }
        )

    df_resultado = pd.DataFrame(resultados)
    if not df_resultado.empty:
        df_resultado = df_resultado.sort_values(["vendas", "faturamento", "leads"], ascending=False)
    else:
        df_resultado = pd.DataFrame(columns=["criativo", "investimento", "leads", "vendas", "faturamento", "cpl", "custo_por_venda", "roas", "taxa_conversao"])
        
    output_file = ANALISES / f"ANALISE_{nome_plataforma}_[PES-MAR-26].csv"
    df_resultado.to_csv(output_file, index=False, encoding="utf-8")
    return df_resultado


def anexar_resumo_google_por_tipo(df_resultado, df_leads_google, vendas_h, vendas_t, investimentos_tipo):
    if df_leads_google.empty:
        return df_resultado

    df_base = df_leads_google.copy()
    df_base["tipo_bucket"] = df_base["*Utm_campaign"].astype(str).apply(bucket_google_por_campanha)
    df_base = df_base[df_base["tipo_bucket"] != ""].copy()

    # Prevenir que fique vazio se investimentos estiver zerado (Opção 1)
    buckets_a_analisar = set(investimentos_tipo.keys())
    if not buckets_a_analisar or sum(investimentos_tipo.values()) == 0:
        buckets_a_analisar = set(df_base["tipo_bucket"].unique())

    linhas = []
    for bucket in buckets_a_analisar:
        investimento = investimentos_tipo.get(bucket, 0.0)
        leads_bucket = df_base[df_base["tipo_bucket"] == bucket].copy()
        emails_bucket = leads_bucket["Email"].dropna().astype(str).str.strip().str.lower().unique()
        num_leads = len(leads_bucket)
        
        # Ignorar buckets sem leads E sem investimento
        if num_leads == 0 and investimento == 0:
            continue
            
        vendas_h_bucket = vendas_h[vendas_h["email"].isin(emails_bucket)] if not vendas_h.empty else vendas_h
        vendas_t_bucket = vendas_t[vendas_t["email"].isin(emails_bucket)] if not vendas_t.empty else vendas_t
        num_vendas = len(vendas_h_bucket) + len(vendas_t_bucket)
        faturamento = float(
            (vendas_h_bucket["valor_num"].sum() if not vendas_h_bucket.empty else 0)
            + (vendas_t_bucket["valor_num"].sum() if not vendas_t_bucket.empty else 0)
        )
        linhas.append(
            {
                "criativo": bucket,
                "investimento": float(investimento),
                "leads": int(num_leads),
                "vendas": int(num_vendas),
                "faturamento": faturamento,
                "cpl": float(investimento) / num_leads if num_leads > 0 else 0,
                "custo_por_venda": float(investimento) / num_vendas if num_vendas > 0 else 0,
                "roas": faturamento / float(investimento) if investimento > 0 else 0,
                "taxa_conversao": (num_vendas / num_leads * 100) if num_leads > 0 else 0,
            }
        )

    if not linhas:
        return df_resultado

    df_tipos = pd.DataFrame(linhas)
    df_sem_tipos = df_resultado[~df_resultado["criativo"].astype(str).isin(df_tipos["criativo"])].copy()
    combinado = pd.concat([df_sem_tipos, df_tipos], ignore_index=True)
    return combinado.sort_values(["vendas", "faturamento", "leads"], ascending=False).reset_index(drop=True)


def main():
    print("=" * 100)
    print("GERADOR DE ANALISES POR PLATAFORMA - PES-MAR-26")
    print("=" * 100)

    leads_file = encontrar_csv_leads()
    df_leads = read_csv_safe(leads_file, sep=",", quoting=csv.QUOTE_MINIMAL, low_memory=False)
    
    col_email = find_column(df_leads, ["Email", "E-mail", "email"])
    col_utm_source = find_column(df_leads, ["*Utm_source", "Utm_source", "utm_source"])
    col_utm_campaign = find_column(df_leads, ["*Utm_campaign", "Utm_campaign", "utm_campaign"])
    col_utm_term = find_column(df_leads, ["*Utm_term", "Utm_term", "utm_term"])
    col_utm_content = find_column(df_leads, ["*Utm_content", "Utm_content", "utm_content"])
    
    df_leads["Email"] = df_leads[col_email].astype(str).str.strip().str.lower()
    df_leads["utm_source_clean"] = df_leads[col_utm_source].fillna("").astype(str).str.strip().str.lower()
    df_leads["utm_campaign_clean"] = df_leads[col_utm_campaign].fillna("").astype(str).str.strip()
    
    df_leads["plataforma"] = df_leads.apply(
        lambda row: detectar_plataforma(row.get(col_utm_source, ""), row.get(col_utm_campaign, "")),
        axis=1,
    )
    df_leads["google_bucket"] = df_leads[col_utm_campaign].astype(str).apply(bucket_google_por_campanha)
    df_leads["criativo"] = df_leads[col_utm_term].astype(str).apply(extrair_codigo_criativo)
    
    sem_criativo = df_leads["criativo"].eq("") | df_leads["criativo"].eq("NAN")
    if "*vk_ad_id" in df_leads.columns:
        df_leads.loc[sem_criativo, "criativo"] = df_leads.loc[sem_criativo, "*vk_ad_id"].astype(str).apply(extrair_codigo_criativo)
        
    sem_criativo = df_leads["criativo"].eq("") | df_leads["criativo"].eq("NAN")
    df_leads.loc[sem_criativo, "criativo"] = df_leads.loc[sem_criativo, col_utm_content].astype(str).apply(extrair_codigo_criativo)
    
    sem_criativo = df_leads["criativo"].eq("") | df_leads["criativo"].eq("NAN")
    google_sem_criativo = sem_criativo & df_leads["plataforma"].eq("google")
    df_leads.loc[google_sem_criativo, "criativo"] = df_leads.loc[google_sem_criativo, col_utm_campaign].astype(str).apply(bucket_google_por_campanha)

    df_leads_captacao = df_leads[df_leads["utm_campaign_clean"].apply(eh_captacao)].copy()
    df_leads_facebook = df_leads_captacao[df_leads_captacao["plataforma"] == "facebook"].copy()
    df_leads_google = df_leads_captacao[df_leads_captacao["plataforma"] == "google"].copy()
    df_leads_google_youtube = df_leads_google[df_leads_google["google_bucket"] == ""].copy()
    df_leads_consolidado = pd.concat([df_leads_facebook, df_leads_google_youtube], ignore_index=True)

    print(f"Arquivo de leads: {leads_file.name}")
    print(f"Leads captacao: {len(df_leads_captacao):,}")
    print(f"Facebook: {len(df_leads_facebook):,}")
    print(f"Google total: {len(df_leads_google):,}")
    print(f"YouTube: {len(df_leads_google_youtube):,}")

    vendas_hotmart, vendas_tmb = carregar_vendas()
    print(f"Hotmart encontradas: {len(vendas_hotmart)}")
    print(f"TMB encontradas: {len(vendas_tmb)}")

    investimentos_facebook = carregar_investimentos_meta()
    investimentos_google = carregar_investimentos_google()
    investimentos_google_tipo = carregar_investimentos_google_por_tipo()
    
    # Criar um dict consolidado resiliente
    investimentos_consolidado = {}
    chaves_totais = set(investimentos_facebook.keys()) | set(investimentos_google.keys())
    for chave in chaves_totais:
        investimentos_consolidado[chave] = investimentos_facebook.get(chave, 0.0) + investimentos_google.get(chave, 0.0)

    gerar_analise_plataforma("FACEBOOK", df_leads_facebook, investimentos_facebook, vendas_hotmart, vendas_tmb)
    df_google_resultado = gerar_analise_plataforma("YOUTUBE", df_leads_google_youtube, investimentos_google, vendas_hotmart, vendas_tmb)
    df_google_resultado = anexar_resumo_google_por_tipo(
        df_google_resultado,
        df_leads_google,
        vendas_hotmart,
        vendas_tmb,
        investimentos_google_tipo,
    )
    df_google_resultado.to_csv(ANALISES / "ANALISE_YOUTUBE_[PES-MAR-26].csv", index=False, encoding="utf-8")
    
    df_consolidado_resultado = gerar_analise_plataforma("CONSOLIDADA", df_leads_consolidado, investimentos_consolidado, vendas_hotmart, vendas_tmb)
    df_consolidado_resultado = anexar_resumo_google_por_tipo(
        df_consolidado_resultado,
        df_leads_google,
        vendas_hotmart,
        vendas_tmb,
        investimentos_google_tipo,
    )
    df_consolidado_resultado.to_csv(ANALISES / "ANALISE_CONSOLIDADA_[PES-MAR-26].csv", index=False, encoding="utf-8")

    print("CSVs gerados em analises/[PES-MAR-26]/")


if __name__ == "__main__":
    main()
