#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de colunas de valor - qual se aproxima dos dados oficiais?
"""

import pandas as pd

print("=" * 110)
print("TESTE DE COLUNAS: Qual é a coluna correta para Receita Líquida?")
print("=" * 110)

print("\nDADOS OFICIAIS ALVO:")
print("-" * 110)
print(f"   Receita Líquida (Dashboard): R$ 864.482,62")
print(f"   Quantidade de Vendas: 549")
print(f"   Ticket Médio: R$ 1.574,65")

print("\n\nTESTANDO COLUNAS:")
print("-" * 110)

df_hotmart = pd.read_csv(
    r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', 
    sep=';', encoding='utf-8', quoting=1, low_memory=False
)

df_tmb = pd.read_csv(
    r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', 
    sep=';', encoding='utf-8', quoting=1, low_memory=False
)

# Teste 1: Usando "Faturamento líquido" (Hotmart) + "Ticket do pedido" (TMB)
print("\n📌 OPÇÃO 1: Faturamento líquido (Hotmart) + Ticket do pedido (TMB)")
print("-" * 110)

hotmart_liq = df_hotmart['Faturamento líquido'].sum()
tmb_valor = df_tmb['Ticket do pedido'].sum()
total_opt1 = hotmart_liq + tmb_valor

hotmart_vendas = len(df_hotmart)
tmb_vendas = len(df_tmb)
total_vendas_opt1 = hotmart_vendas + tmb_vendas

ticket_opt1 = total_opt1 / total_vendas_opt1

diff_opt1 = 864482.62 - total_opt1
diff_opt1_pct = (diff_opt1 / 864482.62) * 100

print(f"   Hotmart (Faturamento líquido): R$ {hotmart_liq:>16,.2f} ({hotmart_vendas:,} vendas)")
print(f"   TMB (Ticket do pedido): R$ {tmb_valor:>21,.2f} ({tmb_vendas:,} vendas)")
print(f"   ─────────────────────────────────────────────────────")
print(f"   TOTAL: R$ {total_opt1:>27,.2f}")
print(f"   Vendas: {total_vendas_opt1:,}")
print(f"   Ticket Médio: R$ {ticket_opt1:>18,.2f}")
print(f"   ✓ Diferença do Oficial: R$ {diff_opt1:,.2f} ({diff_opt1_pct:.1f}%)")

# Teste 2: Usando "Faturamento bruto (sem impostos)" + Ticket do pedido
print("\n📌 OPÇÃO 2: Faturamento bruto (Hotmart) + Ticket do pedido (TMB) [ATUAL]")
print("-" * 110)

hotmart_bruto = df_hotmart['Faturamento bruto (sem impostos)'].sum()
total_opt2 = hotmart_bruto + tmb_valor
ticket_opt2 = total_opt2 / total_vendas_opt1

diff_opt2 = 864482.62 - total_opt2
diff_opt2_pct = (diff_opt2 / 864482.62) * 100

print(f"   Hotmart (Faturamento bruto): R$ {hotmart_bruto:>17,.2f} ({hotmart_vendas:,} vendas)")
print(f"   TMB (Ticket do pedido): R$ {tmb_valor:>21,.2f} ({tmb_vendas:,} vendas)")
print(f"   ─────────────────────────────────────────────────────")
print(f"   TOTAL: R$ {total_opt2:>27,.2f}")
print(f"   Vendas: {total_vendas_opt1:,}")
print(f"   Ticket Médio: R$ {ticket_opt2:>18,.2f}")
print(f"   ✗ Diferença do Oficial: R$ {diff_opt2:,.2f} ({diff_opt2_pct:.1f}%)")

# Análise de qual é melhor
print("\n\n📊 COMPARAÇÃO:")
print("-" * 110)

if abs(diff_opt1) < abs(diff_opt2):
    print(f"✅ OPÇÃO 1 É MAIS PRECISA: {abs(diff_opt1):.0f} vs {abs(diff_opt2):.0f}")
    print(f"\n➜ Use: 'Faturamento líquido' do Hotmart em vez de 'Faturamento bruto'")
else:
    print(f"✅ OPÇÃO 2 É MAIS PRECISA: {abs(diff_opt2):.0f} vs {abs(diff_opt1):.0f}")
    print(f"\n➜ Manter: 'Faturamento bruto' (atual)")

print("\n" + "=" * 110)
