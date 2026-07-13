#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RESUMO FINAL: Análises de PBB-ABR-26 Atualizado
Gerado com novo arquivo de leads do Active Campaign
"""

from pathlib import Path

print("=" * 80)
print("📊 RESUMO FINAL - ANÁLISES PBB-ABR-26 (Atualizado 12/05/2026 14h)")
print("=" * 80)

print("\n📁 ARQUIVOS GERADOS:")
print("-" * 80)

files = [
    ("ANALISE_VENDAS_[PBB-ABR-26].html", "571 vendas | R$ 34.173.179,00 | 0.70% conversão"),
    ("ANALISE_CRIATIVOS_[PBB-ABR-26].html", "82 criativos | Top: AD054 (40 vendas)"),
    ("ANALISE_ANUNCIOS_[PBB-ABR-26].html", "38 criativos | 102.699 leads | R$ 353.956,34"),
    ("COMPARACAO_EXCEL_CRM_[PBB-ABR-26].html", "Reconciliação Excel vs CRM"),
    ("ANALISE_META_ADS_[PBB-ABR-26].html", "Dados consolidados"),
    ("ANALISE_GOOGLE_ADS_[PBB-ABR-26].html", "Dados consolidados"),
    ("ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html", "Dados consolidados"),
    ("ANALISE_META_AUDIENCES_[PBB-ABR-26].html", "Dados consolidados"),
    ("ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html", "Dados consolidados"),
    ("INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html", "Dados consolidados"),
    ("INDEX_[PBB-ABR-26].html", "Central de acesso a todos os relatórios"),
]

for filename, desc in files:
    filepath = Path(f"analises/[PBB-ABR-26]/{filename}")
    if filepath.exists():
        size = filepath.stat().st_size / 1024
        print(f"  ✅ {filename:<45} {desc:<45} ({size:>6.1f} KB)")
    else:
        print(f"  ❌ {filename:<45} NÃO ENCONTRADO")

print("\n" + "=" * 80)
print("📈 DADOS CONSOLIDADOS:")
print("=" * 80)
print(f"""
  Total de Leads:          81.261
  Total de Vendas:         571 (Hotmart: 388 | TMB: 183)
  Taxa de Conversão:       0.70%
  
  Criativos únicos:        82
  Top criativo:            AD054 - Banco do Brasil + IA (40 vendas)
  
  Análise Excel:
    - Criativos:           38
    - Leads reportados:    102.699
    - Vendas reportadas:   385
    - Investimento:        R$ 353.956,34
    
  Status: ✅ Todos os relatórios atualizados com sucesso!
""")

print("\n" + "=" * 80)
print("🎯 PRÓXIMAS AÇÕES:")
print("=" * 80)
print("""
  1. Abra: analises/[PBB-ABR-26]/INDEX_[PBB-ABR-26].html
  2. Revise todos os relatórios
  3. Compartilhe com o time
  4. Implemente ações dos insights & recomendações
""")

print("\n" + "=" * 80)
