"""Calcula CPA puro de captacao a partir dos dados ja extraidos da API."""
import sys, io, statistics
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Dados extraidos da API: (conversoes, custo_R$, bidding, lancamento, tipo)
campanhas = [
    # ── Captacao tCPA ──
    (4913, 64941.22, "tCPA",     "PES-MAI-26", "captacao"),
    (4742, 58327.26, "tCPA",     "PES-MAR-26", "captacao"),
    (4726, 57786.74, "tCPA",     "PES-MAR-26", "captacao"),
    (4269, 52647.89, "tCPA",     "PES-MAR-26", "captacao"),
    (3391, 48312.84, "tCPA",     "PES-MAI-26", "captacao"),
    (3141, 26402.29, "tCPA",     "PES-JAN-26", "captacao"),
    (1978, 26005.38, "tCPA",     "PES-JAN-26", "captacao"),
    (1957, 21119.62, "tCPA",     "PES-JAN-26", "captacao"),
    (1822, 18429.09, "tCPA",     "PES-JAN-26", "captacao"),
    (1361, 11716.58, "tCPA",     "PES-JAN-26", "captacao"),
    (1157, 19558.80, "tCPA",     "PES-MAR-26", "captacao"),
    ( 999, 12983.02, "tCPA",     "PES-MAI-26", "captacao"),
    ( 998, 13737.26, "tCPA",     "PES-JAN-26", "captacao"),
    ( 994, 13789.54, "MAX_CONV", "PES-MAI-26", "captacao"),
    ( 908, 12119.79, "tCPA",     "PES-JAN-26", "captacao"),
    ( 889,  8355.95, "tCPA",     "PES-JAN-26", "captacao"),
    ( 760,  9981.17, "tCPA",     "PES-MAR-26", "captacao"),
    ( 756, 12878.79, "tCPA",     "PES-JAN-26", "captacao"),
    ( 697,  8807.89, "tCPA",     "PES-JAN-26", "captacao"),
    ( 623,  7950.74, "tCPA",     "PES-MAR-26", "captacao"),
    ( 576,  9259.85, "tCPA",     "PES-MAI-26", "captacao"),
    ( 500,  8604.84, "tCPA",     "PES-MAI-26", "captacao"),
    ( 491,  7626.79, "tCPA",     "PES-MAI-26", "captacao"),
    ( 487,  7022.79, "tCPA",     "PES-JAN-26", "captacao"),
    ( 463,  7262.57, "tCPA",     "PES-MAI-26", "captacao"),
    ( 434,  4867.83, "tCPA",     "PES-JAN-26", "captacao"),
    ( 433,  7404.89, "tCPA",     "PES-MAI-26", "captacao"),
    ( 432,  3588.47, "tCPA",     "PES-JAN-26", "captacao"),
    ( 430,  4807.07, "tCPA",     "PES-JAN-26", "captacao"),
    ( 408,  6824.87, "tCPA",     "PES-MAI-26", "captacao"),
    ( 381,  6573.83, "tCPA",     "PES-MAI-26", "captacao"),
    ( 347,  5383.59, "tCPA",     "PES-MAI-26", "captacao"),
    ( 342,  3171.22, "tCPA",     "PES-JAN-26", "captacao"),
    ( 240,  3843.40, "tCPA",     "PES-JAN-26", "captacao"),
    ( 194,  2658.56, "tCPA",     "PES-MAR-26", "captacao"),
    ( 157,  2263.56, "tCPA",     "PES-JAN-26", "captacao"),
    (  93,  1680.61, "tCPA",     "PES-MAI-26", "captacao"),
    (  54,  1222.63, "tCPA",     "PES-MAI-26", "captacao"),
    (  12,   195.33, "tCPA",     "PES-MAI-26", "captacao"),
    (   8,   145.05, "tCPA",     "PES-MAI-26", "captacao"),
    # ── Captacao MAX_CONV ──
    (3479, 20570.78, "MAX_CONV", "PES-MAI-26", "captacao"),
    (1018, 13540.30, "MAX_CONV", "PES-MAR-26", "captacao"),
    # ── Pre-quali CPV (ThruPlay - NAO captacao) ──
    ( 326, 46841.11, "CPV",      "PES-JAN-26", "pre_quali"),
    (  95, 71188.64, "CPV",      "PES-MAR-26", "pre_quali"),
    (  66, 60156.06, "CPV",      "PES-MAI-26", "pre_quali"),
    (  56, 18333.84, "CPV",      "PES-JAN-26", "pre_quali"),
    (  30, 11713.54, "CPV",      "PES-JAN-26", "pre_quali"),
    (  20, 31736.11, "CPV",      "PES-MAR-26", "pre_quali"),
    (  25, 16579.38, "CPV",      "PES-SET-26", "pre_quali"),
    (  16, 11039.55, "CPV",      "PES-SET-26", "pre_quali"),
    (   6, 15048.21, "CPV",      "PES-MAI-26", "pre_quali"),
    (   5,  4700.58, "CPV",      "PES-JAN-26", "pre_quali"),
    (   4,  4721.47, "CPV",      "PES-SET-26", "pre_quali"),
    (   4,  7081.22, "CPV",      "PES-SET-26", "pre_quali"),
    # ── Pre-quali tCPA FRIO (campanha de captacao mas da pré-quali) ──
    (1050, 14715.72, "tCPA",     "PES-MAR-26", "pre_quali_tcpa"),
    # ── Lembrete / RMK ──
    ( 774,   960.93, "MAX_CONV", "PES-MAR-26", "lembrete"),
    (   1,   533.55, "CPM",      "PES-JAN-26", "rmk"),
]


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Por lancamento e tipo ─────────────────────────────────────────────────────
por_lt: dict = {}
for conv, cost, _, lancamento, tipo in campanhas:
    k = (lancamento, tipo)
    e = por_lt.setdefault(k, {"conv": 0, "cost": 0})
    e["conv"] += conv
    e["cost"] += cost

print("=" * 80)
print("  CPA POR LANCAMENTO E TIPO DE CAMPANHA")
print("=" * 80)
print(f"  {'LANCAMENTO':<15} {'TIPO':<16} {'CONV':>8} {'GASTO':>14} {'CPA':>12}")
print(f"  {'─'*15} {'─'*16} {'─'*8} {'─'*14} {'─'*12}")
for (lanc, tipo) in sorted(por_lt.keys()):
    d = por_lt[(lanc, tipo)]
    cpa = d["cost"] / d["conv"] if d["conv"] > 0 else 0
    print(f"  {lanc:<15} {tipo:<16} {d['conv']:>8,} {brl(d['cost']):>14} {brl(cpa) if cpa else '—':>12}")

# ── Captacao pura por lancamento ──────────────────────────────────────────────
print()
print("=" * 80)
print("  CPA PURO DE CAPTACAO (somente campanhas de captacao de lead)")
print("  Exclui: pre-quali CPV, lembrete, RMK, PES-SET-26 em andamento")
print("=" * 80)

capt: dict = {}
for conv, cost, _, lancamento, tipo in campanhas:
    if tipo == "captacao" and lancamento != "PES-SET-26":
        e = capt.setdefault(lancamento, {"conv": 0, "cost": 0})
        e["conv"] += conv
        e["cost"] += cost

print(f"\n  {'LANCAMENTO':<15} {'CONV':>8} {'GASTO':>14} {'CPA CAPTACAO':>14}")
print(f"  {'─'*15} {'─'*8} {'─'*14} {'─'*14}")
cpas = []
for lanc in sorted(capt.keys()):
    d = capt[lanc]
    cpa = d["cost"] / d["conv"]
    cpas.append(cpa)
    print(f"  {lanc:<15} {d['conv']:>8,} {brl(d['cost']):>14} {brl(cpa):>14}")

media   = statistics.mean(cpas)
mediana = statistics.median(cpas)

# Comparativo com mistura
print()
print("=" * 80)
print("  IMPACTO DA CONTAMINACAO (captacao pura vs. agregado com pre-quali)")
print("=" * 80)

# Total geral (todas campanhas, excl SET-26)
por_lanc_total: dict = {}
for conv, cost, _, lancamento, tipo in campanhas:
    if lancamento == "PES-SET-26":
        continue
    e = por_lanc_total.setdefault(lancamento, {"conv": 0, "cost": 0})
    e["conv"] += conv
    e["cost"] += cost

print(f"\n  {'LANCAMENTO':<15} {'CPA CAPTACAO':>14} {'CPA TOTAL':>12} {'DIFERENCA':>12}")
print(f"  {'─'*15} {'─'*14} {'─'*12} {'─'*12}")
for lanc in sorted(capt.keys()):
    cpa_capt  = capt[lanc]["cost"]  / capt[lanc]["conv"]
    d_total   = por_lanc_total.get(lanc, {"conv": 0, "cost": 0})
    cpa_total = d_total["cost"] / d_total["conv"] if d_total["conv"] > 0 else 0
    diff = cpa_total - cpa_capt
    print(f"  {lanc:<15} {brl(cpa_capt):>14} {brl(cpa_total):>12} {'+' + brl(diff) if diff > 0 else brl(diff):>12}")

print()
print("=" * 80)
print("  CONCLUSAO: tCPA PARA PES-SET-26 (campanha de captacao)")
print("=" * 80)
print(f"\n  Media captacao pura:   {brl(media)}")
print(f"  Mediana captacao pura: {brl(mediana)}")
print()
print(f"  Conservador  (mediana +15%):  {brl(mediana * 1.15)}  <- inicio da captacao (learning)")
print(f"  Equilibrado  (mediana):        {brl(mediana)}")
print(f"  Agressivo    (mediana -15%):  {brl(mediana * 0.85)}")
print(f"\n  RECOMENDACAO FINAL: iniciar com {brl(mediana * 1.1)} a {brl(mediana * 1.15)}")
print("=" * 80)
