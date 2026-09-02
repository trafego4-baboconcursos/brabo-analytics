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


def enviar_slack(mensagem: str) -> bool:
    """Envia via Slack Web API (chat.postMessage) usando um Bot Token — o bot
    precisa estar adicionado/convidado no canal de destino. Retorna True se
    o Slack aceitou (usado pra registrar last_sent e permitir catch-up)."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_BUDGET_CHANNEL")
    if not token or not channel:
        logger.warning("SLACK_BOT_TOKEN/SLACK_BUDGET_CHANNEL não configurados — mensagem não enviada.")
        return False
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
            return False
        logger.info("Alerta de orçamento enviado ao Slack com sucesso.")
        return True
    except Exception as e:
        logger.error("Erro ao enviar alerta de orçamento ao Slack: %s", e)
        return False


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


# Estado no BANCO (não em arquivo): o filesystem do container zera a cada
# deploy, o que apagava o estado de etapas ativas/pausadas e impedia saber se
# o último horário de alerta chegou a ser enviado.
_STATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS budget_alert_state (
        id INT PRIMARY KEY DEFAULT 1,
        state JSONB NOT NULL DEFAULT '{}',
        last_sent TIMESTAMPTZ
    )
"""


def _load_state() -> dict:
    try:
        with get_engine().begin() as conn:
            conn.execute(text(_STATE_TABLE_SQL))
            row = conn.execute(text("SELECT state FROM budget_alert_state WHERE id = 1")).fetchone()
        if row and row[0]:
            return row[0] if isinstance(row[0], dict) else _json.loads(row[0])
        return {}
    except Exception:
        logger.exception("Falha ao ler budget_alert_state do banco; usando arquivo local")
        try:
            return _json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}


def _save_state(state: dict, sent: bool = False) -> None:
    try:
        with get_engine().begin() as conn:
            conn.execute(text(_STATE_TABLE_SQL))
            conn.execute(text(
                "INSERT INTO budget_alert_state (id, state, last_sent) "
                "VALUES (1, :s, CASE WHEN :sent THEN NOW() ELSE NULL END) "
                "ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, "
                "last_sent = CASE WHEN :sent THEN NOW() ELSE budget_alert_state.last_sent END"
            ), {"s": _json.dumps(state, ensure_ascii=False), "sent": sent})
    except Exception:
        logger.exception("Falha ao gravar budget_alert_state no banco; usando arquivo local")
        try:
            STATE_FILE.write_text(_json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            logger.exception("Falha ao gravar %s", STATE_FILE)


def _ultimo_horario_previsto(agora=None):
    """O horário de disparo (8h15/13h15/21h15 America/Sao_Paulo) mais recente
    que já passou — pode ser o 21h15 de ontem se ainda não deu 8h15 hoje."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Sao_Paulo")
    agora = agora or datetime.now(tz)
    slots_hoje = [agora.replace(hour=h, minute=15, second=0, microsecond=0) for h in (8, 13, 21)]
    passados = [s for s in slots_hoje if s <= agora]
    if passados:
        return passados[-1]
    return (agora - timedelta(days=1)).replace(hour=21, minute=15, second=0, microsecond=0)


def alerta_pendente() -> bool:
    """True se o último horário de disparo não gerou envio (deploy engoliu o
    cron, Slack falhou etc.) — usado pelo scheduler pra recuperar no boot."""
    try:
        with get_engine().begin() as conn:
            conn.execute(text(_STATE_TABLE_SQL))
            row = conn.execute(text("SELECT last_sent FROM budget_alert_state WHERE id = 1")).fetchone()
        last_sent = row[0] if row else None
        if last_sent is None:
            return True
        return last_sent < _ultimo_horario_previsto()
    except Exception:
        logger.exception("Falha ao checar alerta pendente; assumindo que não há")
        return False


def _listar_codigos_lancamentos() -> list[str] | None:
    """None = falha na consulta (diferente de lista vazia), pro relatório avisar."""
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text("SELECT codigo FROM dim_lancamentos ORDER BY codigo")).fetchall()
        return [r[0] for r in rows]
    except Exception:
        logger.exception("Falha ao listar lançamentos de dim_lancamentos")
        return None


def _ler_launch_config(codigo: str) -> dict:
    try:
        with get_users_engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT etapas, meta_ad_account_ids, google_ad_account_ids, carrinho_end_date, "
                    "       pre_quali_start_date, pre_quali_end_date, captacao_start_date, captacao_end_date, "
                    "       meta_investimento_pre_quali, meta_investimento_captacao "
                    "FROM launch_config WHERE lancamento_codigo = :c"
                ),
                {"c": codigo},
            ).fetchone()
        if not row:
            return {}
        etapas = row[0] or []
        if isinstance(etapas, str):
            etapas = _json.loads(etapas) if etapas else []

        # Fonte única pra Pré-Qualificação/Captação: data E orçamento vêm dos
        # passos 1/2 do wizard (pre_quali_*/captacao_*/meta_investimento*), não
        # dos campos próprios do bloco de Verba — o wizard novo já nem edita
        # esses campos ali (fica só leitura/sincronizado), mas launch_configs
        # salvos antes disso ainda têm o bloco de Verba desatualizado/vazio, e
        # esse fallback cobre esse caso sem precisar editar o banco na mão.
        fallback = {
            "Pré-Qualificação": {"start": row[4], "end": row[5], "total": row[8]},
            "Captação": {"start": row[6], "end": row[7], "total": row[9]},
        }
        for etapa in etapas:
            fb = fallback.get(etapa.get("nome"))
            if not fb:
                continue
            if not etapa.get("start_date") and fb["start"]:
                etapa["start_date"] = str(fb["start"])
            if not etapa.get("end_date") and fb["end"]:
                etapa["end_date"] = str(fb["end"])
            if not etapa.get("total") and fb["total"]:
                etapa["total"] = float(fb["total"])

        return {
            "etapas": etapas,
            "meta_ad_account_ids": row[1] or [],
            "google_ad_account_ids": row[2] or [],
            "carrinho_end_date": str(row[3]) if row[3] else None,
        }
    except Exception as exc:
        logger.exception("Falha ao ler launch_config de %s", codigo)
        # falha de leitura NÃO é "sem etapas" — precisa aparecer no relatório,
        # senão um lançamento ativo some do Slack em silêncio
        return {"_erro_leitura": str(exc)}


def _planejado_acumulado_midia(etapa: dict, hoje: date) -> float:
    """Previsto acumulado (fatia de mídia) do início da etapa até hoje, inclusive.
    Uniforme: pro-rata pelos dias decorridos; personalizada: soma da curva %."""
    try:
        ini = date.fromisoformat(etapa["start_date"])
        fim = date.fromisoformat(etapa["end_date"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    total_midia = _previsto_periodo_midia(etapa)
    total_dias = (fim - ini).days + 1
    if total_dias <= 0:
        return 0.0
    dia_pos = min((hoje - ini).days + 1, total_dias)
    if dia_pos <= 0:
        return 0.0
    if etapa.get("distribuicao") == "personalizada":
        curva = etapa.get("curva_pct") or []
        pct = sum(float(x or 0) for x in curva[:dia_pos])
        return total_midia * pct / 100.0
    return total_midia * dia_pos / total_dias


def _previsto_periodo_midia(etapa: dict) -> float:
    """Total previsto do período inteiro da etapa, só a fatia de mídia (Meta+Google).
    Sem buckets de plataforma cadastrados, assume o total inteiro como mídia."""
    total = float(etapa.get("total") or 0)
    pct_midia = sum(
        float(b.get("pct") or 0)
        for b in (etapa.get("buckets") or [])
        if b.get("tipo") == "campanha" and b.get("plataforma") in ("meta", "google")
    )
    return total * pct_midia / 100.0 if pct_midia > 0 else total


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


def _gasto_db_periodo(codigo: str, data_ini: str, data_fim: str) -> dict[str, dict]:
    """Gasto já consolidado no banco (ETL a cada 30min + reprocessamento profundo
    3h40) entre data_ini e data_fim, agrupado por etapa. Pra período D-1 e antes
    isso é MELHOR que reconsultar a API ao vivo: mais rápido (query local em vez
    de paginar semanas de insights), e reflete os restatements retroativos que o
    Meta/Google fazem (o job de 3h40 existe justamente pra capturar isso — ver
    scheduler.py). lancamento_codigo já vem extraído pelo ETL, sem precisar
    re-parsear o nome da campanha."""
    real: dict[str, dict] = {}

    def _bucket(etapa):
        return real.setdefault(etapa, {
            "spend_meta": 0.0, "spend_google": 0.0,
            "campanhas_meta": set(), "campanhas_google": set(),
        })

    with get_engine().connect() as conn:
        rows_m = conn.execute(text(
            "SELECT campaign_name, SUM(spend) FROM meta_ads_daily "
            "WHERE lancamento_codigo = :c AND date BETWEEN :ini AND :fim "
            "GROUP BY campaign_name"
        ), {"c": codigo, "ini": data_ini, "fim": data_fim}).fetchall()
        rows_g = conn.execute(text(
            "SELECT campaign_name, SUM(cost) FROM google_ads_daily "
            "WHERE lancamento_codigo = :c AND date BETWEEN :ini AND :fim "
            "GROUP BY campaign_name"
        ), {"c": codigo, "ini": data_ini, "fim": data_fim}).fetchall()

    for nome_camp, spend in rows_m:
        etapa, *_ = _categorize_meta(nome_camp or "")
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        b = _bucket(etapa)
        b["spend_meta"] += float(spend or 0)
        b["campanhas_meta"].add(nome_camp)
    for nome_camp, cost in rows_g:
        etapa, *_ = _categorize_google(nome_camp or "")
        if etapa == "Performance Max":
            etapa = ETAPA_PMAX_REDIRECIONA_PARA
        b = _bucket(etapa)
        b["spend_google"] += float(cost or 0)
        b["campanhas_google"].add(nome_camp)
    return real


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
    if cfg.get("_erro_leitura"):
        return None, [f"• *{codigo}*: falha ao ler launch_config — {cfg['_erro_leitura']}"]
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
        detalhe = str(exc)
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                detalhe += f" — {resp.text[:300]}"
            except Exception:
                pass
        return None, [f"• *{codigo}*: {detalhe}"]

    real_hoje = _categorizar_gasto(rows_meta_hoje, rows_google_hoje, codigo)
    state_launch = state.setdefault(codigo, {})

    linhas: list[str] = []
    for etapa in etapas:
        nome = etapa.get("nome")
        try:
            inicio = date.fromisoformat(etapa["start_date"])
        except (KeyError, TypeError, ValueError):
            inicio = None

        # Vigência é decidida pela PLATAFORMA (campanha ativa), não pela config:
        # etapa sem data cadastrada (ou antes da data) entra no relatório mesmo
        # assim se tiver campanha no ar — só fica de fora se não há data E não
        # há campanha ativa.
        ativa_agora = _etapa_ativa(nome, codigo, status_meta, status_google)
        if not ativa_agora and (inicio is None or hoje < inicio):
            continue

        estava_ativa = state_launch.get(nome, "active") == "active"

        if ativa_agora:
            # O que importa é o ACUMULADO da etapa contra o previsto total —
            # o gasto do dia sozinho não conta a história (pedido do time).
            info_hoje = real_hoje.get(nome, {"spend_meta": 0.0, "spend_google": 0.0, "campanhas_meta": set(), "campanhas_google": set()})
            real_dia = info_hoje["spend_meta"] + info_hoje["spend_google"]
            n_campanhas = len(info_hoje["campanhas_meta"]) + len(info_hoje["campanhas_google"])

            previsto_total = _previsto_periodo_midia(etapa)
            previsto_ate_hoje = _planejado_acumulado_midia(etapa, hoje) if inicio and hoje >= inicio else 0.0

            # D-1 pro trás vem do BANCO (já ETL'd, restatements já aplicados,
            # query local rápida); só o dia de hoje é buscado ao vivo — e esse
            # já tínhamos (real_hoje), sem chamada extra. Isso também resolve
            # o pedido de "o relatório das 8h mostra o gasto até ontem 23h59":
            # às 8h a fatia "hoje" ainda é ~0, então o acumulado já sai como
            # D-1 fechado na prática, sem precisar de lógica por horário.
            acumulado = None
            acum_meta = acum_google = 0.0
            if inicio and hoje >= inicio:
                ontem = hoje - timedelta(days=1)
                try:
                    historico = {}
                    if ontem >= inicio:
                        historico = _gasto_db_periodo(codigo, inicio.isoformat(), ontem.isoformat())
                    hist_info = historico.get(nome, {"spend_meta": 0.0, "spend_google": 0.0})
                    acum_meta = hist_info.get("spend_meta", 0.0) + info_hoje["spend_meta"]
                    acum_google = hist_info.get("spend_google", 0.0) + info_hoje["spend_google"]
                    acumulado = acum_meta + acum_google
                except Exception:
                    logger.exception("Falha ao buscar gasto acumulado de %s / %s", codigo, nome)

            if acumulado is not None:
                periodo_txt = f" ({_formatar_data_br(etapa.get('start_date'))} → {_formatar_data_br(etapa.get('end_date'))})" if etapa.get("end_date") else ""
                pct_total = (acumulado / previsto_total * 100) if previsto_total else 0.0
                pct_ritmo = (acumulado / previsto_ate_hoje * 100) if previsto_ate_hoje else 0.0
                status_txt = _status_orcamento(pct_ritmo - 100.0) if previsto_ate_hoje else "— sem orçamento previsto pra essa etapa"
                previsto_txt = (
                    f"    Previsto total da etapa: {_formatar_valor(previsto_total)}\n"
                    f"    Consumido do total: {_formatar_pct(pct_total)}%\n"
                    f"    Previsto até hoje: {_formatar_valor(previsto_ate_hoje)} | Ritmo: {_formatar_pct(pct_ritmo)}%\n"
                ) if previsto_total else "    (sem orçamento previsto cadastrado pra essa etapa)\n"
                linhas.append(
                    f"\n  *{nome}*{periodo_txt}\n"
                    f"    Gasto acumulado: {_formatar_valor(acumulado)} (Meta {_formatar_valor(acum_meta)} · Google {_formatar_valor(acum_google)})\n"
                    f"    Hoje até agora: {_formatar_valor(real_dia)} ({n_campanhas} campanhas ativas)\n"
                    f"{previsto_txt}"
                    f"    Status: {status_txt}"
                )
            elif real_dia > 0:
                # etapa sem período cadastrado (ou campanha no ar antes do início):
                # sem como somar o acumulado — reporta o dia com aviso
                linhas.append(
                    f"\n  *{nome}* — ⚠️ sem período cadastrado no wizard (Verba)\n"
                    f"    Hoje até agora: {_formatar_valor(real_dia)} ({n_campanhas} campanhas ativas)\n"
                    f"    Cadastre datas e verba da etapa pra ver acumulado x previsto"
                )
            state_launch[nome] = "active"
        else:
            if estava_ativa:
                # transição ativa -> pausada: relatório de fechamento (gasto total
                # acumulado) — mesmo padrão banco (D-1 pro trás) + hoje ao vivo
                inicio_consulta = etapa.get("start_date")
                try:
                    if not inicio_consulta:
                        raise ValueError("etapa sem start_date — sem período pra somar o gasto")
                    ontem = hoje - timedelta(days=1)
                    ini_dt = date.fromisoformat(inicio_consulta)
                    historico = _gasto_db_periodo(codigo, inicio_consulta, ontem.isoformat()) if ontem >= ini_dt else {}
                    hist_info = historico.get(nome, {"spend_meta": 0.0, "spend_google": 0.0})
                    hoje_info = real_hoje.get(nome, {"spend_meta": 0.0, "spend_google": 0.0})
                    gasto_total = (
                        hist_info.get("spend_meta", 0.0) + hoje_info.get("spend_meta", 0.0)
                        + hist_info.get("spend_google", 0.0) + hoje_info.get("spend_google", 0.0)
                    )
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
            ontem = hoje - timedelta(days=1)
            for etapa in etapas:
                nome = etapa.get("nome")
                inicio = etapa.get("start_date")
                if not inicio:
                    continue
                ini_dt = date.fromisoformat(inicio)
                historico = _gasto_db_periodo(codigo, inicio, ontem.isoformat()) if ontem >= ini_dt else {}
                hist_info = historico.get(nome, {"spend_meta": 0.0, "spend_google": 0.0})
                hoje_info = real_hoje.get(nome, {"spend_meta": 0.0, "spend_google": 0.0})
                gasto_total = (
                    hist_info.get("spend_meta", 0.0) + hoje_info.get("spend_meta", 0.0)
                    + hist_info.get("spend_google", 0.0) + hoje_info.get("spend_google", 0.0)
                )
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

        codigos = _listar_codigos_lancamentos()
        if codigos is None:
            falhas.append("• Falha ao listar lançamentos (dim_lancamentos indisponível) — relatório incompleto")
            codigos = []
        for codigo in codigos:
            cfg = _ler_launch_config(codigo)
            bloco, erros = _processar_lancamento(codigo, cfg, hoje, state)
            if bloco:
                blocos.append(bloco)
            falhas.extend(erros)

        partes = [f"*Relatório de Orçamento — {hoje.strftime('%d/%m/%Y')}*"]
        if falhas:
            partes.append("\n*⚠️ Falhas na consulta (sem números pra esses lançamentos):*\n" + "\n".join(falhas))
        if blocos:
            partes.append("\n".join(blocos))
        else:
            partes.append("\nNenhuma novidade — nenhum lançamento com etapa ativa ou fechamento hoje.")

        enviado = enviar_slack("\n".join(partes))
        # last_sent só marca quando o Slack aceitou — se falhou, o catch-up do
        # próximo boot/horário reenvia em vez de dar o horário como cumprido
        _save_state(state, sent=enviado)
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