# -*- coding: utf-8 -*-
"""Verifica hipótese: RI com cobrança=1 * parcelas = valor real da venda."""
import pandas as pd

def moeda(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

hdf = pd.read_csv(r"analises\[PBB-ABR-26]\Vendas\hotmart pbb-abr-26.csv", sep=";", encoding="utf-8")

ri = hdf[hdf["Tipo de cobrança"] == "Recuperador Inteligente"].copy()

print(f"RI total: {len(ri)}")
print("\nDistribuição de 'Quantidade de cobranças' nos RI:")
print(ri["Quantidade de cobranças"].value_counts().sort_index().to_dict())

print("\nDistribuição de 'Quantidade total de parcelas' nos RI:")
print(ri["Quantidade total de parcelas"].value_counts().sort_index().to_dict())

# Filtrar apenas cobranças = 1 (primeira cobrança = nova venda)
ri_novos = ri[ri["Quantidade de cobranças"] == 1].copy()
print(f"\nRI com cobrança = 1 (novas assinaturas): {len(ri_novos)}")

# Calcular valor cheio = parcela * total de parcelas
ri_novos["valor_parcela"] = ri_novos["Faturamento bruto (sem impostos)"]
ri_novos["valor_cheio"]   = ri_novos["valor_parcela"] * ri_novos["Quantidade total de parcelas"]
ri_novos["liq_parcela"]   = ri_novos["Faturamento líquido do(a) Produtor(a)"]
ri_novos["liq_cheio"]     = ri_novos["liq_parcela"] * ri_novos["Quantidade total de parcelas"]

print(f"\nAmostra dos valores:")
print(ri_novos[["valor_parcela","Quantidade total de parcelas","valor_cheio","liq_cheio"]].head(10).to_string())

print(f"\nTotal bruto (parcela × qtd parcelas): {moeda(ri_novos['valor_cheio'].sum())}")
print(f"Total líquido (parcela × qtd parcelas): {moeda(ri_novos['liq_cheio'].sum())}")
print(f"Qtd: {len(ri_novos)}")
print(f"Ticket médio bruto: {moeda(ri_novos['valor_cheio'].mean())}")
print(f"Ticket médio líquido: {moeda(ri_novos['liq_cheio'].mean())}")

# Comparar com o gap
gap_liq  = 864_482.62
parc_liq = hdf[hdf["Tipo de cobrança"].str.startswith("Parcelado", na=False)]["Faturamento líquido do(a) Produtor(a)"].sum()
visa_liq = hdf[hdf["Tipo de cobrança"] == "Apenas à vista"]["Faturamento líquido do(a) Produtor(a)"].sum()
tmb_liq  = 279_237.80  # todos os 170 TMB

total_sem_rec = parc_liq + visa_liq + tmb_liq
recorrencia_derivada = gap_liq - total_sem_rec

print(f"\n--- COMPARATIVO ---")
print(f"Recorrência derivada (necessária para fechar R$ 864k): {moeda(recorrencia_derivada)}")
print(f"Recorrência calculada (RI cobrança=1 × parcelas):       {moeda(ri_novos['liq_cheio'].sum())}")
print(f"Diferença: {moeda(abs(recorrencia_derivada - ri_novos['liq_cheio'].sum()))}")
print(f"Bate? {'✅ SIM' if abs(recorrencia_derivada - ri_novos['liq_cheio'].sum()) < 1000 else '❌ NÃO — diferença acima de R$ 1.000'}")

# RI com cobranças > 1
ri_renov = ri[ri["Quantidade de cobranças"] > 1].copy()
print(f"\nRI com cobrança > 1 (renovações — excluir): {len(ri_renov)}")
print(ri_renov["Quantidade de cobranças"].value_counts().to_dict())
