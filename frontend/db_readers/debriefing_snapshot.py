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
import os
import socket
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
# de Pré-Qualificação; 6 = total_grupos_normais/vip e os prev_ correspondentes,
# no Resumo Executivo; 7 = Saúde do Lançamento 2.0, que trocou os 4 fatores
# pelos 7 com peso — `saude_pesos`, `saude_score_meta_fat`, `saude_score_cac`,
# `saude_score_conv`; 8 = Detalhamento de Oferta — `oferta_parcela_cartao` e
# `oferta_parcela_boleto`; 9 = `oferta_preco_parcelado`, que o template lia mas
# ninguém produzia; 10 = mesma forma, valores diferentes — o previsto de
# Remarketing passou a incluir a verba do WhatsApp, e snapshot velho mostraria a
# variação com o sinal trocado; 11 = `saude_faixa`/`saude_em_andamento`, a trava
# de classificação por ROAS — snapshot velho não tem a chave e o template pede
# `dbf.saude_faixa.cor`.)
#
# O número ficou em 5 de 04/09 até 15/09 enquanto o `dbf` ganhava campos novos,
# e o resultado foi /debriefing devolvendo 500: o snapshot antigo passava no
# guard e o template pedia `dbf.total_grupos_vip`, que aquele payload não tinha.
# Subir este número é o que evita isso — não é opcional quando o `dbf` muda.
#
# Aconteceu de novo em 16/09 com a Saúde 2.0 (template pedindo `dbf.saude_pesos`),
# e dessa vez com um agravante: enquanto um processo antigo seguia de pé gravando
# no formato velho, os snapshots alternavam entre válido e quebrado a cada rodada
# de aquecimento, então o 500 ia e voltava sozinho. Subir a versão resolve os dois
# lados — o payload do processo velho passa a ser ignorado em vez de derrubar a
# página —, mas o processo velho só para de sobrescrever quando for reiniciado.
#
# E uma terceira vez em 16/09, com o Detalhamento de Oferta: o `dbf` ganhou
# `oferta_parcela_cartao`/`oferta_parcela_boleto` e o template passou a pedir os
# dois, mas a versão ficou em 7 — 7 dos 9 lançamentos com snapshot v7 antigo,
# todos em 500. Três ocorrências em dois dias: **mudou campo do `dbf`, sobe o
# número no MESMO commit**, antes de rodar qualquer coisa.
#
# Isso agora é cobrado por `tests/test_dbf_contrato.py`, que compara as chaves do
# `dbf` com um manifesto e falha pedindo o bump — de nada adiantou estar escrito
# aqui três vezes.
SNAPSHOT_VERSION = 13

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
    """Grava (upsert) o snapshot. Devolve o tamanho do JSON em bytes, ou 0 se a
    gravação foi recusada por já existir um snapshot de versão mais nova.

    **A tabela é monotônica na versão: um processo nunca sobrescreve o snapshot
    de um processo com código mais novo.** Sem isso, qualquer cópia antiga do app
    com o `.env` de produção rebaixa a tabela inteira a cada rodada do próprio
    aquecimento — e como o leitor descarta payload de versão diferente, todo mundo
    passa a recalcular ao vivo (25-80s por lançamento em vez de 0,2s). Foi o que
    aconteceu em 16/09: uma máquina que não era a de desenvolvimento devolvia os 9
    lançamentos pra versão 6 a cada ~30 min, e não deu pra identificar de onde — o
    tráfego do app passa pelo Supavisor, então `pg_stat_activity.client_addr` é o
    do pooler, não o do cliente. Daí também o `_writer`: a próxima vez que isso
    acontecer, o host e o PID de quem gravou estão no próprio payload.

    O preço é que rollback de verdade (voltar pra uma versão anterior de propósito)
    não consegue regravar por cima — nesse caso, apagar as linhas da tabela.
    """
    payload = {
        **payload,
        "_version": SNAPSHOT_VERSION,
        "_writer": f"{socket.gethostname()}#{os.getpid()}",
    }
    body = json.dumps(payload, default=_json_default, ensure_ascii=False)
    with _get_engine().begin() as conn:
        res = conn.execute(text(f"""
            INSERT INTO {TABLE} (lancamento_codigo, payload, computed_at, duration_ms)
            VALUES (:code, CAST(:payload AS jsonb), now(), :dur)
            ON CONFLICT (lancamento_codigo) DO UPDATE
               SET payload = EXCLUDED.payload, computed_at = now(), duration_ms = EXCLUDED.duration_ms
             WHERE COALESCE(({TABLE}.payload->>'_version')::int, 0) <= :versao
        """), {"code": launch_code, "payload": body, "dur": duration_ms, "versao": SNAPSHOT_VERSION})
        if res.rowcount == 0:
            logger.warning(
                "debriefing_snapshot: gravação de %s recusada — já existe snapshot de versão mais nova "
                "que a deste processo (v%s). Este processo está com código antigo; reinicie-o.",
                launch_code, SNAPSHOT_VERSION,
            )
            return 0
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
