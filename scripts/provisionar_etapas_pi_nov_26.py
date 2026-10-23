"""Provisiona launch_config.etapas do PI-NOV-26 (23/10/26).

Sem `etapas`, o alerta diário de orçamento (etl/budget_alert.py) PULA o lançamento em silêncio — foi por isso
que o PI-NOV-26 nunca apareceu no Slack enquanto PES-NOV-26 e BV-26 apareciam.

Fonte dos números: docs/performance/lancamentos/PI-NOV-26/ORCAMENTO_PI-NOV-26.md (fonte única, revisão de
19/10/26: total R$ 1.000.000, mesmos % por etapa do PI-AGO-26). A estrutura (buckets, curva da captação) é a do
`launch_config.etapas` do PI-AGO-26; as datas das etapas depois da captação andam +98 dias (aulas 10/08 → 16/11).

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
from datetime import date, timedelta
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
DESLOCAMENTO = timedelta(days=98)   # aulas do PI-AGO-26 (10/08) → PI-NOV-26 (16/11)

# total por etapa — ORCAMENTO_PI-NOV-26.md, seção 1, coluna "PI-NOV-26 (19/10)"
TOTAIS = {
    "Pré-Qualificação": 160_000.0, "Captação": 745_000.0, "Lembrete": 3_500.0, "Depoimento": 3_500.0,
    "Aulas no Ar": 5_800.0, "Replay": 3_400.0, "Matrículas Abertas": 6_000.0, "WhatsApp": 72_800.0,
}
# Pré-qualificação: buckets do ORCAMENTO (seção 2, mix 63/37 do PI-AGO-26 após a revisão da diretoria), sem TikTok
PREQUALI_BUCKETS = [
    ("FB Frio", "meta", 93_010.18), ("FB Quente", "meta", 22_934.02), ("FB Específico", "meta", 11_467.01),
    ("YT Frio", "google", 59_863.04), ("YT Quente", "google", 14_965.76),
]
# datas fixas pelo calendário revisto em 19/10/26
PREQUALI = ("2026-10-12", "2026-11-13")
CAPTACAO = ("2026-11-02", "2026-11-16")


def _d(txt: str) -> str:
    return (date.fromisoformat(txt) + DESLOCAMENTO).isoformat()


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
            n["start_date"], n["end_date"] = CAPTACAO   # curva por dia da semana e % por público = os do PI-AGO-26
        else:
            n["start_date"], n["end_date"] = _d(n["start_date"]), _d(n["end_date"])
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

    bak = ROOT / "outputs" / f"backup_launch_config_etapas_{CODIGO}_{date.today():%Y%m%d}.json"
    bak.write_text(json.dumps({"lancamento_codigo": CODIGO, "etapas_anteriores": atual}, ensure_ascii=False, indent=1), encoding="utf-8")
    save_launch_config(CODIGO, {"etapas": etapas})   # grava só `etapas`
    print(f"\nGravado. Backup das etapas anteriores em {bak.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
