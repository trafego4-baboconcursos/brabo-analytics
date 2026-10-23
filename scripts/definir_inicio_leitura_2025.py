"""Define launch_config.pre_quali_start_date (= início da leitura de anúncios) dos 11 lançamentos de 2025.

Por quê: a janela de leitura das páginas (`frontend/services/fetch.py::_get_global_start`) usa pre_quali_start_date →
captacao_start_date → evento → carrinho. Os lançamentos de 2025 só tinham a data do carrinho (5 dias), então
/lancamentos mostrava só o gasto desses 5 dias (PES-MAR-25: R$ 9 mil em vez de R$ 615 mil; ROAS 171x).

Grava o primeiro dia de gasto (= dim_lancamentos.data_inicio). Sem data FINAL de pré-quali de propósito: o
Calendário só desenha etapa com início e fim, então não inventa uma pré-quali que não temos como confirmar.
Direto por SQL (não por save_launch_config): aquele caminho encolhe dim_lancamentos.data_fim para o fim do carrinho
e o ETL usa essa janela para atribuir o gasto ao lançamento.

Uso: python scripts/definir_inicio_leitura_2025.py [--gravar]
"""
import argparse, json, logging, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
logging.disable(logging.CRITICAL)
from sqlalchemy import text  # noqa: E402

from frontend.db import _get_engine, _get_users_engine  # noqa: E402

CODIGOS = ["PI-JAN-25", "PES-JAN-25", "PBB-FEV-25", "PES-MAR-25", "PI-ABR-25", "PBB-MAI-25",
           "PES-JUN-25", "PI-JUL-25", "PBB-AGO-25", "PES-AGO-25", "PBB-OUT-25"]

ap = argparse.ArgumentParser()
ap.add_argument("--gravar", action="store_true")
args = ap.parse_args()
with _get_engine().connect() as c:
    ini = {r[0]: str(r[1]) for r in c.execute(text("SELECT codigo, data_inicio FROM dim_lancamentos WHERE codigo = ANY(:c)"), {"c": CODIGOS})}
with _get_users_engine().connect() as u:
    antes = {r[0]: r[1] for r in u.execute(text("SELECT lancamento_codigo, pre_quali_start_date FROM launch_config WHERE lancamento_codigo = ANY(:c)"), {"c": CODIGOS})}
    for cod in CODIGOS:
        print(f"{cod:11s} pre_quali_start_date: {antes.get(cod)} -> {ini[cod]}")
    if args.gravar:
        bak = ROOT / "outputs" / f"backup_pre_quali_start_2025_{date.today():%Y%m%d}.json"
        bak.write_text(json.dumps({k: (str(v) if v else None) for k, v in antes.items()}, indent=1), encoding="utf-8")
        for cod in CODIGOS:
            u.execute(text("UPDATE launch_config SET pre_quali_start_date = :d, updated_at = NOW() WHERE lancamento_codigo = :c"), {"d": ini[cod], "c": cod})
        u.commit()
        print("gravado; backup em", bak.name)
    else:
        print("simulação (use --gravar)")
