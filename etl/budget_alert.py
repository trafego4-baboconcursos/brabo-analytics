"""
etl/budget_alert.py — Alerta diário de orçamento (planejado x real) via Slack.

Para cada lançamento com etapas provisionadas em launch_config.etapas cuja janela
[start_date, end_date] cobre D-1, consulta Meta Ads e Google Ads AO VIVO (nunca
dado já salvo no banco) pro gasto de D-1, compara com o planejado (curva %/dia x
split de buckets por plataforma) e posta o resultado num webhook do Slack.

Chamado 1x/dia (job cron em etl/scheduler.py, 9h America/Sao_Paulo).

Uso manual (fora do horário de cron):
    python etl/budget_alert.py

Pré-requisitos .env:
    SLACK_BUDGET_WEBHOOK_URL — webhook do Slack pro canal de orçamento
    (mais as credenciais de Meta/Google Ads já usadas pelo ETL normal)
"""
from __future__ import annotations

import os
import sys
import threading
import time as _time
import traceback
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(ROOT_DIR))

load_dotenv(dotenv_path=ROOT_DIR / ".env")

from db import get_engine, get_users_engine  # noqa: E402  (etl/db.py)
from logger import get_logger  # noqa: E402
from etl_meta_ads import fetch_insights  # noqa: E402
from etl_google_ads import fetch_report, fetch_pmax_report  # noqa: E402

from frontend.db_readers.ads_meta import _categorize_campaign as _categorize_meta  # noqa: E402
from frontend.db_readers.ads_google import _categorize_campaign as _categorize_google  # noqa: E402

logger = get_logger("etl.budget_alert")

ETAPAS_PROVISIONADAS = [
    "Pré-Qualificação", "Captação", "Lembrete", "Depoimento",
    "Aulas no Ar", "Replay", "Matrículas Abertas",
]
# Campanhas Performance Max não são uma etapa provisionada — o gasto entra em Captação.
ETAPA_PMAX_REDIRECIONA_PARA = "Captação"

DESVIO_ALERTA_PCT = 10.0

_job_lock = threading.Lock()
_FALHAS_CONSECUTIVAS = 0
_DESABILITADO_ATE = 0.0
_MAX_FALHAS = 5
_PAUSA_HORAS = 6.0


def enviar_slack(mensagem: str) -> None:
    """Envia via Slack Web API (chat.postMessage) usando um Bot Token — o bot
    precisa estar adicionado/convidado no canal de destino."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_BUDGET_CHANNEL")
    if not token or not channel:
        logger.warning("SLACK_BOT_TOKEN/SLACK_BUDGET_CHANNEL não configurados — mensagem não enviada.")
        return
    try:
        import requests
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": channel, "text": mensagem},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            logger.error("Slack recusou o envio do alerta de orçamento: %s", data.get("error"))
            return
        logger.info("Alerta de orçamento enviado ao Slack com sucesso.")
    except Exception as e:
        logger.error("Erro ao enviar alerta de orçamento ao Slack: %s", e)


def _formatar_valor(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _listar_codigos_lancamentos() -> list[str]:
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text("SELECT codigo FROM dim_lancamentos ORDER BY codigo")).fetchall()
        return [r[0] for r in rows]
    except Exception:
        logger.exception("Falha ao listar lançamentos de dim_lancamentos")
        return []


def _ler_launch_config(codigo: str) -> dict:
    try:
        with get_users_engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT etapas, meta_ad_account_ids, google_ad_account_ids "
                    "FROM launch_config WHERE lancamento_codigo = :c"
                ),
                {"c": codigo},
            ).fetchone()
        if not row:
            return {}
        etapas = row[0] or []
        if isinstance(etapas, str):
            import json as _json
            etapas = _json.loads(etapas) if etapas else []
        return {
            "etapas": etapas,
            "meta_ad_account_ids": row[1] or [],
            "google_ad_account_ids": row[2] or [],
        }
    except Exception:
        logger.exception("Falha ao ler launch_config de %s", codigo)
        return {}


def _etapas_ativas(etapas: list[dict], d1: date) -> list[dict]:
    ativas = []
    for et in etapas:
        try:
            ini = date.fromisoformat(et["start_date"])
            fim = date.fromisoformat(et["end_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if ini <= d1 <= fim:
            ativas.append(et)
    return ativas


def _planejado_etapa_dia(etapa: dict, d1: date) -> dict[str, float]:
    """Retorna {"meta": valor_planejado, "google": valor_planejado} pro dia d1."""
    ini = date.fromisoformat(etapa["start_date"])
    fim = date.fromisoformat(etapa["end_date"])
    total_dias = (fim - ini).days + 1
    dia_pos = (d1 - ini).days + 1  # 1-indexado

    total = float(etapa.get("total") or 0)
    if etapa.get("distribuicao") == "personalizada":
        curva = etapa.get("curva_pct") or []
        if 0 < dia_pos <= len(curva):
            pct_dia = float(curva[dia_pos - 1])
        else:
            pct_dia = 0.0
            logger.warning(
                "Etapa %s: dia_pos %d fora da curva_pct (len=%d) — planejado do dia tratado como 0.",
                etapa.get("nome"), dia_pos, len(curva),
            )
    else:
        pct_dia = 100.0 / total_dias if total_dias > 0 else 0.0

    planejado_dia = total * pct_dia / 100.0

    planejado = {"meta": 0.0, "google": 0.0}
    for plataforma in ("meta", "google"):
        pct_plataforma = sum(
            float(b.get("pct") or 0)
            for b in (etapa.get("buckets") or [])
            if b.get("tipo") == "campanha" and b.get("plataforma") == plataforma
        )
        planejado[plataforma] = planejado_dia * pct_plataforma / 100.0
    return planejado


def _gasto_real_meta(account_ids: list[str], d1_str: str) -> dict[str, dict]:
    """Retorna {etapa: {"spend": float, "campanhas": set[str]}}."""
    rows = fetch_insights(d1_str, d1_str, account_ids=account_ids)
    real: dict[str, dict] = {}
    for r in rows:
        etapa, *_ = _categorize_meta(r.get("campaign_name") or "")
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        if etapa not in ETAPAS_PROVISIONADAS:
            continue
        bucket = real.setdefault(etapa, {"spend": 0.0, "campanhas": set()})
        bucket["spend"] += float(r.get("spend") or 0)
        bucket["campanhas"].add(r.get("campaign_name"))
    return real


def _gasto_real_google(customer_ids: list[str], d1_str: str) -> dict[str, dict]:
    """Retorna {etapa: {"spend": float, "campanhas": set[str]}}."""
    rows = fetch_report(d1_str, d1_str, customer_ids=customer_ids)
    rows += fetch_pmax_report(d1_str, d1_str, customer_ids=customer_ids)
    real: dict[str, dict] = {}
    for r in rows:
        camp_name = (r.get("campaign") or {}).get("name") or ""
        etapa, *_ = _categorize_google(camp_name)
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        if etapa not in ETAPAS_PROVISIONADAS:
            continue
        cost = int((r.get("metrics") or {}).get("costMicros", 0)) / 1_000_000
        bucket = real.setdefault(etapa, {"spend": 0.0, "campanhas": set()})
        bucket["spend"] += cost
        bucket["campanhas"].add(camp_name)
    return real


def _formatar_pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _status_orcamento(desvio_pct: float) -> str:
    if desvio_pct > DESVIO_ALERTA_PCT:
        return f"⚠️ Acima do previsto (+{_formatar_pct(desvio_pct)}%)"
    if desvio_pct < -DESVIO_ALERTA_PCT:
        return f"⚠️ Abaixo do previsto ({_formatar_pct(desvio_pct)}%)"
    return "✅ Dentro do previsto"


def rodar_alerta_orcamento() -> None:
    global _FALHAS_CONSECUTIVAS, _DESABILITADO_ATE

    if _DESABILITADO_ATE and _time.time() < _DESABILITADO_ATE:
        restante = int((_DESABILITADO_ATE - _time.time()) / 60)
        logger.warning("Alerta de orçamento pausado pelo circuit breaker por mais %d min.", restante)
        return

    if not _job_lock.acquire(blocking=False):
        logger.warning("Execução anterior do alerta de orçamento ainda em andamento — ciclo ignorado.")
        return

    try:
        d1 = date.today() - timedelta(days=1)
        d1_str = d1.isoformat()
        logger.info("Iniciando alerta de orçamento pro dia %s", d1_str)

        blocos: list[str] = []
        falhas: list[str] = []

        for codigo in _listar_codigos_lancamentos():
            cfg = _ler_launch_config(codigo)
            etapas = cfg.get("etapas") or []
            if not etapas:
                continue
            ativas = _etapas_ativas(etapas, d1)
            if not ativas:
                continue

            try:
                meta_ids = cfg.get("meta_ad_account_ids") or []
                google_ids = cfg.get("google_ad_account_ids") or []
                real_meta = _gasto_real_meta(meta_ids, d1_str) if meta_ids else {}
                real_google = _gasto_real_google(google_ids, d1_str) if google_ids else {}
            except Exception as exc:
                logger.exception("Falha ao consultar APIs de anúncios para %s", codigo)
                falhas.append(f"• *{codigo}*: {exc}")
                continue

            linhas_launch = [f"\n*{codigo}*"]
            for etapa in ativas:
                nome = etapa.get("nome")
                planejado = _planejado_etapa_dia(etapa, d1)
                meta_info = real_meta.get(nome, {"spend": 0.0, "campanhas": set()})
                google_info = real_google.get(nome, {"spend": 0.0, "campanhas": set()})

                plan_total = planejado.get("meta", 0.0) + planejado.get("google", 0.0)
                real_total = meta_info["spend"] + google_info["spend"]
                if plan_total == 0 and real_total == 0:
                    continue

                pct_gasto = (real_total / plan_total * 100) if plan_total else (100.0 if real_total else 0.0)
                desvio = pct_gasto - 100.0
                status = _status_orcamento(desvio) if plan_total else "— sem orçamento previsto pra essa etapa"

                linhas_launch.append(
                    f"\n  *{nome}*\n"
                    f"    Meta: {_formatar_valor(meta_info['spend'])} ({len(meta_info['campanhas'])} campanhas)\n"
                    f"    Google: {_formatar_valor(google_info['spend'])} ({len(google_info['campanhas'])} campanhas)\n"
                    f"    Total: {_formatar_valor(real_total)}\n"
                    f"    Orçamento previsto: {_formatar_valor(plan_total)}\n"
                    f"    % gasto: {_formatar_pct(pct_gasto)}%\n"
                    f"    Status: {status}"
                )
            if len(linhas_launch) > 1:
                blocos.append("\n".join(linhas_launch))

        partes = [f"*Relatório de Orçamento — {d1.strftime('%d/%m/%Y')}*"]
        if falhas:
            partes.append("\n*⚠️ Falhas na consulta (sem números parciais pra esses lançamentos):*\n" + "\n".join(falhas))
        if blocos:
            partes.append("\n".join(blocos))
        else:
            partes.append("\nNenhum lançamento ativo com etapas provisionadas hoje.")

        enviar_slack("\n".join(partes))
        _FALHAS_CONSECUTIVAS = 0
        _DESABILITADO_ATE = 0.0

    except Exception as exc:
        _FALHAS_CONSECUTIVAS += 1
        logger.error("Falha geral no job de alerta de orçamento: %s", exc)
        logger.debug(traceback.format_exc())
        if _FALHAS_CONSECUTIVAS >= _MAX_FALHAS:
            _DESABILITADO_ATE = _time.time() + _PAUSA_HORAS * 3600
            logger.error("Circuit breaker do alerta de orçamento ativado após %d falhas consecutivas.", _MAX_FALHAS)
    finally:
        _job_lock.release()


if __name__ == "__main__":
    rodar_alerta_orcamento()
