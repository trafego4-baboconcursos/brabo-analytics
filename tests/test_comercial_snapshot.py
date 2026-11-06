"""Snapshot do mês (Task 4): serialização exata, obter_mes com store falso, guarda do SQL."""
from datetime import date, datetime
from decimal import Decimal

import pytest

import frontend.db_readers.comercial as com
import frontend.services.comercial.snapshot as snap
from frontend.services.comercial.calculo import LinhaComissao
from frontend.services.comercial.snapshot import ResultadoMes


def _linha(**kw):
    base = dict(transacao="HP1", plataforma="hotmart", papel="venda", beneficiario="Ediléia",
                vendedor_codigo="AT4", data=datetime(2026, 10, 3, 14, 5, 9), tipo="ativa",
                modalidade="a_vista", categoria="PMQ", valor_base=Decimal("89.90"),
                pct=Decimal("0.0350"), valor=Decimal("3.14650"), situacao="elegivel",
                motivo="x", regra_id=7, atribuicao_manual=True)
    base.update(kw)
    return LinhaComissao(**base)


def test_round_trip_exato_com_tudo_e_com_none():
    ls = [_linha(), _linha(transacao="T2", vendedor_codigo=None, tipo=None, categoria=None,
                           valor_base=None, pct=None, motivo=None, regra_id=None,
                           atribuicao_manual=False, valor=Decimal("0"))]
    assert snap.linhas_de_json(snap.linhas_para_json(ls)) == ls


def test_alertas_round_trip():
    sd = [("PES-SET-26", frozenset({"1", "2"}), frozenset())]
    assert snap.alertas_de_json(snap.alertas_para_json(sd)) == sd


class FakeStore:
    def __init__(self, r=None):
        self.r, self.puts, self.marcas = r, [], []

    def get(self, mes):
        return self.r

    def put(self, r):
        self.puts.append(r)
        self.r = r

    def marcar_desatualizado(self, mes):
        self.marcas.append(mes)


@pytest.fixture
def calc(monkeypatch):
    chamadas = []

    def fake(mes, hoje):
        chamadas.append(mes)
        return ResultadoMes(mes, [_linha()], [], hoje)
    monkeypatch.setattr(snap, "calcular_mes", fake)
    return chamadas


HOJE = datetime(2026, 11, 6, 10)


def test_usa_snapshot_quando_existe(calc):
    st = FakeStore(ResultadoMes(date(2026, 10, 1), [], [], HOJE))
    r = snap.obter_mes(date(2026, 10, 15), hoje=HOJE, store=st)
    assert r is st.r and calc == [] and st.puts == []


def test_calcula_e_grava_sem_snapshot(calc):
    st = FakeStore()
    r = snap.obter_mes(date(2026, 10, 1), hoje=HOJE, store=st)
    assert calc == [date(2026, 10, 1)] and st.puts == [r] and len(r.linhas) == 1


def test_recalcula_se_desatualizado(calc):
    st = FakeStore(ResultadoMes(date(2026, 10, 1), [], [], HOJE, desatualizado=True))
    r = snap.obter_mes(date(2026, 10, 1), hoje=HOJE, store=st)
    assert calc and not r.desatualizado and st.puts


def test_falha_ao_gravar_nao_derruba(calc):
    class Ruim(FakeStore):
        def put(self, r):
            raise RuntimeError("banco fora")
    r = snap.obter_mes(date(2026, 10, 1), hoje=HOJE, store=Ruim())
    assert len(r.linhas) == 1


def test_marcar_desatualizado_repassa_primeiro_dia():
    st = FakeStore()
    snap.marcar_desatualizado(date(2026, 10, 20), store=st)
    snap.marcar_desatualizado(store=st)
    assert st.marcas == [date(2026, 10, 1), None]


# ---------------------------------------------------------------- guarda
@pytest.mark.parametrize("sql", [com.SQL_SNAPSHOT_UPSERT, com.SQL_SNAPSHOT_DESATUALIZAR_MES,
                                 com.SQL_SNAPSHOT_DESATUALIZAR_TODOS,
                                 "  " + com.SQL_SNAPSHOT_DESATUALIZAR_MES.replace(" ", "\n  ") + ";"])
def test_guarda_aceita_as_registradas(sql):
    com.exigir_so_comercial(sql)


@pytest.mark.parametrize("sql", [
    com.SQL_SNAPSHOT_DESATUALIZAR_MES.replace("comercial_snapshot", "comercial_vendedores"),
    com.SQL_SNAPSHOT_DESATUALIZAR_MES.replace("comercial_snapshot", "hotmart_oficial"),
    com.SQL_SNAPSHOT_DESATUALIZAR_MES + " OR true",
    com.SQL_SNAPSHOT_DESATUALIZAR_TODOS.replace("= false", "= true"),
    com.SQL_SNAPSHOT_UPSERT + " RETURNING mes",
    com.SQL_SNAPSHOT_UPSERT.replace("comercial_snapshot", "users"),
    "UPDATE comercial_snapshot SET linhas = '[]'",
])
def test_guarda_recusa_variacoes(sql):
    with pytest.raises(RuntimeError):
        com.exigir_so_comercial(sql)


def test_ddl_do_snapshot_confere_com_o_guarda():
    cols = com.colunas_do_ddl()["comercial_snapshot"]
    assert cols["linhas"] == "jsonb" and cols["mes"] == "date"


def test_meses_do_prewarm_virada_de_ano():
    from frontend.services.prewarm import meses_comercial
    assert meses_comercial(datetime(2027, 1, 20, 9)) == [date(2027, 1, 1), date(2026, 12, 1)]
