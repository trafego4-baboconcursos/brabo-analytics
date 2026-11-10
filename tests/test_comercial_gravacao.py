"""Gravação dos cadastros do comercial (Task 3): conferência de colunas, guarda de tabela,
handler estreito de tabela ausente e CLI da carga. Tudo com fakes, sem banco."""
from datetime import date
from decimal import Decimal

import re

import pytest

import frontend.db_readers.comercial as com
import scripts.comercial_carga_inicial as carga
from frontend.services.comercial.modelos import Cadastros
from frontend.services.comercial.tabelas import Participacao, RegraPercentual, ValorBase


# ---------------------------------------------------------------- fakes
class _Res:
    def __init__(self, rows=(), rowcount=1, scalar=None):
        self._rows, self.rowcount, self._scalar = list(rows), rowcount, scalar

    def fetchall(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class FakeConn:
    """`ja_existem`: quantas linhas de cada tabela já estão no banco (2ª carga = todas)."""

    def __init__(self, colunas=(), ja_existem=None):
        self.sql: list[str] = []
        self.params: list = []
        self.colunas = list(colunas)
        self.total: dict[str, int] = dict(ja_existem or {})
        self.ja_existem = dict(ja_existem or {})

    def execute(self, stmt, params=None):
        s = str(stmt)
        self.sql.append(s)
        self.params.append(params)
        if "information_schema.columns" in s:
            return _Res(self.colunas)
        m = re.match(r"SELECT count\(\*\) FROM (\w+)", s)
        if m:
            return _Res(scalar=self.total.get(m.group(1), 0))
        m = re.match(r"INSERT INTO (\w+) \(([^)]*)\)", s)
        if m:
            t, ncol = m.group(1), len(m.group(2).split(","))
            linhas = len(params) // ncol
            novas = max(linhas - self.ja_existem.get(t, 0), 0)
            self.total[t] = self.total.get(t, 0) + novas
            return _Res(rowcount=novas)
        return _Res()


class FakeEngine:
    def __init__(self, conn):
        self.conn, self.begins = conn, 0

    def begin(self):
        eng = self

        class _Ctx:
            def __enter__(self):
                eng.begins += 1
                return eng.conn

            def __exit__(self, *a):
                return False
        return _Ctx()


def _colunas_iguais_ao_ddl():
    return [(t, c, tipo) for t, cols in com.colunas_do_ddl().items() for c, tipo in cols.items()]


# ---------------------------------------------------------------- Ruling 5: colunas
def test_colunas_do_ddl_cobre_todas_as_tabelas():
    cols = com.colunas_do_ddl()
    assert set(cols) == {"comercial_vendedores", "comercial_regras_percentual", "comercial_valores_base",
                         "comercial_participacoes", "comercial_atribuicoes", "comercial_ofertas",
                         "comercial_acessos", "comercial_historico", "comercial_snapshot",
                         "comercial_decisoes_reembolso", "comercial_ajustes",
                         "comercial_janela_reativa", "comercial_metas", "comercial_bonus",
                         "comercial_fechamentos"}
    assert cols["comercial_atribuicoes"] == {
        "transacao": "text", "plataforma": "text", "vendedor_codigo": "text", "origem": "text",
        "status": "text", "pedido_por": "text", "aprovado_por": "text",
        "criado_em": "timestamp with time zone", "motivo": "text",
        "conexao": "text", "telefone_contato": "text", "justificativa": "text"}
    assert cols["comercial_regras_percentual"]["categorias"] == "ARRAY"
    assert cols["comercial_regras_percentual"]["id"] == "integer"
    assert cols["comercial_historico"]["id"] == "bigint"
    assert "CHECK" not in cols["comercial_acessos"] and set(cols["comercial_acessos"]) == {
        "email", "nivel", "vendedor_codigo", "criado_por", "criado_em"}


def test_divergencias_vazia_quando_igual_ou_ausente():
    esperado = com.colunas_do_ddl()
    assert com.divergencias_de_colunas({}) == []
    assert com.divergencias_de_colunas({"comercial_ofertas": dict(esperado["comercial_ofertas"])}) == []


def test_divergencias_coluna_faltando_sobrando_e_tipo():
    of = dict(com.colunas_do_ddl()["comercial_ofertas"])
    del of["codigo_at"]
    of["extra"] = "text"
    of["origem"] = "integer"
    dif = com.divergencias_de_colunas({"comercial_ofertas": of})
    texto = " | ".join(dif)
    assert "codigo_at" in texto and "extra" in texto and "origem" in texto
    assert all("comercial_ofertas" in d for d in dif)


def test_criar_tabelas_aborta_antes_de_qualquer_ddl_se_coluna_diverge():
    rows = [r for r in _colunas_iguais_ao_ddl() if r[:2] != ("comercial_regras_percentual", "forca_tipo")]
    conn = FakeConn(colunas=rows)
    with pytest.raises(RuntimeError, match="forca_tipo"):
        com.criar_tabelas(conn)
    assert not any(s.lstrip().upper().startswith("CREATE") for s in conn.sql)


def test_criar_tabelas_roda_ddl_quando_colunas_batem():
    conn = FakeConn(colunas=_colunas_iguais_ao_ddl())
    com.criar_tabelas(conn)
    assert sum(1 for s in conn.sql if s.lstrip().upper().startswith("CREATE")) == len(com.DDL)


# ---------------------------------------------------------------- guarda: só comercial_*
@pytest.mark.parametrize("sql", com.DDL + [
    "INSERT INTO comercial_vendedores (codigo) VALUES (:c) ON CONFLICT DO NOTHING",
    "INSERT INTO comercial_vendedores (codigo) VALUES (:c) ON CONFLICT DO NOTHING;",
    com._SQL_COLUNAS,
    "SELECT count(*) FROM comercial_vendedores",
])
def test_guarda_aceita_comercial(sql):
    com.exigir_so_comercial(sql)


def test_guarda_aceita_tudo_que_o_writer_emite():
    """Toda instrução real: DDL, consulta de colunas e, por tabela, count + INSERT multi-linha."""
    emitidas = list(com.DDL) + [com._SQL_COLUNAS]
    for tabela, (colunas, linhas) in carga.linhas_para_gravar(_cad(), {"9001"}).items():
        emitidas.append(f"SELECT count(*) FROM {tabela}")
        emitidas.append(carga._insert_multiplo(tabela, colunas, linhas)[0])
    assert len(emitidas) == len(com.DDL) + 1 + 2 * len(carga.TABELAS)
    for sql in emitidas:
        com.exigir_so_comercial(sql)


@pytest.mark.parametrize("sql", [
    "INSERT INTO users (email) VALUES (:e)",
    "UPDATE launch_config SET x = 1",
    "CREATE INDEX ix ON hotmart_oficial (x)",
    "CREATE INDEX IF NOT EXISTS ix ON hotmart_oficial (x)",
    "CREATE TABLE IF NOT EXISTS outra (a text)",
    "DELETE FROM comercial_vendedores",
    "DROP TABLE comercial_vendedores",
    "TRUNCATE comercial_vendedores",
    "INSERT INTO comercial_vendedores SELECT * FROM users",
    "INSERT INTO comercial_vendedores (codigo) SELECT email FROM users",
    "SELECT count(*) FROM users",
    "SELECT * FROM comercial_vendedores",
    # sondas da revisão (bypass da guarda antiga)
    "INSERT INTO comercial_x VALUES (1); TRUNCATE users",
    "INSERT INTO comercial_x (a) VALUES (1); INSERT INTO \"users\" VALUES (1)",
    "WITH d AS (DELETE FROM comercial_vendedores RETURNING *) INSERT INTO comercial_x (a) VALUES (1)",
    "INSERT INTO comercial_x (a) VALUES (1); SELECT pg_terminate_backend(1)",
    "INSERT INTO comercial_x (a) VALUES (1); GRANT ALL ON comercial_x TO public",
    "INSERT INTO comercial_x (a) VALUES (pg_terminate_backend(1))",
    "GRANT ALL ON comercial_x TO public",
    "REVOKE ALL ON comercial_x FROM public",
    "COPY comercial_x FROM '/tmp/x'",
    "ALTER TABLE comercial_x ADD COLUMN y text",
    "INSERT INTO \"comercial_x\" (a) VALUES (1)",
    "CREATE TABLE IF NOT EXISTS comercial_x (a integer REFERENCES users(id))",
])
def test_guarda_recusa_outras_tabelas_e_destrutivos(sql):
    with pytest.raises(RuntimeError):
        com.exigir_so_comercial(sql)


# ---------------------------------------------------------------- handler estreito
class _EngErro:
    def __init__(self, exc):
        self.exc = exc

    def connect(self):
        raise self.exc


def _erro_pg(msg, sql="SELECT codigo, nome FROM comercial_vendedores"):
    from sqlalchemy.exc import ProgrammingError
    return ProgrammingError(sql, {}, Exception(msg))


def test_ler_cadastros_tabela_ausente_devolve_vazio(monkeypatch):
    monkeypatch.setattr(com, "_get_users_engine",
                        lambda: _EngErro(_erro_pg('relation "comercial_vendedores" does not exist')))
    assert com.ler_cadastros() == Cadastros()


@pytest.mark.parametrize("msg", [
    'column "forca_tipo" does not exist',
    'column "x" of relation "comercial_vendedores" does not exist',
    'relation "users" does not exist',
])
def test_ler_cadastros_outro_does_not_exist_propaga(monkeypatch, msg):
    monkeypatch.setattr(com, "_get_users_engine", lambda: _EngErro(_erro_pg(msg)))
    with pytest.raises(Exception, match="does not exist"):
        com.ler_cadastros()


def test_acesso_erro_de_coluna_propaga(monkeypatch):
    import frontend.services.comercial.acesso as ac
    ac.limpar_cache()

    def lanca(email):
        raise _erro_pg('column "vendedor_codigo" does not exist',
                       "SELECT nivel, vendedor_codigo FROM comercial_acessos WHERE lower(email) = :e")
    monkeypatch.setattr(ac, "_ler_banco", lanca)
    with pytest.raises(Exception, match="vendedor_codigo"):
        ac.acesso_comercial({"role": "comercial", "email": "a@x.com"})


# ---------------------------------------------------------------- gravar
def _cad():
    return Cadastros(
        vendedores={"AT4": "Ediléia", "AT12": "Rafael Batista"},
        regras=[RegraPercentual(1, "hotmart", "cartao_pix", "Ativa", Decimal("0.05"), "AT13",
                                date(2026, 1, 1), date(2026, 10, 31),
                                frozenset({"APOSTILA Z", "APOSTILA A", "APOSTILA M"}), "Ativa")],
        valores_base=[ValorBase(1, "hotmart", Decimal("89.90"), Decimal("1477"), "LEAD",
                                date(2026, 1, 1), None)],
        participacoes=[Participacao(1, "Rafael Batista", Decimal("0.003"), Decimal("0.001"),
                                    date(2026, 1, 1), None, "AT12")],
        atribuicoes={"HP1": "AT4", "9001": "AT4"},
        ofertas={"P1": "COM. LEAD - AT9"},
    )


def _linhas(params: dict) -> list[dict]:
    """Parâmetros `<col>_<i>` do INSERT multi-linha -> lista de dicts por linha."""
    out: dict[int, dict] = {}
    for k, v in params.items():
        col, i = k.rsplit("_", 1)
        out.setdefault(int(i), {})[col] = v
    return [out[i] for i in sorted(out)]


def test_gravar_uma_transacao_um_insert_por_tabela_e_contagens(monkeypatch):
    import frontend.services.comercial.acesso as ac
    limpou = []
    monkeypatch.setattr(ac, "limpar_cache", lambda: limpou.append(1))
    conn = FakeConn()
    eng = FakeEngine(conn)
    r = carga.gravar(_cad(), {"9001"}, engine=eng)
    assert eng.begins == 1 and limpou == [1]
    for s in conn.sql:
        com.exigir_so_comercial(s)
    ins = {}
    for s, p in zip(conn.sql, conn.params):
        if s.startswith("INSERT"):
            t = s.split()[2]
            assert t not in ins, f"mais de um INSERT em {t}"
            assert s.rstrip().endswith("ON CONFLICT DO NOTHING")
            ins[t] = _linhas(p)
    assert set(ins) == set(carga.TABELAS)
    assert r == {"comercial_vendedores": (2, 0), "comercial_regras_percentual": (1, 0),
                 "comercial_valores_base": (1, 0), "comercial_participacoes": (1, 0),
                 "comercial_ofertas": (1, 0), "comercial_atribuicoes": (2, 0),
                 "comercial_acessos": (2, 0)}
    assert ins["comercial_regras_percentual"][0]["categorias"] == ["APOSTILA A", "APOSTILA M", "APOSTILA Z"]
    assert ins["comercial_participacoes"][0]["beneficiario_codigo"] == "AT12"
    atr = {l["transacao"]: l for l in ins["comercial_atribuicoes"]}
    assert atr["9001"]["plataforma"] == "tmb" and atr["HP1"]["plataforma"] == "hotmart"
    assert all(l["origem"] == "planilha" and l["status"] == "aprovada" for l in atr.values())
    assert {l["email"]: l["nivel"] for l in ins["comercial_acessos"]} == {
        "comercial_brabo@aprovasim.com": "master", "comercial2@aprovasim.com": "coordenador"}
    assert {l["codigo"]: l["ativo"] for l in ins["comercial_vendedores"]} == {"AT4": True, "AT12": False}
    assert ins["comercial_ofertas"][0] == {"codigo_do_preco": "P1", "nome_deste_preco": "COM. LEAD - AT9",
                                          "codigo_at": "AT9", "origem": "planilha"}


def test_gravar_de_novo_conta_ja_existentes():
    tudo = {t: 99 for t in carga.TABELAS}
    conn = FakeConn(colunas=_colunas_iguais_ao_ddl(), ja_existem=tudo)
    r = carga.gravar(_cad(), {"9001"}, engine=FakeEngine(conn))
    assert r["comercial_vendedores"] == (0, 2) and r["comercial_acessos"] == (0, 2)
    assert all(novas == 0 for novas, _ in r.values())


def test_insert_multiplo_monta_um_comando():
    sql, p = carga._insert_multiplo("comercial_x", ["a", "b"], [{"a": 1, "b": 2}, {"a": 3, "b": None}])
    assert sql == ("INSERT INTO comercial_x (a, b) VALUES (:a_0,:b_0),(:a_1,:b_1) "
                   "ON CONFLICT DO NOTHING")
    assert p == {"a_0": 1, "b_0": 2, "a_1": 3, "b_1": None}


def test_gravar_aborta_sem_insert_se_colunas_divergem():
    rows = [r for r in _colunas_iguais_ao_ddl() if r[1] != "beneficiario_codigo"]
    conn = FakeConn(colunas=rows)
    with pytest.raises(RuntimeError):
        carga.gravar(_cad(), set(), engine=FakeEngine(conn))
    assert not any(s.startswith("INSERT") or s.lstrip().upper().startswith("CREATE") for s in conn.sql)


def test_acessos_iniciais_minusculos():
    assert all(e == e.lower().strip() for e, _ in carga.ACESSOS)


# ---------------------------------------------------------------- CLI
def test_main_sem_flag_sai_2(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--pasta", "p"])
    assert carga.main() == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_main_dry_run_e_gravar_juntos_erro(monkeypatch):
    monkeypatch.setattr("sys.argv", ["x", "--pasta", "p", "--dry-run", "--gravar"])
    with pytest.raises(SystemExit) as e:
        carga.main()
    assert e.value.code == 2


def test_main_gravar_chama_gravar(monkeypatch, capsys):
    import pandas as pd
    chamadas = []
    vendas = pd.DataFrame({"transacao": ["HP1"], "nome": ["Ediléia"], "mes_ano": ["10 - Outubro"]})
    monkeypatch.setattr(carga, "_montar", lambda p: (_cad(), vendas, {"9001"}))
    monkeypatch.setattr(carga, "gravar", lambda cad, ped, engine=None: chamadas.append(ped)
                        or {"comercial_vendedores": (2, 0)})
    import frontend.services.comercial.snapshot as snap
    marcou = []
    monkeypatch.setattr(snap, "marcar_desatualizado", lambda *a, **k: marcou.append(a))
    monkeypatch.setattr("sys.argv", ["x", "--pasta", "p", "--gravar"])
    assert carga.main() == 0
    assert chamadas == [{"9001"}]
    assert marcou == [()]
    assert "comercial_vendedores" in capsys.readouterr().out


def test_main_dry_run_nao_grava(monkeypatch):
    import pandas as pd
    vendas = pd.DataFrame({"transacao": ["HP1"], "nome": ["Ediléia"], "mes_ano": ["10 - Outubro"]})
    monkeypatch.setattr(carga, "_montar", lambda p: (_cad(), vendas, {"9001"}))
    monkeypatch.setattr(carga, "gravar", lambda *a, **k: pytest.fail("dry-run gravou"))
    monkeypatch.setattr("sys.argv", ["x", "--pasta", "p", "--dry-run"])
    assert carga.main() == 0


# ---------------------------------------------------------------- Ruling 23
def test_gravar_nao_semeia_acessos_se_a_tabela_tem_linhas():
    """Ruling 23: acesso removido na tela não volta ao rodar --gravar de novo."""
    conn = FakeConn(colunas=_colunas_iguais_ao_ddl(), ja_existem={"comercial_acessos": 1})
    r = carga.gravar(_cad(), {"9001"}, engine=FakeEngine(conn))
    assert not [s for s in conn.sql if s.startswith("INSERT INTO comercial_acessos")]
    assert r["comercial_acessos"] == (0, 2)  # não semeado: conta como já existentes
    assert r["comercial_vendedores"] == (2, 0)  # as demais seguem ON CONFLICT DO NOTHING


def test_gravar_semeia_acessos_com_tabela_vazia():
    conn = FakeConn(colunas=_colunas_iguais_ao_ddl())
    r = carga.gravar(_cad(), {"9001"}, engine=FakeEngine(conn))
    assert len([s for s in conn.sql if s.startswith("INSERT INTO comercial_acessos")]) == 1
    assert r["comercial_acessos"] == (2, 0)


def test_migrar_so_ddl_e_migracoes():
    conn = FakeConn(colunas=_colunas_iguais_ao_ddl())
    eng = FakeEngine(conn)
    carga.migrar(engine=eng)
    assert eng.begins == 1
    for s in conn.sql:
        com.exigir_so_comercial(s) if not s.lstrip().upper().startswith("SELECT") else None
        assert not s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")), s
        assert not s.startswith("SELECT count")
    feitos = {" ".join(s.split()) for s in conn.sql}
    for _t, sql in com.MIGRACOES:
        assert " ".join(sql.split()) in feitos
    for ddl in com.DDL:
        assert " ".join(ddl.split()) in feitos


def test_main_migrar_nao_le_planilha(monkeypatch, capsys):
    chamadas = []
    monkeypatch.setattr(carga, "_montar", lambda p: pytest.fail("--migrar leu a planilha"))
    monkeypatch.setattr(carga, "gravar", lambda *a, **k: pytest.fail("--migrar gravou dados"))
    monkeypatch.setattr(carga, "migrar", lambda engine=None: chamadas.append(1))
    monkeypatch.setattr("sys.argv", ["x", "--migrar"])
    assert carga.main() == 0
    assert chamadas == [1]


def test_main_migrar_e_gravar_juntos_erro(monkeypatch):
    monkeypatch.setattr("sys.argv", ["x", "--pasta", "p", "--migrar", "--gravar"])
    with pytest.raises(SystemExit) as e:
        carga.main()
    assert e.value.code == 2


def test_main_gravar_sem_pasta_sai_2(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--gravar"])
    assert carga.main() == 2
