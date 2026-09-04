"""
frontend/db_readers/debriefing_snapshot.py — Snapshot pré-calculado do /debriefing.

O contexto inteiro da página (o `dbf` que o template consome, mais as
thumbnails) é calculado uma vez pelo aquecimento (boot e após cada rodada do
ETL) e gravado como JSON na tabela `debriefing_snapshot` do banco analytics.
A página lê UMA linha e renderiza — sem as dezenas de consultas sequenciais
que custavam 60-100s no cache frio. Sem snapshot (lançamento novo, tabela
ainda não criada), a rota cai no cálculo ao vivo de sempre.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import decimal
import json
from typing import Any

from sqlalchemy import text

from frontend.db import _get_engine
from logger import get_logger

logger = get_logger("db")

TABLE = "debriefing_snapshot"

# Versão do formato do payload. Suba este número toda vez que o `dbf` que o
# template consome mudar de forma (campo novo obrigatório, seção nova...).
# Um snapshot gravado com versão diferente é ignorado — a página cai no
# cálculo ao vivo em vez de estourar 500 no template — até o próximo
# aquecimento regravar. (Ex.: 2 = saída dos grupos de WhatsApp, vendas x
# grupos e detalhamento do disparo; 4 = thruview/pct_50 no Novos x Antigos
# de Pré-Qualificação.)
SNAPSHOT_VERSION = 4

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    lancamento_codigo TEXT PRIMARY KEY,
    payload           JSONB NOT NULL,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms       INTEGER
);
"""


def _json_default(o: Any) -> Any:
    """Converte o que o json não conhece: dataclasses viram dict (o template
    acessa `obj.campo`, que no Jinja também funciona em dict), datas viram
    ISO, Decimal vira float, set vira lista, objeto genérico vira __dict__."""
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    if isinstance(o, (_dt.datetime, _dt.date)):
        return o.isoformat()
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o) if all(isinstance(x, str) for x in o) else list(o)
    if hasattr(o, "__dict__"):
        return {k: v for k, v in vars(o).items() if not k.startswith("_")}
    raise TypeError(f"Tipo não serializável no snapshot do debriefing: {type(o).__name__}")


def ensure_table() -> None:
    with _get_engine().begin() as conn:
        conn.execute(text(DDL))


def write_snapshot(launch_code: str, payload: dict, duration_ms: int | None = None) -> int:
    """Grava (upsert) o snapshot. Devolve o tamanho do JSON em bytes."""
    payload = {**payload, "_version": SNAPSHOT_VERSION}
    body = json.dumps(payload, default=_json_default, ensure_ascii=False)
    with _get_engine().begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {TABLE} (lancamento_codigo, payload, computed_at, duration_ms)
            VALUES (:code, CAST(:payload AS jsonb), now(), :dur)
            ON CONFLICT (lancamento_codigo) DO UPDATE
               SET payload = EXCLUDED.payload, computed_at = now(), duration_ms = EXCLUDED.duration_ms
        """), {"code": launch_code, "payload": body, "dur": duration_ms})
    return len(body)


def read_snapshot(launch_code: str) -> dict | None:
    """{payload, computed_at} ou None. Nunca levanta: se a tabela não existir
    ou o banco falhar, a página segue pelo cálculo ao vivo."""
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(text(
                f"SELECT payload, computed_at FROM {TABLE} WHERE lancamento_codigo = :code"
            ), {"code": launch_code}).fetchone()
    except Exception:
        logger.warning("debriefing_snapshot: leitura falhou para %s (seguindo ao vivo)", launch_code, exc_info=True)
        return None
    if not row:
        return None
    payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    versao = payload.get("_version")
    if versao != SNAPSHOT_VERSION:
        logger.warning("debriefing_snapshot: snapshot de %s tem versão %s (esperada %s); ignorado, seguindo ao vivo",
                       launch_code, versao, SNAPSHOT_VERSION)
        return None
    return {"payload": payload, "computed_at": row[1]}
