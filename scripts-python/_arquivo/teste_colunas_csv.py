#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de colunas usando CSV nativo (sem pandas)
"""

import csv
from decimal import Decimal

print("=" * 110)
print("TESTE DE COLUNAS: Qual coluna é mais próxima dos dados oficiais?")
print("=" * 110)

print("\nDADOS OFICIAIS ALVO:")
print("-" * 110)
print(f"   Receita Líquida (Dashboard): R$ 864.482,62")
print(f"   Quantidade de Vendas: 549")

oficial_valor = Decimal("864482.62")

# ===== HOTMART - Faturamento Líquido =====
print("\n📌 Testando: Faturamento líquido (Hotmart) + Ticket do pedido (TMB)")
print("-" * 110)

with open(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    hotmart_liq_total = Decimal("0")
    hotmart_bruto_total = Decimal("0")
    hotmart_count = 0
    
    for row in reader:
        hotmart_count += 1
        try:
            valor_liq = Decimal(row['Faturamento líquido'].replace('.', '').replace(',', '.'))
            hotmart_liq_total += valor_liq
        except:
            pass
        try:
            valor_bruto = Decimal(row['Faturamento bruto (sem impostos)'].replace('.', '').replace(',', '.'))
            hotmart_bruto_total += valor_bruto
        except:
            pass

print(f"   Hotmart - Faturamento líquido: R$ {hotmart_liq_total:>16,.2f} ({hotmart_count:,} vendas)")
print(f"   Hotmart - Faturamento bruto: R$ {hotmart_bruto_total:>17,.2f} ({hotmart_count:,} vendas)")

# ===== TMB =====
with open(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    tmb_total = Decimal("0")
    tmb_count = 0
    
    for row in reader:
        tmb_count += 1
        try:
            valor = Decimal(row['Ticket do pedido'].replace('.', '').replace(',', '.'))
            tmb_total += valor
        except:
            pass

print(f"   TMB - Ticket do pedido: R$ {tmb_total:>25,.2f} ({tmb_count:,} vendas)")

# ===== RESUMO =====
print("\n" + "=" * 110)
print("RESUMO:")
print("-" * 110)

total_liq = hotmart_liq_total + tmb_total
total_bruto = hotmart_bruto_total + tmb_total
total_vendas = hotmart_count + tmb_count

diff_liq = oficial_valor - total_liq
diff_bruto = oficial_valor - total_bruto

print(f"\nOPÇÃO 1 - Faturamento Líquido:")
print(f"   Total: R$ {total_liq:>27,.2f}")
print(f"   Vendas: {total_vendas:>26,}")
print(f"   Ticket Médio: R$ {(total_liq / total_vendas):>18,.2f}")
print(f"   Diferença: R$ {diff_liq:>23,.2f} ({(diff_liq/oficial_valor*100):>5.1f}%)")

print(f"\nOPÇÃO 2 - Faturamento Bruto (ATUAL):")
print(f"   Total: R$ {total_bruto:>27,.2f}")
print(f"   Vendas: {total_vendas:>26,}")
print(f"   Ticket Médio: R$ {(total_bruto / total_vendas):>18,.2f}")
print(f"   Diferença: R$ {diff_bruto:>23,.2f} ({(diff_bruto/oficial_valor*100):>5.1f}%)")

if abs(float(diff_liq)) < abs(float(diff_bruto)):
    print(f"\n✅ MELHOR: Usar 'Faturamento líquido' (diferença menor)")
else:
    print(f"\n✅ MELHOR: Manter 'Faturamento bruto' atual")

print("\n" + "=" * 110)
