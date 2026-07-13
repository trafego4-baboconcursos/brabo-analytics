#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera análises consolidadas de ecossistema para ABR-26.

Sobrescreve:
- ANALISE_META_ADS_[PBB-ABR-26].html
- ANALISE_GOOGLE_ADS_[PBB-ABR-26].html

Cada página consolida o canal principal com a plataforma criativa relacionada:
- Meta Ads + Facebook
- Google Ads + YouTube

E adiciona comparativo com FEV-26 + resumo de respostas de pesquisa.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pandas as pd

BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES = BASE / "analises"
ABR_DIR = ANALISES / "[PBB-ABR-26]"
FEV_DIR = ANALISES / "[PBB-FEV-26]"


def br_to_float(value) -> float:
    if pd.isna(value) or str(value).strip() in {"", "-", "--"}:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    text = re.sub(r"[R$\s]", "", text)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(".", "")
    text = re.sub(r"[^\d.-]", "", text)
    try:
        return float(text) if text else 0.0
    except ValueError:
        return 0.0


def format_money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_number(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", ".")


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def first_existing(*candidates: Path) -> Path:
    # 1. Tentar primeiro o caminho literal
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # 2. Se falhar, tentar buscar no diretório usando glob de forma flexível
    for candidate in candidates:
        parent = candidate.parent
        if parent.exists():
            stem_lower = candidate.stem.lower()
            candidatos = list(parent.glob(f"*{candidate.suffix}"))
            
            # Mapear palavras-chave para achar correspondência inteligente
            keywords = []
            if "meta" in stem_lower or "ma-campanhas" in stem_lower:
                keywords = ["meta", "campanhas"]
            elif "performance" in stem_lower and "anuncio" in stem_lower:
                keywords = ["performance", "anuncio"]
            elif "performance" in stem_lower and "campanha" in stem_lower:
                keywords = ["performance", "campanha"]
            elif "publico" in stem_lower or "audiences" in stem_lower:
                keywords = ["publico", "audience", "target"]
            elif "vendas" in stem_lower:
                keywords = ["vendas", "sales"]
            elif "hotmart" in stem_lower:
                keywords = ["hotmart"]
            elif "tmb" in stem_lower:
                keywords = ["tmb"]
            elif "typeform" in stem_lower:
                keywords = ["typeform"]
                
            if keywords:
                for f in candidatos:
                    f_name = f.name.lower()
                    # Preferir arquivos com o código de campanha
                    if any(kw in f_name for kw in keywords) and "pbb-abr-26" in f_name:
                        return f
                for f in candidatos:
                    f_name = f.name.lower()
                    if any(kw in f_name for kw in keywords):
                        return f
            
            if candidatos:
                return candidatos[0]
                
    raise FileNotFoundError("Nenhum arquivo encontrado para candidatos: " + ", ".join(str(p) for p in candidates))


def load_platform_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["investimento", "leads", "vendas", "faturamento", "cpl", "custo_por_venda", "roas", "taxa_conversao"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def creative_code(value: object) -> str:
    text = str(value).strip().upper()
    if " - " in text:
        return text.split(" - ", 1)[0].strip()
    return text


def read_csv_safe(filepath, sep=',', skiprows=0, **kwargs):
    import pandas as pd
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


def load_captacao_creatives_from_meta(campaign: str) -> set[str]:
    path = first_existing(
        ANALISES / f"[{campaign}]" / "Meta Ads" / f"MA-Campanhas-completas-{campaign}.csv",
        ANALISES / f"[{campaign}]" / "meta ads" / f"MA-Campanhas-Completas-{campaign}.csv",
    )
    df = read_csv_safe(path, low_memory=False)
    col_camp = find_column(df, ["Nome da campanha", "Campanha", "Campaign"])
    col_ad = find_column(df, ["Nome do anúncio", "Nome do anuncio", "Ad name", "Ad Name"])
    if not col_camp or not col_ad or col_camp not in df.columns or col_ad not in df.columns:
        return set()
    filtered = df[df[col_camp].astype(str).str.lower().str.contains("capta", na=False)].copy()
    return {creative_code(value) for value in filtered[col_ad] if str(value).strip()}


def load_captacao_creatives_from_google(campaign: str) -> set[str]:
    filename = f"Performance dos anúncios-pbb-{campaign.lower().replace('pbb-', '').replace('-26', '-26')}.csv"
    path = first_existing(
        ANALISES / f"[{campaign}]" / "Google Ads" / filename,
        ANALISES / f"[{campaign}]" / "google ads" / filename,
    )
    df = read_csv_safe(path, skiprows=2, low_memory=False)
    col_camp = find_column(df, ["Campanha", "Nome da campanha", "Campaign"])
    col_ad = find_column(df, ["Nome do anúncio", "Nome do anuncio", "Ad name", "Ad Name"])
    if not col_camp or not col_ad or col_camp not in df.columns or col_ad not in df.columns:
        return set()
    filtered = df[df[col_camp].astype(str).str.lower().str.contains("capta", na=False)].copy()
    return {creative_code(value) for value in filtered[col_ad] if str(value).strip()}


def filter_platform_by_creatives(df: pd.DataFrame, creatives: set[str]) -> pd.DataFrame:
    if not creatives or "criativo" not in df.columns:
        return df.iloc[0:0].copy() if "criativo" in df.columns else df.copy()
    normalized = df["criativo"].astype(str).str.strip().str.upper()
    return df[normalized.isin(creatives)].copy()


def summarize_platform(df: pd.DataFrame) -> dict:
    total_investimento = float(df["investimento"].sum())
    total_leads = float(df["leads"].sum())
    total_vendas = float(df["vendas"].sum())
    total_faturamento = float(df["faturamento"].sum())
    return {
        "investimento": total_investimento,
        "leads": total_leads,
        "vendas": total_vendas,
        "faturamento": total_faturamento,
        "roas": (total_faturamento / total_investimento) if total_investimento else 0.0,
        "cpl": (total_investimento / total_leads) if total_leads else 0.0,
        "taxa_conv": (total_vendas / total_leads * 100) if total_leads else 0.0,
        "criativos": len(df),
        "top_vendas": df.sort_values(["vendas", "faturamento"], ascending=False).head(8).copy(),
    }


def load_meta_summary(campaign: str) -> dict:
    path = first_existing(
        ANALISES / f"[{campaign}]" / "Meta Ads" / f"MA-Campanhas-completas-{campaign}.csv",
        ANALISES / f"[{campaign}]" / "meta ads" / f"MA-Campanhas-Completas-{campaign}.csv",
    )
    df = pd.read_csv(path, low_memory=False)
    df["valor_gasto"] = df.get("Valor usado (BRL)", 0).apply(br_to_float)
    df["leads"] = pd.to_numeric(df.get("Leads", 0), errors="coerce").fillna(0)
    return {
        "investimento": float(df["valor_gasto"].sum()),
        "leads": float(df["leads"].sum()),
        "ads": int(df["Nome do anúncio"].astype(str).nunique()) if "Nome do anúncio" in df.columns else len(df),
    }


def load_google_summary(campaign: str) -> dict:
    filename = f"Performance da campanha-pbb-{campaign.lower().replace('pbb-', '').replace('-26', '-26')}.csv"
    path = first_existing(
        ANALISES / f"[{campaign}]" / "Google Ads" / filename,
        ANALISES / f"[{campaign}]" / "google ads" / filename,
    )
    df = pd.read_csv(path, skiprows=2, low_memory=False)
    for col in ["Cliques", "Impr.", "Custo", "Conversões"]:
        if col in df.columns:
            df[col] = df[col].apply(br_to_float)
    total_clicks = float(df.get("Cliques", pd.Series(dtype=float)).sum())
    total_impressions = float(df.get("Impr.", pd.Series(dtype=float)).sum())
    total_cost = float(df.get("Custo", pd.Series(dtype=float)).sum())
    total_conversions = float(df.get("Conversões", pd.Series(dtype=float)).sum())
    ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    cpc = (total_cost / total_clicks) if total_clicks else 0.0
    return {
        "campanhas": len(df),
        "cliques": total_clicks,
        "impressões": total_impressions,
        "investimento": total_cost,
        "conversões": total_conversions,
        "ctr": ctr,
        "cpc": cpc,
        "top_campanhas": df.sort_values("Custo", ascending=False).head(10).copy() if "Custo" in df.columns else df.head(10).copy(),
    }


def load_typeform_count(campaign: str) -> int:
    path = first_existing(
        ANALISES / f"[{campaign}]" / "Typeform" / f"typeform-pesquisa-{campaign.lower()}.csv",
        ANALISES / f"[{campaign}]" / "typeform" / f"typeform-{campaign.lower()}.csv",
        ANALISES / f"[{campaign}]" / "typeform" / f"typeform-pesquisa-{campaign.lower()}.csv",
    )
    return len(pd.read_csv(path, low_memory=False))


def load_crm_path(campaign: str) -> Path:
    base = ANALISES / f"[{campaign}]"
    candidates: list[Path] = []
    for folder in [base / "Active Campaign", base / "active-campaing", base / "Active campaign"]:
        if folder.exists():
            candidates.extend(folder.glob("*.csv"))
    if not candidates:
        candidates.extend(f for f in base.rglob("*.csv") if "pbb" in f.name.lower() or "lead" in f.name.lower())
    if not candidates:
        raise FileNotFoundError(f"CRM não encontrado para {campaign}")
    return max(candidates, key=lambda f: f.stat().st_mtime)


def load_typeform_attribution(campaign: str) -> dict:
    tf_path = first_existing(
        ANALISES / f"[{campaign}]" / "Typeform" / f"typeform-pesquisa-{campaign.lower()}.csv",
        ANALISES / f"[{campaign}]" / "typeform" / f"typeform-{campaign.lower()}.csv",
        ANALISES / f"[{campaign}]" / "typeform" / f"typeform-pesquisa-{campaign.lower()}.csv",
    )
    tf = pd.read_csv(tf_path, low_memory=False)
    tf["email_n"] = tf["Digite o seu e-mail."].astype(str).str.lower().str.strip()

    crm = pd.read_csv(load_crm_path(campaign), sep=",", encoding="utf-8", low_memory=False)
    crm["email_n"] = crm["Email"].astype(str).str.lower().str.strip()
    utm_col = next((col for col in crm.columns if "utm_source" in col.lower()), None)
    if not utm_col:
        return {"total": len(tf), "matched": 0, "facebook": 0, "youtube": 0, "google": 0}

    matched = crm[crm["email_n"].isin(set(tf["email_n"]))].copy()
    matched[utm_col] = matched[utm_col].astype(str).str.lower().str.strip()
    return {
        "total": len(tf),
        "matched": int(matched["email_n"].nunique()),
        "facebook": int(matched[utm_col].str.contains(r"facebook|fb", regex=True, na=False).sum()),
        "youtube": int(matched[utm_col].str.contains(r"youtube|yt", regex=True, na=False).sum()),
        "google": int(matched[utm_col].str.contains(r"google|gads|adwords", regex=True, na=False).sum()),
    }


def delta_badge(current: float, previous: float, invert: bool = False) -> tuple[str, str]:
    if previous == 0:
        return ("sem base", "#6b7280")
    delta = ((current / previous) - 1) * 100
    positive = delta >= 0
    better = (not positive) if invert else positive
    arrow = "▲" if delta >= 0 else "▼"
    color = "#31c16c" if better else "#f05454"
    return (f"{arrow} {abs(delta):.1f}%", color)


def render_compare_row(label: str, fev: str, abr: str, badge_text: str, badge_color: str) -> str:
    return (
        f"<tr><td><strong>{label}</strong></td><td class='numero'>{fev}</td>"
        f"<td class='numero'>{abr}</td><td class='numero'><span class='badge' style='background:{badge_color}'>{badge_text}</span></td></tr>"
    )


def render_top_platform_table(df: pd.DataFrame, title: str) -> str:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            "<tr>"
            f"<td><strong>{row['criativo']}</strong></td>"
            f"<td class='numero'>{format_money(row['investimento'])}</td>"
            f"<td class='numero'>{format_number(row['leads'])}</td>"
            f"<td class='numero'>{format_number(row['vendas'])}</td>"
            f"<td class='numero'>{format_money(row['faturamento'])}</td>"
            f"<td class='numero'>{row['roas']:.2f}x</td>"
            f"<td class='numero'>{format_pct(row['taxa_conversao'])}</td>"
            "</tr>"
        )
    return (
        f"<div class='section'><h2>{title}</h2><div class='table-wrap'><table><thead><tr>"
        "<th>Criativo</th><th class='numero'>Investimento</th><th class='numero'>Leads</th>"
        "<th class='numero'>Vendas</th><th class='numero'>Faturamento</th><th class='numero'>ROAS</th>"
        "<th class='numero'>Taxa Conv.</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div></div>"
    )


def render_all_platform_table(df: pd.DataFrame, title: str) -> str:
    ordered = df.sort_values(["vendas", "faturamento", "investimento"], ascending=[False, False, False]).reset_index(drop=True)
    return render_top_platform_table(ordered, title)


def render_google_campaign_table(df: pd.DataFrame, title: str) -> str:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            "<tr>"
            f"<td>{str(row.get('Campanha', '')).strip()}</td>"
            f"<td>{str(row.get('Estado da campanha', '')).strip()}</td>"
            f"<td class='numero'>{format_number(br_to_float(row.get('Cliques', 0)))}</td>"
            f"<td class='numero'>{format_number(br_to_float(row.get('Impr.', 0)))}</td>"
            f"<td class='numero'>{str(row.get('CTR', '')).strip()}</td>"
            f"<td class='numero'>{format_money(br_to_float(row.get('Custo', 0)))}</td>"
            f"<td class='numero'>{format_number(br_to_float(row.get('Conversões', 0)))}</td>"
            "</tr>"
        )
    return (
        f"<div class='section'><h2>{title}</h2><div class='table-wrap'><table><thead><tr>"
        "<th>Campanha</th><th>Status</th><th class='numero'>Cliques</th><th class='numero'>Impressões</th>"
        "<th class='numero'>CTR</th><th class='numero'>Custo</th><th class='numero'>Conversões</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div></div>"
    )


def html_shell(title: str, accent: str, intro: str, summary_cards: list[str], compare_rows: list[str], insight_html: str, extra_sections: list[str]) -> str:
        cards = "".join(summary_cards)
        table_rows = "".join(compare_rows)
        sections = "".join(extra_sections)
        compare_section = ""
        if table_rows:
                compare_section = f"""
            <div class="section">
                <h2>Comparativo ABR x FEV</h2>
                <div class="table-wrap">
                    <table>
                        <thead><tr><th>Métrica</th><th class='numero'>FEV</th><th class='numero'>ABR</th><th class='numero'>Delta</th></tr></thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>
"""
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, {accent} 0%, #10243f 100%); }}
        .wrap {{ max-width: 1400px; margin: 24px auto; background: #fff; border-radius: 18px; box-shadow: 0 28px 60px rgba(0,0,0,.20); overflow: hidden; }}
        .hero {{ padding: 28px 32px; background: linear-gradient(135deg, rgba(255,255,255,.98) 0%, rgba(248,250,252,.98) 100%); border-bottom: 1px solid #e5e7eb; }}
        .hero h1 {{ margin: 0 0 8px; font-size: 32px; color: #111827; }}
        .hero p {{ margin: 0; color: #4b5563; line-height: 1.5; }}
        .content {{ padding: 24px 32px 40px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .card {{ background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; }}
        .card .label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px; }}
        .card .value {{ font-size: 28px; font-weight: 800; color: #111827; }}
        .card .sub {{ margin-top: 6px; font-size: 13px; color: #6b7280; }}
        .section {{ margin-top: 24px; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 20px; }}
        .section h2 {{ margin: 0 0 14px; color: {accent}; font-size: 22px; }}
        .section p {{ color: #4b5563; line-height: 1.6; }}
        .insight {{ background: linear-gradient(135deg, rgba(47,94,227,.08) 0%, rgba(255,255,255,1) 100%); border-left: 4px solid {accent}; }}
        .table-wrap {{ overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: {accent}; color: #fff; padding: 12px 10px; text-align: left; font-size: 13px; }}
        td {{ padding: 11px 10px; border-bottom: 1px solid #e5e7eb; color: #111827; font-size: 14px; }}
        .numero {{ text-align: right; white-space: nowrap; }}
        .badge {{ display: inline-block; color: #fff; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
        .cols-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        @media (max-width: 900px) {{ .cols-2 {{ grid-template-columns: 1fr; }} .hero, .content {{ padding: 18px; }} }}
    </style>
</head>
<body>
    <div class="wrap">
        <div class="hero">
            <h1>{title}</h1>
            <p>{intro}</p>
        </div>
        <div class="content">
            <div class="cards">{cards}</div>
            {compare_section}
            {insight_html}
            {sections}
        </div>
    </div>
</body>
</html>
"""


def build_meta_report() -> None:
    abr_fb_df = filter_platform_by_creatives(
        load_platform_csv(ABR_DIR / "ANALISE_FACEBOOK_[PBB-ABR-26].csv"),
        load_captacao_creatives_from_meta("PBB-ABR-26"),
    )
    abr_fb = summarize_platform(abr_fb_df)
    abr_meta = load_meta_summary("PBB-ABR-26")
    tf_abr = load_typeform_attribution("PBB-ABR-26")

    cpl_meta = abr_meta["investimento"] / max(abr_meta["leads"], 1)

    summary_cards = [
        f"<div class='card'><div class='label'>Meta ABR Investimento</div><div class='value'>{format_money(abr_meta['investimento'])}</div><div class='sub'>{format_number(abr_meta['ads'])} anúncios ativos</div></div>",
        f"<div class='card'><div class='label'>Meta ABR Leads</div><div class='value'>{format_number(abr_meta['leads'])}</div><div class='sub'>CPL {format_money(cpl_meta)}</div></div>",
        f"<div class='card'><div class='label'>Facebook ABR Vendas</div><div class='value'>{format_number(abr_fb['vendas'])}</div><div class='sub'>ROAS {abr_fb['roas']:.2f}x</div></div>",
        f"<div class='card'><div class='label'>Facebook ABR Leads</div><div class='value'>{format_number(abr_fb['leads'])}</div><div class='sub'>Taxa conv. {format_pct(abr_fb['taxa_conv'])}</div></div>",
        f"<div class='card'><div class='label'>Typeform ABR via Facebook</div><div class='value'>{format_number(tf_abr['facebook'])}</div><div class='sub'>{format_number(tf_abr['matched'])} respondentes atribuídos no CRM</div></div>",
        f"<div class='card'><div class='label'>Typeform ABR total</div><div class='value'>{format_number(tf_abr['total'])}</div><div class='sub'>{format_number(tf_abr['total'] - tf_abr['matched'])} sem atribuição de origem</div></div>",
    ]

    compare_rows = []

    insight_html = f"""
      <div class='section insight'>
        <h2>Leitura executiva</h2>
        <p><strong>Captação Meta:</strong> o ecossistema gerou {format_number(abr_meta['leads'])} leads na mídia e CPL médio de {format_money(cpl_meta)}.</p>
        <p><strong>Conversão Facebook:</strong> os criativos de Facebook fecharam {format_number(abr_fb['vendas'])} vendas, com ROAS médio de {abr_fb['roas']:.2f}x.</p>
        <p><strong>Pesquisa atribuída:</strong> {format_number(tf_abr['facebook'])} respondentes do Typeform vieram de Facebook após cruzamento por email com o CRM.</p>
      </div>
    """

    extra_sections = [
        f"<div class='section'><h2>Pesquisa Typeform atribuída</h2><div class='table-wrap'><table><thead><tr><th>Origem</th><th class='numero'>Respondentes</th></tr></thead><tbody>"
        f"<tr><td><strong>Facebook</strong></td><td class='numero'>{format_number(tf_abr['facebook'])}</td></tr>"
        f"<tr><td><strong>YouTube</strong></td><td class='numero'>{format_number(tf_abr['youtube'])}</td></tr>"
        f"<tr><td><strong>Google</strong></td><td class='numero'>{format_number(tf_abr['google'])}</td></tr>"
        f"<tr><td><strong>Respondentes atribuídos no CRM</strong></td><td class='numero'>{format_number(tf_abr['matched'])}</td></tr>"
        f"<tr><td><strong>Total Typeform</strong></td><td class='numero'>{format_number(tf_abr['total'])}</td></tr>"
        "</tbody></table></div></div>",
        render_all_platform_table(abr_fb_df, "Criativos de captação — Facebook ABR"),
    ]

    html = html_shell(
        title="Meta Ads + Facebook — Ecossistema ABR-26",
        accent="#1877f2",
        intro="Consolidação da captação Meta Ads com a performance criativa do Facebook no mês vigente, incluindo o cruzamento de respondentes do Typeform por origem real no CRM.",
        summary_cards=summary_cards,
        compare_rows=compare_rows,
        insight_html=insight_html,
        extra_sections=extra_sections,
    )
    (ABR_DIR / "ANALISE_META_ADS_[PBB-ABR-26].html").write_text(html, encoding="utf-8")


def build_google_report() -> None:
    abr_yt_df = filter_platform_by_creatives(
        load_platform_csv(ABR_DIR / "ANALISE_YOUTUBE_[PBB-ABR-26].csv"),
        load_captacao_creatives_from_google("PBB-ABR-26"),
    )
    abr_yt = summarize_platform(abr_yt_df)
    abr_google = load_google_summary("PBB-ABR-26")
    tf_abr = load_typeform_attribution("PBB-ABR-26")

    cpc_google = abr_google["cpc"]

    summary_cards = [
        f"<div class='card'><div class='label'>Google ABR Conversões</div><div class='value'>{format_number(abr_google['conversões'])}</div><div class='sub'>{format_money(abr_google['investimento'])} investidos</div></div>",
        f"<div class='card'><div class='label'>Google ABR CPC</div><div class='value'>{format_money(cpc_google)}</div><div class='sub'>CTR {format_pct(abr_google['ctr'])}</div></div>",
        f"<div class='card'><div class='label'>YouTube ABR Vendas</div><div class='value'>{format_number(abr_yt['vendas'])}</div><div class='sub'>ROAS {abr_yt['roas']:.2f}x</div></div>",
        f"<div class='card'><div class='label'>Typeform ABR via Google</div><div class='value'>{format_number(tf_abr['google'])}</div><div class='sub'>{format_number(tf_abr['youtube'])} via YouTube</div></div>",
        f"<div class='card'><div class='label'>Typeform ABR total</div><div class='value'>{format_number(tf_abr['total'])}</div><div class='sub'>{format_number(tf_abr['matched'])} respondentes atribuídos no CRM</div></div>",
        f"<div class='card'><div class='label'>YouTube ABR Leads</div><div class='value'>{format_number(abr_yt['leads'])}</div><div class='sub'>Taxa conv. {format_pct(abr_yt['taxa_conv'])}</div></div>",
    ]

    compare_rows = []

    insight_html = f"""
      <div class='section insight'>
        <h2>Leitura executiva</h2>
        <p><strong>Conversão de mídia:</strong> o Google Ads fechou {format_number(abr_google['conversões'])} conversões com CPC médio de {format_money(cpc_google)}.</p>
        <p><strong>Conversão criativa:</strong> os criativos de YouTube fecharam {format_number(abr_yt['vendas'])} vendas e ROAS médio de {abr_yt['roas']:.2f}x.</p>
        <p><strong>Pesquisa atribuída:</strong> o cruzamento Typeform × CRM identificou {format_number(tf_abr['google'])} respondentes vindos de Google e {format_number(tf_abr['youtube'])} vindos de YouTube.</p>
      </div>
    """

    extra_sections = [
        f"<div class='section'><h2>Pesquisa Typeform atribuída</h2><div class='table-wrap'><table><thead><tr><th>Origem</th><th class='numero'>Respondentes</th></tr></thead><tbody>"
        f"<tr><td><strong>Google</strong></td><td class='numero'>{format_number(tf_abr['google'])}</td></tr>"
        f"<tr><td><strong>YouTube</strong></td><td class='numero'>{format_number(tf_abr['youtube'])}</td></tr>"
        f"<tr><td><strong>Facebook</strong></td><td class='numero'>{format_number(tf_abr['facebook'])}</td></tr>"
        f"<tr><td><strong>Respondentes atribuídos no CRM</strong></td><td class='numero'>{format_number(tf_abr['matched'])}</td></tr>"
        f"<tr><td><strong>Total Typeform</strong></td><td class='numero'>{format_number(tf_abr['total'])}</td></tr>"
        "</tbody></table></div></div>",
        render_all_platform_table(abr_yt_df, "Criativos de captação — YouTube ABR"),
    ]

    html = html_shell(
        title="Google Ads + YouTube — Ecossistema ABR-26",
        accent="#4285f4",
        intro="Consolidação do Google Ads com a camada criativa do YouTube no mês vigente, incluindo o cruzamento de respondentes do Typeform por origem real no CRM.",
        summary_cards=summary_cards,
        compare_rows=compare_rows,
        insight_html=insight_html,
        extra_sections=extra_sections,
    )
    (ABR_DIR / "ANALISE_GOOGLE_ADS_[PBB-ABR-26].html").write_text(html, encoding="utf-8")


def main() -> None:
    build_meta_report()
    build_google_report()
    print("✓ ANALISE_META_ADS_[PBB-ABR-26].html atualizado")
    print("✓ ANALISE_GOOGLE_ADS_[PBB-ABR-26].html atualizado")


if __name__ == "__main__":
    main()
