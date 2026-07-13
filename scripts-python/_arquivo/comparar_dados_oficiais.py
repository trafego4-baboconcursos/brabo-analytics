#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPARAÇÃO: Dados Oficiais vs Dados CSV Reais
Objetivo: Validar os dados de vendas e identificar discrepâncias
"""

import pandas as pd
from datetime import datetime

print("=" * 110)
print("COMPARAÇÃO: DADOS OFICIAIS vs DADOS CSV REAIS - PBB-ABR-26")
print("=" * 110)

# ===== DADOS OFICIAIS (da imagem/dashboard) =====
print("\n1. DADOS OFICIAIS (Dashboard/Sistema Oficial):")
print("-" * 110)

dados_oficiais = {
    'receita_liquida': 864482.62,
    'roas': 2.15,
    'qtd_vendas': 549,
    'ticket_medio': 1574.65,
    'investimento': 401447.92,
    'lucro': 463034.70,
    'data_ultima_venda': '27/04/2026 13:58:55'
}

print(f"   Receita Líquida: R$ {dados_oficiais['receita_liquida']:>16,.2f}")
print(f"   ROAS: {dados_oficiais['roas']:>25,.2f}x")
print(f"   Quantidade de Vendas: {dados_oficiais['qtd_vendas']:>13,}")
print(f"   Ticket Médio: R$ {dados_oficiais['ticket_medio']:>18,.2f}")
print(f"   Investimento: R$ {dados_oficiais['investimento']:>17,.2f}")
print(f"   Lucro: R$ {dados_oficiais['lucro']:>26,.2f}")
print(f"   Última Venda: {dados_oficiais['data_ultima_venda']:>28}")

# ===== DADOS CSV REAIS =====
print("\n2. DADOS CSV REAIS (Arquivos Locais):")
print("-" * 110)

df_hotmart = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8', quoting=1, low_memory=False)
df_tmb = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8', quoting=1, low_memory=False)

# Cálculos dos dados CSV
hotmart_vendas = len(df_hotmart)
hotmart_valor = df_hotmart['Faturamento bruto (sem impostos)'].sum()

tmb_vendas = len(df_tmb)
tmb_valor = df_tmb['Ticket do pedido'].sum()

total_vendas_csv = hotmart_vendas + tmb_vendas
total_valor_csv = hotmart_valor + tmb_valor
ticket_medio_csv = total_valor_csv / total_vendas_csv if total_vendas_csv > 0 else 0

print(f"\n   Hotmart:")
print(f"      Vendas: {hotmart_vendas:>25,}")
print(f"      Valor Total: R$ {hotmart_valor:>17,.2f}")

print(f"\n   TMB:")
print(f"      Vendas: {tmb_vendas:>25,}")
print(f"      Valor Total: R$ {tmb_valor:>17,.2f}")

print(f"\n   TOTAL CSV:")
print(f"      Vendas: {total_vendas_csv:>25,}")
print(f"      Valor Total: R$ {total_valor_csv:>17,.2f}")
print(f"      Ticket Médio: R$ {ticket_medio_csv:>18,.2f}")

# ===== ANÁLISE DE DISCREPÂNCIAS =====
print("\n3. ANÁLISE DE DISCREPÂNCIAS:")
print("-" * 110)

gap_vendas = dados_oficiais['qtd_vendas'] - total_vendas_csv
gap_vendas_pct = (gap_vendas / dados_oficiais['qtd_vendas']) * 100 if dados_oficiais['qtd_vendas'] > 0 else 0

gap_valor = dados_oficiais['receita_liquida'] - total_valor_csv
gap_valor_pct = (gap_valor / dados_oficiais['receita_liquida']) * 100 if dados_oficiais['receita_liquida'] > 0 else 0

gap_ticket = dados_oficiais['ticket_medio'] - ticket_medio_csv
gap_ticket_pct = (gap_ticket / dados_oficiais['ticket_medio']) * 100 if dados_oficiais['ticket_medio'] > 0 else 0

print(f"\n   Quantidade de Vendas:")
print(f"      Oficial: {dados_oficiais['qtd_vendas']:>25,}")
print(f"      CSV: {total_vendas_csv:>28,}")
print(f"      GAP: {gap_vendas:>31,} ({gap_vendas_pct:>5.1f}%)")

print(f"\n   Valor Total (Receita):")
print(f"      Oficial: R$ {dados_oficiais['receita_liquida']:>20,.2f}")
print(f"      CSV: R$ {total_valor_csv:>24,.2f}")
print(f"      GAP: R$ {gap_valor:>29,.2f} ({gap_valor_pct:>5.1f}%)")

print(f"\n   Ticket Médio:")
print(f"      Oficial: R$ {dados_oficiais['ticket_medio']:>20,.2f}")
print(f"      CSV: R$ {ticket_medio_csv:>24,.2f}")
print(f"      GAP: R$ {gap_ticket:>29,.2f} ({gap_ticket_pct:>5.1f}%)")

# ===== INVESTIGAÇÃO =====
print("\n4. INVESTIGAÇÃO - POSSÍVEIS CAUSAS:")
print("-" * 110)

if gap_vendas > 0:
    print(f"\n   ❌ FALTAM {gap_vendas} VENDAS NOS ARQUIVOS CSV")
    print(f"      - Verificar se há vendas em plataformas adicionais não listadas")
    print(f"      - Comparar datas: arquivo CSV pode estar incompleto (vai até {df_hotmart['Data da Compra'].max() if 'Data da Compra' in df_hotmart.columns else 'data desconhecida'})")
    print(f"      - Verificar se há filtros aplicados no CSV que estão excluindo vendas")

if gap_valor > 0:
    print(f"\n   ❌ FALTAM R$ {gap_valor:,.2f} EM VALORES NOS ARQUIVOS CSV")
    print(f"      - Valor adicional por venda faltante: R$ {gap_valor/max(gap_vendas, 1):,.2f}")
    print(f"      - Pode haver desconto/taxa aplicada nos arquivos CSV que não reflete a receita oficial")
    print(f"      - Verificar se o 'Faturamento bruto (sem impostos)' é realmente a receita líquida")

# ===== PRÓXIMOS PASSOS =====
print("\n5. RECOMENDAÇÕES:")
print("-" * 110)
print(f"""
   1. LOCALIZAR VENDAS FALTANTES ({gap_vendas} vendas = R$ {gap_valor/max(gap_vendas, 1):,.2f} cada):
      a) Verificar se há arquivo Vendas/tmb-pbb-abr-26.csv completo
      b) Buscar vendas em outros períodos (antes/depois da data do arquivo)
      c) Conferir se há vendas de outras plataformas não mapeadas

   2. VALIDAR COLUNAS DE VALOR:
      a) Hotmart: Coluna '{df_hotmart.columns.tolist()}' é receita LÍQUIDA ou BRUTA?
      b) TMB: Coluna '{df_tmb.columns.tolist()}' inclui impostos/taxas?
      c) Dashboard oficial usa 'Receita Líquida' - verificar se CSVs estão alinhados

   3. COMPARAÇÃO GRANULAR:
      a) Plotar vendas por dia para ambas as fontes
      b) Identificar qual período tem discrepância
      c) Verificar se há vendas com valor zero ou nulo

   4. PRÓXIMAS AÇÕES:
      a) Solicitar export completo e oficial das vendas
      b) Verificar se há vendas em sistemas adicionais (Shopify, Stripe, etc)
      c) Confirmar data de início/fim do período de análise

""")

print("=" * 110)
print(f"Análise gerada em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")
print("=" * 110)
