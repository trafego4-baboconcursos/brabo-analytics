"""Provisiona launch_config.etapas do PI-NOV-26 (23/10/26).

Sem `etapas`, o alerta diário de orçamento (etl/budget_alert.py) PULA o lançamento em silêncio — foi por isso
que o PI-NOV-26 nunca apareceu no Slack enquanto PES-NOV-26 e BV-26 apareciam.

Fonte dos números: docs/performance/lancamentos/PI-NOV-26/ORCAMENTO_PI-NOV-26.md (fonte única). Revisão de
23/10/26: "Estratégia de Verba" do Murilo (22/10) — etapas, buckets, curva da captação e datas do remarketing. Do `launch_config.etapas` do PI-AGO-26 vem só o molde (ordem das etapas e
buckets das etapas menores).

Uso:
    python scripts/provisionar_etapas_pi_nov_26.py            # simulação: monta, confere a soma e mostra
    python scripts/provisionar_etapas_pi_nov_26.py --gravar   # faz backup da linha e grava só `etapas`
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
logging.disable(logging.CRITICAL)

from sqlalchemy import text  # noqa: E402

from frontend.db import _get_users_engine  # noqa: E402
from frontend.db_readers.launches import save_launch_config  # noqa: E402

CODIGO = "PI-NOV-26"
MOLDE = "PI-AGO-26"

# total por etapa — Estratégia de Verba do Murilo (22/10/26), passos 2 e 3
TOTAIS = {
    "Pré-Qualificação": 160_000.0, "Captação": 740_000.0, "Lembrete": 5_244.0, "Depoimento": 1_348.0,
    "Aulas no Ar": 8_620.0, "Replay": 3_546.0, "Matrículas Abertas": 1_242.0, "WhatsApp": 80_000.0,
}
# Pré-qualificação: 55% Meta (72 frio / 18 quente / 10 específico) · 45% Google (80 frio / 20 quente) — passos 6 e 7
PREQUALI_BUCKETS = [
    ("FB Frio", "meta", 63_360.0), ("FB Quente", "meta", 15_840.0), ("FB Específico", "meta", 8_800.0),
    ("YT Frio", "google", 57_600.0), ("YT Quente", "google", 14_400.0),
]
# Captação: % por público (passo 4, TikTok 0%) e curva = média PI-JUL-25 + PI-JAN-26, último dia 4,5% (passo 11)
CAPTACAO_BUCKETS = [
    ("FB Quente", "meta", 33.0), ("FB Frio", "meta", 7.5), ("FB Específico", "meta", 13.0),
    ("YT Quente", "google", 25.0), ("YT Frio", "google", 3.5), ("YT Específico", "google", 18.0),
]
CAPTACAO_CURVA = [10.99, 9.71, 7.13, 6.59, 7.27, 5.70, 6.02, 8.61, 8.39, 7.24, 5.81, 4.58, 3.78, 3.68, 4.50]
# datas fixas pelo calendário revisto em 19/10/26 e pelas janelas do remarketing do passo 3
PREQUALI = ("2026-10-12", "2026-11-13")
CAPTACAO = ("2026-11-02", "2026-11-16")
DATAS = {"Lembrete": ("2026-11-13", "2026-11-16"), "Depoimento": ("2026-11-16", "2026-11-19"),
         "Aulas no Ar": ("2026-11-16", "2026-11-19"), "Replay": ("2026-11-16", "2026-11-19"),
         "Matrículas Abertas": ("2026-11-16", "2026-11-19"), "WhatsApp": ("2026-11-02", "2026-11-19")}


def montar(molde: list[dict]) -> list[dict]:
    saida = []
    soma_pq = sum(v for _, _, v in PREQUALI_BUCKETS)
    for e in molde:
        n = copy.deepcopy(e)
        nome = n["nome"]
        n["total"] = TOTAIS[nome]
        if nome == "Pré-Qualificação":
            n["start_date"], n["end_date"] = PREQUALI
            n["buckets"] = [{"pct": round(v / soma_pq * 100, 2), "nome": b, "tipo": "campanha", "plataforma": p}
                            for b, p, v in PREQUALI_BUCKETS]
            n["curva_pct"], n["distribuicao"] = [], "uniforme"
        elif nome == "Captação":
            n["start_date"], n["end_date"] = CAPTACAO
            n["buckets"] = [{"pct": pct, "nome": b, "tipo": "campanha", "plataforma": p} for b, p, pct in CAPTACAO_BUCKETS]
            n["curva_pct"], n["distribuicao"] = list(CAPTACAO_CURVA), "personalizada"
        else:
            n["start_date"], n["end_date"] = DATAS[nome]
        saida.append(n)
    return saida


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gravar", action="store_true")
    args = ap.parse_args()

    with _get_users_engine().connect() as conn:
        molde = conn.execute(text("SELECT etapas FROM launch_config WHERE lancamento_codigo=:c"), {"c": MOLDE}).scalar()
        atual = conn.execute(text("SELECT etapas FROM launch_config WHERE lancamento_codigo=:c"), {"c": CODIGO}).scalar()
    molde = json.loads(molde) if isinstance(molde, str) else molde
    atual = json.loads(atual) if isinstance(atual, str) else (atual or [])
    etapas = montar(molde)

    soma = round(sum(e["total"] for e in etapas), 2)
    assert soma == 1_000_000.0, f"soma {soma} != 1.000.000"
    cap = next(e for e in etapas if e["nome"] == "Captação")
    assert round(sum(cap["curva_pct"]), 2) == 100.0, sum(cap["curva_pct"])
    assert round(sum(b["pct"] for b in cap["buckets"]), 2) == 100.0
    pq = next(e for e in etapas if e["nome"] == "Pré-Qualificação")
    assert abs(sum(b["pct"] for b in pq["buckets"]) - 100.0) < 0.05

    print(f"etapas atuais no banco: {len(atual)}")
    for e in etapas:
        print(f"  {e['nome']:20s} R$ {e['total']:>11,.2f}  {e['start_date']} a {e['end_date']}  buckets={len(e['buckets'])}")
    print(f"  {'SOMA':20s} R$ {soma:>11,.2f}")

    if not args.gravar:
        print("\nSimulação: nada foi gravado. Rode com --gravar.")
        return 0

    bak = ROOT / "outputs" / "backups" / f"backup_launch_config_etapas_{CODIGO}_{date.today():%Y%m%d}.json"
    bak.parent.mkdir(parents=True, exist_ok=True)
    bak.write_text(json.dumps({"lancamento_codigo": CODIGO, "etapas_anteriores": atual}, ensure_ascii=False, indent=1), encoding="utf-8")
    save_launch_config(CODIGO, {"etapas": etapas})   # grava só `etapas`
    print(f"\nGravado. Backup das etapas anteriores em {bak.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
