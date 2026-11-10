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

    def fechamento(self, mes):  # Task 7b: nenhum mês fechado aqui
        return None

    def inicio_calculo(self):
        return datetime(2026, 11, 6, 9, 59)

    def put(self, r, calculo_inicio):
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
        def put(self, r, calculo_inicio):
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
    com.SQL_SNAPSHOT_DESATUALIZAR_TODOS + " WHERE true",
    com.SQL_SNAPSHOT_DESATUALIZAR_TODOS.replace("= true", "= false"),
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


# ---------------------------------------------------------------- fix round 1
def test_snapshot_de_dia_anterior_e_recalculado(calc):
    st = FakeStore(ResultadoMes(date(2026, 10, 1), [], [], datetime(2026, 11, 5, 23, 59)))
    snap.obter_mes(date(2026, 10, 1), hoje=HOJE, store=st)
    assert calc == [date(2026, 10, 1)] and st.puts


def test_gerado_em_e_hora_real_nao_o_hoje_passado(monkeypatch):
    monkeypatch.setattr(snap, "agora_sp", lambda: datetime(2030, 1, 1, 12))
    monkeypatch.setattr("frontend.db_readers.comercial.ler_cadastros",
                        lambda: __import__("frontend.services.comercial.modelos", fromlist=["x"]).Cadastros())
    monkeypatch.setattr("frontend.db_readers.comercial.ler_vendas", lambda *a, **k: [])
    monkeypatch.setattr("frontend.db_readers.comercial.ler_janelas", lambda *a, **k: ([], []))
    monkeypatch.setattr("frontend.db_readers.comercial.meses_fechados", lambda: {})
    monkeypatch.setattr("frontend.db_readers.comercial.ler_linhas_fechadas", lambda meses: {})
    r = snap.calcular_mes(date(2026, 10, 1), datetime(2026, 11, 6))
    assert r.gerado_em == datetime(2030, 1, 1, 12)


def test_invalidacao_durante_o_calculo_mantem_desatualizado(monkeypatch):
    """Simula a semântica do upsert: desatualizado = invalidado_em > calculo_inicio."""
    class StoreCorrida(FakeStore):
        invalidado_em = None
        gravado_desat = None

        def put(self, r, calculo_inicio):
            self.gravado_desat = self.invalidado_em is not None and self.invalidado_em > calculo_inicio
            self.r = ResultadoMes(r.mes, r.linhas, r.sem_data, r.gerado_em, self.gravado_desat)

    st = StoreCorrida()

    def calcula_e_invalida(mes, hoje):
        st.invalidado_em = datetime(2026, 11, 6, 10, 0)  # cadastro mudou no meio do cálculo
        return ResultadoMes(mes, [_linha()], [], hoje)
    monkeypatch.setattr(snap, "calcular_mes", calcula_e_invalida)
    snap.recalcular_mes(date(2026, 10, 1), hoje=HOJE, store=st)
    assert st.gravado_desat is True
    # e a próxima leitura recalcula
    assert snap.obter_mes(date(2026, 10, 1), hoje=HOJE, store=st).desatualizado is False


def test_registradas_novas_e_copias_recusadas():
    com.exigir_so_comercial(com.SQL_MIGRACAO_SNAPSHOT_INVALIDADO)
    for ruim in (com.SQL_MIGRACAO_SNAPSHOT_INVALIDADO.replace("comercial_snapshot", "users"),
                 com.SQL_MIGRACAO_SNAPSHOT_INVALIDADO.replace("ADD COLUMN IF NOT EXISTS invalidado_em timestamptz",
                                                              "DROP COLUMN linhas"),
                 com.SQL_SNAPSHOT_UPSERT.replace("> :calculo_inicio", "IS NOT NULL")):
        with pytest.raises(RuntimeError):
            com.exigir_so_comercial(ruim)
    assert "invalidado_em = now()" in com.SQL_SNAPSHOT_DESATUALIZAR_MES


def test_store_get_ignora_snapshot_de_formato_antigo(monkeypatch):
    class Eng:
        def connect(self):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, *a, **k):
            class R:
                def fetchone(s):
                    return (datetime(2026, 11, 6), [{"transacao": "x"}], [], False)  # faltam campos
            return R()
    monkeypatch.setattr("frontend.db._get_users_engine", lambda: Eng())
    assert snap.StoreBanco().get(date(2026, 10, 1)) is None


def test_criar_tabelas_migra_antes_de_conferir():
    from tests.test_comercial_gravacao import FakeConn, _colunas_iguais_ao_ddl
    rows = [r for r in _colunas_iguais_ao_ddl() if r[:2] != ("comercial_snapshot", "invalidado_em")]

    class Conn(FakeConn):
        def execute(self, stmt, params=None):
            res = super().execute(stmt, params)
            if str(stmt).startswith("ALTER TABLE"):
                self.colunas.append(("comercial_snapshot", "invalidado_em", "timestamp with time zone"))
            return res
    c = Conn(colunas=rows)
    com.criar_tabelas(c)  # sem a migração a conferência estouraria
    assert any(s.startswith("ALTER TABLE comercial_snapshot") for s in c.sql)


# ---------------------------------------------------------------- prewarm
def test_warm_comercial_tenta_os_dois_meses_e_loga_erro(monkeypatch):
    import asyncio
    import frontend.services.prewarm as pw
    tentados = []

    def fake(mes, *, hoje=None, store=None):
        tentados.append(mes)
        if len(tentados) == 1:
            raise RuntimeError("banco fora")
    monkeypatch.setattr(snap, "recalcular_mes", fake)
    asyncio.run(pw.warm_comercial("teste"))
    assert len(tentados) == 2 and tentados[0] > tentados[1]
    assert pw._COMERCIAL_EM_CURSO is False


def test_warm_comercial_nao_reentra(monkeypatch):
    import asyncio
    import frontend.services.prewarm as pw
    monkeypatch.setattr(pw, "_COMERCIAL_EM_CURSO", True)
    monkeypatch.setattr(snap, "recalcular_mes", lambda *a, **k: pytest.fail("reentrou"))
    asyncio.run(pw.warm_comercial("teste"))
    assert pw._COMERCIAL_EM_CURSO is True


def test_ler_guardado_devolve_snapshot_velho_sem_recalcular(calc):
    velho = ResultadoMes(date(2026, 9, 1), [_linha()], [], datetime(2026, 10, 1), desatualizado=True)
    st = FakeStore(velho)
    r = snap.ler_guardado(date(2026, 9, 15), store=st)
    assert r is velho and calc == [] and st.puts == []


def test_ler_guardado_none_sem_snapshot(calc):
    assert snap.ler_guardado(date(2026, 9, 1), store=FakeStore()) is None and calc == []


def test_ler_guardado_prefere_o_congelado(calc):
    congelado = ResultadoMes(date(2026, 9, 1), [], [], datetime(2026, 10, 2), fechado=True)

    class Fechado(FakeStore):
        def fechamento(self, mes):
            return congelado
    assert snap.ler_guardado(date(2026, 9, 1), store=Fechado(ResultadoMes(date(2026, 9, 1), [], [], HOJE))) is congelado
