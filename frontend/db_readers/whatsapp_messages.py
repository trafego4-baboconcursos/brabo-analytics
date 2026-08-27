"""
frontend/db_readers/whatsapp_messages.py — Volume de mensagens WhatsApp Business
(banco analytics, tabela whatsapp_messages_daily), sincronizado com as datas do
lançamento.

Sem custo em R$ — as contas monitoradas são faturadas via Unichat como parceiro,
e o Meta esconde o campo de custo pra WABAs faturadas por parceiro. O que dá pra
mostrar é volume de mensagens enviadas/entregues por dia, por número, dentro da
janela do lançamento (dim_lancamentos.data_inicio/data_fim).

Além da janela de datas, filtra pelas contas do produto do lançamento (campo
`product` em config/whatsapp_accounts.yaml, mapeado a partir da lista "Números
Unnichat" em 2026-08-27) — sem esse filtro, contas de outros produtos que
mandaram mensagem no mesmo período apareciam junto, mesmo sem relação com o
lançamento. Contas com `bot_ia: true` (ex: Olívia) atendem os 3 produtos e
entram em qualquer lançamento; contas com `product: null` (institucionais,
ainda não confirmadas) ficam de fora.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.models import Launch

logger = get_logger("db")

_ACCOUNTS_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "whatsapp_accounts.yaml"


def _allowed_waba_ids(prefix: str) -> set[str] | None:
    """WABA ids do produto do lançamento (+ bot_ia, que cobre os 3).
    Retorna None se o config não existir (nesse caso não filtra por conta)."""
    try:
        cfg = yaml.safe_load(_ACCOUNTS_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return None
    out = set()
    for acc in cfg.get("accounts", []):
        waba_id = acc.get("waba_id")
        if not waba_id:
            continue
        if acc.get("bot_ia") or acc.get("product") == prefix:
            out.add(waba_id)
    return out


def _read_uncached(launch_code: str, start: date, end: date) -> dict | None:
    if not start or not end:
        return None
    prefix = launch_code.split("-")[0] if launch_code else ""
    allowed = _allowed_waba_ids(prefix)
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

    if allowed is not None:
        rows = [r for r in rows if r.waba_id in allowed]

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
