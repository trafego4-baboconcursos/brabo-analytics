# -*- coding: utf-8 -*-
"""Calcula receita por método de pagamento para cruzar com dashboard oficial."""
import pandas as pd

def br2f(v):
    if pd.isna(v) or v == "" or v == "--": return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def moeda(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

# ── HOTMART ────────────────────────────────────────────────────────────────────
hdf = pd.read_csv(r"analises\[PBB-ABR-26]\Vendas\hotmart pbb-abr-26.csv", sep=";", encoding="utf-8")

# Colunas de faturamento
col_bruto = "Faturamento bruto (sem impostos)"
col_liq   = "Faturamento líquido do(a) Produtor(a)"

parc   = hdf[hdf["Tipo de cobrança"].str.startswith("Parcelado", na=False)].copy()
visa   = hdf[hdf["Tipo de cobrança"] == "Apenas à vista"].copy()
ri     = hdf[hdf["Tipo de cobrança"] == "Recuperador Inteligente"].copy()

parc12 = parc[parc["Quantidade total de parcelas"] == 12]
outros = parc[parc["Quantidade total de parcelas"] != 12]

# ── TMB ────────────────────────────────────────────────────────────────────────
tdf = pd.read_csv(r"analises\[PBB-ABR-26]\Vendas\tmb pbb-abr-26.csv", sep=";", encoding="utf-8")
tdf["_v"] = tdf["Ticket do pedido"].apply(br2f)
tmb_all   = tdf  # todos os 170 (incluindo cancelados)
tmb_ok    = tdf[tdf["Status Pedido"] == "Em Dia"]

# ── RESULTADOS ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("BREAKDOWN POR MÉTODO DE PAGAMENTO")
print("=" * 60)

OFICIAL_LIQ = 864_482.62
OFICIAL_BRUTO = None  # não informado

rows = []

# Parcelado 12x
rows.append({
    "Método":  "Parcelado em 12x",
    "Qtd":     len(parc12),
    "Bruto":   parc12[col_bruto].sum(),
    "Líquido": parc12[col_liq].sum(),
})
# Outros parcelamentos
rows.append({
    "Método":  "Outros parcelamentos",
    "Qtd":     len(outros),
    "Bruto":   outros[col_bruto].sum(),
    "Líquido": outros[col_liq].sum(),
})
# À vista
rows.append({
    "Método":  "À vista",
    "Qtd":     len(visa),
    "Bruto":   visa[col_bruto].sum(),
    "Líquido": visa[col_liq].sum(),
})
# RI
rows.append({
    "Método":  "RI Hotmart (~R$150/mês) — excluído",
    "Qtd":     len(ri),
    "Bruto":   ri[col_bruto].sum(),
    "Líquido": ri[col_liq].sum(),
})
# TMB todos
rows.append({
    "Método":  "Boleto Parcelado TMB (todos 170)",
    "Qtd":     len(tmb_all),
    "Bruto":   tmb_all["_v"].sum(),
    "Líquido": tmb_all["_v"].sum(),
})
# TMB só Em Dia
rows.append({
    "Método":  "  ↳ TMB apenas Em Dia (167)",
    "Qtd":     len(tmb_ok),
    "Bruto":   tmb_ok["_v"].sum(),
    "Líquido": tmb_ok["_v"].sum(),
})

print(f"\n{'Método':<40} {'Qtd':>5}   {'Bruto':>15}   {'Líquido':>15}")
print("-" * 80)
for r in rows:
    print(f"{r['Método']:<40} {r['Qtd']:>5}   {moeda(r['Bruto']):>15}   {moeda(r['Líquido']):>15}")

# Subtotal sem RI, sem recorrência
sub_qtd  = len(parc12) + len(outros) + len(visa) + len(tmb_all)
sub_brut = parc12[col_bruto].sum() + outros[col_bruto].sum() + visa[col_bruto].sum() + tmb_all["_v"].sum()
sub_liq  = parc12[col_liq].sum() + outros[col_liq].sum() + visa[col_liq].sum() + tmb_all["_v"].sum()

print("-" * 80)
print(f"{'Subtotal (sem Recorrência)':<40} {sub_qtd:>5}   {moeda(sub_brut):>15}   {moeda(sub_liq):>15}")

# Recorrência derivada
rec_qtd  = 549 - sub_qtd
rec_liq  = OFICIAL_LIQ - sub_liq
rec_tick = rec_liq / rec_qtd if rec_qtd > 0 else 0
print(f"{'Recorrência (derivada = oficial - subtotal)':<40} {rec_qtd:>5}   {'?':>15}   {moeda(rec_liq):>15}")
print("=" * 80)
print(f"{'TOTAL OFICIAL':<40} {'549':>5}   {'?':>15}   {moeda(OFICIAL_LIQ):>15}")

print(f"\nTicket médio derivado Recorrência: {moeda(rec_tick)}")
print(f"\nObs: Os {len(ri)} RI (~R$150/mês) NÃO estão incluídos no subtotal acima")
print(f"     (são cobranças mensais de assinatura, não vendas completas)")
