"""Cadastra os 11 lançamentos de 2025 (PI/PES/PBB) em dim_lancamentos + launch_config.

Origem dos dados (levantados em 22/10/26, ver MUDANCAS_BV-26.md item 319):
  - data_inicio/data_fim = primeiro e último dia com gasto Meta na tag do lançamento (o fim nunca
    antes do fechamento do carrinho);
  - carrinho = semana da live: abre na QUINTA (pico de vendas da Hotmart em todos) e fecha na SEGUNDA;
  - produtos Hotmart = família "360" de cada vertical (em 2025 não existia a "Mentoria Vitalícia").

Uso:
    python scripts/cadastrar_lancamentos_2025.py            # simulação: só mostra
    python scripts/cadastrar_lancamentos_2025.py --gravar   # grava (ignora os que já existem)

Reversão: apagar as linhas de dim_lancamentos e launch_config desses códigos (o script grava a lista
em outputs/backup_cadastro_lancamentos_2025_<data>.json).
"""
from __future__ import annotations

import argparse
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

from frontend.db import _get_engine  # noqa: E402
from frontend.db_readers.launches import create_launch, save_launch_config  # noqa: E402

META_CA2 = ["act_1407542209639031"]
META_BB = ["act_438212624024216", "act_1175937361058463"]
GOOGLE_CA2 = ["6482320788"]
GOOGLE_BB = ["1450466453"]

# vertical -> (projeto em dim_lancamentos, contas Meta, contas Google, produtos Hotmart)
VERTICAIS = {
    "PI":  ("INSS", META_CA2, GOOGLE_CA2, ["3069557", "5441747", "3119689"]),    # INSS 360, Mentoria INSS 360, INSS 360 (Recorrência)
    "PES": ("TJ",   META_CA2, GOOGLE_CA2, ["2636505", "5441627", "2653187"]),    # Escrevente 360, Mentoria Escrevente 360, (Recorrência)
    "PBB": ("BB",   META_BB,  GOOGLE_BB,  ["4689087", "5441803", "4718081"]),    # BB 360, Mentoria BB 360, BB 360 (Recorrência)
}

# código: (primeiro dia com gasto, último dia com gasto, quinta que abre o carrinho, segunda que fecha)
LANCAMENTOS = {
    "PI-JAN-25":  ("2025-01-01", "2025-02-24", "2025-01-16", "2025-01-20"),
    "PES-JAN-25": ("2025-01-01", "2025-01-27", "2025-01-23", "2025-01-27"),
    "PBB-FEV-25": ("2025-01-14", "2025-02-16", "2025-02-13", "2025-02-17"),
    "PES-MAR-25": ("2025-02-17", "2025-03-24", "2025-03-20", "2025-03-24"),
    "PI-ABR-25":  ("2025-03-10", "2025-05-12", "2025-04-10", "2025-04-14"),
    "PBB-MAI-25": ("2025-04-07", "2025-05-08", "2025-05-08", "2025-05-12"),
    "PES-JUN-25": ("2025-05-12", "2025-06-16", "2025-06-12", "2025-06-16"),
    "PI-JUL-25":  ("2025-06-16", "2025-07-21", "2025-07-17", "2025-07-21"),
    "PBB-AGO-25": ("2025-07-14", "2025-08-18", "2025-08-14", "2025-08-18"),
    "PES-AGO-25": ("2025-08-01", "2025-08-25", "2025-08-21", "2025-08-25"),
    "PBB-OUT-25": ("2025-09-04", "2025-10-12", "2025-10-09", "2025-10-13"),
}


def _config(codigo: str, abre: str, fecha: str) -> dict:
    _, meta, google, hotmart = VERTICAIS[codigo.split("-")[0]]
    return {
        "meta_ad_account_ids": meta,
        "google_ad_account_ids": google,
        "filtro_lancamento": codigo,
        "filtro_captacao": "captação",
        "filtro_quente": "quente",
        "filtro_frio": "frio",
        "carrinho_start_date": abre,
        "carrinho_end_date": fecha,
        "abertura_oficial_carrinho": abre,
        "hotmart_produto_ids": hotmart,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gravar", action="store_true")
    args = ap.parse_args()

    periodos = {}
    for cod, (ini, fim, abre, fecha) in LANCAMENTOS.items():   # confere o padrão combinado: quinta → segunda
        assert date.fromisoformat(abre).weekday() == 3, f"{cod}: {abre} não é quinta"
        assert date.fromisoformat(fecha).weekday() == 0, f"{cod}: {fecha} não é segunda"
        assert date.fromisoformat(ini) <= date.fromisoformat(abre) <= date.fromisoformat(fecha), cod
        # o lançamento vai até o carrinho fechar, mesmo que o gasto pare antes (3 do BB param no domingo)
        periodos[cod] = (ini, max(fim, fecha))

    with _get_engine().connect() as conn:
        existentes = {r[0] for r in conn.execute(text("SELECT codigo FROM dim_lancamentos WHERE codigo = ANY(:c)"), {"c": list(LANCAMENTOS)})}

    criados = []
    for cod, (_, _, abre, fecha) in LANCAMENTOS.items():
        ini, fim = periodos[cod]
        projeto = VERTICAIS[cod.split("-")[0]][0]
        if cod in existentes:
            print(f"= {cod}: já existe, pulado")
            continue
        print(f"+ {cod:11s} {projeto:5s} {ini} a {fim} | carrinho qui {abre} -> seg {fecha}")
        if not args.gravar:
            continue
        create_launch(cod, cod, projeto, ini, fim)
        save_launch_config(cod, _config(cod, abre, fecha))   # sincroniza dim com as datas do carrinho...
        with _get_engine().connect() as conn:                 # ...então volta ao período do gasto (combinado)
            conn.execute(text("UPDATE dim_lancamentos SET data_inicio=:i, data_fim=:f, updated_at=NOW() WHERE codigo=:c"),
                         {"i": ini, "f": fim, "c": cod})
            conn.commit()
        criados.append(cod)

    if args.gravar:
        out = ROOT / "outputs" / f"backup_cadastro_lancamentos_2025_{date.today():%Y%m%d}.json"
        out.write_text(json.dumps({"criados": criados}, indent=1), encoding="utf-8")
        print(f"\nGravados: {len(criados)}  (lista em {out.name})")
    else:
        print("\nSimulação: nada foi gravado. Rode com --gravar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
