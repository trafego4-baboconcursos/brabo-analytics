"""Cache em memória dos meses guardados (Desempenho lento, 10/11/26): relê só quando a versão
do mês muda; store injetado não usa cache."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from frontend.services.comercial import snapshot as snap

SET = date(2026, 9, 1)
NOV = date(2026, 11, 1)


class _Store:
    def __init__(self):
        self.lidas = []

    def fechamento(self, mes):
        self.lidas.append(("fech", mes))
        return None

    def get(self, mes):
        self.lidas.append(("get", mes))
        return snap.ResultadoMes(mes, [], [], datetime(2026, 11, 10, 8))


@pytest.fixture
def banco(monkeypatch):
    st = _Store()
    versoes = {SET: ((datetime(2026, 10, 1, 8), False, None), None),
               NOV: ((datetime(2026, 11, 10, 8), False, None), None)}
    monkeypatch.setattr(snap, "StoreBanco", lambda: st)
    monkeypatch.setattr(snap, "versoes_guardadas", lambda: versoes)
    snap.limpar_cache()
    yield st, versoes
    snap.limpar_cache()


def test_ler_guardado_relê_so_quando_a_versao_muda(banco):
    st, versoes = banco
    a = snap.ler_guardado(SET, versoes=versoes)
    b = snap.ler_guardado(SET, versoes=versoes)
    assert a is b and st.lidas == [("fech", SET), ("get", SET)]
    novas = {**versoes, SET: ((datetime(2026, 11, 10, 9), True, None), None)}  # invalidado
    snap.ler_guardado(SET, versoes=novas)
    assert len(st.lidas) == 4


def test_ler_guardado_sem_versao_do_mes_e_none_sem_ir_ao_banco(banco):
    st, versoes = banco
    assert snap.ler_guardado(date(2026, 5, 1), versoes=versoes) is None and st.lidas == []


def test_store_injetado_nao_usa_cache(banco):
    st, versoes = banco
    outro = _Store()
    snap.ler_guardado(SET, store=outro, versoes=versoes)
    snap.ler_guardado(SET, store=outro, versoes=versoes)
    assert len(outro.lidas) == 4 and st.lidas == []


def test_obter_mes_em_dia_sai_da_memoria(banco):
    st, versoes = banco
    hoje = datetime(2026, 11, 10, 15)
    a = snap.obter_mes(NOV, hoje=hoje)
    b = snap.obter_mes(NOV, hoje=hoje)
    assert a is b and st.lidas == [("fech", NOV), ("get", NOV)]


def test_obter_mes_de_ontem_nao_sai_da_memoria(banco, monkeypatch):
    st, _versoes = banco
    calc = []
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: calc.append(mes) or
                        snap.ResultadoMes(mes, [], [], datetime(2026, 11, 11, 9)))
    snap.obter_mes(NOV, hoje=datetime(2026, 11, 11, 9))  # snapshot de 10/11: velho
    snap.obter_mes(NOV, hoje=datetime(2026, 11, 11, 9))
    assert calc == [NOV, NOV]  # nunca devolve do cache um snapshot de dia anterior
