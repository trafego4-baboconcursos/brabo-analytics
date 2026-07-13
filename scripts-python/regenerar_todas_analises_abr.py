#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script master para regenerar todas as analises de PBB-ABR-26.

Ordem de execução (importa - scripts posteriores sobrescrevem os anteriores):
    1. generate_all_reports_pbb_abr  → INDEX, Google Ads, Leads, Audiences, Insights
    2. generate_analise_anuncios_FINAL        → ANALISE_ANUNCIOS (versão correta com CRM)
    3. generate_analise_criativos_FINAL       → ANALISE_CRIATIVOS (versão correta com CRM)
    4. generate_analise_meta_ads_com_investimentos → ANALISE_META_ADS legado (base de dados real)
    5. generate_analises_por_plataforma       → CSVs Facebook/YouTube/Consolidada
    6. generate_htmls_por_plataforma          → HTMLs Facebook/YouTube/Consolidada
    7. generate_analise_ecossistemas_abr      → sobrescreve Meta Ads / Google Ads com versão consolidada
    8. inject_nav_all                         → reinjeta sidebar atualizada
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")

SCRIPTS = [
    ("scripts-python/generate_all_reports_pbb_abr.py",
     "Pacote base (INDEX, Google Ads, Leads, Audiences, Insights)"),
    ("scripts-python/generate_analise_anuncios_FINAL.py",
     "Analise de anuncios/vendas (FINAL - usa dados CRM)"),
    ("scripts-python/generate_analise_criativos_FINAL.py",
     "Analise de criativos (FINAL - usa dados CRM)"),
    ("scripts-python/generate_analise_meta_ads_com_investimentos.py",
     "Meta Ads com investimento e ROAS real"),
    ("scripts-python/generate_analises_por_plataforma.py",
     "Analises por plataforma - CSVs (Facebook / YouTube / Consolidada)"),
    ("scripts-python/generate_htmls_por_plataforma.py",
     "HTMLs por plataforma (Facebook / YouTube / Consolidada)"),
    ("scripts-python/generate_analise_ecossistemas_abr.py",
     "Consolidacao Meta+Facebook e Google+YouTube com comparativo FEV"),
    ("scripts-python/generate_analise_typeform.py",
     "Analise Typeform — confronto pesquisa x leads x vendas"),
    ("scripts-python/inject_nav_all.py",
     "Reinjeta a sidebar consolidada em todos os HTMLs"),
]

print("=" * 80)
print("REGENERANDO TODAS AS ANALISES - PBB-ABR-26")
print("=" * 80)

for script, desc in SCRIPTS:
    full = BASE / script
    if not full.exists():
        print(f"\n[ERRO] Arquivo nao encontrado: {full}")
        sys.exit(1)

    print(f"\n[EXEC] {desc}")
    result = subprocess.run([sys.executable, str(full)], cwd=str(BASE))

    if result.returncode != 0:
        print(f"[FALHA] {script} retornou codigo {result.returncode}")
        sys.exit(result.returncode)
    print("[OK]")

print("\n" + "=" * 80)
print("CONCLUIDO: Todas as analises ABR foram regeneradas com sucesso.")
print("=" * 80)
