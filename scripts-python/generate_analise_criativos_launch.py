#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable creatives analysis report generator.

This script extracts the same core metrics used in the creatives dashboards
from CSV sources under analises/[CAMPAIGN]/ and renders an HTML report that can
be reused for another launch with minimal configuration.
"""

from __future__ import annotations

import argparse
import csv as csv_mod
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from csv_resolver import resolve_csv


WORKSPACE_ROOT = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
LOGO_PATH = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"


@dataclass(frozen=True)
class LaunchConfig:
    campaign_code: str
    campaign_folder: str
    product_name: str | None = None
    period_label: str | None = None
    reference_folder: str | None = None
    output_filename: str | None = None

    @property
    def analysis_dir(self) -> Path:
        return WORKSPACE_ROOT / "analises" / self.campaign_folder

    @property
    def output_path(self) -> Path:
        if self.output_filename:
            return self.analysis_dir / self.output_filename
        return self.analysis_dir / f"ANALISE_CRIATIVOS_[{self.campaign_code}].html"

    @property
    def slug(self) -> str:
        return self.campaign_code.lower()


def parse_args() -> LaunchConfig:
    parser = argparse.ArgumentParser(description="Generate creatives analysis HTML for a launch.")
    parser.add_argument("--campaign-code", required=True, help="Campaign code, e.g. PBB-ABR-26")
    parser.add_argument("--campaign-folder", required=True, help="Campaign folder, e.g. [PBB-ABR-26]")
    parser.add_argument("--product-name", help="Optional product or launch name shown in the subtitle")
    parser.add_argument("--period-label", help="Optional date span shown in explanatory copy")
    parser.add_argument("--reference-folder", help="Optional reference campaign folder for validated-vs-new classification")
    parser.add_argument("--output-filename", help="Optional output filename inside the campaign folder")
    args = parser.parse_args()
    return LaunchConfig(
        campaign_code=args.campaign_code,
        campaign_folder=args.campaign_folder,
        product_name=args.product_name,
        period_label=args.period_label,
        reference_folder=args.reference_folder,
        output_filename=args.output_filename,
    )


def br_money(value: float | int | None) -> str:
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"



def br_number(value: float | int | None) -> str:
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except Exception:
        return "-"



def pct(value: float | int | None, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except Exception:
        return "-"



def safe_ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator



def normalize_ad_id(raw: object) -> str | None:
    if pd.isna(raw):
        return None
    match = re.search(r"(?i)(ad\d+)", str(raw).strip())
    return match.group(1).upper() if match else None



def first_existing(paths: Iterable[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)



def campaign_file(directory: Path, canonical: str, aliases: Iterable[str]) -> Path:
    return resolve_csv(directory, canonical, aliases)


def campaign_code_from_folder(folder_name: str) -> str:
    return folder_name.strip().strip("[]")



def load_meta_campaigns(
    config: LaunchConfig,
    folder: Path | None = None,
    campaign_code: str | None = None,
) -> pd.DataFrame:
    campaign_dir = folder or config.analysis_dir
    effective_code = campaign_code or config.campaign_code
    effective_slug = effective_code.lower()
    meta_dir = campaign_dir / "Meta Ads"
    meta_file = campaign_file(
        meta_dir,
        f"meta-{effective_slug}.csv",
        [
            f"MA-Campanhas-Completas-{effective_code}.csv",
            f"MA-Campanhas-completas-{effective_code}.csv",
            f"Campanhas-Completas-{effective_slug}.csv",
            f"Campanhas-Completas-{effective_slug.replace('-', ' ')}.csv",
        ],
    )
    df_meta = pd.read_csv(meta_file, encoding="utf-8", low_memory=False)
    for col in ["Valor usado (BRL)", "Leads", "Impressões", "Cliques (todos)", "Cliques no link"]:
        if col in df_meta.columns:
            df_meta[col] = pd.to_numeric(df_meta[col], errors="coerce").fillna(0)
    if "Cliques (todos)" in df_meta.columns:
        df_meta["_clicks"] = df_meta["Cliques (todos)"]
    elif "Cliques no link" in df_meta.columns:
        df_meta["_clicks"] = df_meta["Cliques no link"]
    else:
        df_meta["_clicks"] = 0
    if "Nome do anúncio" not in df_meta.columns:
        df_meta["Nome do anúncio"] = "Sem nome"
    df_meta["ad_id"] = df_meta["Nome do anúncio"].apply(normalize_ad_id)
    return df_meta



def filter_captacao(df_meta: pd.DataFrame) -> pd.DataFrame:
    mask = df_meta["Nome da campanha"].astype(str).str.lower().str.contains("capta", na=False)
    return df_meta[mask].copy()



def classify_creatives(df_meta: pd.DataFrame, config: LaunchConfig) -> pd.DataFrame:
    df_classified = df_meta.copy()
    if config.reference_folder:
        ref_dir = WORKSPACE_ROOT / "analises" / config.reference_folder
        ref_code = campaign_code_from_folder(config.reference_folder)
        ref_meta = filter_captacao(load_meta_campaigns(config, ref_dir, ref_code))
        ref_ids = set(ref_meta["ad_id"].dropna().unique())
        df_classified["tipo"] = df_classified["ad_id"].apply(
            lambda ad_id: "Validado" if ad_id in ref_ids else "Novo"
        )
        return df_classified

    df_classified["tipo"] = df_classified["Nome da campanha"].astype(str).str.lower().apply(
        lambda name: "Novo" if "[novos-ads]" in name else "Validado"
    )
    return df_classified



def load_leads(config: LaunchConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    leads_dir = config.analysis_dir / "Active Campaign"
    leads_file = max(leads_dir.glob("*.csv"), key=lambda path: path.stat().st_mtime)
    df_leads = pd.read_csv(
        leads_file,
        encoding="utf-8",
        low_memory=False,
        quoting=csv_mod.QUOTE_MINIMAL,
    )
    df_leads["Email"] = df_leads["Email"].astype(str).str.strip().str.lower()
    utm_content_col = "*Utm_content" if "*Utm_content" in df_leads.columns else next(
        column for column in df_leads.columns if "utm_content" in column.lower()
    )
    df_leads_utm = df_leads[df_leads[utm_content_col].notna()].copy()
    df_leads_utm["criativo_base"] = df_leads_utm[utm_content_col].astype(str).str.strip()
    df_leads_utm["ad_id"] = df_leads_utm["criativo_base"].apply(normalize_ad_id)
    return df_leads, df_leads_utm



def load_hotmart(config: LaunchConfig) -> pd.DataFrame:
    vendas_dir = config.analysis_dir / "Vendas"
    hot_file = campaign_file(
        vendas_dir,
        f"hotmart-{config.slug}.csv",
        [f"hotmart {config.slug}.csv", f"hotmart - {config.slug}.csv"],
    )
    raw = pd.read_csv(hot_file, sep=";", encoding="utf-8")
    raw["email"] = raw["Email do(a) Comprador(a)"].astype(str).str.strip().str.lower()
    charge_type_col = next((col for col in raw.columns if "tipo" in col.lower() and "cobran" in col.lower()), None)
    if charge_type_col is None:
        df_hot = raw.copy()
        df_hot["val"] = pd.to_numeric(df_hot["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
        return df_hot

    parcelas_col = "Quantidade total de parcelas"
    cobrancas_col = "Quantidade de cobranças"
    normal = raw[raw[charge_type_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
    normal["val"] = pd.to_numeric(normal["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
    ri = raw[
        (raw[charge_type_col].astype(str).str.strip() == "Recuperador Inteligente")
        & (pd.to_numeric(raw[cobrancas_col], errors="coerce").fillna(0) == 1)
    ].copy()
    ri[parcelas_col] = pd.to_numeric(ri[parcelas_col], errors="coerce").fillna(1)
    ri["val"] = pd.to_numeric(ri["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0) * ri[parcelas_col]
    return pd.concat([normal, ri], ignore_index=True)



def load_tmb(config: LaunchConfig) -> pd.DataFrame:
    vendas_dir = config.analysis_dir / "Vendas"
    tmb_file = campaign_file(
        vendas_dir,
        f"tmb-{config.slug}.csv",
        [f"tmb {config.slug}.csv", f"tmb - {config.slug}.csv"],
    )
    df_tmb = pd.read_csv(tmb_file, sep=";", encoding="utf-8")
    email_col = next(col for col in df_tmb.columns if "mail" in str(col).lower())
    ticket_col = next(col for col in df_tmb.columns if "icket" in str(col).lower() and "pedido" in str(col).lower())
    df_tmb["email"] = df_tmb[email_col].astype(str).str.strip().str.lower()
    df_tmb["val"] = pd.to_numeric(df_tmb[ticket_col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
    return df_tmb


def parse_brl_number(value: object) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip().replace("R$", "").strip()
    if text in {"", "--", "None", "nan"}:
        return 0.0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def load_google_ads_spend(config: LaunchConfig) -> pd.DataFrame:
    google_dir = config.analysis_dir / "Google Ads"
    google_file = campaign_file(
        google_dir,
        f"google-ads-performance-dos-anuncios-{config.slug}.csv",
        [
            f"Performance dos anúncios-{config.slug}.csv",
            f"Performance dos an\u00fancios-{config.slug}.csv",
        ],
    )
    df_google = pd.read_csv(google_file, encoding="utf-8", skiprows=2)
    ad_col = next(
        (column for column in df_google.columns if "nome do anúncio" in str(column).lower()),
        next(column for column in df_google.columns if "nome do an" in str(column).lower()),
    )
    cost_col = next(
        (column for column in df_google.columns if str(column).strip().lower() == "custo"),
        next(column for column in df_google.columns if "custo" in str(column).lower()),
    )
    df_google["ad_id"] = df_google[ad_col].apply(normalize_ad_id)
    df_google["inv_google"] = df_google[cost_col].apply(parse_brl_number)
    return df_google[df_google["ad_id"].notna()].groupby("ad_id", as_index=False).agg(
        inv_google=("inv_google", "sum")
    )



def load_platform_analysis(config: LaunchConfig, stem: str) -> pd.DataFrame | None:
    path = config.analysis_dir / f"ANALISE_{stem}_[{config.campaign_code}].csv"
    if not path.exists():
        return None
    df_platform = pd.read_csv(path)
    for column in ["investimento", "leads", "vendas", "faturamento", "roas"]:
        if column in df_platform.columns:
            df_platform[column] = pd.to_numeric(df_platform[column], errors="coerce").fillna(0)
    return df_platform



def load_typeform(config: LaunchConfig) -> pd.DataFrame | None:
    typeform_dir = config.analysis_dir / "Typeform"
    if not typeform_dir.exists():
        return None
    typeform_file = first_existing(
        [
            typeform_dir / f"typeform-pesquisa-{config.slug}.csv",
            typeform_dir / f"typeform-{config.slug}.csv",
        ]
    )
    if typeform_file is None:
        return None
    return pd.read_csv(typeform_file, low_memory=False)



def build_crm_stats(df_leads_utm: pd.DataFrame, df_hot: pd.DataFrame, df_tmb: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for ad_id, group in df_leads_utm.groupby("ad_id"):
        emails = set(group["Email"].dropna().unique())
        leads_crm = len(group)
        vendas = len(df_hot[df_hot["email"].isin(emails)]) + len(df_tmb[df_tmb["email"].isin(emails)])
        faturamento = df_hot[df_hot["email"].isin(emails)]["val"].sum() + df_tmb[df_tmb["email"].isin(emails)]["val"].sum()
        rows.append(
            {
                "ad_id": ad_id,
                "leads_crm": leads_crm,
                "vendas": vendas,
                "fat": faturamento,
                "conv_rate": safe_ratio(vendas * 100, leads_crm),
            }
        )
    return pd.DataFrame(rows)



def build_main_dataset(config: LaunchConfig) -> dict[str, object]:
    df_meta_all = load_meta_campaigns(config)
    df_meta = classify_creatives(filter_captacao(df_meta_all), config)
    meta_by_ad = df_meta.groupby(["Nome do anúncio", "ad_id", "tipo"]).agg(
        inv_meta=("Valor usado (BRL)", "sum"),
        leads_meta=("Leads", "sum"),
        impr=("Impressões", "sum"),
        clicks=("_clicks", "sum"),
    ).reset_index()
    meta_by_ad["CPL_meta"] = meta_by_ad["inv_meta"] / meta_by_ad["leads_meta"].replace(0, np.nan)
    meta_by_ad["CTR"] = meta_by_ad["clicks"] / meta_by_ad["impr"].replace(0, np.nan) * 100
    google_by_ad = load_google_ads_spend(config)

    df_leads, df_leads_utm = load_leads(config)
    df_hot = load_hotmart(config)
    df_tmb = load_tmb(config)
    df_crm = build_crm_stats(df_leads_utm, df_hot, df_tmb)

    df_merged = pd.merge(meta_by_ad, df_crm, on="ad_id", how="left")
    df_merged = pd.merge(df_merged, google_by_ad, on="ad_id", how="left")
    for column in ["leads_crm", "vendas", "fat", "conv_rate"]:
        df_merged[column] = df_merged[column].fillna(0)
    df_merged["inv_google"] = df_merged["inv_google"].fillna(0)
    df_merged["inv"] = df_merged["inv_meta"] + df_merged["inv_google"]
    df_merged["ROAS"] = df_merged["fat"] / df_merged["inv"].replace(0, np.nan)
    df_merged["CPA_real"] = df_merged["inv"] / df_merged["vendas"].replace(0, np.nan)
    df_merged = df_merged.sort_values(["vendas", "fat", "leads_meta"], ascending=False)

    df_valid = df_merged[df_merged["tipo"] == "Validado"].copy()
    df_novos = df_merged[df_merged["tipo"] == "Novo"].copy()

    tracked_emails = set(df_leads_utm["Email"])
    rast_h = df_hot[df_hot["email"].isin(tracked_emails)]
    rast_t = df_tmb[df_tmb["email"].isin(tracked_emails)]

    total_vendas = len(df_hot) + len(df_tmb)
    total_faturamento = df_hot["val"].sum() + df_tmb["val"].sum()
    rastreadas = len(rast_h) + len(rast_t)
    faturamento_rastreado = rast_h["val"].sum() + rast_t["val"].sum()
    ticket_medio = safe_ratio(total_faturamento, total_vendas)
    roas_rastreado = safe_ratio(faturamento_rastreado, df_merged["inv"].sum())

    platform_frames = []
    for stem, origem in [("FACEBOOK", "Facebook"), ("YOUTUBE", "YouTube")]:
        df_platform = load_platform_analysis(config, stem)
        if df_platform is not None and "criativo" in df_platform.columns:
            df_platform = df_platform.copy()
            df_platform["origem"] = origem
            df_platform["ad_id"] = df_platform["criativo"].apply(normalize_ad_id)
            platform_frames.append(df_platform)
    df_platform_rank = None
    if platform_frames:
        df_platform_all = pd.concat(platform_frames, ignore_index=True)
        df_platform_rank = df_platform_all.groupby(["ad_id", "origem"], as_index=False).agg(
            investimento=("investimento", "sum"),
            leads_plat=("leads", "sum"),
            vendas_plat=("vendas", "sum"),
            fat_plat=("faturamento", "sum"),
        )
        df_platform_rank = pd.merge(
            df_platform_rank,
            df_crm[["ad_id", "leads_crm", "conv_rate"]],
            on="ad_id",
            how="left",
        )
        df_platform_rank["leads_crm"] = df_platform_rank["leads_crm"].fillna(0)
        df_platform_rank["conv_rate"] = df_platform_rank["conv_rate"].fillna(0)
        df_platform_rank["roas"] = df_platform_rank["fat_plat"] / df_platform_rank["investimento"].replace(0, np.nan)
        df_platform_rank = df_platform_rank.sort_values(["vendas_plat", "fat_plat"], ascending=False)

    df_typeform = load_typeform(config)
    do_zero_rows: list[dict[str, object]] = []
    do_zero_share = None
    if df_typeform is not None and "Digite o seu e-mail." in df_typeform.columns:
        level_col = next(
            (column for column in df_typeform.columns if "você se considera" in str(column).lower()),
            None,
        )
        if level_col:
            df_typeform = df_typeform.copy()
            df_typeform["email"] = df_typeform["Digite o seu e-mail."].astype(str).str.strip().str.lower()
            df_typeform["is_do_zero"] = df_typeform[level_col].astype(str).str.contains("zero", case=False, na=False)
            do_zero_share = df_typeform["is_do_zero"].mean() * 100
            df_typeform_latest = df_typeform.drop_duplicates(subset=["email"], keep="last")
            tf_join = df_typeform_latest.merge(
                df_leads_utm[["Email", "ad_id"]].drop_duplicates().rename(columns={"Email": "email"}),
                on="email",
                how="inner",
            )
            buyers = set(df_hot["email"]) | set(df_tmb["email"])
            for ad_id, group in tf_join.groupby("ad_id"):
                unique_group = group.drop_duplicates(subset=["email"])
                do_zero = unique_group[unique_group["is_do_zero"]]
                if not len(do_zero):
                    continue
                buyers_from_zero = sum(email in buyers for email in set(do_zero["email"]))
                do_zero_rows.append(
                    {
                        "ad_id": ad_id,
                        "respondentes": unique_group["email"].nunique(),
                        "do_zero": do_zero["email"].nunique(),
                        "do_zero_compraram": buyers_from_zero,
                        "tx_compra_do_zero": safe_ratio(buyers_from_zero * 100, do_zero["email"].nunique()),
                    }
                )
            do_zero_rows.sort(key=lambda row: (-int(row["do_zero"]), -int(row["respondentes"]), str(row["ad_id"])))

    return {
        "df_merged": df_merged,
        "df_valid": df_valid,
        "df_novos": df_novos,
        "df_platform_rank": df_platform_rank,
        "total_vendas": total_vendas,
        "total_faturamento": total_faturamento,
        "rastreadas": rastreadas,
        "faturamento_rastreado": faturamento_rastreado,
        "ticket_medio": ticket_medio,
        "roas_rastreado": roas_rastreado,
        "total_leads": len(df_leads),
        "leads_utm": len(df_leads_utm),
        "criativos_com_venda": int((df_merged["vendas"] > 0).sum()),
        "investimento_total": float(df_meta_all[df_meta_all["ad_id"].notna()]["Valor usado (BRL)"].sum() + google_by_ad["inv_google"].sum()),
        "meta_investimento": float(df_meta_all[df_meta_all["ad_id"].notna()]["Valor usado (BRL)"].sum()),
        "google_investimento": float(google_by_ad["inv_google"].sum()),
        "novos_verdict": build_verdict(df_valid, df_novos),
        "do_zero_rows": do_zero_rows,
        "do_zero_share": do_zero_share,
    }



def build_verdict(df_valid: pd.DataFrame, df_novos: pd.DataFrame) -> dict[str, str]:
    sum_valid = {
        "inv": df_valid["inv_meta"].sum(),
        "leads": df_valid["leads_meta"].sum(),
        "vendas": df_valid["vendas"].sum(),
        "fat": df_valid["fat"].sum(),
    }
    sum_novos = {
        "inv": df_novos["inv_meta"].sum(),
        "leads": df_novos["leads_meta"].sum(),
        "vendas": df_novos["vendas"].sum(),
        "fat": df_novos["fat"].sum(),
    }
    sum_valid["CPL"] = safe_ratio(sum_valid["inv"], sum_valid["leads"])
    sum_novos["CPL"] = safe_ratio(sum_novos["inv"], sum_novos["leads"])
    sum_valid["ROAS"] = safe_ratio(sum_valid["fat"], sum_valid["inv"])
    sum_novos["ROAS"] = safe_ratio(sum_novos["fat"], sum_novos["inv"])
    if not sum_novos["leads"]:
        return {
            "color": "#667eea",
            "text": "Sem criativos novos identificados pela regra atual de classificação.",
            "sum_valid": sum_valid,
            "sum_novos": sum_novos,
        }
    novos_win = sum_novos["CPL"] < sum_valid["CPL"] if sum_valid["leads"] else False
    return {
        "color": "#28a745" if novos_win else "#dc3545",
        "text": "Novos tiveram CPL menor — candidatos a escalar" if novos_win else "Validados seguem mais eficientes em CPL",
        "sum_valid": sum_valid,
        "sum_novos": sum_novos,
    }



def metric_card(label: str, value: str, subtext: str, destaque: bool = False) -> str:
    class_name = "metric-card destaque" if destaque else "metric-card"
    return (
        f'<div class="{class_name}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="subtext">{subtext}</div>'
        f'</div>'
    )



def summary_card(title: str, color: str, data: dict[str, float]) -> str:
    return (
        f'<div style="background:{color}18;border:2px solid {color};border-radius:12px;padding:20px">'
        f'<div style="font-size:.95rem;font-weight:800;color:{color};margin-bottom:12px">{title}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<div><div style="font-size:1.1rem;font-weight:800">{br_money(data["inv"])}</div><div style="font-size:11px;color:#64748b">Investimento</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{br_number(data["leads"])}</div><div style="font-size:11px;color:#64748b">Leads plataforma</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800;color:{color}">{br_money(data["CPL"])}</div><div style="font-size:11px;color:#64748b">CPL médio</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{br_number(data["vendas"])}</div><div style="font-size:11px;color:#64748b">Vendas rastreadas</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{br_money(data["fat"])}</div><div style="font-size:11px;color:#64748b">Faturamento rastreado</div></div>'
        f'<div><div style="font-size:1.1rem;font-weight:800">{data["ROAS"]:.2f}×</div><div style="font-size:11px;color:#64748b">ROAS</div></div>'
        f'</div></div>'
    )



def build_top_rows(df: pd.DataFrame, limit: int = 10) -> str:
    rows = []
    top = df[df["vendas"] > 0].head(limit)
    for index, (_, row) in enumerate(top.iterrows(), start=1):
        rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td>{index}º</td>",
                    f"<td><strong>{row['ad_id'] or '-'}</strong></td>",
                    f"<td class=\"numero\">{br_number(row['leads_crm'])}</td>",
                    f"<td class=\"numero\">{br_number(row['vendas'])}</td>",
                    f"<td class=\"numero\">{pct(row['conv_rate'])}</td>",
                    f"<td class=\"numero\">{br_money(row['fat'])}</td>",
                    f"<td class=\"numero\">{br_money(safe_ratio(row['fat'], row['leads_crm']))}</td>",
                    "</tr>",
                ]
            )
        )
    return "".join(rows)



def build_roas_rows(df: pd.DataFrame, limit: int = 10) -> str:
    filtered = df[df["vendas"] >= 2].copy().sort_values(["ROAS", "vendas"], ascending=False)
    rows = []
    for index, (_, row) in enumerate(filtered.head(limit).iterrows(), start=1):
        rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td><strong>{index}º</strong></td>",
                    f"<td><strong>{row['ad_id'] or '-'}</strong></td>",
                    f"<td class=\"numero\">{br_number(row['vendas'])}</td>",
                    f"<td class=\"numero\">{br_money(row['fat'])}</td>",
                    f"<td class=\"numero\">{br_money(row['inv'])}</td>",
                    f"<td class=\"numero\"><span style=\"color:#22c55e;font-weight:700\">{row['ROAS']:.2f}x</span></td>",
                    f"<td class=\"numero\">{br_money(row['CPA_real']) if pd.notna(row['CPA_real']) else '-'}</td>",
                    f"<td class=\"numero\">{pct(row['conv_rate'])}</td>",
                    "</tr>",
                ]
            )
        )
    return "".join(rows)



def build_do_zero_rows(rows: list[dict[str, object]], limit: int = 10) -> str:
    html_rows = []
    for row in rows[:limit]:
        html_rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td><strong>{row['ad_id']}</strong></td>",
                    f"<td class=\"numero\">{br_number(row['respondentes'])}</td>",
                    f"<td class=\"numero\">{br_number(row['do_zero'])}</td>",
                    f"<td class=\"numero\">{br_number(row['do_zero_compraram'])}</td>",
                    f"<td class=\"numero\">{pct(row['tx_compra_do_zero'])}</td>",
                    "</tr>",
                ]
            )
        )
    return "".join(html_rows)



def render_html(config: LaunchConfig, dataset: dict[str, object]) -> str:
    df_merged = dataset["df_merged"]
    verdict = dataset["novos_verdict"]
    sum_valid = verdict["sum_valid"]
    sum_novos = verdict["sum_novos"]
    rastreadas = int(dataset["rastreadas"])
    total_vendas = int(dataset["total_vendas"])
    nao_rastreadas = total_vendas - rastreadas
    meta_inv = float(dataset["meta_investimento"])
    google_inv = float(dataset["google_investimento"])
    coverage = safe_ratio(rastreadas * 100, total_vendas)
    leads_coverage = safe_ratio(int(dataset["leads_utm"]) * 100, int(dataset["total_leads"]))
    subtitle_bits = ["Painel gerado a partir de CSVs de CRM, vendas e mídia"]
    if config.product_name:
        subtitle_bits.append(config.product_name)
    if config.period_label:
        subtitle_bits.append(config.period_label)
    do_zero_block = ""
    if dataset["do_zero_rows"]:
        do_zero_block = f"""
    <div class="info-box">
      <h2>1.3 Pesquisa + Captação: quem mais puxa o público \"do zero\"?</h2>
      <p><strong>Cruzamento real:</strong> Typeform + CRM + vendas por e-mail, com quebra por criativo via UTM.</p>
      <p>No Typeform, <strong>{pct(dataset['do_zero_share'], 1)}</strong> dos respondentes se declararam \"do zero\".</p>
      <table>
        <thead>
          <tr>
            <th>Criativo</th>
            <th class="numero">Resp. Typeform</th>
            <th class="numero">\"Do zero\"</th>
            <th class="numero">\"Do zero\" que compraram</th>
            <th class="numero">Tx. compra \"do zero\"</th>
          </tr>
        </thead>
        <tbody>{build_do_zero_rows(dataset['do_zero_rows'])}</tbody>
      </table>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Análise de Criativos — {config.campaign_code}</title>
<link rel="icon" type="image/png" href="{FAVICON_PATH}">
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap');
:root {{
  --font-display:'Sora','Segoe UI',sans-serif;
  --font-body:'Space Grotesk','Segoe UI',sans-serif;
  --bg:#b8bee6;
  --surface:#f6f7fb;
  --card:#ffffff;
  --ink:#1f2330;
  --muted:#6b7280;
  --primary:#2f5ee3;
  --accent:#f5576c;
  --shadow:0 18px 55px rgba(20,26,52,.14);
  --r-lg:20px;
  --r-md:12px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:radial-gradient(1200px 900px at 20% 0%, #cfd5ff 0%, var(--bg) 55%, #adb5e3 100%);color:var(--ink);line-height:1.6}}
.wrap{{max-width:1340px;margin:24px auto;background:var(--surface);border-radius:var(--r-lg);overflow:hidden;box-shadow:var(--shadow)}}
.hdr{{background:var(--card);padding:28px 32px;display:flex;align-items:center;gap:20px;border-bottom:2px solid var(--accent)}}
.hdr img{{height:44px;border-radius:10px}}
.hdr h1{{font-family:var(--font-display);font-size:1.45rem;font-weight:800}}
.hdr p{{font-size:.82rem;color:var(--muted);margin-top:3px}}
.content{{padding:28px 32px;display:flex;flex-direction:column;gap:10px}}
.section,.info-box{{background:var(--card);border-radius:var(--r-lg);padding:22px 24px;box-shadow:0 8px 28px rgba(20,26,52,.07)}}
.section-title{{font-family:var(--font-display);font-size:.95rem;font-weight:800;display:flex;align-items:center;gap:10px;padding-bottom:12px;margin-bottom:16px;border-bottom:3px solid var(--accent)}}
.note,.alert{{padding:12px 16px;border-radius:0 8px 8px 0;font-size:13px;margin-bottom:16px}}
.note{{background:#eef3ff;border-left:4px solid var(--primary);color:#374165}}
.alert{{background:#fff7ed;border-left:4px solid #f59e0b;color:#9a3412}}
.metrics-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px;margin-bottom:10px}}
.metric-card{{background:var(--surface);padding:20px;border-radius:var(--r-md);box-shadow:0 4px 12px rgba(20,26,52,.07);text-align:center}}
.metric-card.destaque{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff}}
.metric-card .label{{font-size:.82em;opacity:.8;margin-bottom:8px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}}
.metric-card .value{{font-family:var(--font-display);font-size:2em;font-weight:800;line-height:1.1}}
.metric-card .subtext{{font-size:.78em;margin-top:6px;opacity:.75}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:12px}}
thead th{{font-family:var(--font-display);background:linear-gradient(135deg,var(--primary),#5b7ff0);color:#fff;padding:10px 12px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}}
tbody td{{padding:9px 12px;border-bottom:1px solid #f0f2f8;vertical-align:middle}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:#f5f7ff}}
.numero{{text-align:right}}
.pill-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}
.pill{{display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;font-size:.8em;font-weight:700}}
.pill.ok{{background:#e6fffa;color:#0f766e}}
.pill.warn{{background:#fff7ed;color:#c2410c}}
.footer-note{{text-align:center;font-size:11px;color:var(--muted);padding:18px 20px;border-top:1px solid #e8ecf6;margin-top:8px;background:var(--card)}}
@media (max-width:900px){{.content{{padding:16px}}.hdr{{padding:18px;flex-wrap:wrap}}.section,.info-box{{padding:16px}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <a href="INDEX_[{config.campaign_code}].html"><img src="{LOGO_PATH}" alt="Brabo"></a>
    <div>
      <h1>📊 Análise de Criativos — {config.campaign_code}</h1>
      <p>{' | '.join(subtitle_bits)}</p>
    </div>
  </div>
  <div class="content">
    <div class="section">
      <div class="section-title">1. Visão Executiva Consolidada</div>
      <div class="note"><strong>Painel principal consolidado</strong> com métricas de vendas, rastreamento, investimento e leitura rápida de performance dos criativos.</div>
      <div class="metrics-grid">
        {metric_card('📈 Vendas Totais', br_number(total_vendas), f'Rastreadas: {br_number(rastreadas)} | Não rastreadas: {br_number(nao_rastreadas)}', True)}
        {metric_card('💰 Valor Total', br_money(dataset['total_faturamento']), f'Ticket médio: {br_money(dataset['ticket_medio'])}', True)}
        {metric_card('🎯 Total de Leads', br_number(dataset['total_leads']), f'Com UTM: {br_number(dataset['leads_utm'])} ({pct(leads_coverage)})')}
        {metric_card('📱 Criativos com Venda', br_number(dataset['criativos_com_venda']), 'Criativos com vendas rastreadas')}
        {metric_card('💸 Investimento Total', br_money(dataset['investimento_total']), f'Meta: {br_money(meta_inv)} | Google: {br_money(google_inv)}', True)}
        {metric_card('📊 ROAS Rastreado', f"{dataset['roas_rastreado']:.2f}x", 'Receita atribuída ÷ investimento', True)}
      </div>
      <div class="alert"><strong>Importante:</strong> {br_number(rastreadas)} de {br_number(total_vendas)} vendas ({pct(coverage)}) foram rastreadas por criativo via UTM.</div>
    </div>

    <div class="info-box">
      <h2>1.1 Top Criativos por Vendas</h2>
      <p>Ranking dos criativos com vendas rastreadas via CRM → vendas.</p>
      <table>
        <thead>
          <tr>
            <th>Posição</th>
            <th>Criativo</th>
            <th class="numero">Leads CRM</th>
            <th class="numero">Vendas</th>
            <th class="numero">Taxa Conv.</th>
            <th class="numero">Valor Total</th>
            <th class="numero">Valor/Lead</th>
          </tr>
        </thead>
        <tbody>{build_top_rows(df_merged)}</tbody>
      </table>
    </div>

    {do_zero_block}

    <div class="info-box">
      <h2>1.4 Top 10 Anúncios por ROAS (mín. 2 vendas)</h2>
      <p>Anúncios com melhor retorno sobre investimento, considerando receita atribuída via CRM.</p>
      <table>
        <thead>
          <tr>
            <th>Pos.</th><th>Criativo</th><th class="numero">Vendas</th><th class="numero">Receita</th><th class="numero">Investimento</th><th class="numero">ROAS</th><th class="numero">CPA</th><th class="numero">Conv.%</th>
          </tr>
        </thead>
        <tbody>{build_roas_rows(df_merged)}</tbody>
      </table>
    </div>

    <div class="section">
      <div class="section-title">2. Validados vs Novos — Comparativo</div>
      <div class="note">Classificação automática por referência histórica ou flag <code>[novos-ads]</code>, com conversão calculada via CRM → Hotmart/TMB.</div>
      <div class="alert" style="background:{verdict['color']}18;border-left-color:{verdict['color']};color:{verdict['color']}"><strong>Leitura:</strong> {verdict['text']}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        {summary_card('✅ Criativos Validados', '#28a745', sum_valid)}
        {summary_card('🆕 Criativos Novos', '#ff9800', sum_novos)}
      </div>
    </div>
  </div>
  <div class="footer-note">Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Saída: {config.output_path.name}</div>
</div>
</body>
</html>"""
    return html



def generate_report(config: LaunchConfig) -> Path:
    dataset = build_main_dataset(config)
    html = render_html(config, dataset)
    config.output_path.write_text(html, encoding="utf-8")
    print(f"✓ Relatório gerado: {config.output_path}")
    print(
        {
            "campaign": config.campaign_code,
            "vendas_total": int(dataset["total_vendas"]),
            "rastreadas": int(dataset["rastreadas"]),
            "leads_total": int(dataset["total_leads"]),
            "leads_utm": int(dataset["leads_utm"]),
            "faturamento_total": round(float(dataset["total_faturamento"]), 2),
            "investimento_total": round(float(dataset["investimento_total"]), 2),
        }
    )
    return config.output_path



def main() -> None:
    config = parse_args()
    generate_report(config)


if __name__ == "__main__":
    main()
