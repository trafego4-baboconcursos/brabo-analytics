"""
etl/budget_alert.py — Alerta de orçamento (planejado x real) via Slack.

Para cada lançamento com etapas provisionadas em launch_config.etapas, consulta
Meta Ads e Google Ads AO VIVO (nunca dado já salvo no banco) pro status das
campanhas e pro gasto de HOJE até o momento da execução, compara com o
planejado (curva %/dia x split de buckets por plataforma) e posta no Slack.

Uma etapa só aparece no relatório diário enquanto tiver pelo menos uma
campanha ATIVA na plataforma. Quando todas as campanhas de uma etapa saem do
ar (pausadas/encerradas) de uma execução pra outra, sai um relatório de
FECHAMENTO uma única vez (gasto total acumulado do início da etapa até então)
e ela some do relatório diário até ser reativada de verdade na plataforma.
No dia de fechamento do carrinho (carrinho_end_date), sai também um resumo
completo com o gasto total de TODAS as etapas, ativas ou não.

Chamado 3x/dia (job cron em etl/scheduler.py, 8h/13h/21h America/Sao_Paulo).

Uso manual (fora do horário de cron):
    python etl/budget_alert.py

Pré-requisitos .env:
    SLACK_BOT_TOKEN, SLACK_BUDGET_CHANNEL — bot já convidado no canal
    (mais as credenciais de Meta/Google Ads já usadas pelo ETL normal)
"""
from __future__ import annotations

import json as _json
import os
import sys
import threading
import time as _time
import traceback
from datetime import date
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
from etl_meta_ads import fetch_insights, fetch_campaign_status as fetch_meta_status, extract_launch_code as extract_launch_code_meta  # noqa: E402
from etl_google_ads import fetch_report, fetch_pmax_report, fetch_campaign_status as fetch_google_status, extract_launch_code as extract_launch_code_google  # noqa: E402

from frontend.db_readers.ads_meta import _categorize_campaign as _categorize_meta  # noqa: E402
from frontend.db_readers.ads_google import _categorize_campaign as _categorize_google  # noqa: E402

logger = get_logger("etl.budget_alert")

ETAPAS_PROVISIONADAS_PADRAO = [
    "Pré-Qualificação", "Captação", "Lembrete", "Depoimento",
    "Aulas no Ar", "Replay", "Matrículas Abertas",
]
# Campanhas Performance Max não são uma etapa provisionada — o gasto entra em Captação.
ETAPA_PMAX_REDIRECIONA_PARA = "Captação"

DESVIO_ALERTA_PCT = 10.0
STATUS_ATIVO_META = {"ACTIVE"}
STATUS_ATIVO_GOOGLE = {"ENABLED"}

STATE_FILE = BASE_DIR / "budget_alert_state.json"

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


def _formatar_pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _formatar_data_br(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or ""


def _status_orcamento(desvio_pct: float) -> str:
    if desvio_pct > DESVIO_ALERTA_PCT:
        return f"⚠️ Acima do previsto (+{_formatar_pct(desvio_pct)}%)"
    if desvio_pct < -DESVIO_ALERTA_PCT:
        return f"⚠️ Abaixo do previsto ({_formatar_pct(desvio_pct)}%)"
    return "✅ Dentro do previsto"


def _load_state() -> dict:
    try:
        return _json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(_json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        logger.exception("Falha ao gravar %s", STATE_FILE)


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
                    "SELECT etapas, meta_ad_account_ids, google_ad_account_ids, carrinho_end_date "
                    "FROM launch_config WHERE lancamento_codigo = :c"
                ),
                {"c": codigo},
            ).fetchone()
        if not row:
            return {}
        etapas = row[0] or []
        if isinstance(etapas, str):
            etapas = _json.loads(etapas) if etapas else []
        return {
            "etapas": etapas,
            "meta_ad_account_ids": row[1] or [],
            "google_ad_account_ids": row[2] or [],
            "carrinho_end_date": str(row[3]) if row[3] else None,
        }
    except Exception:
        logger.exception("Falha ao ler launch_config de %s", codigo)
        return {}


def _planejado_etapa_dia(etapa: dict, hoje: date) -> dict[str, float]:
    """Retorna {"meta": valor_planejado, "google": valor_planejado} pro dia de hoje."""
    ini = date.fromisoformat(etapa["start_date"])
    fim = date.fromisoformat(etapa["end_date"])
    total_dias = (fim - ini).days + 1
    dia_pos = (hoje - ini).days + 1  # 1-indexado

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


def _previsto_periodo_midia(etapa: dict) -> float:
    """Total previsto do período inteiro da etapa, só a fatia de mídia (Meta+Google)."""
    total = float(etapa.get("total") or 0)
    pct_midia = sum(
        float(b.get("pct") or 0)
        for b in (etapa.get("buckets") or [])
        if b.get("tipo") == "campanha" and b.get("plataforma") in ("meta", "google")
    )
    return total * pct_midia / 100.0


def _categorizar_gasto(rows_meta: list[dict], rows_google: list[dict], codigo: str) -> dict[str, dict]:
    """Soma spend/campanhas por etapa (Meta e Google separados), filtrando pelo código do lançamento."""
    real: dict[str, dict] = {}

    def _bucket(etapa):
        return real.setdefault(etapa, {
            "spend_meta": 0.0, "spend_google": 0.0,
            "campanhas_meta": set(), "campanhas_google": set(),
        })

    for r in rows_meta:
        nome_camp = r.get("campaign_name") or ""
        if extract_launch_code_meta(nome_camp) != codigo:
            continue
        etapa, *_ = _categorize_meta(nome_camp)
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        b = _bucket(etapa)
        b["spend_meta"] += float(r.get("spend") or 0)
        b["campanhas_meta"].add(nome_camp)
    for r in rows_google:
        nome_camp = (r.get("campaign") or {}).get("name") or ""
        if extract_launch_code_google(nome_camp) != codigo:
            continue
        etapa, *_ = _categorize_google(nome_camp)
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        cost = int((r.get("metrics") or {}).get("costMicros", 0)) / 1_000_000
        b = _bucket(etapa)
        b["spend_google"] += cost
        b["campanhas_google"].add(nome_camp)
    return real


def _total_gasto(info: dict) -> float:
    return info.get("spend_meta", 0.0) + info.get("spend_google", 0.0)


def _etapa_ativa(nome: str, codigo: str, status_meta: dict[str, str], status_google: dict[str, str]) -> bool:
    """True se pelo menos uma campanha da etapa está ativa (ACTIVE/ENABLED) na plataforma."""
    for camp_name, st in status_meta.items():
        if extract_launch_code_meta(camp_name) != codigo:
            continue
        etapa, *_ = _categorize_meta(camp_name)
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        if etapa == nome and st in STATUS_ATIVO_META:
            return True
    for camp_name, st in status_google.items():
        if extract_launch_code_google(camp_name) != codigo:
            continue
        etapa, *_ = _categorize_google(camp_name)
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        if etapa == nome and st in STATUS_ATIVO_GOOGLE:
            return True
    return False


def _processar_lancamento(codigo: str, cfg: dict, hoje: date, state: dict) -> tuple[str | None, list[str]]:
    """Retorna (bloco_de_mensagem_ou_None, [erros])."""
    etapas = cfg.get("etapas") or []
    if not etapas:
        return None, []

    meta_ids = cfg.get("meta_ad_account_ids") or []
    google_ids = cfg.get("google_ad_account_ids") or []

    try:
        status_meta = fetch_meta_status(meta_ids) if meta_ids else {}
        status_google = fetch_google_status(google_ids) if google_ids else {}
        rows_meta_hoje = fetch_insights(hoje.isoformat(), hoje.isoformat(), account_ids=meta_ids) if meta_ids else []
        rows_google_hoje = (
            fetch_report(hoje.isoformat(), hoje.isoformat(), customer_ids=google_ids)
            + fetch_pmax_report(hoje.isoformat(), hoje.isoformat(), customer_ids=google_ids)
        ) if google_ids else []
    except Exception as exc:
        logger.exception("Falha ao consultar APIs de anúncios para %s", codigo)
        return None, [f"• *{codigo}*: {exc}"]

    real_hoje = _categorizar_gasto(rows_meta_hoje, rows_google_hoje, codigo)
    state_launch = state.setdefault(codigo, {})

    linhas: list[str] = []
    for etapa in etapas:
        nome = etapa.get("nome")
        try:
            inicio = date.fromisoformat(etapa["start_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if hoje < inicio:
            continue  # etapa ainda não começou

        ativa_agora = _etapa_ativa(nome, codigo, status_meta, status_google)
        estava_ativa = state_launch.get(nome, "active") == "active"

        if ativa_agora:
            planejado = _planejado_etapa_dia(etapa, hoje)
            info = real_hoje.get(nome, {"spend_meta": 0.0, "spend_google": 0.0, "campanhas_meta": set(), "campanhas_google": set()})
            plan_total = planejado["meta"] + planejado["google"]
            real_total = info["spend_meta"] + info["spend_google"]
            if plan_total or real_total:
                pct_gasto = (real_total / plan_total * 100) if plan_total else (100.0 if real_total else 0.0)
                status_txt = _status_orcamento(pct_gasto - 100.0) if plan_total else "— sem orçamento previsto pra essa etapa"
                linhas.append(
                    f"\n  *{nome}* (hoje até agora)\n"
                    f"    Meta: {_formatar_valor(info['spend_meta'])} ({len(info['campanhas_meta'])} campanhas)\n"
                    f"    Google: {_formatar_valor(info['spend_google'])} ({len(info['campanhas_google'])} campanhas)\n"
                    f"    Total: {_formatar_valor(real_total)}\n"
                    f"    Orçamento previsto hoje: {_formatar_valor(plan_total)}\n"
                    f"    % gasto: {_formatar_pct(pct_gasto)}%\n"
                    f"    Status: {status_txt}"
                )
            state_launch[nome] = "active"
        else:
            if estava_ativa:
                # transição ativa -> pausada: relatório de fechamento (gasto total acumulado)
                fim_consulta = min(etapa.get("end_date") or hoje.isoformat(), hoje.isoformat())
                try:
                    rows_m = fetch_insights(etapa["start_date"], fim_consulta, account_ids=meta_ids) if meta_ids else []
                    rows_g = (
                        fetch_report(etapa["start_date"], fim_consulta, customer_ids=google_ids)
                        + fetch_pmax_report(etapa["start_date"], fim_consulta, customer_ids=google_ids)
                    ) if google_ids else []
                    total_periodo = _categorizar_gasto(rows_m, rows_g, codigo)
                    gasto_total = _total_gasto(total_periodo.get(nome, {}))
                except Exception:
                    logger.exception("Falha ao buscar gasto total de fechamento pra %s / %s", codigo, nome)
                    gasto_total = None
                valor_txt = _formatar_valor(gasto_total) if gasto_total is not None else "(falha ao consultar)"
                linhas.append(
                    f"\n  *{nome}* — 🔴 campanhas pausadas/encerradas\n"
                    f"    Gasto total acumulado: {valor_txt}"
                )
            state_launch[nome] = "paused"
            # se já estava pausada, não repete no relatório

    # Fechamento do carrinho: resumo de TODAS as etapas, ativas ou não
    if cfg.get("carrinho_end_date") == hoje.isoformat():
        try:
            resumo_linhas = ["\n  *📋 Fechamento do carrinho — resumo completo*"]
            for etapa in etapas:
                nome = etapa.get("nome")
                inicio = etapa.get("start_date")
                if not inicio:
                    continue
                fim_consulta = min(etapa.get("end_date") or hoje.isoformat(), hoje.isoformat())
                rows_m = fetch_insights(inicio, fim_consulta, account_ids=meta_ids) if meta_ids else []
                rows_g = (
                    fetch_report(inicio, fim_consulta, customer_ids=google_ids)
                    + fetch_pmax_report(inicio, fim_consulta, customer_ids=google_ids)
                ) if google_ids else []
                total_periodo = _categorizar_gasto(rows_m, rows_g, codigo)
                gasto_total = _total_gasto(total_periodo.get(nome, {}))
                previsto_total = _previsto_periodo_midia(etapa)
                resumo_linhas.append(
                    f"    {nome}: {_formatar_valor(gasto_total)} "
                    f"(previsto {_formatar_valor(previsto_total)})"
                )
            linhas.append("\n".join(resumo_linhas))
        except Exception:
            logger.exception("Falha ao montar resumo de fechamento do carrinho pra %s", codigo)

    if not linhas:
        return None, []
    return "\n*" + codigo + "*" + "".join(linhas), []


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
        hoje = date.today()
        logger.info("Iniciando alerta de orçamento — hoje %s", hoje.isoformat())

        state = _load_state()
        blocos: list[str] = []
        falhas: list[str] = []

        for codigo in _listar_codigos_lancamentos():
            cfg = _ler_launch_config(codigo)
            bloco, erros = _processar_lancamento(codigo, cfg, hoje, state)
            if bloco:
                blocos.append(bloco)
            falhas.extend(erros)

        _save_state(state)

        partes = [f"*Relatório de Orçamento — {hoje.strftime('%d/%m/%Y')}*"]
        if falhas:
            partes.append("\n*⚠️ Falhas na consulta (sem números pra esses lançamentos):*\n" + "\n".join(falhas))
        if blocos:
            partes.append("\n".join(blocos))
        else:
            partes.append("\nNenhuma novidade — nenhum lançamento com etapa ativa ou fechamento hoje.")

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