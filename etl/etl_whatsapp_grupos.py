"""
ETL: Grupos de WhatsApp (SendFlow) → Supabase
    - whatsapp_grupos_diario: 1 snapshot/dia por lançamento+bloco (normal/vip)
      com Total / Total Limpo / Grupos Cheios, mesma regra de contagem do
      sendflow-analytics-poller (o que alimenta o Sheets).

Não mexe no sendflow-analytics-poller nem no Sheets — lê a API da SendFlow
direto, de forma independente (mesmo padrão do etl_instagram.py: "foto" do
dia, não histórico retroativo — a API não devolve estado de dias passados).

Rodado 1x/dia via etl/scheduler.py (perto da meia-noite, pra "Leads no dia"
refletir o fechamento do dia) — não entra no ciclo de 30 min do run_all.py
pra não somar mais uma fonte batendo na SendFlow o dia inteiro (o poller já
consulta os mesmos releases a cada 15-30 min; o token do BB já teve bloqueio
recorrente por excesso de chamadas).

Uso:
    python etl/etl_whatsapp_grupos.py
"""
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from sendflow_grupos import (
    load_config, export_leads, contar_grupos_cheios, contar_numeros,
    tratar_falha_export_leads, RELEASES_BLOQUEADOS,
)
import os

load_dotenv()

logger = get_logger("etl.whatsapp_grupos")


def _contar_bloco(token: str, release_id: str) -> dict | None:
    if release_id in RELEASES_BLOQUEADOS:
        return None
    try:
        leads = export_leads(token, release_id)
    except Exception as e:
        tratar_falha_export_leads(e, release_id, logger)
        return None
    _, numeros_limpo = contar_numeros(leads)
    grupos_cheios = None
    try:
        grupos_cheios = contar_grupos_cheios(token, release_id)
    except Exception:
        logger.exception("falha ao consultar /groups (release %s)", release_id)
    return {"total": len(leads), "total_limpo": len(numeros_limpo), "grupos_cheios": grupos_cheios}


def _upsert(hoje: str, launch_code: str, bloco: str, dados: dict) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO whatsapp_grupos_diario
                    (date, launch_code, bloco, total, total_limpo, grupos_cheios, updated_at)
                VALUES
                    (:date, :launch_code, :bloco, :total, :total_limpo, :grupos_cheios, NOW())
                ON CONFLICT (date, launch_code, bloco) DO UPDATE SET
                    total = EXCLUDED.total,
                    total_limpo = EXCLUDED.total_limpo,
                    grupos_cheios = COALESCE(EXCLUDED.grupos_cheios, whatsapp_grupos_diario.grupos_cheios),
                    updated_at = NOW()
            """),
            {"date": hoje, "launch_code": launch_code, "bloco": bloco, **dados},
        )


def main() -> None:
    cfg = load_config()
    if not cfg:
        logger.warning("config/sendflow_contagem.yaml vazio ou não encontrado — nada a fazer.")
        return

    hoje = date.today().isoformat()
    erros = []
    primeira = True
    for launch_code, blocos in cfg.items():
        for bloco, info in blocos.items():
            if not primeira:
                time.sleep(1.5)  # espaça chamadas — mesmo cuidado de rate limit do sendflow_contagem.py
            primeira = False

            token = os.environ.get(info["token_env"])
            if not token:
                logger.warning("env var %s não configurada — pulando %s/%s", info["token_env"], launch_code, bloco)
                continue

            dados = _contar_bloco(token, info["release_id"])
            if dados is None:
                erros.append(f"{launch_code}/{bloco}")
                continue

            _upsert(hoje, launch_code, bloco, dados)
            logger.info(
                "%s/%s: total=%s total_limpo=%s grupos_cheios=%s",
                launch_code, bloco, dados["total"], dados["total_limpo"], dados["grupos_cheios"],
            )

    if erros:
        logger.warning("Falhas nesta rodada (mantido o valor anterior no banco): %s", ", ".join(erros))


if __name__ == "__main__":
    main()
