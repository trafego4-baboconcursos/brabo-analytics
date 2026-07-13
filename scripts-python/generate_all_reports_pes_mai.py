#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
import runpy
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")
ANALISES = BASE / "analises" / "[PES-MAI-26]"
CONFIG = BASE / "config" / "launches" / "pes-mai-26.yaml"
LOGO_PATH = "../../img/logo-brabo-concursos.png"
FAVICON_PATH = "../../img/favicon-brabo-concursos.png"


def executar_script(rel_path: str):
    caminho = BASE / rel_path
    print(f"\n>>> Executando {caminho.name}...")
    runpy.run_path(str(caminho), run_name="__main__")


def executar_analise_utm():
    print("\n>>> Executando análise genérica de atribuição UTM...")
    subprocess.run(
        [str(BASE / ".venv" / "Scripts" / "python.exe"), str(BASE / "src" / "run.py"), "--config", str(CONFIG)],
        check=True,
    )


def atualizar_nav_global():
    print("\n>>> Atualizando navegação global dos HTMLs...")
    subprocess.run(
        [str(BASE / ".venv" / "Scripts" / "python.exe"), str(BASE / "scripts-python" / "inject_nav_all.py")],
        check=True,
    )


def ler_csv(path: Path) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()


def resumo_csv(df: pd.DataFrame) -> tuple[str, str]:
    if df.empty:
        return "0", "Sem dados"
    leads = int(df["leads"].sum()) if "leads" in df.columns else 0
    vendas = int(df["vendas"].sum()) if "vendas" in df.columns else 0
    roas = 0.0
    if "investimento" in df.columns and "faturamento" in df.columns and float(df["investimento"].sum()) > 0:
        roas = float(df["faturamento"].sum()) / float(df["investimento"].sum())
    return f"{len(df):,}".replace(",", "."), f"{leads:,} leads | {vendas:,} vendas | ROAS {roas:.2f}x".replace(",", ".")


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
            text-decoration:none;
            color:inherit;
        }

        .card h3 {
            margin-bottom: 10px;
            color:#333;
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

        h2 {
            margin-top: 30px;
            margin-bottom: 15px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
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
        }
    </style>
    """


def gerar_index():
    fb_df = ler_csv(ANALISES / "ANALISE_FACEBOOK_[PES-MAI-26].csv")
    yt_df = ler_csv(ANALISES / "ANALISE_YOUTUBE_[PES-MAI-26].csv")
    cons_df = ler_csv(ANALISES / "ANALISE_CONSOLIDADA_[PES-MAI-26].csv")

    fb_kpi, fb_sub = resumo_csv(fb_df)
    yt_kpi, yt_sub = resumo_csv(yt_df)
    cons_kpi, cons_sub = resumo_csv(cons_df)

    cards = [
        ("Funil Completo", "ANALISE_FUNIL_[PES-MAI-26].html", "Funil", "Leads, compradores e conversão macro", "#2563eb"),
        ("Meta Ads", "ANALISE_META_ADS_[PES-MAI-26].html", "Meta", "Campanhas e conjuntos com maior investimento", "#1877f2"),
        ("Google Ads", "ANALISE_GOOGLE_ADS_[PES-MAI-26].html", "Google", "Campanhas, custo, cliques e conversões", "#db4437"),
        ("Leads Confronto", "ANALISE_LEADS_CONFRONTO_[PES-MAI-26].html", "CRM", "Confronto de leads por plataforma e clima", "#0f766e"),
        ("Meta Audiences", "ANALISE_META_AUDIENCES_[PES-MAI-26].html", "Públicos", "Leitura dos conjuntos de anúncios Meta", "#0891b2"),
        ("Google Audiences", "ANALISE_GOOGLE_AUDIENCES_[PES-MAI-26].html", "Segmentos", "Públicos do Google por custo e cliques", "#f59e0b"),
        ("Criativos", "ANALISE_CRIATIVOS_[PES-MAI-26].html", "Criativos", "Comparativo Meta x Google/YouTube", "#7c3aed"),
        ("Anúncios", "ANALISE_ANUNCIOS_[PES-MAI-26].html", "Ranking", "Top peças por vendas e faturamento", "#e11d48"),
        ("Facebook", "ANALISE_FACEBOOK_[PES-MAI-26].html", fb_kpi, fb_sub, "#1877f2"),
        ("Google / YouTube", "ANALISE_YOUTUBE_[PES-MAI-26].html", yt_kpi, yt_sub, "#db4437"),
        ("Consolidada", "ANALISE_CONSOLIDADA_[PES-MAI-26].html", cons_kpi, cons_sub, "#0f9d58"),
        ("Typeform", "ANALISE_TYPEFORM_[PES-MAI-26].html", "2 pesquisas", "Captação + alunos", "#ab47bc"),
        ("Insights", "INSIGHTS_RECOMENDACOES_[PES-MAI-26].html", "Resumo", "Leituras executivas e próximos focos", "#14b8a6"),
        ("Atribuição UTM", "../../outputs/reports/ANALISE_ATRIBUICAO_UTM_[PES-MAI-26].html", "UTMs", "Leads, receita e ROAS por origem", "#ff8f00"),
    ]

    cards_html = "".join(
        f'''<div class="card">
                <h3>{titulo}</h3>
                <p style="margin-bottom: 12px; color:#555;">{sub}</p>
                <div style="font-weight: bold; margin-bottom: 10px; color:#333;">{kpi}</div>
                <a href="{href}" style="color: #667eea; text-decoration: none; font-weight: bold;">Ver Análise →</a>
            </div>'''
        for titulo, href, kpi, sub, cor in cards
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análises PES-MAI-26</title>
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
                <h1>📊 Campanha PES-MAI-26</h1>
                <p>Projeto Escrevente - Captação</p>
                <p>Período: Maio de 2026</p>
            </div>
        </div>
        <div class="content">
            <h2>📈 Resumo da Campanha</h2>
            <div style="margin: 20px 0;">
                <div class="metric-box">
                    <div class="label">Período</div>
                    <div class="value">Mai/2026</div>
                </div>
                <div class="metric-box">
                    <div class="label">Status</div>
                    <div class="value">Ativo</div>
                </div>
            </div>
            <h2>🎯 Análises Disponíveis</h2>
            <div class="grid">{cards_html}</div>
            <div class="footer">Análises geradas em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Brabo Concursos</div>
        </div>
    </div>
</body>
</html>"""

    output = ANALISES / "INDEX_[PES-MAI-26].html"
    output.write_text(html, encoding="utf-8")
    print(f"\n✓ INDEX gerado: {output}")


def main():
    print("=" * 100)
    print("GERADOR DE RELATORIOS - PES-MAI-26")
    print("=" * 100)
    executar_script("scripts-python/generate_analises_por_plataforma_pes_mai.py")
    executar_script("scripts-python/generate_htmls_por_plataforma_pes_mai_parity.py")
    executar_script("scripts-python/generate_analise_typeform_pes_mai_parity.py")
    executar_script("scripts-python/generate_analise_funil_pes_mai.py")
    executar_script("scripts-python/generate_analise_criativos_pes_mai.py")
    executar_script("scripts-python/generate_all_reports_pes_mai_parity.py")
    executar_analise_utm()
    atualizar_nav_global()
    print("\nConcluido.")


if __name__ == "__main__":
    main()