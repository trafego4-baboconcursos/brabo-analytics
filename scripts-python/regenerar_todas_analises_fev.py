#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script master para regenerar todas as analises de PBB-FEV-26.
"""

import subprocess
import sys
from pathlib import Path

BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")

SCRIPTS = [
    ("scripts-python/generate_all_reports_pbb.py", "Pacote principal (index + 8 relatorios)"),
    ("scripts-python/generate_analise_criativos.py", "Analise de criativos"),
    ("scripts-python/generate_analise_vendas_final.py", "Analise de vendas final"),
    ("scripts-python/generate_analise_google_anuncios_fev.py", "Analise Google Anuncios"),
    ("scripts-python/generate_analises_por_plataforma_fev.py", "CSVs por plataforma (Facebook, YouTube, Consolidada)"),
    ("scripts-python/generate_htmls_por_plataforma_fev.py", "HTMLs por plataforma (Facebook, YouTube, Consolidada)"),
    ("scripts-python/generate_analise_typeform_fev.py", "Analise Typeform"),
]

print("=" * 80)
print("REGENERANDO TODAS AS ANALISES - PBB-FEV-26")
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
print("CONCLUIDO: Todas as analises FEV foram regeneradas com sucesso.")
print("=" * 80)
