"""Área Comercial — Inconsistências (Task 6): reivindicar, aprovar/recusar, atribuir, reembolso
a verificar, ajuste manual. Sem banco: um FakeBanco que entende SÓ as declarações exatas do
módulo (qualquer outro SQL estoura), então a rota roda as escritas de verdade sobre ele.
"""
import os

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

from datetime import date, datetime  # noqa: E402
from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402

import frontend.db_readers.comercial as com  # noqa: E402
from frontend.services.comercial import acesso as acesso_mod  # noqa: E402
from frontend.services.comercial import inconsistencias as inc  # noqa: E402
from frontend.services.comercial import snapshot as snap  # noqa: E402
from frontend.services.comercial import telas  # noqa: E402
from frontend.services.comercial.acesso import AcessoComercial  # noqa: E402
from frontend.services.comercial.calculo import LinhaComissao, calcular  # noqa: E402
from frontend.services.comercial.modelos import Cadastros, Venda  # noqa: E402
from frontend.services.comercial.snapshot import ResultadoMes  # noqa: E402
from frontend.services.comercial.tabelas import RegraPercentual, ValorBase  # noqa: E402


def _n(sql: str) -> str:
    return " ".join(str(sql).split())


# ---------------------------------------------------------------- FakeBanco
class _Res:
    def __init__(self, rows=(), rowcount=0):
        self._rows, self.rowcount = list(rows), rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeBanco:
    """Tabelas comercial_* em memória. Só aceita as declarações exatas do módulo."""

    def __init__(self):
        self.atrib: dict[tuple, dict] = {}
        self.decisoes: dict[tuple, dict] = {}
        self.ajustes: list[dict] = []
        self.historico: list[dict] = []
        self.sql: list[str] = []
        h = {
            com.SQL_ATRIB_LER: self._atrib_ler,
            com.SQL_ATRIB_REIVINDICAR: self._reivindicar,
            com.SQL_ATRIB_APROVAR: lambda p: self._decidir(p, "aprovada"),
            com.SQL_ATRIB_RECUSAR: lambda p: self._decidir(p, "recusada"),
            com.SQL_ATRIB_GESTOR: self._gestor,
            com.SQL_REEMBOLSO_LER_UM: self._reemb_ler,
            com.SQL_REEMBOLSO_UPSERT: self._reemb_upsert,
            com.SQL_AJUSTE_LER_ATIVO: self._aj_ler,
            com.SQL_AJUSTE_DESATIVAR: self._aj_desativar,
            com.SQL_AJUSTE_INSERIR: self._aj_inserir,
            com.SQL_HISTORICO_INSERIR: self._hist,
            com.SQL_TRANSACOES_PENDENTES: lambda p: _Res([(k[1],) for k, v in self.atrib.items()
                                                          if v["status"] == "pendente"]),
            com.SQL_FILA_PENDENTES: lambda p: _Res([self._fila(k, v) for k, v in self.atrib.items()
                                                    if v["status"] == "pendente"]),
            com.SQL_FILA_DO_VENDEDOR: lambda p: _Res([self._fila(k, v) for k, v in self.atrib.items()
                                                      if v["vendedor_codigo"] == p["codigo"]
                                                      and v["origem"] == "reivindicacao"]),
            com.SQL_HISTORICO_RECENTE: lambda p: _Res([(h["tabela"], h["registro_id"], h["campo"], h["antes"],
                                                        h["depois"], h["por"], datetime(2026, 11, 6, 10))
                                                       for h in reversed(self.historico)]),
            com.SQL_VENDEDORES_LISTA: lambda p: _Res([("AT4", "Ediléia"), ("AT9", "Jheniffer")]),
            com.SQL_CODIGOS_CONFLITO: lambda p: _Res([("T-CONF", "lead AT4", "lead AT9")]),
            com.SQL_FECH_DA_TRANSACAO: lambda p: _Res([]),  # Task 7b: nenhum mês fechado aqui
            com.SQL_FECH_ATIVOS: lambda p: _Res([]),
        }
        self.h = {_n(k): v for k, v in h.items()}

    # conexão
    def execute(self, stmt, params=None):
        s = _n(stmt)
        self.sql.append(s)
        if s not in self.h:
            raise AssertionError(f"SQL fora do esperado: {s[:120]}")
        return self.h[s](params or {})

    def connect(self):
        return self

    begin = connect

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    # handlers
    @staticmethod
    def _k(p):
        return (p["plataforma"], p["transacao"])

    def _fila(self, k, v):
        return (k[0], k[1], v["vendedor_codigo"], v["origem"], v["status"], v["pedido_por"],
                v.get("aprovado_por"), datetime(2026, 11, 6, 9), v.get("motivo"))

    def _atrib_ler(self, p):
        v = self.atrib.get(self._k(p))
        return _Res([(v["status"], v["vendedor_codigo"])] if v else [])

    def _reivindicar(self, p):
        if self._k(p) in self.atrib:
            return _Res(rowcount=0)
        self.atrib[self._k(p)] = {"vendedor_codigo": p["vendedor_codigo"], "origem": "reivindicacao",
                                  "status": "pendente", "pedido_por": p["por"]}
        return _Res(rowcount=1)

    def _decidir(self, p, novo):
        v = self.atrib.get(self._k(p))
        if not v or v["status"] != "pendente":
            return _Res(rowcount=0)
        v.update(status=novo, aprovado_por=p["por"], motivo=p.get("motivo"))
        return _Res(rowcount=1)

    def _gestor(self, p):
        v = self.atrib.get(self._k(p))
        if v and v["status"] == "aprovada":
            return _Res(rowcount=0)
        self.atrib[self._k(p)] = {"vendedor_codigo": p["vendedor_codigo"], "origem": "gestor",
                                  "status": "aprovada", "pedido_por": p["por"],
                                  "aprovado_por": p["por"], "motivo": p["motivo"]}
        return _Res(rowcount=1)

    def _reemb_ler(self, p):
        v = self.decisoes.get(self._k(p))
        return _Res([(v["decisao"],)] if v else [])

    def _reemb_upsert(self, p):
        self.decisoes[self._k(p)] = dict(p)
        return _Res(rowcount=1)

    def _aj_ler(self, p):
        return _Res([(a["pct"], a["valor_base"]) for a in self.ajustes if a["ativo"]
                     and (a["plataforma"], a["transacao"]) == self._k(p)])

    def _aj_desativar(self, p):
        n = 0
        for a in self.ajustes:
            if a["ativo"] and (a["plataforma"], a["transacao"]) == self._k(p):
                a["ativo"], n = False, n + 1
        return _Res(rowcount=n)

    def _aj_inserir(self, p):
        if any(a["ativo"] and (a["plataforma"], a["transacao"]) == self._k(p) for a in self.ajustes):
            raise AssertionError("índice parcial: dois ajustes ativos")
        self.ajustes.append({**p, "ativo": True})
        return _Res(rowcount=1)

    def _hist(self, p):
        self.historico.append(dict(p))
        return _Res(rowcount=1)


@pytest.fixture
def banco(monkeypatch):
    b = FakeBanco()
    monkeypatch.setattr(com, "_get_users_engine", lambda: b)
    return b


# ---------------------------------------------------------------- guarda (Ruling 8)
def test_todas_as_escritas_da_tela_passam_na_guarda():
    for sql in com.ESCRITAS_TELA:
        com.exigir_so_comercial(sql)


@pytest.mark.parametrize("quase", [
    # sem a trava de status: aprovaria de novo / sobrescreveria
    "UPDATE comercial_atribuicoes SET status = 'aprovada', aprovado_por = :por "
    "WHERE plataforma = :plataforma AND transacao = :transacao",
    # status vindo de parâmetro em vez de literal
    "UPDATE comercial_atribuicoes SET status = :status, aprovado_por = :por "
    "WHERE plataforma = :plataforma AND transacao = :transacao AND status = 'pendente'",
    # mesma forma em outra tabela
    "UPDATE users SET status = 'aprovada', aprovado_por = :por "
    "WHERE plataforma = :plataforma AND transacao = :transacao AND status = 'pendente'",
    # desativar todos os ajustes
    "UPDATE comercial_ajustes SET ativo = false",
    # upsert do gestor sem o WHERE (sobrescreveria aprovada)
    com.SQL_ATRIB_GESTOR.replace(" WHERE comercial_atribuicoes.status <> 'aprovada'", ""),
    # upsert do reembolso com comando a mais
    com.SQL_REEMBOLSO_UPSERT + "; DROP TABLE comercial_historico",
    com.SQL_AJUSTE_DESATIVAR + " OR true",
    "DELETE FROM comercial_ajustes WHERE ativo",
])
def test_quase_copias_sao_recusadas(quase):
    with pytest.raises(RuntimeError, match="recusou"):
        com.exigir_so_comercial(quase)


def test_escritas_passam_pela_guarda_ao_executar(banco, monkeypatch):
    vistas = []
    original = com.exigir_so_comercial
    monkeypatch.setattr(com, "exigir_so_comercial", lambda s: (vistas.append(_n(s)), original(s)))
    com.reivindicar("HP1", "hotmart", "AT4", "a@x")
    com.decidir_atribuicao("HP1", "hotmart", True, "g@x")
    com.atribuir_gestor("HP2", "hotmart", "AT9", "g@x", None)
    com.decidir_reembolso("HP3", "hotmart", "tira", "pediu no dia 2", "g@x")
    com.gravar_ajuste("HP4", "hotmart", D("0.10"), None, "outbound", "g@x")
    escritas = [s for s in banco.sql if not s.startswith("SELECT")]
    assert escritas == vistas  # nenhuma escrita sem passar pela guarda
    assert set(vistas) <= {_n(q) for q in com.ESCRITAS_TELA}


def test_ddl_novas_tabelas_e_indice_parcial():
    cols = com.colunas_do_ddl()
    assert set(cols["comercial_decisoes_reembolso"]) == {"plataforma", "transacao", "decisao", "justificativa",
                                                         "decidido_por", "decidido_em"}
    assert set(cols["comercial_ajustes"]) == {"id", "plataforma", "transacao", "pct", "valor_base",
                                              "justificativa", "criado_por", "criado_em", "ativo"}
    assert any("ux_comercial_ajustes_ativo" in d and "WHERE ativo" in d for d in com.DDL)
    for d in com.DDL:
        com.exigir_so_comercial(d)


# ---------------------------------------------------------------- escritas (sobre o FakeBanco)
def test_reivindicar_aprovar_e_aprovar_de_novo_nao_duplica(banco):
    com.reivindicar("HP1", "hotmart", "AT4", "edi@x")
    assert banco.atrib[("hotmart", "HP1")]["status"] == "pendente"
    assert com.decidir_atribuicao("HP1", "hotmart", True, "gestor@x") == "AT4"
    assert banco.atrib[("hotmart", "HP1")]["status"] == "aprovada"
    with pytest.raises(com.EscritaRecusada) as e:
        com.decidir_atribuicao("HP1", "hotmart", True, "gestor@x")
    assert e.value.codigo == "ja_aprovada"
    assert [h["depois"] for h in banco.historico] == ["pendente (AT4)", "aprovada (AT4)"]
    assert banco.historico[1]["por"] == "gestor@x"


@pytest.mark.parametrize("status,codigo", [("pendente", "ja_reivindicada"), ("aprovada", "ja_atribuida"),
                                           ("recusada", "ja_recusada")])
def test_reivindicar_de_novo_recusa(banco, status, codigo):
    banco.atrib[("hotmart", "HP1")] = {"vendedor_codigo": "AT9", "origem": "reivindicacao",
                                       "status": status, "pedido_por": "x"}
    with pytest.raises(com.EscritaRecusada) as e:
        com.reivindicar("HP1", "hotmart", "AT4", "edi@x")
    assert e.value.codigo == codigo
    assert banco.historico == []


def test_gestor_atribui_sobre_recusada_mas_nao_sobre_aprovada(banco):
    banco.atrib[("tmb", "9")] = {"vendedor_codigo": "AT9", "origem": "reivindicacao", "status": "recusada",
                                 "pedido_por": "x"}
    com.atribuir_gestor("9", "tmb", "AT4", "g@x", "conferido")
    assert banco.atrib[("tmb", "9")]["status"] == "aprovada"
    assert banco.historico[-1]["antes"] == "recusada (AT9)"
    with pytest.raises(com.EscritaRecusada):
        com.atribuir_gestor("9", "tmb", "AT9", "g@x")


def test_ajuste_desativa_o_anterior(banco):
    com.gravar_ajuste("HP4", "hotmart", D("0.10"), None, "outbound", "g@x")
    com.gravar_ajuste("HP4", "hotmart", None, D("1477"), "base à mão", "g@x")
    assert [a["ativo"] for a in banco.ajustes] == [False, True]
    assert banco.historico[-1]["antes"] == "pct=0.10; base="
    assert banco.historico[-1]["depois"] == "pct=; base=1477: base à mão"


# ---------------------------------------------------------------- motor: ajuste
def _venda(tx="HP1", valor="1726", cod="AT4", conflito=False, cancelada_em=None):
    return Venda("hotmart", tx, datetime(2026, 10, 5, 10), "1", "Mentoria", "COM. LEAD", cod, conflito,
                 "cartao_pix", None, D(valor), True, cancelada_em)


def _cad(**kw):
    regras = [RegraPercentual(1, "hotmart", "cartao_pix", "Ativa", D("0.04"), None, date(2026, 1, 1), None)]
    base = [ValorBase(1, "hotmart", D("1726"), D("1726"), "LEAD", date(2026, 1, 1), None)]
    return Cadastros({"AT4": "Ediléia"}, regras, base, [], {}, **kw)


HOJE = datetime(2026, 11, 30)


def test_ajuste_de_pct_troca_a_regra():
    [l] = calcular([_venda()], _cad(ajustes={"HP1": (D("0.10"), None)}), [], HOJE)
    assert (l.pct, l.valor, l.ajuste_manual, l.situacao) == (D("0.10"), D("172.60"), True, "elegivel")


def test_ajuste_de_base_torna_calculavel_venda_sem_valor_base():
    [sem] = calcular([_venda(valor="12.34")], _cad(), [], HOJE)
    assert sem.motivo == "sem_valor_base"
    [l] = calcular([_venda(valor="12.34")], _cad(ajustes={"HP1": (None, D("1477"))}), [], HOJE)
    assert (l.valor_base, l.pct, l.valor, l.situacao, l.ajuste_manual) == (D("1477"), D("0.04"), D("59.08"),
                                                                           "elegivel", True)
    assert l.valor_cobrado == D("12.34")


def test_ajuste_de_pct_resolve_sem_regra():
    c = _cad(ajustes={"HP1": (D("0.05"), None)})
    c.regras = []
    [l] = calcular([_venda()], c, [], HOJE)
    assert (l.situacao, l.valor, l.regra_id) == ("elegivel", D("86.30"), None)


def test_ajuste_nao_resolve_sem_codigo_nem_cancelada():
    [l] = calcular([_venda(cod=None)], _cad(ajustes={"HP1": (D("0.10"), D("1000"))}), [], HOJE)
    assert (l.situacao, l.motivo, l.valor) == ("inconsistente", "sem_codigo", D("0"))
    [c] = calcular([_venda(cancelada_em=datetime(2026, 10, 6))], _cad(ajustes={"HP1": (D("0.10"), None)}), [], HOJE)
    assert (c.situacao, c.valor) == ("cancelada", D("0"))


def test_sem_ajuste_linha_nao_marcada():
    [l] = calcular([_venda()], _cad(), [], HOJE)
    assert l.ajuste_manual is False


def test_snapshot_antigo_sem_campos_novos_carrega():
    [l] = calcular([_venda()], _cad(), [], HOJE)
    d = snap.linha_para_json(l)
    del d["ajuste_manual"], d["valor_cobrado"]
    velho = snap.linha_de_json(d)
    assert velho.ajuste_manual is False and velho.valor_cobrado is None
    assert snap.linhas_de_json(snap.linhas_para_json([l]))[0] == l


def test_ler_cadastros_carrega_decisoes_e_ajustes(monkeypatch):
    class Conn(FakeBanco):
        def __init__(self):
            super().__init__()
            vazio = lambda p: _Res([])  # noqa: E731
            for sql in ("SELECT codigo, nome FROM comercial_vendedores",
                        "SELECT codigo_do_preco, nome_deste_preco FROM comercial_ofertas",
                        "SELECT transacao, vendedor_codigo FROM comercial_atribuicoes WHERE status = 'aprovada'"):
                self.h[_n(sql)] = vazio
            self.h[_n(com.SQL_DECISOES_LER)] = lambda p: _Res([("HP9", "mantem")])
            self.h[_n(com.SQL_AJUSTES_ATIVOS)] = lambda p: _Res([("HP4", D("0.10"), None)])

        def execute(self, stmt, params=None):
            s = _n(stmt)
            if s.startswith("SELECT id,"):
                return _Res([])
            return super().execute(stmt, params)
    c = Conn()
    monkeypatch.setattr(com, "_get_users_engine", lambda: c)
    cad = com.ler_cadastros()
    assert cad.decisoes_reembolso == {"HP9": "mantem"}
    assert cad.ajustes == {"HP4": (D("0.10"), None)}


# ---------------------------------------------------------------- serviço
MASTER = AcessoComercial("master", None)
COORD = AcessoComercial("coordenador", None)
AT4 = AcessoComercial("vendedor", "AT4")


def _l(tx, cod, sit="elegivel", motivo=None, base="1000", papel="venda", benef=None, manual=False, plat="hotmart"):
    b = D(base) if base else None
    return LinhaComissao(tx, plat, papel, benef or {"AT4": "Ediléia", "AT9": "Jheniffer"}.get(cod, "(sem vendedor)"),
                         cod, datetime(2026, 10, 5, 10), "Ativa", "cartao_pix", "LEAD", b,
                         D("0.04") if sit != "inconsistente" else None,
                         D("40") if sit == "elegivel" else D("0"), sit, motivo, 1, manual,
                         valor_cobrado=D("89.90"))


def _linhas():
    return [
        _l("HP-EDI-1", "AT4"),
        _l("HP-JHE-REEMB", "AT9", "reembolso_a_verificar"),
        _l("HP-EDI-REEMB", "AT4", "reembolso_a_verificar"),
        _l("T-CONF", None, "inconsistente", "conflito_codigo", plat="tmb"),
        _l("HP-SEMBASE", "AT9", "inconsistente", "sem_valor_base", base=None),
        _l("HP-SEMREGRA", "AT4", "inconsistente", "sem_regra"),
        _l("HP-NOVO", "AT6", benef="Vendedor 6"),
        *[_l(f"HP-SEM-{i:03d}", None, "inconsistente", "sem_codigo") for i in range(250)],
    ]


def _res():
    return ResultadoMes(date(2026, 10, 1), _linhas(), [], datetime(2026, 11, 6, 9, 42))


def _fila(gestor):
    return {"pendentes": [{"transacao": "HP-SEM-001", "vendedor_codigo": "AT9", "status": "pendente"}] if gestor else [],
            "minhas": [] if gestor else [{"transacao": "HP-SEM-002", "vendedor_codigo": "AT4", "status": "pendente"},
                                         {"transacao": "HP-X", "vendedor_codigo": "AT9", "status": "pendente"}],
            "historico": [{"tabela": "t"}] if gestor else [], "vendedores": [], "com_pedido": {"HP-SEM-001"}}


def test_view_gestor_separa_secoes_e_limita_lista():
    v = inc.view_inconsistencias(_res(), telas.resolver_periodo("2026-10", None, None, date(2026, 11, 6)),
                                 MASTER, _fila(True), {"T-CONF": ("AT4", "AT9")})
    assert [l.transacao for l in v["reembolso"]] == ["HP-EDI-REEMB", "HP-JHE-REEMB"]
    assert [(c.linha.transacao, c.codigos) for c in v["conflitos"]] == [("T-CONF", ("AT4", "AT9"))]
    assert [l.transacao for l in v["sem_base"]] == ["HP-SEMBASE"]
    assert [l.transacao for l in v["sem_regra"]] == ["HP-SEMREGRA"]
    assert v["codigos_novos"] == [("AT6", "Vendedor 6")]
    assert v["sem_codigo_total"] == 250 and len(v["sem_codigo"]) == inc.LIMITE_LISTA
    assert v["sem_codigo_cortado"] is True
    assert len(v["pendentes"]) == 1 and v["historico"]


def test_view_vendedor_so_busca_e_proprios_pedidos():
    p = telas.resolver_periodo("2026-10", None, None, date(2026, 11, 6))
    v = inc.view_inconsistencias(_res(), p, AT4, _fila(False))
    assert v["sem_codigo"] == []  # sem busca, nada
    for chave in ("pendentes", "reembolso", "conflitos", "sem_base", "sem_regra", "codigos_novos", "historico"):
        assert v[chave] == [], chave
    assert [m["transacao"] for m in v["minhas"]] == ["HP-SEM-002"]  # o de AT9 cai mesmo se vier
    v = inc.view_inconsistencias(_res(), p, AT4, _fila(False), q="sem-01")
    assert {l.transacao for l in v["sem_codigo"]} == {f"HP-SEM-{i:03d}" for i in range(10, 20)}
    assert (v["sem_codigo_total"], v["sem_codigo_achadas"]) == (250, 10)  # total do mês não muda com a busca


@pytest.mark.parametrize("pct,base,esperado", [("10", "", (D("0.1"), None)), ("0,75", "", (D("0.0075"), None)),
                                               ("", "1.477,50", (None, D("1477.50"))), ("", "1477", (None, D("1477")))])
def test_ler_ajuste(pct, base, esperado):
    assert inc.ler_ajuste(pct, base) == esperado


@pytest.mark.parametrize("pct,base", [("", ""), ("abc", ""), ("101", ""), ("", "-5"), ("NaN", "")])
def test_ler_ajuste_invalido(pct, base):
    with pytest.raises(inc.EntradaInvalida):
        inc.ler_ajuste(pct, base)


def test_entrada():
    assert inc.plataforma_de("HP123") == "hotmart" and inc.plataforma_de("98765") == "tmb"
    assert inc.limpar_transacao(" hp123 ") == "HP123"
    assert inc.limpar_codigo("at 04") == "AT4"
    assert inc.codigo_do_pedido(AT4, "AT9") == "AT4"  # vendedor sempre para si
    assert inc.codigo_do_pedido(MASTER, "at9") == "AT9"
    for ruim in ("", "x' OR 1=1", "a" * 65):
        with pytest.raises(inc.EntradaInvalida):
            inc.limpar_transacao(ruim)


# ---------------------------------------------------------------- rotas
_USUARIOS = {"master@teste.local": MASTER, "coord@teste.local": COORD, "edileia@teste.local": AT4,
             "pri@teste.local": AcessoComercial("vendedor", "AT11"),
             "fin@teste.local": AcessoComercial("consulta")}


@pytest.fixture(scope="module")
def _app_client():
    from fastapi.testclient import TestClient

    from frontend.app import app

    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def cli(_app_client, banco, monkeypatch):
    import frontend.routes.comercial as rotas

    desat = []
    monkeypatch.setattr(telas, "ler_extras", lambda periodo, acesso: ({}, {}))  # bônus/meta: Task 7a
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: _res())
    monkeypatch.setattr(snap, "marcar_desatualizado", lambda mes=None, **kw: desat.append(mes))
    monkeypatch.setattr(inc, "linhas_guardadas", lambda mes: _linhas() if mes == date(2026, 10, 1) else None)
    monkeypatch.setattr(rotas, "_hoje", lambda: date(2026, 11, 6))
    monkeypatch.setattr(rotas, "get_launches", lambda: [])
    monkeypatch.setattr(acesso_mod, "acesso_comercial", lambda user, **kw: _USUARIOS.get((user or {}).get("email")))
    _app_client.desat = desat
    _app_client.banco = banco
    _app_client.cookies.clear()
    return _app_client


def _como(c, email, role="comercial"):
    from frontend.auth import _sign_session
    c.cookies.set("session_token", _sign_session("u-" + email, role, ["PI"], email))
    return c


ROTAS_POST = ["/comercial/reivindicar", "/comercial/atribuicoes/aprovar", "/comercial/atribuicoes/recusar",
              "/comercial/atribuir", "/comercial/reembolso", "/comercial/ajuste"]


def test_rotas_registradas():
    from frontend.auth import ROUTE_PERMISSIONS, _CMRC_AREA
    for p in ["/comercial/inconsistencias", *ROTAS_POST]:
        assert ROUTE_PERMISSIONS[p] == _CMRC_AREA


@pytest.mark.parametrize("rota", ROTAS_POST)
def test_sem_nivel_403_e_nada_grava(cli, rota):
    r = _como(cli, "ninguem@teste.local", "leitura").post(rota, data={"transacao": "HP1", "justificativa": "x",
                                                                        "motivo": "x", "decisao": "tira",
                                                                        "vendedor_codigo": "AT4", "pct": "10"})
    assert r.status_code == 403
    assert cli.banco.sql == [] and cli.desat == []


@pytest.mark.parametrize("rota", ROTAS_POST[1:])
def test_vendedor_nao_aprova_nem_decide(cli, rota):
    r = _como(cli, "edileia@teste.local").post(rota, data={"transacao": "HP1", "justificativa": "x", "motivo": "x",
                                                            "decisao": "tira", "vendedor_codigo": "AT4", "pct": "10"})
    assert r.status_code == 403
    assert cli.banco.sql == []


def test_fluxo_vendedor_reivindica_coordenador_aprova(cli):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar",
                                               data={"transacao": "HP-SEM-007", "vendedor_codigo": "AT9",
                                                     "mes": "2026-10"})
    assert r.status_code == 303
    assert r.headers["location"] == "/comercial/inconsistencias?mes=2026-10&ok=reivindicada"
    a = cli.banco.atrib[("hotmart", "HP-SEM-007")]
    assert (a["status"], a["vendedor_codigo"], a["origem"], a["pedido_por"]) == (
        "pendente", "AT4", "reivindicacao", "edileia@teste.local")  # código do form ignorado
    assert cli.desat == []  # pendente não muda o cálculo

    r = _como(cli, "coord@teste.local").post("/comercial/atribuicoes/aprovar",
                                             data={"transacao": "HP-SEM-007", "mes": "2026-10"})
    assert r.status_code == 303 and "ok=aprovada" in r.headers["location"]
    assert a["status"] == "aprovada" and a["aprovado_por"] == "coord@teste.local"
    assert [h["depois"] for h in cli.banco.historico] == ["pendente (AT4)", "aprovada (AT4)"]
    assert cli.desat == [date(2026, 10, 1)]  # mês da venda

    r = _como(cli, "coord@teste.local").post("/comercial/atribuicoes/aprovar",
                                             data={"transacao": "HP-SEM-007", "mes": "2026-10"})
    assert r.status_code == 303 and "erro=ja_aprovada" in r.headers["location"]
    assert len(cli.banco.historico) == 2 and len(cli.banco.atrib) == 1
    assert cli.desat == [date(2026, 10, 1)]


def test_mensagem_ja_aprovada_aparece_na_pagina(cli):
    html = _como(cli, "master@teste.local").get("/comercial/inconsistencias?mes=2026-10&erro=ja_aprovada").text
    assert inc.MENSAGENS_ERRO["ja_aprovada"].split(" — ")[0] in html


def test_mensagem_livre_na_url_nao_aparece(cli):
    html = _como(cli, "master@teste.local").get("/comercial/inconsistencias?mes=2026-10&erro=<b>golpe</b>").text
    assert "<b>golpe" not in html and 'class="cm-msg' not in html  # só código conhecido vira mensagem


def test_reivindicar_venda_ja_sua_recusa(cli):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar",
                                               data={"transacao": "HP-EDI-1", "mes": "2026-10"})
    assert "erro=ja_e_sua" in r.headers["location"]
    assert cli.banco.atrib == {}


def test_reivindicar_duplicado(cli):
    _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": "HP-SEM-001", "mes": "2026-10"})
    r = _como(cli, "master@teste.local").post("/comercial/reivindicar",
                                              data={"transacao": "HP-SEM-001", "vendedor_codigo": "AT9", "mes": "2026-10"})
    assert "erro=ja_reivindicada" in r.headers["location"]
    assert cli.banco.atrib[("hotmart", "HP-SEM-001")]["vendedor_codigo"] == "AT4"


def test_recusar_exige_motivo(cli):
    cli.banco.atrib[("hotmart", "HP1")] = {"vendedor_codigo": "AT4", "origem": "reivindicacao",
                                           "status": "pendente", "pedido_por": "x"}
    r = _como(cli, "master@teste.local").post("/comercial/atribuicoes/recusar",
                                              data={"transacao": "HP1", "motivo": "   ", "mes": "2026-10"})
    assert r.status_code == 400 and "obrigatório" in r.text
    assert cli.banco.atrib[("hotmart", "HP1")]["status"] == "pendente" and cli.banco.historico == []
    r = _como(cli, "master@teste.local").post("/comercial/atribuicoes/recusar",
                                              data={"transacao": "HP1", "motivo": "não é dela", "mes": "2026-10"})
    assert r.status_code == 303
    assert cli.banco.atrib[("hotmart", "HP1")]["motivo"] == "não é dela"
    assert cli.desat == []


def test_ajuste_sem_justificativa_400(cli):
    r = _como(cli, "master@teste.local").post("/comercial/ajuste",
                                              data={"transacao": "HP-SEMBASE", "valor_base": "1477", "mes": "2026-10"})
    assert r.status_code == 400
    assert cli.banco.sql == [] and cli.desat == []


def test_ajuste_grava_e_invalida_mes(cli):
    r = _como(cli, "master@teste.local").post("/comercial/ajuste",
                                              data={"transacao": "HP-SEMBASE", "valor_base": "1.477,00", "pct": "",
                                                    "justificativa": "base à mão", "mes": "2026-10"})
    assert r.status_code == 303 and "ok=ajuste" in r.headers["location"]
    [a] = cli.banco.ajustes
    assert (a["valor_base"], a["pct"], a["por"]) == (D("1477.00"), None, "master@teste.local")
    assert cli.banco.historico[-1]["tabela"] == "comercial_ajustes"
    assert cli.desat == [date(2026, 10, 1)]


def test_venda_fora_do_mes_invalida_todos(cli):
    r = _como(cli, "master@teste.local").post("/comercial/ajuste",
                                              data={"transacao": "HP-OUTRO-MES", "pct": "10",
                                                    "justificativa": "outbound", "mes": "2026-10"})
    assert r.status_code == 303
    assert cli.desat == [None]


def test_reembolso_decide_com_justificativa(cli):
    r = _como(cli, "master@teste.local").post("/comercial/reembolso",
                                              data={"transacao": "HP-JHE-REEMB", "decisao": "talvez",
                                                    "justificativa": "x", "mes": "2026-10"})
    assert r.status_code == 400
    r = _como(cli, "master@teste.local").post("/comercial/reembolso",
                                              data={"transacao": "HP-JHE-REEMB", "decisao": "tira",
                                                    "justificativa": "", "mes": "2026-10"})
    assert r.status_code == 400 and cli.banco.decisoes == {}
    r = _como(cli, "master@teste.local").post("/comercial/reembolso",
                                              data={"transacao": "HP-JHE-REEMB", "decisao": "tira",
                                                    "justificativa": "pediu no 3º dia", "mes": "2026-10"})
    assert r.status_code == 303
    assert cli.banco.decisoes[("hotmart", "HP-JHE-REEMB")]["decisao"] == "tira"
    assert cli.banco.historico[-1]["depois"] == "tira: pediu no 3º dia"
    assert cli.desat == [date(2026, 10, 1)]


def test_atribuir_resolve_conflito(cli):
    r = _como(cli, "coord@teste.local").post("/comercial/atribuir",
                                             data={"transacao": "T-CONF", "vendedor_codigo": "AT9", "mes": "2026-10"})
    assert r.status_code == 303 and "ok=atribuida" in r.headers["location"]
    assert cli.banco.atrib[("tmb", "T-CONF")]["status"] == "aprovada"
    assert cli.desat == [date(2026, 10, 1)]


def test_pagina_master(cli):
    cli.banco.atrib[("hotmart", "HP-SEM-001")] = {"vendedor_codigo": "AT9", "origem": "reivindicacao",
                                                  "status": "pendente", "pedido_por": "jhe@x"}
    r = _como(cli, "master@teste.local").get("/comercial/inconsistencias?mes=2026-10")
    assert r.status_code == 200, r.text[:300]
    html = r.text
    for trecho in ("Reembolso a verificar", "HP-JHE-REEMB", "Mantém", "Tira", "Escolher AT4", "Escolher AT9",
                   "HP-SEMBASE", "HP-SEMREGRA", "Ajuste manual", "Vendedor 6", "Reivindicações pendentes",
                   "Aprovar", "Recusar", "Histórico recente", 'action="/comercial/atribuir"',
                   'href="/comercial/inconsistencias"'):
        assert trecho in html, trecho
    assert html.count('<td style="white-space:nowrap;">HP-SEM-') == inc.LIMITE_LISTA + 1  # 200 da lista + 1 pedido pendente; nunca as 250
    assert 'name="inicio"' not in html  # sem período livre nesta tela


def test_pagina_vendedor_isolada(cli):
    cli.banco.atrib[("hotmart", "HP-X")] = {"vendedor_codigo": "AT9", "origem": "reivindicacao",
                                            "status": "pendente", "pedido_por": "jhe@x"}
    cli.banco.atrib[("hotmart", "HP-MEU")] = {"vendedor_codigo": "AT4", "origem": "reivindicacao",
                                              "status": "recusada", "pedido_por": "edileia@teste.local",
                                              "motivo": "sem prova"}
    html = _como(cli, "edileia@teste.local").get("/comercial/inconsistencias?mes=2026-10").text
    assert "HP-MEU" in html and "sem prova" in html
    for proibido in ("HP-X", "HP-JHE-REEMB", "HP-EDI-REEMB", "T-CONF", "HP-SEMBASE", "HP-SEMREGRA",
                     "Jheniffer", "jhe@x", "Histórico recente", "Mantém", "/comercial/atribuir", "/comercial/ajuste",
                     "HP-SEM-0"):
        assert proibido not in html, proibido
    html = _como(cli, "edileia@teste.local").get("/comercial/inconsistencias?mes=2026-10&q=SEM-00").text
    assert "HP-SEM-005" in html and 'action="/comercial/reivindicar"' in html


def test_pagina_sem_nivel_403(cli):
    assert _como(cli, "ninguem@teste.local", "leitura").get("/comercial/inconsistencias").status_code == 403


def test_menu_tem_inconsistencias(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial/ranking").text
    assert 'href="/comercial/inconsistencias"' in html


# ---------------------------------------------------------------- fix round 1
# Ruling 14 — reivindicação só de venda achada no mês e reivindicável
def _recusa(fn, *a):
    with pytest.raises(com.EscritaRecusada) as e:
        fn(*a)
    return e.value.codigo


def test_conferir_reivindicacao_ramos():
    f = inc.conferir_reivindicacao
    sem = _l("HP-S", None, "inconsistente", "sem_codigo")
    conf = _l("T-C", None, "inconsistente", "conflito_codigo", plat="tmb")
    f(sem, "AT4")  # sem código: pode
    assert _recusa(f, None, "AT4") == "venda_nao_encontrada"
    assert _recusa(f, _l("HP-M", "AT9", manual=True), "AT4") == "ja_atribuida"
    assert _recusa(f, _l("HP-O", "AT9"), "AT4") == "de_outro"
    assert _recusa(f, _l("HP-O", "AT9", "inconsistente", "sem_valor_base", base=None), "AT4") == "de_outro"
    assert _recusa(f, _l("HP-E", "AT4"), "AT4") == "ja_e_sua"
    f(conf, "AT4", ("AT4", "AT9"))  # conflito: quem pede é um dos dois
    assert _recusa(f, conf, "AT11", ("AT4", "AT9")) == "de_outro"
    assert _recusa(f, conf, "AT4", None) == "conflito_gestor"
    assert _recusa(f, conf, "AT4", ("AT4", None)) == "conflito_gestor"


@pytest.mark.parametrize("mes", ["", "   ", "lixo", "2025-12", "2026-12"])
def test_reivindicar_sem_mes_valido_400(cli, mes):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": "HP-SEM-007", "mes": mes})
    assert r.status_code == 400
    assert cli.banco.atrib == {} and cli.banco.historico == []


def test_reivindicar_sem_mes_mensagem(cli):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": "HP-SEM-007"})
    assert r.status_code == 400 and "Informe o mês da venda" in r.text


def test_reivindicar_venda_fora_do_mes_recusa(cli):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar",
                                               data={"transacao": "HP-NAO-EXISTE", "mes": "2026-10"})
    assert "erro=venda_nao_encontrada" in r.headers["location"]
    assert cli.banco.atrib == {}


def test_reivindicar_sem_snapshot_guardado_usa_calculo_do_mes(cli, monkeypatch):
    chamadas = []
    monkeypatch.setattr(inc, "linhas_guardadas", lambda mes: None)
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: (chamadas.append(mes), _res())[1])
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar",
                                               data={"transacao": "HP-SEM-003", "mes": "2026-10"})
    assert "ok=reivindicada" in r.headers["location"]
    assert chamadas == [date(2026, 10, 1)]


@pytest.mark.parametrize("tx", ["HP-JHE-REEMB", "HP-SEMBASE", "HP-NOVO"])
def test_reivindicar_venda_de_outro_vendedor(cli, tx):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": tx, "mes": "2026-10"})
    assert "erro=de_outro" in r.headers["location"]
    assert cli.banco.atrib == {}


def test_reivindicar_conflito_com_o_proprio_codigo(cli):
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": "T-CONF", "mes": "2026-10"})
    assert "ok=reivindicada" in r.headers["location"]
    assert cli.banco.atrib[("tmb", "T-CONF")]["vendedor_codigo"] == "AT4"


def test_reivindicar_conflito_sem_o_proprio_codigo(cli):
    r = _como(cli, "pri@teste.local").post("/comercial/reivindicar", data={"transacao": "T-CONF", "mes": "2026-10"})
    assert "erro=de_outro" in r.headers["location"]
    assert cli.banco.atrib == {}


def test_reivindicar_conflito_sem_os_dois_codigos(cli, monkeypatch):
    monkeypatch.setattr(com, "ler_codigos_conflito", lambda pedidos: {})
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": "T-CONF", "mes": "2026-10"})
    assert "erro=conflito_gestor" in r.headers["location"]
    assert cli.banco.atrib == {}


def test_reivindicar_venda_atribuida_a_mao(cli, monkeypatch):
    ls = _linhas() + [_l("HP-MANUAL", "AT9", manual=True)]
    monkeypatch.setattr(inc, "linhas_guardadas", lambda mes: ls)
    r = _como(cli, "edileia@teste.local").post("/comercial/reivindicar", data={"transacao": "HP-MANUAL", "mes": "2026-10"})
    assert "erro=ja_atribuida" in r.headers["location"]


def test_pendentes_mostram_dono_atual(cli):
    cli.banco.atrib[("hotmart", "HP-JHE-REEMB")] = {"vendedor_codigo": "AT4", "origem": "reivindicacao",
                                                    "status": "pendente", "pedido_por": "edi@x"}
    cli.banco.atrib[("hotmart", "HP-SEM-004")] = {"vendedor_codigo": "AT4", "origem": "reivindicacao",
                                                  "status": "pendente", "pedido_por": "edi@x"}
    cli.banco.atrib[("hotmart", "HP-OUTRO-MES")] = {"vendedor_codigo": "AT4", "origem": "reivindicacao",
                                                    "status": "pendente", "pedido_por": "edi@x"}
    html = _como(cli, "master@teste.local").get("/comercial/inconsistencias?mes=2026-10").text
    tabela = html[html.index("Reivindicações pendentes"):html.index("Vendas sem código (")]
    assert "Dono atual da venda" in tabela
    assert "Jheniffer (AT9)" in tabela and "venda de outro vendedor" in tabela
    assert "sem código" in tabela and "fora deste mês" in tabela


def test_view_pendente_com_dono():
    p = telas.resolver_periodo("2026-10", None, None, date(2026, 11, 6))
    fila = {"pendentes": [{"transacao": "HP-JHE-REEMB", "vendedor_codigo": "AT4", "status": "pendente"},
                          {"transacao": "HP-SEM-001", "vendedor_codigo": "AT4", "status": "pendente"}]}
    [a, b] = inc.view_inconsistencias(_res(), p, MASTER, fila)["pendentes"]
    assert (a["dono"], a["dono_motivo"], a["de_outro"]) == ("Jheniffer (AT9)", None, True)
    assert (b["dono"], b["dono_motivo"], b["de_outro"]) == ("sem código", "sem_codigo", False)


# Important 2 — ajuste concorrente
def test_ajuste_concorrente_vira_recusa(banco):
    from sqlalchemy.exc import IntegrityError

    def estoura(p):
        raise IntegrityError("INSERT", {}, Exception('duplicate key value violates "ux_comercial_ajustes_ativo"'))
    banco.h[_n(com.SQL_AJUSTE_INSERIR)] = estoura
    assert _recusa(com.gravar_ajuste, "HP4", "hotmart", D("0.1"), None, "x", "g@x") == "ajuste_concorrente"
    assert banco.historico == []


def test_ajuste_concorrente_rota_303(cli):
    from sqlalchemy.exc import IntegrityError

    def estoura(p):
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))
    cli.banco.h[_n(com.SQL_AJUSTE_INSERIR)] = estoura
    r = _como(cli, "master@teste.local").post("/comercial/ajuste", data={"transacao": "HP-SEMBASE", "pct": "10",
                                                                          "justificativa": "x", "mes": "2026-10"})
    assert r.status_code == 303 and "erro=ajuste_concorrente" in r.headers["location"]
    assert cli.desat == []
    assert "ajuste_concorrente" in inc.MENSAGENS_ERRO


# Important 3 — ponto de milhar
@pytest.mark.parametrize("pct,base,esperado", [
    ("", "1.477", (None, D("1477"))), ("", "12.345", (None, D("12345"))), ("", "123.456", (None, D("123456"))),
    ("", "1477", (None, D("1477"))), ("", "1.477,50", (None, D("1477.50"))), ("", "1.5", (None, D("1.5"))),
    ("", "89.90", (None, D("89.90"))), ("4,5", "", (D("0.045"), None)), ("4.5", "", (D("0.045"), None)),
])
def test_numero_ponto_de_milhar(pct, base, esperado):
    assert inc.ler_ajuste(pct, base) == esperado


def test_venda_da_camila_aparece_em_sem_codigo_e_pode_ser_reivindicada():
    from dataclasses import replace  # noqa: PLC0415
    v = Venda("hotmart", "HP1", datetime(2026, 10, 5, 10), "6856971", "Mentoria",
              "COM. LEAD - Camila", None, False, "cartao_pix", None, D("1726"), True, None)
    cad = Cadastros({"AT4": "Edileia"}, [RegraPercentual(1, "hotmart", "cartao_pix", "Ativa", D("0.04"), None,
                                                          date(2026, 1, 1), None)],
                    [ValorBase(1, "hotmart", D("1726"), D("1726"), "LEAD", date(2026, 1, 1), None)], [], {})
    l = calcular([v], cad, [], datetime(2026, 11, 30))[0]
    assert l.papel == "ia"
    assert inc.sem_codigo([l], None) == [l]
    inc.conferir_reivindicacao(l, "AT4")
    assert inc.localizar([l], "HP1") == l
    assert inc.sem_codigo([replace(l, situacao="cancelada")], None) == []


# ---------------------------------------------------------------- nível consulta (Financeiro/RH)
def test_pagina_consulta_ve_tudo_sem_botoes(cli):
    cli.banco.atrib[("hotmart", "HP-SEM-001")] = {"vendedor_codigo": "AT9", "origem": "reivindicacao",
                                                  "status": "pendente", "pedido_por": "jhe@x"}
    r = _como(cli, "fin@teste.local").get("/comercial/inconsistencias?mes=2026-10")
    assert r.status_code == 200, r.text[:300]
    html = r.text
    for trecho in ("Reembolso a verificar", "HP-JHE-REEMB", "HP-SEMBASE", "HP-SEMREGRA",
                   "Reivindicações pendentes", "Histórico recente", "decisão do gestor"):
        assert trecho in html, trecho
    for proibido in ('action="/comercial/reembolso"', 'action="/comercial/atribuir"', 'action="/comercial/ajuste"',
                     'action="/comercial/atribuicoes/aprovar"', 'action="/comercial/atribuicoes/recusar"',
                     'action="/comercial/reivindicar"', "Escolher AT4"):
        assert proibido not in html, proibido


@pytest.mark.parametrize("rota", ROTAS_POST)
def test_consulta_nao_grava(cli, rota):
    r = _como(cli, "fin@teste.local").post(rota, data={"transacao": "HP-JHE-REEMB", "justificativa": "x",
                                                       "motivo": "x", "decisao": "tira", "mes": "2026-10",
                                                       "vendedor_codigo": "AT4", "pct": "10"})
    assert r.status_code == 403
    assert cli.banco.sql == [] and cli.desat == []
