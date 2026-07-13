#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = globals().get("BASE", Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm"))
CAMPAIGN_CODE = globals().get("CAMPAIGN_CODE", "PBB-FEV-26")
CAMPAIGN_FOLDER = globals().get("CAMPAIGN_FOLDER", "[PBB-FEV-26]")
ACTIVE_FOLDER = globals().get("ACTIVE_FOLDER", "active-campaing")
TYPEFORM_FOLDER = globals().get("TYPEFORM_FOLDER", "typeform")
VENDAS_FOLDER = globals().get("VENDAS_FOLDER", "vendas")
HOTMART_FILE = globals().get("HOTMART_FILE", "hotmart pbb-fev-26.csv")
TMB_FILE = globals().get("TMB_FILE", "tmb pbb-fev-26.csv")
OUTPUT_FILE = globals().get("OUTPUT_FILE", "ANALISE_VENDAS_[PBB-FEV-26].html")

ANALISES = BASE / "analises" / CAMPAIGN_FOLDER
ACTIVE_PATH = ANALISES / ACTIVE_FOLDER
TYPEFORM_PATH = ANALISES / TYPEFORM_FOLDER
VENDAS_PATH = ANALISES / VENDAS_FOLDER
OUTPUT_PATH = ANALISES / OUTPUT_FILE


def br_money(value):
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def br_int(value):
    return f"{int(round(float(value))):,}".replace(",", ".")


def br_pct(value):
    return f"{float(value):.2f}%".replace(".", ",")


def normalizar_texto(value):
    if pd.isna(value):
        return ""
    value = str(value).strip().lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\s+", " ", value)
    return value


def limpar_numero(value):
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ";" in text:
        text = text.split(";", 1)[0]
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    text = re.sub(r"[^\d\-.]", "", text)
    try:
        return float(text)
    except Exception:
        return 0.0


def encontrar_csv(folder, pattern="*.csv"):
    arquivos = sorted(folder.glob(pattern))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {folder}")
    return max(arquivos, key=lambda path: path.stat().st_mtime)


def encontrar_coluna(columns, *termos):
    normalized = {col: normalizar_texto(col) for col in columns}
    for col, norm in normalized.items():
        if all(term in norm for term in termos):
            return col
    return None


def encontrar_coluna_email(columns):
    normalized = {col: normalizar_texto(col) for col in columns}
    for col, norm in normalized.items():
        if "email" in norm or "mail" in norm:
            return col
    return None


def detectar_canal(source):
    texto = normalizar_texto(source)
    if not texto:
        return "Sem rastreio"
    if texto.startswith("fb") or "facebook" in texto or "meta" in texto or "instagram" in texto:
        return "Meta / Facebook"
    if texto.startswith("yt") or "youtube" in texto:
        return "YouTube"
    if "google" in texto or texto.startswith("g-") or texto.startswith("gg"):
        return "Google"
    if "whatsapp" in texto or "comercial" in texto:
        return "Comercial / WhatsApp"
    return "Outros"


def top_rows(df, group_col, value_col="valor_num", count_col="email_n", limit=10, label=None):
    if group_col not in df.columns or df.empty:
        return []
    series = get_series(df, group_col)
    base = df[series.astype(str).str.strip() != ""].copy()
    base["__grupo_top__"] = get_series(base, group_col).astype(str).str.strip()
    if base.empty:
        return []
    grouped = (
        base.groupby("__grupo_top__")
        .agg(
            compradores=(count_col, "nunique"),
            transacoes=(count_col, "size"),
            faturamento=(value_col, "sum"),
        )
        .reset_index()
        .sort_values(["faturamento", "compradores"], ascending=False)
        .head(limit)
    )
    rows = []
    for _, row in grouped.iterrows():
        ticket = row["faturamento"] / row["transacoes"] if row["transacoes"] else 0
        rows.append({
            "label": str(row["__grupo_top__"]) if label is None else label(str(row["__grupo_top__"])),
            "compradores": int(row["compradores"]),
            "transacoes": int(row["transacoes"]),
            "faturamento": float(row["faturamento"]),
            "ticket": float(ticket),
        })
    return rows


def html_table(headers, rows):
    if not rows:
        return "<div class='empty-box'>Dados não disponíveis para esta leitura.</div>"
    head_html = "".join(f"<th>{header}</th>" for header in headers)
    body_html = "".join(rows)
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def get_series(df, column_name):
    selected = df[column_name]
    if isinstance(selected, pd.DataFrame):
        return selected.iloc[:, 0]
    return selected


def render_group_table(rows, first_label):
    html_rows = []
    for row in rows:
        html_rows.append(
            f"<tr><td>{row['label']}</td>"
            f"<td style='text-align:right'>{br_int(row['compradores'])}</td>"
            f"<td style='text-align:right'>{br_int(row['transacoes'])}</td>"
            f"<td style='text-align:right'>{br_money(row['faturamento'])}</td>"
            f"<td style='text-align:right'>{br_money(row['ticket'])}</td></tr>"
        )
    return html_table([first_label, "Compradores", "Transações", "Faturamento", "Ticket Médio"], html_rows)


def calcular_propensao(df, pergunta_col, minimo_leads=80):
    if pergunta_col not in df.columns or df.empty:
        return pd.DataFrame()
    serie = get_series(df, pergunta_col)
    base = df[serie.astype(str).str.strip() != ""].copy()
    if base.empty:
        return pd.DataFrame()
    base["__resposta_prop__"] = get_series(base, pergunta_col).astype(str).str.strip()
    grouped = (
        base.groupby("__resposta_prop__")
        .agg(
            leads=("email_n", "nunique"),
            compradores=("comprador", "sum"),
            faturamento=("valor_comprado", "sum"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["leads"] >= minimo_leads].copy()
    if grouped.empty:
        return grouped
    grouped["tx_conv"] = grouped.apply(lambda row: (row["compradores"] / row["leads"] * 100) if row["leads"] else 0, axis=1)
    grouped["ticket"] = grouped.apply(lambda row: (row["faturamento"] / row["compradores"]) if row["compradores"] else 0, axis=1)
    grouped = grouped.sort_values(["tx_conv", "compradores", "faturamento"], ascending=[False, False, False])
    return grouped


def pick_propensity_insights(propensao_map, min_buyers_for_ticket=8):
    candidatos = []
    for pergunta, df in propensao_map.items():
        if df.empty:
            continue
        for _, row in df.iterrows():
            candidatos.append({
                "pergunta": pergunta,
                "resposta": str(row.iloc[0]),
                "leads": int(row["leads"]),
                "compradores": int(row["compradores"]),
                "tx_conv": float(row["tx_conv"]),
                "ticket": float(row["ticket"]),
                "faturamento": float(row["faturamento"]),
            })
    if not candidatos:
        return {"volume": None, "conversao": None, "ticket": None}
    volume = sorted(candidatos, key=lambda item: (item["compradores"], item["faturamento"]), reverse=True)[0]
    conversao = sorted(candidatos, key=lambda item: (item["tx_conv"], item["compradores"]), reverse=True)[0]
    ticket_candidates = [item for item in candidatos if item["compradores"] >= min_buyers_for_ticket]
    ticket = sorted(ticket_candidates or candidatos, key=lambda item: (item["ticket"], item["compradores"]), reverse=True)[0]
    return {"volume": volume, "conversao": conversao, "ticket": ticket}


print("📥 Carregando bases de vendas consolidadas...")

crm_path = encontrar_csv(ACTIVE_PATH)
typeform_paths = sorted(TYPEFORM_PATH.glob("*.csv"))

crm = pd.read_csv(crm_path, low_memory=False)
typeform_frames = []
for typeform_path in typeform_paths:
    df_typeform_src = pd.read_csv(typeform_path, low_memory=False)
    tf_email_src = encontrar_coluna_email(df_typeform_src.columns)
    df_typeform_src["email_n"] = df_typeform_src[tf_email_src].astype(str).str.lower().str.strip()
    df_typeform_src = df_typeform_src[df_typeform_src["email_n"].str.contains("@", na=False)].copy()
    df_typeform_src["typeform_origem"] = typeform_path.name
    typeform_frames.append(df_typeform_src)
if not typeform_frames:
    raise FileNotFoundError(f"Nenhum CSV encontrado em {TYPEFORM_PATH}")
typeform = pd.concat(typeform_frames, ignore_index=True, sort=False)
hotmart = pd.read_csv(VENDAS_PATH / HOTMART_FILE, sep=";", encoding="utf-8")
try:
    tmb_raw = pd.read_csv(VENDAS_PATH / TMB_FILE, sep=";", encoding="utf-8")
except UnicodeDecodeError:
    tmb_raw = pd.read_csv(VENDAS_PATH / TMB_FILE, sep=";", encoding="latin-1")

crm_email_col = encontrar_coluna_email(crm.columns) or "Email"
crm["email_n"] = crm[crm_email_col].astype(str).str.lower().str.strip()
crm = crm[crm["email_n"].str.contains("@", na=False)].copy()
crm = crm.drop_duplicates("email_n", keep="first")

crm_source_col = encontrar_coluna(crm.columns, "utm", "source")
crm_medium_col = encontrar_coluna(crm.columns, "utm", "medium")
crm_campaign_col = encontrar_coluna(crm.columns, "utm", "campaign")
crm_content_col = encontrar_coluna(crm.columns, "utm", "content")
crm_temp_col = encontrar_coluna(crm.columns, "temperatura")
crm_eng_col = encontrar_coluna(crm.columns, "engajamento")

typeform = typeform.drop_duplicates("email_n", keep="last")

tf_gender_col = encontrar_coluna(typeform.columns, "genero")
tf_state_col = encontrar_coluna(typeform.columns, "estado")
tf_age_col = encontrar_coluna(typeform.columns, "qual a sua idade") or encontrar_coluna(typeform.columns, "idade")
tf_school_col = encontrar_coluna(typeform.columns, "grau", "escolaridade")
tf_prof_col = encontrar_coluna(typeform.columns, "situacao", "profissional")
tf_study_col = encontrar_coluna(typeform.columns, "voce se considera")
tf_commit_col = encontrar_coluna(typeform.columns, "se compromete")
tf_graton_col = encontrar_coluna(typeform.columns, "felipe graton") or encontrar_coluna(typeform.columns, "ivan neto")
tf_reason_col = encontrar_coluna(typeform.columns, "por que voce decidiu") or encontrar_coluna(typeform.columns, "o que fez voce decidir")
tf_doubt_col = encontrar_coluna(typeform.columns, "duvida numero 1") or encontrar_coluna(typeform.columns, "duvida ou medo")

hotmart["email_n"] = hotmart["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
hotmart = hotmart[hotmart["email_n"].str.contains("@", na=False)].copy()
# RI cobrança=1 (novas assinaturas) × parcelas = valor total do contrato; excluir cobrança>1
_tipo_col = encontrar_coluna(hotmart.columns, "tipo", "cobran")
_par_col_vf = "Quantidade total de parcelas"
_cob_col_vf = "Quantidade de cobranças"
if _tipo_col:
    _vf_norm = hotmart[hotmart[_tipo_col].astype(str).str.strip() != "Recuperador Inteligente"].copy()
    _vf_norm["valor_num"] = _vf_norm["Faturamento líquido do(a) Produtor(a)"].apply(limpar_numero)
    _vf_ri = hotmart[
        (hotmart[_tipo_col].astype(str).str.strip() == "Recuperador Inteligente") &
        (pd.to_numeric(hotmart[_cob_col_vf], errors="coerce").fillna(0) == 1)
    ].copy()
    _vf_ri[_par_col_vf] = pd.to_numeric(_vf_ri[_par_col_vf], errors="coerce").fillna(1)
    _vf_ri["valor_num"] = _vf_ri["Faturamento líquido do(a) Produtor(a)"].apply(limpar_numero) * _vf_ri[_par_col_vf]
    hotmart = pd.concat([_vf_norm, _vf_ri], ignore_index=True)
    hotmart["email_n"] = hotmart["Email do(a) Comprador(a)"].astype(str).str.lower().str.strip()
else:
    hotmart["valor_num"] = hotmart["Faturamento líquido do(a) Produtor(a)"].apply(limpar_numero)
hotmart["plataforma_venda"] = "Hotmart"
hotmart["forma_pagamento"] = hotmart.get("Método de pagamento", pd.Series(["Cartão"] * len(hotmart))).fillna("Cartão")
hotmart["estado_venda"] = hotmart.get("Estado / Província", pd.Series([""] * len(hotmart))).fillna("")
hotmart["cidade_venda"] = hotmart.get("Cidade", pd.Series([""] * len(hotmart))).fillna("")
hotmart["nome_cliente"] = hotmart.get("Comprador(a)", pd.Series([""] * len(hotmart))).fillna("")

# TMB — incluir apenas vendas válidas (Vigente/Efetivado)
tmb = tmb_raw.copy()
tmb_status_col = encontrar_coluna(tmb.columns, "situa") or encontrar_coluna(tmb.columns, "status")
if tmb_status_col:
    tmb_status_norm = tmb[tmb_status_col].astype(str).str.strip().str.lower()
    tmb = tmb[tmb_status_norm.isin({"vigente", "efetivado"})].copy()
tmb_email_col = encontrar_coluna_email(tmb.columns) or encontrar_coluna(tmb.columns, "cliente")
tmb["email_n"] = tmb[tmb_email_col].astype(str).str.lower().str.strip()
tmb = tmb[tmb["email_n"].str.contains("@", na=False)].copy()
tmb["valor_num"] = tmb[(encontrar_coluna(tmb.columns, "ticket") or "Ticket (R$)")].apply(limpar_numero)
tmb["plataforma_venda"] = "TMB"
tmb["forma_pagamento"] = tmb.get("Modalidade de Contrato", pd.Series(["Boleto / TMB"] * len(tmb))).fillna("Boleto / TMB")
tmb["estado_venda"] = tmb.get("Estado", pd.Series([""] * len(tmb))).fillna("")
tmb["cidade_venda"] = tmb.get("Cidade", pd.Series([""] * len(tmb))).fillna("")
tmb["nome_cliente"] = tmb.get("Cliente Nome", pd.Series([""] * len(tmb))).fillna("")
tmb["utm_source_sale"] = tmb.get("utm_source", pd.Series([""] * len(tmb))).fillna("")
tmb["utm_medium_sale"] = tmb.get("utm_medium", pd.Series([""] * len(tmb))).fillna("")
tmb["utm_campaign_sale"] = tmb.get("utm_campaign", pd.Series([""] * len(tmb))).fillna("")
tmb["utm_content_sale"] = tmb.get("utm_content", pd.Series([""] * len(tmb))).fillna("")

sales = pd.concat(
    [
        hotmart[["email_n", "nome_cliente", "valor_num", "plataforma_venda", "forma_pagamento", "estado_venda", "cidade_venda"]],
        tmb[["email_n", "nome_cliente", "valor_num", "plataforma_venda", "forma_pagamento", "estado_venda", "cidade_venda", "utm_source_sale", "utm_medium_sale", "utm_campaign_sale", "utm_content_sale"]],
    ],
    ignore_index=True,
    sort=False,
)

crm_join_cols = ["email_n"]
for col in [crm_source_col, crm_medium_col, crm_campaign_col, crm_content_col, crm_temp_col, crm_eng_col]:
    if col:
        crm_join_cols.append(col)
sales = sales.merge(crm[crm_join_cols], on="email_n", how="left")

tf_join_cols = ["email_n"]
for col in [tf_gender_col, tf_state_col, tf_age_col, tf_school_col, tf_prof_col, tf_study_col, tf_commit_col, tf_graton_col, tf_reason_col, tf_doubt_col]:
    if col:
        tf_join_cols.append(col)
sales = sales.merge(typeform[tf_join_cols], on="email_n", how="left")
sales["tem_crm"] = sales["email_n"].isin(set(crm["email_n"]))
sales["tem_typeform"] = sales["email_n"].isin(set(typeform["email_n"]))

sales["utm_source_final"] = sales[crm_source_col] if crm_source_col else ""
sales["utm_medium_final"] = sales[crm_medium_col] if crm_medium_col else ""
sales["utm_campaign_final"] = sales[crm_campaign_col] if crm_campaign_col else ""
sales["utm_content_final"] = sales[crm_content_col] if crm_content_col else ""

for col_final, col_fallback in [
    ("utm_source_final", "utm_source_sale"),
    ("utm_medium_final", "utm_medium_sale"),
    ("utm_campaign_final", "utm_campaign_sale"),
    ("utm_content_final", "utm_content_sale"),
]:
    if col_fallback in sales.columns:
        sales[col_final] = sales[col_final].fillna("")
        sales.loc[sales[col_final].astype(str).str.strip() == "", col_final] = sales.loc[
            sales[col_final].astype(str).str.strip() == "", col_fallback
        ]

sales["canal_origem"] = sales["utm_source_final"].apply(detectar_canal)
sales["estado_final"] = sales["estado_venda"].fillna("")
if tf_state_col:
    sales.loc[sales["estado_final"].astype(str).str.strip() == "", "estado_final"] = sales.loc[
        sales["estado_final"].astype(str).str.strip() == "", tf_state_col
    ]
sales["cidade_final"] = sales["cidade_venda"].fillna("")

total_receita = float(sales["valor_num"].sum())
total_transacoes = int(len(sales))
compradores_unicos = int(sales["email_n"].nunique())
ticket_medio = total_receita / total_transacoes if total_transacoes else 0
crm_match = int(sales.loc[sales["tem_crm"], "email_n"].nunique())
tf_match = int(sales.loc[sales["tem_typeform"], "email_n"].nunique())
leads_total = int(crm["email_n"].nunique())
taxa_conv = compradores_unicos / leads_total * 100 if leads_total else 0

platform_summary = (
    sales.groupby("plataforma_venda")
    .agg(transacoes=("email_n", "size"), compradores=("email_n", "nunique"), faturamento=("valor_num", "sum"))
    .reset_index()
)
platform_summary["ticket"] = platform_summary.apply(lambda row: row["faturamento"] / row["transacoes"] if row["transacoes"] else 0, axis=1)

rows_origem = top_rows(sales, "canal_origem", limit=8)
rows_campaign = top_rows(sales, "utm_campaign_final", limit=10, label=lambda value: value if value.strip() else "Sem campanha")
rows_state = top_rows(sales, "estado_final", limit=10, label=lambda value: value if value.strip() else "Não informado")
rows_city = top_rows(sales, "cidade_final", limit=10, label=lambda value: value if value.strip() else "Não informado")

lead_base = crm[["email_n"]].copy()
lead_base["comprador"] = lead_base["email_n"].isin(set(sales["email_n"]))
lead_base["valor_comprado"] = lead_base["email_n"].map(sales.groupby("email_n")["valor_num"].sum()).fillna(0)
for col in [crm_source_col, crm_medium_col, crm_campaign_col, crm_content_col, crm_temp_col, crm_eng_col]:
    if col:
        lead_base = lead_base.merge(crm[["email_n", col]], on="email_n", how="left")
lead_base = lead_base.merge(typeform[tf_join_cols], on="email_n", how="left")

propensao_map = {}
questoes = {
    "Compromisso de 2h/dia": tf_commit_col,
    "Já assistiu conteúdo do Graton": tf_graton_col,
    "Perfil de estudo": tf_study_col,
    "Faixa etária": tf_age_col,
    "Situação profissional": tf_prof_col,
    "Escolaridade": tf_school_col,
}
for label, column in questoes.items():
    if column:
        propensao_map[label] = calcular_propensao(lead_base, column)

prop_rows = []
for label, df_prop in propensao_map.items():
    if df_prop.empty:
        continue
    top = df_prop.head(2)
    for _, row in top.iterrows():
        resposta = str(row.iloc[0])
        prop_rows.append(
            f"<tr><td>{label}</td><td>{resposta}</td>"
            f"<td style='text-align:right'>{br_int(row['leads'])}</td>"
            f"<td style='text-align:right'>{br_int(row['compradores'])}</td>"
            f"<td style='text-align:right'>{br_pct(row['tx_conv'])}</td>"
            f"<td style='text-align:right'>{br_money(row['faturamento'])}</td>"
            f"<td style='text-align:right'>{br_money(row['ticket'])}</td></tr>"
        )

propensity_insights = pick_propensity_insights(propensao_map)
insight_volume = propensity_insights["volume"]
insight_conversao = propensity_insights["conversao"]
insight_ticket = propensity_insights["ticket"]
top_origem = rows_origem[0] if rows_origem else None
top_estado = rows_state[0] if rows_state else None

demographic_tables = []
for title, column in [
    ("Gênero", tf_gender_col),
    ("Faixa etária", tf_age_col),
    ("Situação profissional", tf_prof_col),
    ("Escolaridade", tf_school_col),
]:
    if not column:
        continue
    rows = top_rows(sales, column, limit=8)
    if rows:
        demographic_tables.append((title, render_group_table(rows, title)))

payment_rows = []
for _, row in platform_summary.iterrows():
    payment_rows.append(
        f"<tr><td>{row['plataforma_venda']}</td>"
        f"<td style='text-align:right'>{br_int(row['compradores'])}</td>"
        f"<td style='text-align:right'>{br_int(row['transacoes'])}</td>"
        f"<td style='text-align:right'>{br_money(row['faturamento'])}</td>"
        f"<td style='text-align:right'>{br_money(row['ticket'])}</td></tr>"
    )

html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Vendas - {CAMPAIGN_CODE}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', 'Segoe UI', sans-serif; background: linear-gradient(135deg, #eff3ff 0%, #f7f9ff 100%); color: #1f2937; }}
        .container {{ max-width: 1380px; margin: 24px auto; padding: 0 18px 40px; }}
        .hero {{ background: linear-gradient(135deg, #1f4fd8 0%, #6aa8ff 100%); color: white; border-radius: 18px; padding: 28px; box-shadow: 0 20px 50px rgba(47,94,227,.22); margin-bottom: 22px; }}
        .hero h1 {{ font-size: 34px; margin-bottom: 8px; }}
        .hero p {{ opacity: .92; margin-top: 4px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-top: 18px; }}
        .metric {{ background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.16); border-radius: 14px; padding: 16px; backdrop-filter: blur(10px); }}
        .metric .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; opacity: .85; margin-bottom: 6px; }}
        .metric .value {{ font-size: 26px; font-weight: 800; }}
        .section {{ background: white; border-radius: 16px; padding: 22px; margin-bottom: 18px; box-shadow: 0 10px 32px rgba(15,23,42,.08); border: 1px solid #e8ecf5; }}
        .section h2 {{ font-size: 22px; margin-bottom: 14px; color: #1d4ed8; }}
        .section-intro {{ color: #667085; margin-bottom: 16px; }}
        .grid-2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
        .grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
        .card {{ background: #f8faff; border: 1px solid #dfe7fb; border-radius: 14px; padding: 16px; }}
        .card h3 {{ font-size: 16px; margin-bottom: 10px; color: #233876; }}
        .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: #eef3ff; color: #2f5ee3; font-size: 12px; font-weight: 700; margin-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #2f5ee3; color: white; text-align: left; padding: 12px; font-weight: 700; }}
        td {{ padding: 12px; border-bottom: 1px solid #e7ecf3; vertical-align: top; }}
        tr:hover td {{ background: #f8fbff; }}
        .insight {{ padding: 16px; border-radius: 14px; margin-top: 12px; }}
        .insight.success {{ background: #f0fdf4; border: 1px solid #bbf7d0; }}
        .insight.warn {{ background: #fffbeb; border: 1px solid #fde68a; }}
        .insight.info {{ background: #eff6ff; border: 1px solid #bfdbfe; }}
        .insight strong {{ display: block; margin-bottom: 6px; }}
        .footer {{ text-align: center; color: #667085; font-size: 12px; padding-top: 8px; }}
        .empty-box {{ padding: 16px; border-radius: 12px; background: #f8fafc; color: #667085; border: 1px dashed #cbd5e1; }}
        @media (max-width: 980px) {{
            .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
            .hero h1 {{ font-size: 28px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <section class="hero">
            <h1>💰 Análise de Vendas Integrada</h1>
            <p>Cruzamento entre Typeform, Active Campaign, Hotmart e TMB para leitura de origem, ticket, perfil comprador e propensão.</p>
            <p>Atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            <div class="metrics">
                <div class="metric"><div class="label">Receita Total</div><div class="value">{br_money(total_receita)}</div></div>
                <div class="metric"><div class="label">Transações</div><div class="value">{br_int(total_transacoes)}</div></div>
                <div class="metric"><div class="label">Compradores Únicos</div><div class="value">{br_int(compradores_unicos)}</div></div>
                <div class="metric"><div class="label">Ticket Médio</div><div class="value">{br_money(ticket_medio)}</div></div>
                <div class="metric"><div class="label">Leads no CRM</div><div class="value">{br_int(leads_total)}</div></div>
                <div class="metric"><div class="label">Conversão Lead → Compra</div><div class="value">{br_pct(taxa_conv)}</div></div>
                <div class="metric"><div class="label">Compradores no CRM</div><div class="value">{br_int(crm_match)}</div></div>
                <div class="metric"><div class="label">Compradores no Typeform</div><div class="value">{br_int(tf_match)}</div></div>
            </div>
        </section>

        <section class="section">
            <h2>📌 Leitura Executiva</h2>
            <div class="grid-3">
                <div class="insight success">
                    <strong>Origem mais valiosa</strong>
                    {f"{top_origem['label']} lidera com {br_money(top_origem['faturamento'])}, {br_int(top_origem['compradores'])} compradores e ticket médio de {br_money(top_origem['ticket'])}." if top_origem else "Origem ainda sem volume suficiente para leitura."}
                </div>
                <div class="insight info">
                    <strong>Concentração geográfica</strong>
                    {f"{top_estado['label']} concentra o maior faturamento mapeado, com {br_money(top_estado['faturamento'])} e {br_int(top_estado['compradores'])} compradores." if top_estado else "Sem concentração geográfica mapeável com os dados atuais."}
                </div>
                <div class="insight warn">
                    <strong>Maior volume comprador</strong>
                    {f"Na dimensão {insight_volume['pergunta']}, a resposta '{insight_volume['resposta']}' gerou {br_int(insight_volume['compradores'])} compradores, {br_pct(insight_volume['tx_conv'])} de conversão e {br_money(insight_volume['faturamento'])} de faturamento." if insight_volume else "Ainda não há amostra mínima suficiente para leitura robusta de volume."}
                </div>
                <div class="insight success">
                    <strong>Maior conversão</strong>
                    {f"Na dimensão {insight_conversao['pergunta']}, a resposta '{insight_conversao['resposta']}' entregou {br_pct(insight_conversao['tx_conv'])} de conversão sobre {br_int(insight_conversao['leads'])} leads." if insight_conversao else "Ainda não há amostra mínima suficiente para leitura robusta de conversão."}
                </div>
                <div class="insight info">
                    <strong>Maior ticket</strong>
                    {f"Na dimensão {insight_ticket['pergunta']}, a resposta '{insight_ticket['resposta']}' fechou ticket médio de {br_money(insight_ticket['ticket'])} com {br_int(insight_ticket['compradores'])} compradores." if insight_ticket else "Ainda não há amostra mínima suficiente para leitura robusta de ticket."}
                </div>
            </div>
        </section>

        <section class="section">
            <h2>💳 Fechamento Comercial</h2>
            <div class="section-intro">Fechamento por plataforma de venda, separado entre transações e compradores únicos.</div>
            {html_table(["Plataforma", "Compradores", "Transações", "Faturamento", "Ticket Médio"], payment_rows)}
        </section>

        <section class="section">
            <h2>🧭 Origem das Vendas</h2>
            <div class="grid-2">
                <div class="card">
                    <div class="pill">Top canais</div>
                    {render_group_table(rows_origem, "Canal de Origem")}
                </div>
                <div class="card">
                    <div class="pill">Top campanhas</div>
                    {render_group_table(rows_campaign, "UTM Campaign")}
                </div>
            </div>
        </section>

        <section class="section">
            <h2>👥 Perfil Demográfico</h2>
            <div class="section-intro">Leitura dos compradores que conseguiram ser vinculados ao Typeform.</div>
            <div class="grid-2">
                {''.join(f"<div class='card'><div class='pill'>{title}</div>{table}</div>" for title, table in demographic_tables) if demographic_tables else "<div class='empty-box'>Não houve correspondência suficiente entre vendas e respostas do Typeform para abrir o perfil demográfico.</div>"}
            </div>
        </section>

        <section class="section">
            <h2>📍 Geografia das Vendas</h2>
            <div class="grid-2">
                <div class="card">
                    <div class="pill">Estados</div>
                    {render_group_table(rows_state, "UF")}
                </div>
                <div class="card">
                    <div class="pill">Cidades</div>
                    {render_group_table(rows_city, "Cidade")}
                </div>
            </div>
        </section>

        <section class="section">
            <h2>🧪 Propensão por Resposta</h2>
            <div class="section-intro">Taxa de conversão calculada sobre leads que responderam o Typeform e foram localizados no CRM. Cortamos grupos muito pequenos para evitar falso positivo.</div>
            {html_table(["Dimensão", "Resposta", "Leads", "Compradores", "Tx. Conversão", "Faturamento", "Ticket Médio"], prop_rows)}
        </section>

        <section class="section">
            <h2>💡 Insights Acionáveis</h2>
            <div class="grid-3">
                <div class="insight info">
                    <strong>Rastreabilidade</strong>
                    {br_int(crm_match)} compradores bateram com o Active e {br_int(tf_match)} também bateram com o Typeform. Toda venda fora desse cruzamento ainda fica sem leitura comportamental completa.
                </div>
                <div class="insight success">
                    <strong>Prioridade comercial</strong>
                    Use a tabela de origem para priorizar os canais e campanhas que combinam receita alta com ticket saudável, em vez de otimizar apenas por volume de venda.
                </div>
                <div class="insight warn">
                    <strong>Próximo nível</strong>
                    A próxima evolução é levar essas dimensões para score comercial: origem, temperatura, engajamento e respostas de propensão podem virar régua e priorização de atendimento.
                </div>
            </div>
        </section>

        <div class="footer">Relatório gerado automaticamente para {CAMPAIGN_CODE} | Brabo Concursos</div>
    </div>
</body>
</html>
"""

OUTPUT_PATH.write_text(html, encoding="utf-8")

print(f"✓ Relatório gerado: {OUTPUT_PATH}")
print(f"  Receita total: {br_money(total_receita)}")
print(f"  Compradores únicos: {br_int(compradores_unicos)}")
print(f"  Ticket médio: {br_money(ticket_medio)}")