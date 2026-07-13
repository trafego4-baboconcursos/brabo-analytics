import pandas as pd

print("\n" + "=" * 100)
print("VERIFICACAO AD093 NAS 3 ANALISES GERADAS")
print("=" * 100)

# Carregar os 3 arquivos
fb = pd.read_csv(r'analises/[PBB-ABR-26]/ANALISE_FACEBOOK_[PBB-ABR-26].csv')
yt = pd.read_csv(r'analises/[PBB-ABR-26]/ANALISE_YOUTUBE_[PBB-ABR-26].csv')
cons = pd.read_csv(r'analises/[PBB-ABR-26]/ANALISE_CONSOLIDADA_[PBB-ABR-26].csv')

print("\n>>> AD093 - FACEBOOK:")
ad93_fb = fb[fb['criativo'] == 'AD093']
if len(ad93_fb) > 0:
    print(f"   Investimento: R$ {ad93_fb['investimento'].sum():,.2f}")
    print(f"   Leads: {int(ad93_fb['leads'].sum()):,}")
    print(f"   Vendas: {int(ad93_fb['vendas'].sum())}")
    print(f"   Faturamento: R$ {ad93_fb['faturamento'].sum():,.2f}")
    print(f"   ROAS: {ad93_fb['roas'].iloc[0]:.2f}x")
else:
    print("   Nao encontrado")

print("\n>>> AD093 - YOUTUBE:")
ad93_yt = yt[yt['criativo'] == 'AD093']
if len(ad93_yt) > 0:
    print(f"   Investimento: R$ {ad93_yt['investimento'].sum():,.2f}")
    print(f"   Leads: {int(ad93_yt['leads'].sum()):,}")
    print(f"   Vendas: {int(ad93_yt['vendas'].sum())}")
    print(f"   Faturamento: R$ {ad93_yt['faturamento'].sum():,.2f}")
    print(f"   ROAS: {ad93_yt['roas'].iloc[0]:.2f}x")
else:
    print("   Nao encontrado")

print("\n>>> AD093 - CONSOLIDADO:")
ad93_cons = cons[cons['criativo'] == 'AD093']
if len(ad93_cons) > 0:
    print(f"   Investimento: R$ {ad93_cons['investimento'].sum():,.2f}")
    print(f"   Leads: {int(ad93_cons['leads'].sum()):,}")
    print(f"   Vendas: {int(ad93_cons['vendas'].sum())}")
    print(f"   Faturamento: R$ {ad93_cons['faturamento'].sum():,.2f}")
    print(f"   ROAS: {ad93_cons['roas'].iloc[0]:.2f}x")
else:
    print("   Nao encontrado")

print("\n" + "=" * 100)
print("RESUMO GERAL:")
print("=" * 100)

print(f"\n>>> FACEBOOK:")
print(f"   Total investido: R$ {fb['investimento'].sum():,.2f}")
print(f"   Total vendas: {int(fb['vendas'].sum())}")
print(f"   Total faturamento: R$ {fb['faturamento'].sum():,.2f}")
print(f"   ROAS medio: {(fb['faturamento'].sum() / fb['investimento'].sum()):.2f}x")
print(f"   Top 5 por vendas:")
for idx, row in fb.nlargest(5, 'vendas').iterrows():
    print(f"      {row['criativo']:10} → {int(row['vendas']):3} vendas | R$ {row['investimento']:9,.2f} | ROAS {row['roas']:.2f}x")

print(f"\n>>> YOUTUBE:")
print(f"   Total investido: R$ {yt['investimento'].sum():,.2f}")
print(f"   Total vendas: {int(yt['vendas'].sum())}")
print(f"   Total faturamento: R$ {yt['faturamento'].sum():,.2f}")
print(f"   ROAS medio: {(yt['faturamento'].sum() / yt['investimento'].sum()):.2f}x")
print(f"   Top 5 por vendas:")
for idx, row in yt.nlargest(5, 'vendas').iterrows():
    print(f"      {row['criativo']:10} → {int(row['vendas']):3} vendas | R$ {row['investimento']:9,.2f} | ROAS {row['roas']:.2f}x")

print(f"\n>>> CONSOLIDADO:")
print(f"   Total investido: R$ {cons['investimento'].sum():,.2f}")
print(f"   Total vendas: {int(cons['vendas'].sum())}")
print(f"   Total faturamento: R$ {cons['faturamento'].sum():,.2f}")
print(f"   ROAS medio: {(cons['faturamento'].sum() / cons['investimento'].sum()):.2f}x")

print("\n" + "=" * 100)
