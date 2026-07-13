#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera relatorio HTML: ANALISE_GOOGLE_ANUNCIOS_[PBB-FEV-26].html
Analise detalhada de criativos/anuncios do Google Ads para PBB-FEV-26.
"""

from datetime import datetime
from pathlib import Path
import pandas as pd

BASE_PATH = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ADS_CSV = BASE_PATH / "analises" / "[PBB-FEV-26]" / "google ads" / "Performance dos anúncios-pbb-fev-26.csv"
OUT_HTML = BASE_PATH / "analises" / "[PBB-FEV-26]" / "ANALISE_GOOGLE_ANUNCIOS_[PBB-FEV-26].html"


def to_number(value):
    """Converte formatos br (1.234,56 / 0,71%) para float."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return 0.0

    s = s.replace("%", "")
    s = s.replace("R$", "")
    s = s.replace(" ", "")
    s = s.replace(".", "").replace(",", ".")

    try:
        return float(s)
    except Exception:
        return 0.0


def fmt_money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(v):
    return f"{int(round(v)):,}".replace(",", ".")


def fmt_pct(v):
    return f"{v:.2f}%".replace(".", ",")


def css():
    return """
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }
        .container {
            max-width: 1250px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: white;
            padding: 30px;
            display: flex;
            align-items: center;
            gap: 20px;
            border-bottom: 1px solid #eee;
        }
        .header img { max-width: 100px; height: auto; }
        .header h1 { color: #4285f4; font-size: 28px; margin-bottom: 5px; }
        .header p { color: #666; }
        .content { padding: 30px; }
        .section-title {
            color: #4285f4;
            border-bottom: 3px solid #4285f4;
            padding-bottom: 8px;
            margin: 25px 0 15px;
            font-size: 22px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }
        .metric-box {
            background: linear-gradient(135deg, #4285f412 0%, #34a85312 100%);
            border-left: 4px solid #4285f4;
            border-radius: 6px;
            padding: 14px;
        }
        .metric-value { font-size: 22px; font-weight: bold; color: #4285f4; }
        .metric-label { color: #666; font-size: 13px; margin-top: 4px; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0 20px;
            font-size: 14px;
        }
        th {
            background: #4285f4;
            color: white;
            padding: 10px;
            text-align: left;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        tr:hover { background: #f7f9ff; }
        .footer {
            text-align: center;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #eee;
            padding: 18px;
            margin-top: 20px;
        }
        .badge {
            display: inline-block;
            background: #eef4ff;
            color: #2e5cb8;
            border: 1px solid #d8e5ff;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            margin-bottom: 8px;
        }
    </style>
    """


print("Carregando dados de Google Ads (anuncios) FEV...")
if not ADS_CSV.exists():
    raise FileNotFoundError(f"Arquivo nao encontrado: {ADS_CSV}")

df = pd.read_csv(ADS_CSV, encoding="utf-8", skiprows=2)

# Conversao das principais metricas
for col in ["Cliques", "Impr.", "CPC méd.", "Custo", "Conversões", "Custo / conv.", "CTR", "Taxa de conv."]:
    if col in df.columns:
        df[col] = df[col].apply(to_number)

# Higienizacao
if "Nome do anúncio" in df.columns:
    df["Nome do anúncio"] = df["Nome do anúncio"].fillna("(sem nome)").astype(str)
if "Campanha" in df.columns:
    df["Campanha"] = df["Campanha"].fillna("(sem campanha)").astype(str)
if "Grupo de anúncios" in df.columns:
    df["Grupo de anúncios"] = df["Grupo de anúncios"].fillna("(sem grupo)").astype(str)

# Remove linhas vazias de total/rodape de export
if "Nome do anúncio" in df.columns:
    df = df[df["Nome do anúncio"].str.strip() != ""]

# KPIs
total_invest = df["Custo"].sum() if "Custo" in df.columns else 0
total_conv = df["Conversões"].sum() if "Conversões" in df.columns else 0
total_impr = df["Impr."].sum() if "Impr." in df.columns else 0
total_clicks = df["Cliques"].sum() if "Cliques" in df.columns else 0
ctr_medio = (total_clicks / total_impr * 100) if total_impr > 0 else 0
cpa_medio = (total_invest / total_conv) if total_conv > 0 else 0

# Tabelas
top_conv = df.sort_values("Conversões", ascending=False).head(10) if "Conversões" in df.columns else df.head(10)
top_ctr = df[df["Impr."] >= 50000].sort_values("CTR", ascending=False).head(10) if "CTR" in df.columns and "Impr." in df.columns else df.head(10)
high_cpa = df[df["Conversões"] >= 100].sort_values("Custo / conv.", ascending=False).head(10) if "Conversões" in df.columns and "Custo / conv." in df.columns else df.head(10)

html = f"""
<!DOCTYPE html>
<html lang=\"pt-BR\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Análise de Criativos Google Ads - PBB-FEV-26</title>
    <link rel=\"icon\" type=\"image/png\" href=\"../../img/favicon-brabo-concursos.png\">
    {css()}
</head>
<body>
    <div class=\"container\">
        <div class=\"header\">
            <a href=\"INDEX_[PBB-FEV-26].html\">
                <img src=\"../../img/logo-brabo-concursos.png\" alt=\"Brabo Concursos\">
            </a>
            <div>
                <h1>Análise de Criativos Google Ads</h1>
                <p>Campanha PBB-FEV-26</p>
                <p>Atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
            </div>
        </div>

        <div class=\"content\">
            <span class=\"badge\">Fonte: Performance dos anúncios (Google Ads)</span>
            <h2 class=\"section-title\">Resumo Executivo</h2>
            <div class=\"metric-grid\">
                <div class=\"metric-box\"><div class=\"metric-value\">{fmt_money(total_invest)}</div><div class=\"metric-label\">Investimento Total</div></div>
                <div class=\"metric-box\"><div class=\"metric-value\">{fmt_int(total_conv)}</div><div class=\"metric-label\">Conversões</div></div>
                <div class=\"metric-box\"><div class=\"metric-value\">{fmt_int(total_impr)}</div><div class=\"metric-label\">Impressões</div></div>
                <div class=\"metric-box\"><div class=\"metric-value\">{fmt_int(total_clicks)}</div><div class=\"metric-label\">Cliques</div></div>
                <div class=\"metric-box\"><div class=\"metric-value\">{fmt_pct(ctr_medio)}</div><div class=\"metric-label\">CTR Médio</div></div>
                <div class=\"metric-box\"><div class=\"metric-value\">{fmt_money(cpa_medio)}</div><div class=\"metric-label\">CPA Médio</div></div>
            </div>

            <h2 class=\"section-title\">Top 10 Criativos por Conversões</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Campanha</th>
                        <th>Grupo</th>
                        <th>Cliques</th>
                        <th>Impressões</th>
                        <th>CTR</th>
                        <th>Custo</th>
                        <th>Conversões</th>
                        <th>CPA</th>
                    </tr>
                </thead>
                <tbody>
"""

for _, r in top_conv.iterrows():
    html += f"""
                    <tr>
                        <td>{str(r.get('Nome do anúncio', '(sem nome)'))[:80]}</td>
                        <td>{str(r.get('Campanha', '(sem campanha)'))[:70]}</td>
                        <td>{str(r.get('Grupo de anúncios', '(sem grupo)'))[:70]}</td>
                        <td>{fmt_int(r.get('Cliques', 0))}</td>
                        <td>{fmt_int(r.get('Impr.', 0))}</td>
                        <td>{fmt_pct(r.get('CTR', 0))}</td>
                        <td>{fmt_money(r.get('Custo', 0))}</td>
                        <td>{fmt_int(r.get('Conversões', 0))}</td>
                        <td>{fmt_money(r.get('Custo / conv.', 0))}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>

            <h2 class=\"section-title\">Top CTR (mín. 50.000 impressões)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Campanha</th>
                        <th>CTR</th>
                        <th>Impressões</th>
                        <th>Conversões</th>
                        <th>CPA</th>
                    </tr>
                </thead>
                <tbody>
"""

for _, r in top_ctr.iterrows():
    html += f"""
                    <tr>
                        <td>{str(r.get('Nome do anúncio', '(sem nome)'))[:90]}</td>
                        <td>{str(r.get('Campanha', '(sem campanha)'))[:80]}</td>
                        <td>{fmt_pct(r.get('CTR', 0))}</td>
                        <td>{fmt_int(r.get('Impr.', 0))}</td>
                        <td>{fmt_int(r.get('Conversões', 0))}</td>
                        <td>{fmt_money(r.get('Custo / conv.', 0))}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>

            <h2 class=\"section-title\">Maior CPA (mín. 100 conversões)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Criativo</th>
                        <th>Campanha</th>
                        <th>Custo</th>
                        <th>Conversões</th>
                        <th>CPA</th>
                        <th>CTR</th>
                    </tr>
                </thead>
                <tbody>
"""

for _, r in high_cpa.iterrows():
    html += f"""
                    <tr>
                        <td>{str(r.get('Nome do anúncio', '(sem nome)'))[:90]}</td>
                        <td>{str(r.get('Campanha', '(sem campanha)'))[:80]}</td>
                        <td>{fmt_money(r.get('Custo', 0))}</td>
                        <td>{fmt_int(r.get('Conversões', 0))}</td>
                        <td>{fmt_money(r.get('Custo / conv.', 0))}</td>
                        <td>{fmt_pct(r.get('CTR', 0))}</td>
                    </tr>
"""

html += f"""
                </tbody>
            </table>

            <div class=\"footer\">
                <p>Relatório consolidado | Brabo Concursos</p>
                <p><a href=\"INDEX_[PBB-FEV-26].html\" style=\"color: #4285f4; text-decoration: none; font-weight: bold;\">← Voltar para INDEX</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

OUT_HTML.write_text(html, encoding="utf-8")
print(f"Relatorio gerado: {OUT_HTML}")
print(f"  Linhas lidas: {len(df)}")
print(f"  Investimento: {fmt_money(total_invest)} | Conversoes: {fmt_int(total_conv)}")
