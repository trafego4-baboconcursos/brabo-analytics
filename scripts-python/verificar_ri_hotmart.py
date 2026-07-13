# -*- coding: utf-8 -*-
"""Verificar se os RI do Hotmart são recorrência válida ou retentativas."""
import pandas as pd

hpath = r"analises\[PBB-ABR-26]\Vendas\hotmart pbb-abr-26.csv"
hdf = pd.read_csv(hpath, sep=";", encoding="utf-8")

# Separar os grupos
ri   = hdf[hdf["Tipo de cobrança"] == "Recuperador Inteligente"].copy()
parc = hdf[hdf["Tipo de cobrança"].str.startswith("Parcelado", na=False)].copy()
visa = hdf[hdf["Tipo de cobrança"] == "Apenas à vista"].copy()

print(f"Parcelado: {len(parc)} | RI: {len(ri)} | À vista: {len(visa)}")
print()

# Quantas parcelas cada grupo tem?
print("Parcelado — distribuição de parcelas:")
print(parc["Quantidade total de parcelas"].value_counts().sort_index().to_dict())

print("\nRI — distribuição de parcelas:")
print(ri["Quantidade total de parcelas"].value_counts().sort_index().to_dict())

print("\nÀ vista — distribuição de parcelas:")
print(visa["Quantidade total de parcelas"].value_counts().sort_index().to_dict())

# Método de pagamento por grupo
print("\nMétodo pagamento — Parcelado:")
print(parc["Método de pagamento"].value_counts().to_dict())

print("\nMétodo pagamento — RI:")
print(ri["Método de pagamento"].value_counts().to_dict())

# Transação do Produto Principal — se for recorrência, deve ter valor != None
print("\n'Transação do Produto Principal' — RI:")
print(ri["Transação do Produto Principal"].isna().sum(), "nulos de", len(ri))
print(ri["Transação do Produto Principal"].value_counts().head(5).to_dict())

# Verifica se RI tem "Código de assinante"
print("\n'Código do assinante' — RI não nulos:")
print(ri["Código do assinante"].notna().sum(), "de", len(ri))
print(ri["Código do assinante"].value_counts().head(5).to_dict())

# Verifica clientes únicos por email — RI vs Parcelado overlap?
ri_emails   = set(ri["Email do(a) Comprador(a)"].dropna())
parc_emails = set(parc["Email do(a) Comprador(a)"].dropna())
print(f"\nEmails únicos — RI: {len(ri_emails)} | Parcelado: {len(parc_emails)}")
print(f"Overlap (mesmo email em RI e Parcelado): {len(ri_emails & parc_emails)}")
print(f"RI-only emails: {len(ri_emails - parc_emails)}")

# Canal usado para venda
print("\nCanal usado — RI:")
print(ri["Canal usado para venda"].value_counts().to_dict())
print("\nCanal usado — Parcelado:")
print(parc["Canal usado para venda"].value_counts().to_dict())

# Faturamento dos RI
print(f"\nFaturamento RI: R$ {ri['Faturamento bruto (sem impostos)'].sum():,.2f}")
print(f"Faturamento Parcelado: R$ {parc['Faturamento bruto (sem impostos)'].sum():,.2f}")
print(f"Faturamento À vista: R$ {visa['Faturamento bruto (sem impostos)'].sum():,.2f}")
print(f"Total: R$ {hdf['Faturamento bruto (sem impostos)'].sum():,.2f}")

# Valores individuais RI - são tickets normais ou parcelas mensais?
print("\nValores RI — primeiros 10:")
print(ri["Faturamento bruto (sem impostos)"].head(10).tolist())
print("Ticket médio RI:", round(ri["Faturamento bruto (sem impostos)"].mean(), 2))
print("Ticket médio Parcelado:", round(parc["Faturamento bruto (sem impostos)"].mean(), 2))
