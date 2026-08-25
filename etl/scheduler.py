"""
Agendador de ETL — executa as rotinas via APScheduler.
Mantém o banco de dados do Supabase atualizado com duas cargas:
- a cada 30 min, janela móvel de 3 dias (hoje e os 2 anteriores) para conversões;
- 1x/dia (3h40), janela profunda de 14 dias para capturar restatements
  retroativos das plataformas (gasto corrigido dias depois pelo Meta/Google).

Uso:
    python etl/scheduler.py
"""
import sys
import subprocess
import os
import threading
import logging
from functools import partial
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

from budget_alert import rodar_alerta_orcamento

BASE_DIR     = Path(__file__).parent
ORQUESTRADOR = BASE_DIR / "run_all.py"
INTERVALO_MINUTOS = 30

load_dotenv(dotenv_path=BASE_DIR.parent / ".env")

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE = BASE_DIR / "scheduler.log"
logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# ── Lock: impede execuções sobrepostas ────────────────────────────────────────
_job_lock = threading.Lock()

# ── Circuit breaker ────────────────────────────────────────────────────────────
_FALHAS_CONSECUTIVAS: int = 0
_DESABILITADO_ATE: float = 0.0
_MAX_FALHAS: int = 5          # desabilita após 5 falhas seguidas
_PAUSA_HORAS: float = 6.0     # fica pausado por 6 horas


def enviar_alerta_webhook(mensagem: str, erro_detalhado: str = "") -> None:
    webhook_url = os.environ.get("ERROR_WEBHOOK_URL")
    if not webhook_url:
        return
    payload = {
        "content": f"🚨 **Falha no ETL - Brabo Analytics** 🚨\n\n**Mensagem:** {mensagem}",
        "embeds": [
            {
                "title": "Detalhes do Erro",
                "description": f"```\n{erro_detalhado[:1900]}\n```" if erro_detalhado else "Sem logs adicionais.",
                "color": 15158332,
            }
        ],
    }
    try:
        import requests
        r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Alerta de erro enviado via Webhook com sucesso.")
    except Exception as e:
        logger.error("Erro ao disparar webhook de alerta: %s", e)


def rodar_carga(dias_janela: int = 2) -> None:
    global _FALHAS_CONSECUTIVAS, _DESABILITADO_ATE
    import time as _time

    # Circuit breaker: pula ciclos enquanto pausado após muitas falhas
    if _DESABILITADO_ATE and _time.time() < _DESABILITADO_ATE:
        restante = int((_DESABILITADO_ATE - _time.time()) / 60)
        logger.warning("ETL pausado pelo circuit breaker por mais %d min.", restante)
        return

    # Se a execução anterior ainda não terminou, pula este ciclo
    if not _job_lock.acquire(blocking=False):
        logger.warning("ETL anterior ainda em execução — ciclo ignorado para evitar sobreposição.")
        return

    try:
        hoje  = datetime.now()
        inicio = (hoje - timedelta(days=dias_janela)).strftime("%Y-%m-%d")
        fim    = hoje.strftime("%Y-%m-%d")

        logger.info("Iniciando rodada do ETL. Janela de atualização: %s até %s (%d dias)", inicio, fim, dias_janela)

        cmd = [sys.executable, str(ORQUESTRADOR), "--since", inicio, "--until", fim]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")

        if result.returncode == 0:
            logger.info("ETL executado com sucesso.")
            if result.stdout:
                logger.info("Saída do ETL:\n%s", result.stdout.strip())
            _FALHAS_CONSECUTIVAS = 0
            _DESABILITADO_ATE = 0.0
        else:
            _FALHAS_CONSECUTIVAS += 1
            msg_erro = f"Erro ao executar ETL (Código de Saída: {result.returncode}) — falha {_FALHAS_CONSECUTIVAS}/{_MAX_FALHAS}"
            logger.error(msg_erro)
            if result.stderr:
                logger.error("Detalhes do erro:\n%s", result.stderr.strip())
            if _FALHAS_CONSECUTIVAS >= _MAX_FALHAS:
                _DESABILITADO_ATE = _time.time() + _PAUSA_HORAS * 3600
                msg_cb = f"Circuit breaker ativado após {_MAX_FALHAS} falhas consecutivas. ETL pausado por {_PAUSA_HORAS:.0f}h."
                logger.error(msg_cb)
                enviar_alerta_webhook(msg_cb, result.stderr or result.stdout)
            else:
                enviar_alerta_webhook(msg_erro, result.stderr or result.stdout)

    except Exception as exc:
        import traceback
        _FALHAS_CONSECUTIVAS += 1
        msg_erro = f"Falha na execução do subprocesso do ETL: {exc}"
        logger.error(msg_erro)
        enviar_alerta_webhook(msg_erro, traceback.format_exc())
    finally:
        _job_lock.release()


def _on_job_event(event) -> None:
    """Callback do APScheduler para erros e jobs perdidos (misfire)."""
    if event.code == EVENT_JOB_MISSED:
        logger.warning("Job ETL perdeu o horário agendado (misfire); será executado na próxima janela.")
    elif event.code == EVENT_JOB_ERROR:
        logger.error("APScheduler reportou erro no job ETL: %s", event.exception)
        enviar_alerta_webhook("APScheduler reportou erro inesperado no job ETL.", str(event.exception))


def main() -> None:
    logger.info("=====================================================")
    logger.info("  Agendador de ETL Iniciado — Brabo Analytics")
    logger.info("  Frequência: a cada %d minuto(s)", INTERVALO_MINUTOS)
    logger.info("  Log file: %s", LOG_FILE.as_posix())
    logger.info("=====================================================")

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_listener(_on_job_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED)

    # coalesce=True: se perdeu N disparos enquanto ocupado, executa apenas 1 ao desbloquear
    # misfire_grace_time=300: tolera até 5 min de atraso antes de marcar como misfire
    scheduler.add_job(
        rodar_carga,
        trigger="interval",
        minutes=INTERVALO_MINUTOS,
        coalesce=True,
        misfire_grace_time=300,
        id="etl_carga",
        name="ETL Brabo Analytics",
        next_run_time=datetime.now(),  # executa imediatamente ao iniciar
    )

    # Reprocessamento profundo diário (janela de 14 dias), 3h40 da madrugada:
    # captura restatements retroativos das plataformas — ex.: em 07/08/26 o Meta
    # corrigiu o gasto do AD322 dias depois, quando o dia já estava fora da
    # janela móvel curta. O _job_lock garante que não sobrepõe a carga horária.
    scheduler.add_job(
        partial(rodar_carga, dias_janela=14),
        trigger="cron",
        hour=3,
        minute=40,
        coalesce=True,
        misfire_grace_time=3600,
        id="etl_carga_profunda",
        name="ETL janela profunda diária (14 dias)",
    )

    # Alerta de orçamento (planejado x real), 3x/dia — minute=15 propositalmente
    # deslocado do :00/:30 do ETL horário (INTERVALO_MINUTOS) pra evitar as duas
    # rotinas baterem nas mesmas contas do Meta/Google ao mesmo tempo (rate limit).
    scheduler.add_job(
        rodar_alerta_orcamento,
        trigger="cron",
        hour="8,13,21",
        minute=15,
        coalesce=True,
        misfire_grace_time=1800,
        id="alerta_orcamento",
        name="Alerta de Orçamento (8h15/13h15/21h15)",
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Agendador encerrado pelo usuário.")
        scheduler.shutdown(wait=False)
        sys.exit(0)


if __name__ == "__main__":
    main()
