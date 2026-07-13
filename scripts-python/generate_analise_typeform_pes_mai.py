#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv as csvmod
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES = BASE / "analises" / "[PES-MAI-26]"
TYPEFORM = ANALISES / "Typeform"
VENDAS = ANALISES / "Vendas"
ACTIVE = ANALISES / "Active Campaign"
OUTPUT = ANALISES / "ANALISE_TYPEFORM_[PES-MAI-26].html"
LOGO_PATH = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"


def encontrar_coluna(df: pd.DataFrame, *termos: str) -> str | None:
    termos = tuple(t.lower() for t in termos)
    for coluna in df.columns:
        col = coluna.lower()
        if all(termo in col for termo in termos):
            return coluna
    return None


def normalizar_email(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    out = df.copy()
    out["email_norm"] = out[coluna].astype(str).str.strip().str.lower()
    out = out[out["email_norm"].str.contains("@", na=False)].copy()
    out = out.drop_duplicates("email_norm", keep="last")
    return out


def detectar_plataforma(src: str) -> str:
    texto = str(src).strip().lower()
    if any(chave in texto for chave in ["facebook", "fb", "meta", "instagram"]):
        return "Meta / Facebook"
    if any(chave in texto for chave in ["google", "youtube", "yt", "gads", "adwords"]):
        return "Google / YouTube"
    return "Outros"


def carregar_vendas() -> pd.DataFrame:
    hm_raw = pd.read_csv(VENDAS / "pes-mai-26-hotmart.csv", sep=";", encoding="utf-8", low_memory=False)
    hm_raw = normalizar_email(hm_raw, "Email do(a) Comprador(a)")
    _tipo_c = next((c for c in hm_raw.columns if "tipo" in c.lower() and "cobran" in c.lower()), None)
    if _tipo_c:
        _par_c = "Quantidade total de parcelas"
        _cob_c = "Quantidade de cobranças"
        _t_norm = hm_raw[hm_raw[_tipo_c].astype(str).str.strip() != "Recuperador Inteligente"].copy()
        _t_norm["valor"] = pd.to_numeric(_t_norm["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
        _t_ri = hm_raw[
            (hm_raw[_tipo_c].astype(str).str.strip() == "Recuperador Inteligente") &
            (pd.to_numeric(hm_raw[_cob_c], errors="coerce").fillna(0) == 1)
        ].copy()
        _t_ri[_par_c] = pd.to_numeric(_t_ri[_par_c], errors="coerce").fillna(1)
        _t_ri["valor"] = pd.to_numeric(_t_ri["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0) * _t_ri[_par_c]
        hm = pd.concat([_t_norm, _t_ri], ignore_index=True)
    else:
        hm = hm_raw.copy()
        hm["valor"] = pd.to_numeric(hm["Faturamento líquido do(a) Produtor(a)"], errors="coerce").fillna(0)
    hm["origem_venda"] = "Hotmart"

    tmb = pd.read_csv(VENDAS / "pes-mai-26-tmb.csv", sep=";", encoding="utf-8", low_memory=False)
    email_col = next(c for c in tmb.columns if "mail" in c.lower())
    valor_col = next(c for c in tmb.columns if "ticket" in c.lower())
    tmb = normalizar_email(tmb, email_col)
    tmb["valor"] = pd.to_numeric(tmb[valor_col], errors="coerce").fillna(0)
    tmb["origem_venda"] = "TMB"

    return pd.concat(
        [hm[["email_norm", "valor", "origem_venda"]], tmb[["email_norm", "valor", "origem_venda"]]],
        ignore_index=True,
    )


def tabela_linhas(df: pd.DataFrame, label_col: str, value_col: str, limit: int = 10) -> str:
    if df.empty:
        return "<tr><td colspan='2'>Sem dados</td></tr>"
    linhas = []
    for _, row in df.head(limit).iterrows():
        linhas.append(f"<tr><td>{row[label_col]}</td><td style='text-align:right'>{row[value_col]}</td></tr>")
    return "".join(linhas)


def metric_box(label: str, value: str) -> str:
    return f'<div class="metric-box"><div class="label">{label}</div><div class="value">{value}</div></div>'


def main():
    print("=" * 90)
    print("ANALISE TYPEFORM - PES-MAI-26")
    print("=" * 90)

    tf_cap = pd.read_csv(TYPEFORM / "responses-pesquisa-pes-mai-26.csv", low_memory=False)
    tf_alunos = pd.read_csv(TYPEFORM / "responses-pesquisa-alunos-pes-mai-26.csv", low_memory=False)
    tf_cap = normalizar_email(tf_cap, encontrar_coluna(tf_cap, "e-mail") or "Digite o seu e-mail.")
    tf_alunos = normalizar_email(tf_alunos, encontrar_coluna(tf_alunos, "e-mail") or "Digite o seu e-mail")

    crm_file = max(ACTIVE.glob("*.csv"), key=lambda path: path.stat().st_mtime)
    crm = pd.read_csv(crm_file, sep=",", quoting=csvmod.QUOTE_MINIMAL, low_memory=False)
    crm = normalizar_email(crm, "Email")
    crm["utm_source"] = crm.get("*Utm_source", "").fillna("")
    crm["plataforma"] = crm["utm_source"].apply(detectar_plataforma)

    vendas = carregar_vendas()
    vendas_emails = set(vendas["email_norm"])

    tf_total = pd.concat([
        tf_cap.assign(pesquisa="Captação"),
        tf_alunos.assign(pesquisa="Alunos"),
    ], ignore_index=True).drop_duplicates("email_norm", keep="last")

    tf_total["entrou_crm"] = tf_total["email_norm"].isin(set(crm["email_norm"]))
    tf_total["comprou"] = tf_total["email_norm"].isin(vendas_emails)

    crm_attr = crm[["email_norm", "utm_source", "plataforma"]].drop_duplicates("email_norm", keep="last")
    tf_total = tf_total.merge(crm_attr, on="email_norm", how="left")
    tf_total["plataforma"] = tf_total["plataforma"].fillna("Sem CRM")

    receita_por_email = vendas.groupby("email_norm")["valor"].sum()
    tf_total["receita"] = tf_total["email_norm"].map(receita_por_email).fillna(0)

    total_cap = len(tf_cap)
    total_alunos = len(tf_alunos)
    total_unicos = len(tf_total)
    match_crm = int(tf_total["entrou_crm"].sum())
    match_sales = int(tf_total["comprou"].sum())
    receita_total = float(tf_total["receita"].sum())

    por_pesquisa = (
        tf_total.groupby("pesquisa")
        .agg(respondentes=("email_norm", "nunique"), crm=("entrou_crm", "sum"), compradores=("comprou", "sum"), receita=("receita", "sum"))
        .reset_index()
    )
    por_pesquisa["taxa_crm"] = (por_pesquisa["crm"] / por_pesquisa["respondentes"] * 100).round(1)
    por_pesquisa["taxa_compra"] = (por_pesquisa["compradores"] / por_pesquisa["respondentes"] * 100).round(1)
    por_pesquisa["receita_fmt"] = por_pesquisa["receita"].map(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    origem = (
        tf_total.groupby("plataforma")["email_norm"]
        .nunique()
        .reset_index(name="respondentes")
        .sort_values("respondentes", ascending=False)
    )

    cap_estado_col = encontrar_coluna(tf_cap, "estado")
    alunos_origem_col = encontrar_coluna(tf_alunos, "conheceu") or encontrar_coluna(tf_alunos, "ivan neto")

    estados = pd.DataFrame(columns=["estado", "respondentes"])
    if cap_estado_col:
        estados = (
            tf_cap[cap_estado_col]
            .fillna("Não informado")
            .astype(str)
            .value_counts()
            .head(10)
            .rename_axis("estado")
            .reset_index(name="respondentes")
        )

    origem_alunos = pd.DataFrame(columns=["origem", "respondentes"])
    if alunos_origem_col:
        origem_alunos = (
            tf_alunos[alunos_origem_col]
            .fillna("Não informado")
            .astype(str)
            .value_counts()
            .head(10)
            .rename_axis("origem")
            .reset_index(name="respondentes")
        )

    linhas_pesquisa = "".join(
        f"<tr><td>{row['pesquisa']}</td><td style='text-align:right'>{int(row['respondentes'])}</td><td style='text-align:right'>{int(row['crm'])}</td><td style='text-align:right'>{row['taxa_crm']:.1f}%</td><td style='text-align:right'>{int(row['compradores'])}</td><td style='text-align:right'>{row['taxa_compra']:.1f}%</td><td style='text-align:right'>{row['receita_fmt']}</td></tr>"
        for _, row in por_pesquisa.iterrows()
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise Typeform - PES-MAI-26</title>
    <link rel="icon" type="image/png" href="{FAVICON_PATH}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #333; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 20px auto; background: white; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; border-radius: 8px; }}
        .header {{ background: white; color: #333; padding: 40px 20px; display: flex; justify-content: center; align-items: center; text-align: center; flex-wrap: wrap; border-bottom: 1px solid #eee; }}
        .header-logo {{ margin-right: 30px; }}
        .header-logo img {{ max-width: 120px; height: auto; }}
        .header-title h1 {{ font-size: 32px; margin-bottom: 10px; color: #333; }}
        .header-title p {{ font-size: 14px; color: #666; margin: 5px 0; }}
        .content {{ padding: 40px; max-width: 100%; margin: 0 auto; }}
        .metric-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin: 10px 15px 10px 0; display: inline-block; min-width: 200px; }}
        .metric-box .label {{ font-size: 12px; text-transform: uppercase; opacity: 0.9; margin-bottom: 5px; }}
        .metric-box .value {{ font-size: 24px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
        th {{ background: #667eea; color: white; text-align: left; padding: 12px; font-size: 14px; }}
        td {{ padding: 12px; border-bottom: 1px solid #ddd; }}
        .two-col {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:20px; }}
        .note {{ color:#555; margin-top:10px; line-height:1.6; }}
        h2 {{ margin-top: 30px; margin-bottom: 15px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #eee; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-logo"><a href="INDEX_[PES-MAI-26].html"><img src="{LOGO_PATH}" alt="Brabo Concursos"></a></div>
            <div class="header-title">
                <h1>📝 Typeform + Pesquisa de Alunos</h1>
                <p>Campanha PES-MAI-26</p>
                <p>Período: Maio de 2026</p>
            </div>
        </div>
        <div class="content">
            <p class="note">Cruzamento entre CRM, vendas e as duas pesquisas disponíveis para medir cobertura, qualidade e origem dos respondentes.</p>
            <div style="margin: 20px 0;">
                {metric_box('Pesquisa de Captação', f'{total_cap:,}'.replace(',', '.'))}
                {metric_box('Pesquisa de Alunos', f'{total_alunos:,}'.replace(',', '.'))}
                {metric_box('Respondentes Únicos', f'{total_unicos:,}'.replace(',', '.'))}
                {metric_box('Match no CRM', f'{match_crm:,}'.replace(',', '.'))}
                {metric_box('Compradores', f'{match_sales:,}'.replace(',', '.'))}
                {metric_box('Receita Rastreável', f"R$ {receita_total:,.0f}".replace(',', '.'))}
            </div>

        <section>
            <h2>Resumo por Pesquisa</h2>
            <table>
                <thead><tr><th>Pesquisa</th><th>Respondentes</th><th>No CRM</th><th>Taxa CRM</th><th>Compradores</th><th>Taxa Compra</th><th>Receita</th></tr></thead>
                <tbody>{linhas_pesquisa}</tbody>
            </table>
        </section>

        <section class="two-col">
            <div>
                <h2>Origem dos Respondentes no CRM</h2>
                <table>
                    <thead><tr><th>Plataforma</th><th>Respondentes</th></tr></thead>
                    <tbody>{tabela_linhas(origem, 'plataforma', 'respondentes')}</tbody>
                </table>
            </div>
            <div>
                <h2>Top Estados da Pesquisa de Captação</h2>
                <table>
                    <thead><tr><th>Estado</th><th>Respondentes</th></tr></thead>
                    <tbody>{tabela_linhas(estados, 'estado', 'respondentes')}</tbody>
                </table>
            </div>
        </section>

        <section class="two-col">
            <div>
                <h2>Como os Alunos Conheceram o Ivan</h2>
                <table>
                    <thead><tr><th>Origem</th><th>Respondentes</th></tr></thead>
                    <tbody>{tabela_linhas(origem_alunos, 'origem', 'respondentes')}</tbody>
                </table>
            </div>
            <div>
                <h2>Leitura Executiva</h2>
                <p class="note">A pesquisa de captação mede intenção de entrada e cobertura do CRM. A pesquisa de alunos adiciona a leitura pós-conversão, mostrando quais canais e argumentos de vendas chegaram até quem efetivamente comprou.</p>
                <p class="note">Com a mudança de UTM para <strong>facebook</strong> e <strong>google</strong>, a atribuição agora consolida corretamente Meta e Google/YouTube no cruzamento com CRM e vendas.</p>
                <p class="note">Os resultados desta página usam emails únicos. Isso evita dobrar respondentes que aparecem nas duas pesquisas ou repetem envio.</p>
            </div>
        </section>
        <div class="footer">Análises geradas em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</div>
        </div>
    </div>
</body>
</html>"""

    OUTPUT.write_text(html, encoding="utf-8")
    print(f"✓ Relatório gerado: {OUTPUT}")


if __name__ == "__main__":
    main()