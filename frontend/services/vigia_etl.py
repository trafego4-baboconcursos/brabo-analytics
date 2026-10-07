"""
frontend/services/vigia_etl.py — avisa quando o ETL para.

POR QUE MORA NO SITE, E NÃO NO ETL. Se o ETL parou, ele não consegue avisar que
parou. O site é outro serviço no EasyPanel e fica de pé sozinho, então é ele
quem vigia: a cada `INTERVALO_MIN` lê o `etl_runs` (cada carga do ETL grava ali
fonte, horário e status) e o histórico de UTM.

POR QUE IMPORTA MAIS DO QUE "DADO ATRASADO". Desde 07/10/26 o histórico de UTM
por lançamento (`lead_utm_lancamento`) só registra o que o ETL vê. ETL parado
por dias = cadastros desses dias sem histórico — e a perda é silenciosa. A faixa
antiga da tela só aparecia depois de 25h e só para quem abrisse o site; o canal
de alerta do próprio ETL (`ERROR_WEBHOOK_URL`) estava vazio. Ninguém era avisado.

DOIS TIPOS DE PROBLEMA:
  1. **ETL parado** — uma fonte crítica sem carga OK além do limite dela.
  2. **Histórico não grava** — o Active Campaign carrega, mas o histórico não
     é escrito. Foi exatamente o estado de 07/10/26: o site foi atualizado e o
     serviço do ETL ficou com o código antigo, sobrescrevendo a `leads` sem
     gravar o histórico.

MENSAGEM: Slack, no mesmo canal e bot do alerta de orçamento. Uma mensagem
quando o problema aparece, lembrete a cada `LEMBRETE_H` enquanto durar, e uma
quando normaliza. O estado fica em memória: depois de um restart do site, no
máximo uma mensagem repetida — aceitável, e evita criar tabela só pra isso.

Só leitura no banco. Nada de DDL aqui (lição de 07/10/26: DDL no caminho de
leitura pega lock exclusivo a cada chamada).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from logger import get_logger

logger = get_logger("frontend")

INTERVALO_MIN = 15
LEMBRETE_H = 6
ATRASO_INICIAL_MIN = 5  # o boot do site é pesado; a primeira checagem espera

# Limite por fonte = ~4x a cadência real (medida em 07/10/26 no etl_runs):
# Meta e Google carregam a cada 30 min, o Active Campaign a cada 60 min.
LIMITES_H: dict[str, float] = {
    "meta_ads": 2.0,
    "google_ads": 2.0,
    "active_campaign": 3.0,
}
NOMES: dict[str, str] = {
    "meta_ads": "Meta Ads",
    "google_ads": "Google Ads",
    "active_campaign": "Active Campaign",
}
HISTORICO = "historico_utm"

_TZ = ZoneInfo("America/Sao_Paulo")

# Estado em memória, lido pelo _base_ctx para a faixa da tela.
ESTADO: dict = {"problemas": [], "checado_em": None, "desde": None, "avisado_em": None}


def _local(dt: datetime | None) -> str:
    if dt is None:
        return "nunca"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ).strftime("%d/%m %H:%M")


def _ha(agora: datetime, dt: datetime) -> str:
    horas = (agora - dt).total_seconds() / 3600
    return f"{horas:.0f}h" if horas >= 1 else f"{horas * 60:.0f} min"


def avaliar(ultimas_ok: dict[str, datetime | None],
            historico_ultimo: datetime | None,
            agora: datetime) -> list[dict]:
    """Regra pura: o que está errado agora. Sem banco, para dar pra testar.

    `ultimas_ok`: fonte → horário da última carga OK (UTC), ou None.
    `historico_ultimo`: última escrita do ETL no histórico de UTM, ou None
    quando a tabela não existe (aí a checagem do histórico não se aplica).
    """
    problemas: list[dict] = []
    for fonte, limite in LIMITES_H.items():
        ultima = ultimas_ok.get(fonte)
        if ultima is None or agora - ultima > timedelta(hours=limite):
            problemas.append({
                "tipo": "etl_parado",
                "fonte": fonte,
                "texto": (f"{NOMES[fonte]} sem carga desde {_local(ultima)}"
                          + (f" (há {_ha(agora, ultima)})" if ultima else "")),
            })

    ac = ultimas_ok.get("active_campaign")
    ac_ok = ac is not None and agora - ac <= timedelta(hours=LIMITES_H["active_campaign"])
    if ac_ok and historico_ultimo is not None:
        # O histórico é gravado na mesma passada do AC, antes da `leads`. Se o
        # AC carregou e o histórico ficou para trás mais que o limite do AC, o
        # ETL está rodando sem gravar — código antigo no serviço ou gancho
        # falhando.
        if ac - historico_ultimo > timedelta(hours=LIMITES_H["active_campaign"]):
            problemas.append({
                "tipo": "historico_parado",
                "fonte": HISTORICO,
                "texto": (f"o Active Campaign carregou às {_local(ac)}, mas o histórico de UTM "
                          f"não é gravado desde {_local(historico_ultimo)} — o serviço do ETL "
                          f"está com a versão atual?"),
            })
    return problemas


def _ler_estado_banco() -> tuple[dict[str, datetime | None], datetime | None]:
    from frontend.db import _get_engine  # noqa: PLC0415

    ultimas: dict[str, datetime | None] = {f: None for f in LIMITES_H}
    historico: datetime | None = None
    with _get_engine().connect() as conn:
        for fonte, quando in conn.execute(text("""
            SELECT source, max(finished_at) FROM etl_runs
            WHERE status = 'ok' AND source = ANY(:fontes)
            GROUP BY source
        """), {"fontes": list(LIMITES_H)}).fetchall():
            if quando is not None and quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            ultimas[fonte] = quando
    try:
        with _get_engine().connect() as conn:
            # ORDER BY ... LIMIT 1, não max(): é a forma que usa o índice
            # idx_lead_utm_lancamento_visto (0,1 s contra 3,5 s, medido).
            historico = conn.execute(text("""
                SELECT ultimo_visto_em FROM lead_utm_lancamento
                WHERE origem <> 'seed_leads'
                ORDER BY ultimo_visto_em DESC LIMIT 1
            """)).scalar()
    except Exception as e:
        if "does not exist" not in str(e):
            raise
        historico = None  # tabela ainda não existe: a checagem não se aplica
    return ultimas, historico


def _enviar_slack(mensagem: str) -> bool:
    """chat.postMessage com o mesmo bot e canal do alerta de orçamento."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    canal = os.environ.get("SLACK_BUDGET_CHANNEL")
    if not token or not canal:
        logger.warning("Vigia do ETL: SLACK_BOT_TOKEN/SLACK_BUDGET_CHANNEL ausentes neste "
                       "serviço — o alerta só aparece na tela.")
        return False
    try:
        import requests  # noqa: PLC0415
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": canal, "text": mensagem},
            timeout=15,
        )
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            logger.error("Vigia do ETL: Slack recusou a mensagem: %s", r.text[:300])
        return ok
    except Exception:
        logger.exception("Vigia do ETL: falha ao enviar para o Slack")
        return False


def _mensagem_problema(problemas: list[dict], lembrete: bool) -> str:
    cab = ":rotating_light: *ETL parado — Brabo Analytics*" if not lembrete \
        else ":rotating_light: *Lembrete: o ETL continua parado — Brabo Analytics*"
    linhas = [cab] + [f"• {p['texto']}" for p in problemas]
    linhas.append("Enquanto isso, as páginas não atualizam e o histórico de UTM não registra "
                  "os cadastros novos — quem trocar de lançamento nesse intervalo perde a linha.")
    return "\n".join(linhas)


def checar_e_avisar(agora: datetime | None = None) -> list[dict]:
    """Uma rodada do vigia. Devolve os problemas encontrados."""
    agora = agora or datetime.now(timezone.utc)
    ultimas, historico = _ler_estado_banco()
    problemas = avaliar(ultimas, historico, agora)
    tinha = bool(ESTADO["problemas"])

    if problemas and not tinha:
        ESTADO["desde"] = agora
        if _enviar_slack(_mensagem_problema(problemas, lembrete=False)):
            ESTADO["avisado_em"] = agora
        logger.error("Vigia do ETL: %s", "; ".join(p["texto"] for p in problemas))
    elif problemas and tinha:
        ultimo_aviso = ESTADO["avisado_em"] or ESTADO["desde"]
        if ultimo_aviso is None or agora - ultimo_aviso >= timedelta(hours=LEMBRETE_H):
            if _enviar_slack(_mensagem_problema(problemas, lembrete=True)):
                ESTADO["avisado_em"] = agora
    elif not problemas and tinha:
        _enviar_slack(":white_check_mark: *ETL normalizado — Brabo Analytics*\n"
                      "Todas as fontes voltaram a carregar e o histórico de UTM está sendo gravado.")
        ESTADO["desde"] = None
        ESTADO["avisado_em"] = None
        logger.info("Vigia do ETL: normalizado.")

    ESTADO["problemas"] = problemas
    ESTADO["checado_em"] = agora
    return problemas


async def _laco() -> None:
    await asyncio.sleep(ATRASO_INICIAL_MIN * 60)
    while True:
        try:
            await asyncio.to_thread(checar_e_avisar)
        except Exception:
            logger.exception("Vigia do ETL: rodada falhou")
        await asyncio.sleep(INTERVALO_MIN * 60)


_TAREFA: asyncio.Task | None = None


def agendar_vigia() -> None:
    """Chamado no startup do site. Uma tarefa só por processo."""
    global _TAREFA
    if _TAREFA is not None and not _TAREFA.done():
        return
    _TAREFA = asyncio.create_task(_laco())
    logger.info("Vigia do ETL agendado: a cada %d min (primeira em %d min).",
                INTERVALO_MIN, ATRASO_INICIAL_MIN)
