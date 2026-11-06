"""Snapshot do mês: cache do cálculo da comissão (Task 4).

`calcular_mes` lê cadastros + vendas + janelas e roda o motor (~13 s por mês); `obter_mes`
devolve o snapshot gravado em `comercial_snapshot` quando está em dia, senão recalcula e grava.
Toda escrita em cadastro chama `marcar_desatualizado`. O store é injetável para testes.
"""
from __future__ import annotations

import calendar
import json
from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import text

from logger import get_logger
from frontend.services.comercial.calculo import LinhaComissao, calcular

logger = get_logger("db")
_SP = ZoneInfo("America/Sao_Paulo")


@dataclass
class ResultadoMes:
    mes: date
    linhas: list[LinhaComissao]
    sem_data: list  # [(lançamento, produtos hotmart, produtos tmb)]
    gerado_em: datetime
    desatualizado: bool = False


# ---------------------------------------------------------------- serialização
_DEC = {f.name for f in fields(LinhaComissao) if "Decimal" in str(f.type)}


def linha_para_json(l: LinhaComissao) -> dict:
    d: dict = {}
    for f in fields(LinhaComissao):
        v = getattr(l, f.name)
        if isinstance(v, Decimal):
            v = str(v)
        elif isinstance(v, datetime):
            v = v.isoformat()
        d[f.name] = v
    return d


def linha_de_json(d: dict) -> LinhaComissao:
    kw = dict(d)
    for k in _DEC:
        if kw[k] is not None:
            kw[k] = Decimal(kw[k])
    kw["data"] = datetime.fromisoformat(kw["data"])
    return LinhaComissao(**kw)


def linhas_para_json(linhas: list[LinhaComissao]) -> str:
    return json.dumps([linha_para_json(l) for l in linhas], ensure_ascii=False)


def linhas_de_json(txt: str | list) -> list[LinhaComissao]:
    dados = json.loads(txt) if isinstance(txt, (str, bytes)) else txt
    return [linha_de_json(d) for d in dados]


def alertas_para_json(sem_data: list) -> str:
    return json.dumps([[a, sorted(b), sorted(c)] for a, b, c in sem_data], ensure_ascii=False)


def alertas_de_json(txt: str | list) -> list:
    dados = json.loads(txt) if isinstance(txt, (str, bytes)) else txt
    return [(a, frozenset(b), frozenset(c)) for a, b, c in dados]


# ---------------------------------------------------------------- cálculo
def _ultimo_dia(mes: date) -> date:
    return date(mes.year, mes.month, calendar.monthrange(mes.year, mes.month)[1])


def calcular_mes(mes: date, hoje: datetime) -> ResultadoMes:
    """Cadastros do banco + vendas do mês + janelas -> linhas. `hoje`: agora em SP."""
    from frontend.db_readers.comercial import ler_cadastros, ler_janelas, ler_vendas  # noqa: PLC0415

    ini, fim = mes.replace(day=1), _ultimo_dia(mes)
    cad = ler_cadastros()
    vendas = ler_vendas(ini, fim, transacoes_extra=frozenset(cad.atribuicoes), ofertas=cad.ofertas)
    janelas, sem_data = ler_janelas(ini, fim)
    linhas = calcular(vendas, cad, janelas, hoje)
    return ResultadoMes(ini, linhas, sem_data, hoje)


# ---------------------------------------------------------------- store
class Store(Protocol):
    def get(self, mes: date) -> ResultadoMes | None: ...
    def put(self, r: ResultadoMes) -> None: ...
    def marcar_desatualizado(self, mes: date | None) -> None: ...


class StoreBanco:
    """Snapshot em `comercial_snapshot` (banco operacional). Tabela ausente = sem snapshot."""

    def get(self, mes: date) -> ResultadoMes | None:
        from frontend.db import _get_users_engine  # noqa: PLC0415
        from frontend.db_readers.comercial import tabela_comercial_ausente  # noqa: PLC0415
        try:
            with _get_users_engine().connect() as c:
                row = c.execute(text(
                    "SELECT gerado_em, linhas, alertas, desatualizado FROM comercial_snapshot "
                    "WHERE mes = :mes"), {"mes": mes.replace(day=1)}).fetchone()
        except Exception as exc:
            if tabela_comercial_ausente(exc):
                return None
            raise
        if row is None:
            return None
        gerado, linhas, alertas, desat = row
        if gerado.tzinfo is not None:  # timestamptz volta com fuso; o resto do módulo usa SP naive
            gerado = gerado.astimezone(_SP).replace(tzinfo=None)
        return ResultadoMes(mes.replace(day=1), linhas_de_json(linhas), alertas_de_json(alertas),
                            gerado, bool(desat))

    def put(self, r: ResultadoMes) -> None:
        from frontend.db import _get_users_engine  # noqa: PLC0415
        from frontend.db_readers.comercial import SQL_SNAPSHOT_UPSERT, exigir_so_comercial  # noqa: PLC0415
        exigir_so_comercial(SQL_SNAPSHOT_UPSERT)
        with _get_users_engine().begin() as c:
            c.execute(text(SQL_SNAPSHOT_UPSERT),
                      {"mes": r.mes, "gerado_em": r.gerado_em.replace(tzinfo=_SP) if r.gerado_em.tzinfo is None else r.gerado_em, "linhas": linhas_para_json(r.linhas),
                       "alertas": alertas_para_json(r.sem_data)})

    def marcar_desatualizado(self, mes: date | None) -> None:
        from frontend.db import _get_users_engine  # noqa: PLC0415
        from frontend.db_readers import comercial as com  # noqa: PLC0415
        sql = com.SQL_SNAPSHOT_DESATUALIZAR_TODOS if mes is None else com.SQL_SNAPSHOT_DESATUALIZAR_MES
        com.exigir_so_comercial(sql)
        with _get_users_engine().begin() as c:
            c.execute(text(sql), {} if mes is None else {"mes": mes.replace(day=1)})


def agora_sp() -> datetime:
    return datetime.now(_SP).replace(tzinfo=None)


def obter_mes(mes: date, *, hoje: datetime | None = None, store: Store | None = None) -> ResultadoMes:
    """Snapshot em dia se houver; senão calcula, grava e devolve.

    GANCHO Task 7: mês fechado devolve as linhas congeladas (comercial_fechamentos) aqui,
    antes de olhar o snapshot."""
    store = store or StoreBanco()
    mes = mes.replace(day=1)
    r = store.get(mes)
    if r is not None and not r.desatualizado:
        return r
    return recalcular_mes(mes, hoje=hoje, store=store)


def recalcular_mes(mes: date, *, hoje: datetime | None = None, store: Store | None = None) -> ResultadoMes:
    """Calcula e grava o snapshot (ignora o existente). Falha ao gravar não derruba o cálculo."""
    store = store or StoreBanco()
    r = calcular_mes(mes.replace(day=1), hoje or agora_sp())
    try:
        store.put(r)
    except Exception:
        logger.exception("comercial: não gravou o snapshot de %s", mes)
    return r


def marcar_desatualizado(mes: date | None = None, *, store: Store | None = None) -> None:
    """Chamado por toda escrita em cadastro. None = todos os meses."""
    (store or StoreBanco()).marcar_desatualizado(mes.replace(day=1) if mes else None)
