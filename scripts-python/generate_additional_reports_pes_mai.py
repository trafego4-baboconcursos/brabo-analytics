#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv as csvmod
from datetime import datetime
from pathlib import Path
import unicodedata

import pandas as pd


BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES = BASE / "analises" / "[PES-MAI-26]"
GOOGLE = ANALISES / "Google Ads"
META = ANALISES / "Meta Ads"
ACTIVE = ANALISES / "Active Campaign"
TYPEFORM = ANALISES / "Typeform"
VENDAS = ANALISES / "Vendas"
LOGO_PATH = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"


def br_money(value: float) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def br_int(value: float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def br_pct(value: float) -> str:
    return f"{float(value):.2f}%".replace(".", ",")


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def parse_number(value) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    try:
        return pd.read_csv(path, **kwargs)
    except UnicodeDecodeError:
        kwargs.setdefault("encoding", "latin-1")
        return pd.read_csv(path, **kwargs)


def filter_campaign_scope(df: pd.DataFrame, column_name: str) -> pd.DataFrame:
    if column_name not in df.columns:
        return df
    return df[df[column_name].astype(str).str.contains("PES-MAI-26", case=False, na=False)].copy()


def load_sales() -> tuple[pd.DataFrame, float, int]:
    hm_raw = read_csv(VENDAS / "pes-mai-26-hotmart.csv", sep=";", encoding="utf-8", low_memory=False)
    hm_raw["email"] = hm_raw["Email do(a) Comprador(a)"].astype(str).str.strip().str.lower()
    hm_raw = hm_raw[hm_raw["email"].str.contains("@", na=False)].copy()
    _tipo_c = next((c for c in hm_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
    if _tipo_c:
        _par_c = "Quantidade total de parcelas"
        _cob_c = "Quantidade de cobranças"
        _h_norm = hm_raw[hm_raw[_tipo_c].astype(str).str.strip() != "Recuperador Inteligente"].copy()
        _h_norm["valor"] = pd.to_numeric(_h_norm["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
        _h_ri = hm_raw[
            (hm_raw[_tipo_c].astype(str).str.strip() == "Recuperador Inteligente") &
            (pd.to_numeric(hm_raw[_cob_c], errors="coerce").fillna(0) == 1)
        ].copy()
        _h_ri[_par_c] = pd.to_numeric(_h_ri[_par_c], errors="coerce").fillna(1)
        _h_ri["valor"] = pd.to_numeric(_h_ri["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0) * _h_ri[_par_c]
        hm = pd.concat([_h_norm[["email", "valor"]], _h_ri[["email", "valor"]]], ignore_index=True)
    else:
        hm = hm_raw.copy()
        hm["valor"] = pd.to_numeric(hm["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)

    tmb = read_csv(VENDAS / "pes-mai-26-tmb.csv", sep=";", encoding="utf-8", low_memory=False)
    email_col = next(c for c in tmb.columns if "mail" in c.lower())
    ticket_col = next(c for c in tmb.columns if "ticket" in c.lower())
    tmb["email"] = tmb[email_col].astype(str).str.strip().str.lower()
    tmb["valor"] = pd.to_numeric(tmb[ticket_col], errors="coerce").fillna(0)
    tmb = tmb[tmb["email"].str.contains("@", na=False)].copy()

    sales = pd.concat([hm[["email", "valor"]], tmb[["email", "valor"]]], ignore_index=True)
    return sales, float(sales["valor"].sum()), int(sales["email"].nunique())


def load_crm() -> pd.DataFrame:
    crm_file = max(ACTIVE.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    crm = read_csv(crm_file, sep=",", quoting=csvmod.QUOTE_MINIMAL, low_memory=False)
    crm["email"] = crm["Email"].astype(str).str.strip().str.lower()
    crm = crm[crm["email"].str.contains("@", na=False)].copy()
    crm["utm_source"] = crm.get("*Utm_source", "").fillna("")
    crm["utm_campaign"] = crm.get("*Utm_campaign", "").fillna("")
    crm["utm_medium"] = crm.get("*Utm_medium", "").fillna("")
    crm["plataforma"] = crm["utm_source"].apply(classificar_plataforma)
    crm["clima"] = crm["utm_campaign"].apply(classificar_clima)
    return crm


def classificar_plataforma(value: str) -> str:
    text = normalize_text(value)
    if any(chave in text for chave in ["facebook", "fb", "meta", "instagram"]):
        return "Meta / Facebook"
    if any(chave in text for chave in ["google", "youtube", "yt", "gads", "adwords"]):
        return "Google / YouTube"
    if "whatsapp" in text or "comercial" in text:
        return "Comercial / WhatsApp"
    return "Outros"


def classificar_clima(value: str) -> str:
    text = normalize_text(value)
    if "quente" in text:
        return "Quente"
    if "frio" in text:
        return "Frio"
    if "especific" in text:
        return "Específico"
    return "Outros"


def get_css_base() -> str:
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
            vertical-align: top;
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

        .metric-box .sub {
            font-size: 12px;
            opacity: 0.9;
            margin-top: 6px;
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
            margin-top: 30px;
        }

        .two-col {
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(360px,1fr));
            gap:20px;
            align-items:start;
        }

        .note {
            color:#555;
            line-height:1.7;
            margin: 12px 0;
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
            .metric-box {
                min-width: unset;
                width: 100%;
                margin-right: 0;
            }
        }
    </style>
    """


def base_html(title: str, subtitle: str, metrics_html: str, sections_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    {get_css_base()}
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-logo">
                <a href="INDEX_[PES-MAI-26].html">
                    <img src="{LOGO_PATH}" alt="Brabo Concursos">
                </a>
            </div>
            <div class="header-title">
                <h1>{title}</h1>
                <p>Campanha PES-MAI-26</p>
                <p>Período: Maio de 2026</p>
            </div>
        </div>
        <div class="content">
            <p class="note">{subtitle}</p>
            <div style="margin: 20px 0;">{metrics_html}</div>
            {sections_html}
            <div class="footer">
                <p>Análises geradas em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</p>
            </div>
        </div>
    </div>
</body>
</html>"""


def metric(label: str, value: str, sub: str = "") -> str:
    return f'<div class="metric-box"><div class="label">{label}</div><div class="value">{value}</div><div class="sub">{sub}</div></div>'


def table_from_df(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p class='note'>Sem dados disponíveis.</p>"
    head = "".join(f"<th>{col}</th>" for col in df.columns)
    rows = []
    for _, row in df.iterrows():
        rows.append("<tr>" + "".join(f"<td>{row[col]}</td>" for col in df.columns) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def write_report(filename: str, title: str, subtitle: str, metrics_html: str, sections_html: str):
    (ANALISES / filename).write_text(base_html(title, subtitle, metrics_html, sections_html), encoding="utf-8")
    print(f"✓ {filename}")


def main():
    sales, receita_total, compradores = load_sales()
    crm = load_crm()
    total_leads = int(crm["email"].nunique())
    tf_cap = read_csv(TYPEFORM / "typeform-projeto-pes-mai-26.csv", low_memory=False)
    tf_alunos = read_csv(TYPEFORM / "typeform-alunos-pes-mai-26.csv", low_memory=False)
    meta = read_csv(META / "Campanhas-Completas-pes-mai-26.csv", sep=",", low_memory=False)
    ga_campaign = read_csv(GOOGLE / "Performance da campanha-pes-mai-26.csv", sep=",", skiprows=2, low_memory=False)
    ga_ads = read_csv(GOOGLE / "Performance dos anúncios-pes-mai-26.csv", sep=",", skiprows=2, low_memory=False)
    ga_aud = read_csv(GOOGLE / "Públicos-alvo-pes-mai-26.csv", sep=",", skiprows=2, low_memory=False)
    meta = filter_campaign_scope(meta, "Nome da campanha")
    ga_campaign = filter_campaign_scope(ga_campaign, "Campanha")
    ga_ads = filter_campaign_scope(ga_ads, "Campanha")
    ga_aud = filter_campaign_scope(ga_aud, "Campanha")
    cons = read_csv(ANALISES / "ANALISE_CONSOLIDADA_[PES-MAI-26].csv")
    fb = read_csv(ANALISES / "ANALISE_FACEBOOK_[PES-MAI-26].csv")
    yt = read_csv(ANALISES / "ANALISE_YOUTUBE_[PES-MAI-26].csv")

    meta["investimento"] = meta["Valor usado (BRL)"].apply(parse_number)
    meta["leads_num"] = pd.to_numeric(meta["Leads"], errors="coerce").fillna(0)
    meta_campaigns = meta.groupby("Nome da campanha").agg(Investimento=("investimento", "sum"), Leads=("leads_num", "sum"), Anuncios=("Nome do anúncio", "nunique")).reset_index().sort_values("Investimento", ascending=False).head(15)
    meta_campaigns["Investimento"] = meta_campaigns["Investimento"].map(br_money)
    meta_campaigns["Leads"] = meta_campaigns["Leads"].map(br_int)
    meta_campaigns["Anuncios"] = meta_campaigns["Anuncios"].map(br_int)
    meta_sets = meta.groupby("Nome do conjunto de anúncios").agg(Investimento=("investimento", "sum"), Leads=("leads_num", "sum")).reset_index().sort_values("Investimento", ascending=False).head(15)
    meta_sets["Investimento"] = meta_sets["Investimento"].map(br_money)
    meta_sets["Leads"] = meta_sets["Leads"].map(br_int)

    ga_campaign["Custo"] = ga_campaign["Custo"].apply(parse_number)
    ga_campaign["Conversões"] = ga_campaign["Conversões"].apply(parse_number)
    ga_campaign["Cliques"] = ga_campaign["Cliques"].apply(parse_number)
    ga_top = ga_campaign[["Campanha", "Tipo de campanha", "Cliques", "Conversões", "Custo"]].copy().sort_values("Custo", ascending=False).head(15)
    ga_top["Cliques"] = ga_top["Cliques"].map(br_int)
    ga_top["Conversões"] = ga_top["Conversões"].map(br_int)
    ga_top["Custo"] = ga_top["Custo"].map(br_money)

    ga_aud["Custo"] = ga_aud["Custo"].apply(parse_number)
    ga_aud["Cliques"] = ga_aud["Cliques"].apply(parse_number)
    ga_aud_top = ga_aud[["Segmento de público-alvo", "Campanha", "Grupo de anúncios", "Cliques", "Custo"]].copy().sort_values("Custo", ascending=False).head(20)
    ga_aud_top["Cliques"] = ga_aud_top["Cliques"].map(br_int)
    ga_aud_top["Custo"] = ga_aud_top["Custo"].map(br_money)

    leads_platform = crm.groupby("plataforma")["email"].nunique().reset_index(name="Leads").sort_values("Leads", ascending=False)
    leads_platform["Leads"] = leads_platform["Leads"].map(br_int)
    leads_clima = crm.groupby("clima")["email"].nunique().reset_index(name="Leads").sort_values("Leads", ascending=False)
    leads_clima["Leads"] = leads_clima["Leads"].map(br_int)

    funil_sections = "".join([
        '<section class="section two-col"><div><h2>Funil Base</h2>' + table_from_df(pd.DataFrame([
            {"Etapa": "Leads CRM", "Volume": br_int(total_leads)},
            {"Etapa": "Pesquisa de captação", "Volume": br_int(len(tf_cap))},
            {"Etapa": "Pesquisa de alunos", "Volume": br_int(len(tf_alunos))},
            {"Etapa": "Compradores únicos", "Volume": br_int(compradores)},
        ])) + '</div><div><h2>Leads por Clima</h2>' + table_from_df(leads_clima.rename(columns={"clima": "Clima"})) + '</div></section>'
    ])
    write_report(
        "ANALISE_FUNIL_[PES-MAI-26].html",
        "Funil Completo | PES-MAI-26",
        "Leitura macro do lançamento com base em CRM, pesquisas e compradores únicos.",
        metric("Leads CRM", br_int(total_leads)) + metric("Compradores", br_int(compradores)) + metric("Receita", br_money(receita_total)) + metric("Conv. Lead→Compra", br_pct(compradores / total_leads * 100 if total_leads else 0)),
        funil_sections,
    )

    write_report(
        "ANALISE_META_ADS_[PES-MAI-26].html",
        "Meta Ads | PES-MAI-26",
        "Resumo da operação Meta com campanhas e conjuntos de anúncios mais relevantes.",
        metric("Investimento Meta", br_money(meta["investimento"].sum())) + metric("Leads Meta", br_int(meta["leads_num"].sum())) + metric("Anúncios", br_int(meta["Nome do anúncio"].nunique())) + metric("CPL médio", br_money(meta["investimento"].sum() / meta["leads_num"].sum() if meta["leads_num"].sum() else 0)),
        '<section class="section two-col"><div><h2>Top Campanhas</h2>' + table_from_df(meta_campaigns.rename(columns={"Nome da campanha": "Campanha"})) + '</div><div><h2>Top Conjuntos</h2>' + table_from_df(meta_sets.rename(columns={"Nome do conjunto de anúncios": "Conjunto"})) + '</div></section>',
    )

    write_report(
        "ANALISE_GOOGLE_ADS_[PES-MAI-26].html",
        "Google Ads | PES-MAI-26",
        "Resumo de campanhas Google com leitura de custo, cliques e conversões reportadas.",
        metric("Investimento Google", br_money(ga_campaign["Custo"].sum())) + metric("Cliques", br_int(ga_campaign["Cliques"].sum())) + metric("Conversões", br_int(ga_campaign["Conversões"].sum())) + metric("Campanhas", br_int(len(ga_campaign))),
        '<section class="section"><h2>Top Campanhas</h2>' + table_from_df(ga_top) + '</section>',
    )

    write_report(
        "ANALISE_LEADS_CONFRONTO_[PES-MAI-26].html",
        "Leads Confronto | PES-MAI-26",
        "Distribuição dos leads do CRM por plataforma e clima, confrontada com as bases de mídia.",
        metric("Leads CRM", br_int(total_leads)) + metric("Meta/FB", br_int(int(crm[crm["plataforma"] == "Meta / Facebook"]["email"].nunique()))) + metric("Google/YT", br_int(int(crm[crm["plataforma"] == "Google / YouTube"]["email"].nunique()))) + metric("Outros", br_int(int(crm[~crm["plataforma"].isin(["Meta / Facebook", "Google / YouTube"])]["email"].nunique()))),
        '<section class="section two-col"><div><h2>Leads por Plataforma</h2>' + table_from_df(leads_platform.rename(columns={"plataforma": "Plataforma"})) + '</div><div><h2>Leads por Clima</h2>' + table_from_df(leads_clima.rename(columns={"clima": "Clima"})) + '</div></section>',
    )

    write_report(
        "ANALISE_META_AUDIENCES_[PES-MAI-26].html",
        "Meta Audiences | PES-MAI-26",
        "Leitura dos conjuntos de anúncios mais relevantes em Meta Ads.",
        metric("Conjuntos", br_int(meta["Nome do conjunto de anúncios"].nunique())) + metric("Campanhas", br_int(meta["Nome da campanha"].nunique())) + metric("Investimento", br_money(meta["investimento"].sum())) + metric("Leads", br_int(meta["leads_num"].sum())),
        '<section class="section"><h2>Top Conjuntos por Investimento</h2>' + table_from_df(meta_sets.rename(columns={"Nome do conjunto de anúncios": "Conjunto"})) + '</section>',
    )

    write_report(
        "ANALISE_GOOGLE_AUDIENCES_[PES-MAI-26].html",
        "Google Audiences | PES-MAI-26",
        "Segmentos de público-alvo do Google Ads por custo e cliques.",
        metric("Segmentos", br_int(ga_aud["Segmento de público-alvo"].nunique())) + metric("Investimento", br_money(ga_aud["Custo"].sum())) + metric("Cliques", br_int(ga_aud["Cliques"].sum())) + metric("Grupos", br_int(ga_aud["Grupo de anúncios"].nunique())),
        '<section class="section"><h2>Top Segmentos</h2>' + table_from_df(ga_aud_top) + '</section>',
    )

    google_tipos = yt[yt["criativo"].astype(str).str.upper().isin(["SEARCH", "PMAX", "DISPLAY"])][["criativo", "investimento", "leads", "vendas", "faturamento", "roas"]].copy()
    if not google_tipos.empty:
        google_tipos["investimento"] = google_tipos["investimento"].map(br_money)
        google_tipos["leads"] = google_tipos["leads"].map(br_int)
        google_tipos["vendas"] = google_tipos["vendas"].map(br_int)
        google_tipos["faturamento"] = google_tipos["faturamento"].map(br_money)
        google_tipos["roas"] = google_tipos["roas"].map(lambda v: f"{v:.2f}x")

    criativos = cons[["criativo", "investimento", "leads", "vendas", "faturamento", "roas"]].copy().sort_values(["vendas", "faturamento"], ascending=False).head(20)
    criativos["investimento"] = criativos["investimento"].map(br_money)
    criativos["leads"] = criativos["leads"].map(br_int)
    criativos["vendas"] = criativos["vendas"].map(br_int)
    criativos["faturamento"] = criativos["faturamento"].map(br_money)
    criativos["roas"] = criativos["roas"].map(lambda v: f"{v:.2f}x")

    write_report(
        "ANALISE_ANUNCIOS_[PES-MAI-26].html",
        "Anúncios | PES-MAI-26",
        "Ranking dos anúncios/criativos consolidados com investimento, leads, vendas e ROAS.",
        metric("Criativos", br_int(len(cons))) + metric("Investimento", br_money(cons["investimento"].sum())) + metric("Vendas", br_int(cons["vendas"].sum())) + metric("Receita", br_money(cons["faturamento"].sum())),
        '<section class="section"><h2>Top Criativos</h2>' + table_from_df(criativos.rename(columns={"criativo": "Criativo", "investimento": "Investimento", "leads": "Leads", "vendas": "Vendas", "faturamento": "Faturamento", "roas": "ROAS"})) + '</section>',
    )

    write_report(
        "ANALISE_CRIATIVOS_[PES-MAI-26].html",
        "Criativos | PES-MAI-26",
        "Comparativo entre a base consolidada, Facebook e Google/YouTube.",
        metric("Facebook", br_int(len(fb))) + metric("Google/YT", br_int(len(yt))) + metric("Consolidado", br_int(len(cons))) + metric("Receita Total", br_money(receita_total)),
        '<section class="section two-col"><div><h2>Top Facebook</h2>' + table_from_df(fb[["criativo", "leads", "vendas", "faturamento", "roas"]].sort_values(["vendas", "faturamento"], ascending=False).head(12).assign(leads=lambda d: d["leads"].map(br_int), vendas=lambda d: d["vendas"].map(br_int), faturamento=lambda d: d["faturamento"].map(br_money), roas=lambda d: d["roas"].map(lambda v: f"{v:.2f}x")).rename(columns={"criativo": "Criativo", "leads": "Leads", "vendas": "Vendas", "faturamento": "Faturamento", "roas": "ROAS"})) + '</div><div><h2>Top Google / YouTube</h2>' + table_from_df(yt[["criativo", "leads", "vendas", "faturamento", "roas"]].sort_values(["vendas", "faturamento"], ascending=False).head(12).assign(leads=lambda d: d["leads"].map(br_int), vendas=lambda d: d["vendas"].map(br_int), faturamento=lambda d: d["faturamento"].map(br_money), roas=lambda d: d["roas"].map(lambda v: f"{v:.2f}x")).rename(columns={"criativo": "Criativo", "leads": "Leads", "vendas": "Vendas", "faturamento": "Faturamento", "roas": "ROAS"})) + '</div></section>',
    )

    insights_rows = pd.DataFrame([
        {"Insight": "Receita total rastreada", "Leitura": br_money(receita_total)},
        {"Insight": "Compradores únicos", "Leitura": br_int(compradores)},
        {"Insight": "Meta domina em volume de leads", "Leitura": br_int(int(crm[crm["plataforma"] == "Meta / Facebook"]["email"].nunique()))},
        {"Insight": "Google domina em investimento bruto", "Leitura": br_money(ga_campaign["Custo"].sum())},
        {"Insight": "Pesquisa de alunos adicionada", "Leitura": br_int(len(tf_alunos)) + " respostas"},
    ])
    insights_sections = '<section class="section"><h2>Leituras prioritárias</h2>' + table_from_df(insights_rows) + '</section>'
    if not google_tipos.empty:
        insights_sections += '<section class="section"><h2>Google por Tipo de Campanha</h2>' + table_from_df(google_tipos.rename(columns={"criativo": "Tipo", "investimento": "Investimento", "leads": "Leads", "vendas": "Vendas", "faturamento": "Faturamento", "roas": "ROAS"})) + '</section>'
    insights_sections += '<section class="section"><p class="note">1. Reforçar a leitura cruzada de vendas com UTMs de Google Search e base comercial/WhatsApp.</p><p class="note">2. Manter a separação entre pesquisa de captação e pesquisa de alunos para distinguir intenção de entrada de motivo real de compra.</p><p class="note">3. Search e P-Max já aparecem com venda no CRM; Display segue forte em captação, mas sem venda em last-touch nessa exportação atual.</p></section>'
    write_report(
        "INSIGHTS_RECOMENDACOES_[PES-MAI-26].html",
        "Insights & Recomendações | PES-MAI-26",
        "Resumo executivo da campanha com os principais sinais do lançamento.",
        metric("Receita", br_money(receita_total)) + metric("Compradores", br_int(compradores)) + metric("Leads", br_int(total_leads)) + metric("Captação Typeform", br_int(len(tf_cap))),
        insights_sections,
    )


if __name__ == "__main__":
    main()