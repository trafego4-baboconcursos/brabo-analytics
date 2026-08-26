"""
frontend/db_readers/whatsapp_messages.py — Volume de mensagens WhatsApp Business
(banco analytics, tabela whatsapp_messages_daily), sincronizado com as datas do
lançamento.

Sem custo em R$ — as contas monitoradas são faturadas via Unichat como parceiro,
e o Meta esconde o campo de custo pra WABAs faturadas por parceiro. O que dá pra
mostrar é volume de mensagens enviadas/entregues por dia, por número, dentro da
janela do lançamento (dim_lancamentos.data_inicio/data_fim).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.models import Launch

logger = get_logger("db")


def _read_uncached(launch_code: str, start: date, end: date) -> dict | None:
    if not start or not end:
        return None
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT date, waba_id, account_name, phone_number, sent, delivered "
                    "FROM whatsapp_messages_daily WHERE date BETWEEN :s AND :e "
                    "ORDER BY date"
                ),
                {"s": start, "e": end},
            ).fetchall()
    except Exception:
        logger.exception("read_whatsapp_messages: falha para %s", launch_code)
        return None

    if not rows:
        return {"accounts": [], "total_sent": 0, "total_delivered": 0, "start": str(start), "end": str(end)}

    by_account: dict[str, dict] = {}
    for r in rows:
        key = r.waba_id
        acc = by_account.setdefault(key, {
            "waba_id": r.waba_id,
            "name": r.account_name or r.waba_id,
            "phone": r.phone_number,
            "series": [],
            "total_sent": 0,
            "total_delivered": 0,
        })
        acc["series"].append({"date": str(r.date), "sent": r.sent or 0, "delivered": r.delivered or 0})
        acc["total_sent"] += r.sent or 0
        acc["total_delivered"] += r.delivered or 0

    accounts = sorted(by_account.values(), key=lambda a: -a["total_sent"])
    total_sent = sum(a["total_sent"] for a in accounts)
    total_delivered = sum(a["total_delivered"] for a in accounts)

    return {
        "accounts": accounts,
        "total_sent": total_sent,
        "total_delivered": total_delivered,
        "start": str(start),
        "end": str(end),
    }


def read_whatsapp_messages(launch: Launch | None) -> dict | None:
    if not launch or not launch.data_inicio:
        return None
    end = launch.data_fim or date.today()
    end = min(end, date.today())
    return _read_uncached(launch.code, launch.data_inicio, end)
