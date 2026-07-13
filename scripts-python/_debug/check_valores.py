## AD110 cross-platform confrontation script
import pandas as pd

# Hotmart
df_h = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_h['valor'] = pd.to_numeric(
    df_h['Faturamento bruto (sem impostos)'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

# TMB
df_t = pd.read_csv(r'analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv', sep=';', encoding='utf-8')
df_t = df_t[df_t['Situação'] == 'Efetivado'] if 'Situação' in df_t.columns else df_t
df_t['valor'] = pd.to_numeric(
    df_t['Ticket do pedido'].astype(str).str.replace('.', '').str.replace(',', '.'),
    errors='coerce'
).fillna(0)

print("HOTMART:")
print(f"  Vendas: {len(df_h)}")
print(f"  Valor total: R$ {df_h['valor'].sum():,.2f}")
print(f"  Ticket médio: R$ {df_h['valor'].mean():,.2f}")

print("\nTMB:")
print(f"  Vendas: {len(df_t)}")
print(f"  Valor total: R$ {df_t['valor'].sum():,.2f}")
print(f"  Ticket médio: R$ {df_t['valor'].mean():,.2f}")

print(f"\nTOTAL GERAL: R$ {(df_h['valor'].sum() + df_t['valor'].sum()):,.2f}")
print(f"Total vendas: {len(df_h) + len(df_t)}")
