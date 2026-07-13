#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comparação correta - valores já estão em formato correto
"""

import csv
from decimal import Decimal

print("=" * 110)
print("COMPARAÇÃO FINAL: Dados Oficiais vs CSVs")
print("=" * 110)

oficial_valor = Decimal("864482.62")
oficial_vendas = 549

print("\nDADOS OFICIAIS:")
print("-" * 110)
print(f"   Receita Líquida: R$ {oficial_valor:>20,.2f}")
print(f"   Vendas: {oficial_vendas:>33,}")
print(f"   Ticket Médio: R$ {(oficial_valor / oficial_vendas):>18,.2f}")

# ===== HOTMART =====
print("\n\nLENDO HOTMART:")
print("-" * 110)

with open(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    hotmart_bruto = Decimal("0")
    hotmart_liq = Decimal("0")
    hotmart_count = 0
    
    for row in reader:
        hotmart_count += 1
        valor_bruto_str = row['Faturamento bruto (sem impostos)'].strip()
        valor_liq_str = row['Faturamento líquido'].strip()
        
        try:
            hotmart_bruto += Decimal(valor_bruto_str)
            hotmart_liq += Decimal(valor_liq_str)
        except Exception as e:
            print(f"Erro na linha {hotmart_count}: {e}")

print(f"   Total Faturamento Bruto: R$ {hotmart_bruto:>15,.2f} ({hotmart_count:,} vendas)")
print(f"   Total Faturamento Líquido: R$ {hotmart_liq:>14,.2f} ({hotmart_count:,} vendas)")

# ===== TMB =====
print("\n\nLENDO TMB:")
print("-" * 110)

with open(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    tmb_total = Decimal("0")
    tmb_count = 0
    
    for row in reader:
        tmb_count += 1
        valor_str = row['Ticket do pedido'].strip()
        
        try:
            # TMB já usa ponto como decimal - sem conversão necessária
            valor = Decimal(valor_str)
            tmb_total += valor
        except Exception as e:
            print(f"Erro na linha {tmb_count}: {e}")

print(f"   Total Ticket do Pedido: R$ {tmb_total:>16,.2f} ({tmb_count:,} vendas)")

# ===== COMPARAÇÃO =====
print("\n\n" + "=" * 110)
print("RESUMO COMPARATIVO:")
print("=" * 110)

total_bruto = hotmart_bruto + tmb_total
total_liq = hotmart_liq + tmb_total
total_vendas_csv = hotmart_count + tmb_count

diff_bruto = oficial_valor - total_bruto
diff_liq = oficial_valor - total_liq

print(f"\nOPÇÃO 1 - Faturamento Bruto (ATUAL):")
print(f"   Receita: R$ {total_bruto:>24,.2f}")
print(f"   Vendas: {total_vendas_csv:>30,}")
print(f"   Ticket Médio: R$ {(total_bruto / total_vendas_csv):>18,.2f}")
print(f"   Diferença: R$ {diff_bruto:>24,.2f} ({(diff_bruto/oficial_valor*100):>6.1f}%)")

print(f"\nOPÇÃO 2 - Faturamento Líquido:")
print(f"   Receita: R$ {total_liq:>24,.2f}")
print(f"   Vendas: {total_vendas_csv:>30,}")
print(f"   Ticket Médio: R$ {(total_liq / total_vendas_csv):>18,.2f}")
print(f"   Diferença: R$ {diff_liq:>24,.2f} ({(diff_liq/oficial_valor*100):>6.1f}%)")

if abs(float(diff_liq)) < abs(float(diff_bruto)):
    print(f"\n✅ MELHOR: Usar 'Faturamento líquido' (diferença MENOR)")
    print(f"   Recomendação: Atualizar scripts para usar coluna 'Faturamento líquido' do Hotmart")
else:
    print(f"\n✅ MANTER: 'Faturamento bruto' (diferença menor ou similar)")

print("\n" + "=" * 110)
