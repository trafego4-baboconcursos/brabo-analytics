#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RESUMO FINAL - Análises Atualizadas com Dados de Google Ads
PBB-ABR-26 (12/05/2026 14h)
"""

print("=" * 90)
print(" " * 20 + "RESUMO FINAL - ANALISES ATUALIZADAS PBB-ABR-26")
print("=" * 90)

print("""
DADOS DO ACTIVE CAMPAIGN (CRM):
  Total de Leads: 81.261
  Total de Vendas: 571 (Hotmart: 388 | TMB: 183)
  Taxa de Conversao: 0.70%

DADOS DAS PLATAFORMAS (EXCEL):
  
  Facebook Ads:
    - Leads: 59.372
    - Investimento: R$ 151.066,91
    - CPL: R$ 2,54
    
  Google Ads:
    - Conversions: 28.409
    - Investimento: R$ 154.834,78
    - CPL: R$ 5,45
    
  TOTAL PLATAFORMAS:
    - Leads/Conversions: 87.781
    - Investimento: R$ 305.901,69
    - CPL Medio: R$ 3,48

RECONCILIACAO:
  Discrepancia: Excel tem 8% MAIS leads que CRM
  Leads nao rastreados no CRM: 6.520 (da diferenca de 81.261 CRM vs 87.781 Excel)
  
  * Isso significa que ~7,4% dos leads capturados nas plataformas nao estao sendo 
    importados/rastreados no CRM (Active Campaign)

ANALISES GERADAS (11 relatorios):
  OK - ANALISE_VENDAS_[PBB-ABR-26].html (4,6 KB)
  OK - ANALISE_CRIATIVOS_[PBB-ABR-26].html (13,9 KB)
  OK - ANALISE_ANUNCIOS_[PBB-ABR-26].html (23,9 KB)
  OK - COMPARACAO_EXCEL_CRM_[PBB-ABR-26].html (10,2 KB) - ATUALIZADO COM DADOS DE GA
  OK - ANALISE_META_ADS_[PBB-ABR-26].html (6,4 KB)
  OK - ANALISE_GOOGLE_ADS_[PBB-ABR-26].html (6,3 KB)
  OK - ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html (6,3 KB)
  OK - ANALISE_META_AUDIENCES_[PBB-ABR-26].html (6,3 KB)
  OK - ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html (6,3 KB)
  OK - INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html (6,4 KB)
  OK - INDEX_[PBB-ABR-26].html (10,2 KB)

RECOMENDACOES:
  1. Investigar por que 6.520 leads nao estao no CRM
  2. Validar integracao do Active Campaign com Facebook/Google Ads
  3. Revisar leads de Google Ads (maior CPL - R$ 5,45 vs FB - R$ 2,54)
  4. Monitorar top criativo AD054 (40 vendas)
  5. Considerar pausar criativos com baixa performance

ARQUIVOS LOCALIZADOS:
  c:\\Users\\trafe\\OneDrive\\Desktop\\workspace-mmm\\analises\\[PBB-ABR-26]\\
  
PROXIMAS ACOES:
  1. Abra INDEX_[PBB-ABR-26].html
  2. Revise cada relatorio
  3. Compartilhe insights com o time
  4. Implemente melhorias de campanha

""")

print("=" * 90)
print(" " * 25 + "Analise concluida com sucesso!")
print("=" * 90)
