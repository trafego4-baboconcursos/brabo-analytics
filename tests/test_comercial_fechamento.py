"""Área Comercial — fechar o mês, reabrir e estorno (Task 7b, Ruling 17). Sem banco: o FakeBanco da
Task 7a (só as declarações exatas, volta atrás na exceção) com a tabela comercial_fechamentos.
"""
import os

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

import json  # noqa: E402
from dataclasses import replace  # noqa: E402
from datetime import date, datetime, timedelta  # noqa: E402
from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402

import frontend.db_readers.comercial as com  # noqa: E402
from frontend.services.comercial import acesso as acesso_mod  # noqa: E402
from frontend.services.comercial import fechamento as fech  # noqa: E402
from frontend.services.comercial import snapshot as snap  # noqa: E402
from frontend.services.comercial import telas  # noqa: E402
from frontend.services.comercial.acesso import AcessoComercial  # noqa: E402
from frontend.services.comercial.calculo import LinhaComissao, resumo_por_beneficiario  # noqa: E402
from frontend.services.comercial.modelos import Cadastros, Venda  # noqa: E402
from frontend.services.comercial.snapshot import ResultadoMes  # noqa: E402
from tests.test_comercial_regras_tela import FakeBanco  # noqa: E402

OUT, NOV, SET, DEZ = date(2026, 10, 1), date(2026, 11, 1), date(2026, 9, 1), date(2026, 12, 1)
HOJE = datetime(2026, 11, 6, 15)
MASTER = AcessoComercial("master")
COORD = AcessoComercial("coordenador")
AT4 = AcessoComercial("vendedor", "AT4")


def _l(tx, cod="AT4", base="2000", sit="elegivel", papel="venda", benef=None, pct="0.04", dia=5, mes=10):
    valor = D(base) * D(pct) if sit in ("elegivel", "prevista", "reembolso_a_verificar") else D("0")
    return LinhaComissao(tx, "hotmart", papel, benef or {"AT4": "Ediléia", "AT9": "Jheniffer"}[cod], cod,
                         datetime(2026, mes, dia, 10), "Ativa", "cartao_pix", "LEAD", D(base), D(pct), valor,
                         sit, None, 1, False)


def _linhas_out():
    return [_l("HP-EDI-1", sit="elegivel", dia=5),
            _l("HP-EDI-PREV", sit="prevista", dia=29),
            _l("HP-EDI-PREV", sit="prevista", dia=29, papel="participacao", benef="Rafael Batista", pct="0.003"),
            _l("HP-JHE-1", "AT9", "5000", dia=6),
            _l("HP-CANC", sit="cancelada", dia=7)]


def _res(linhas=None, mes=OUT):
    return ResultadoMes(mes, _linhas_out() if linhas is None else linhas, [], datetime(2026, 11, 6, 9, 42))


@pytest.fixture
def banco(monkeypatch):
    b = FakeBanco()
    monkeypatch.setattr(com, "_get_users_engine", lambda: b)
    return b


def _congelar(banco, mes, linhas, ativo=True, bonus=None):
    banco.fechamentos[mes] = {
        "ativo": ativo, "fechado_por": "coord@teste.local", "fechado_em": datetime(2026, mes.month % 12 + 1, 2, 10),
        "linhas": json.loads(snap.linhas_para_json(linhas)), "bonus": json.loads(fech.bonus_para_json(bonus or {})),
        "totais": {}, "reaberto_por": None, "reaberto_em": None, "motivo_reabertura": None}


# ---------------------------------------------------------------- guarda e DDL
def test_ddl_e_escritas_passam_na_guarda():
    cols = com.colunas_do_ddl()["comercial_fechamentos"]
    assert cols == {"mes": "date", "ativo": "boolean", "fechado_por": "text",
                    "fechado_em": "timestamp with time zone", "linhas": "jsonb", "bonus": "jsonb", "totais": "jsonb",
                    "reaberto_por": "text", "reaberto_em": "timestamp with time zone", "motivo_reabertura": "text"}
    for sql in com.ESCRITAS_FECHAMENTO:
        com.exigir_so_comercial(sql)


@pytest.mark.parametrize("quase", [
    com.SQL_FECH_REABRIR.replace(" AND ativo", ""),
    com.SQL_FECH_REABRIR.replace("WHERE mes = :mes AND ativo", ""),
    com.SQL_FECH_GRAVAR.replace(" WHERE NOT comercial_fechamentos.ativo", ""),
    "UPDATE comercial_fechamentos SET linhas = :linhas WHERE mes = :mes",
    "DELETE FROM comercial_fechamentos WHERE mes = :mes",
])
def test_quase_copias_recusadas(quase):
    with pytest.raises(RuntimeError, match="recusou"):
        com.exigir_so_comercial(quase)


# ---------------------------------------------------------------- fechar
def test_fechar_recusa_com_reembolso_a_verificar(banco, monkeypatch):
    linhas = _linhas_out() + [_l("HP-AV", sit="reembolso_a_verificar"), _l("HP-AV2", sit="reembolso_a_verificar")]
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: _res(linhas))
    with pytest.raises(fech.AVerificar) as e:
        fech.fechar(OUT, "coord@teste.local", HOJE)
    assert e.value.qtd == 2
    assert banco.fechamentos == {} and banco.historico == [] and banco.escritas() == []


def test_fechar_so_mes_que_terminou(banco, monkeypatch):
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: pytest.fail("não devia calcular"))
    for m in (NOV, DEZ, date(2025, 12, 1)):
        with pytest.raises(com.EscritaRecusada, match="mes_nao_terminou"):
            fech.fechar(m, "coord@teste.local", HOJE)
    _congelar(banco, OUT, _linhas_out())
    with pytest.raises(com.EscritaRecusada, match="ja_fechado"):
        fech.fechar(OUT, "coord@teste.local", HOJE)


def test_fechar_congela_de_calculo_novo_e_obter_mes_devolve_congelado(banco, monkeypatch):
    calculos = []
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: (calculos.append(mes), _res())[1])
    banco.bonus[("AT4", OUT)] = {"valor": D("150"), "justificativa": "campanha"}
    t = fech.fechar(OUT, "coord@teste.local", HOJE)
    assert calculos == [OUT]  # cálculo novo, não o snapshot guardado
    # pago = elegível + prevista + bônus (vendas); participação à parte
    assert t["elegivel"] == "280.00" and t["prevista"] == "80.00" and t["bonus"] == "150.00"
    assert t["total_pago"] == "510.00" and t["participacao"] == "6.00" and t["linhas"] == 5
    f = banco.fechamentos[OUT]
    assert f["ativo"] and f["fechado_por"] == "coord@teste.local" and len(f["linhas"]) == 5
    assert f["bonus"] == {"AT4": {"valor": "150", "nome": "Ediléia", "justificativa": "campanha"}}
    h = banco.historico[-1]
    assert (h["tabela"], h["registro_id"], h["campo"], h["antes"]) == ("comercial_fechamentos", "2026-10", "ativo", None)
    assert h["depois"].startswith("fechado: 5 linhas") and h["por"] == "coord@teste.local"

    # depois de fechado: nunca recalcula, e regra/bônus novos não mudam o mês
    monkeypatch.setattr(snap, "calcular_mes", lambda *a, **k: pytest.fail("mês fechado recalculado"))
    com.nova_versao_regra(1, D("0.10"), NOV, "coord@teste.local")
    banco.bonus[("AT4", OUT)] = {"valor": D("999"), "justificativa": None}  # (na tela, recusado; aqui direto)
    r = snap.obter_mes(OUT, hoje=HOJE)
    assert r.fechado and r.fechado_por == "coord@teste.local"
    assert r.linhas == _res().linhas
    assert r.bonus == {"AT4": {"valor": D("150.00"), "nome": "Ediléia", "justificativa": "campanha"}}
    v = telas.view_comissoes(r, telas.resolver_periodo("2026-10", None, None, NOV), MASTER, None,
                             {"AT4": {"valor": D("999"), "nome": "Ediléia", "justificativa": None}}, [], hoje=HOJE.date())
    assert v["kpis"]["bonus"] == D("150.00") and v["kpis"]["total"] == D("510.00")
    assert {r_["codigo"]: r_["a_pagar"] for r_ in v["vendedores"]} == {"AT4": D("80") + D("80") + D("150"),
                                                                      "AT9": D("200")}
    assert v["fechar"] is None and v["reabre"] is True and v["edita_bonus"] is False


def test_reabrir_e_fechar_de_novo(banco, monkeypatch):
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: _res())
    fech.fechar(OUT, "coord@teste.local", HOJE)
    with pytest.raises(ValueError):
        com.reabrir_mes(OUT, "  ", "coord@teste.local")
    com.reabrir_mes(OUT, "faltou uma venda", "master@teste.local")
    assert banco.fechamentos[OUT]["ativo"] is False and snap.StoreBanco().fechamento(OUT) is None
    assert com.mes_fechado(OUT) is False
    assert banco.historico[-1]["depois"] == "reaberto: faltou uma venda"
    with pytest.raises(com.EscritaRecusada, match="nao_fechado"):
        com.reabrir_mes(OUT, "de novo", "master@teste.local")
    fech.fechar(OUT, "master@teste.local", HOJE)  # reativa com linhas novas
    f = banco.fechamentos[OUT]
    assert f["ativo"] and f["fechado_por"] == "master@teste.local" and f["reaberto_por"] is None
    assert "reaberto por master@teste.local" in banco.historico[-1]["antes"]
    assert "faltou uma venda" in banco.historico[-1]["antes"]


# ---------------------------------------------------------------- estorno
def _venda(tx, dia, cancelada=None, mes=10):
    return Venda("hotmart", tx, datetime(2026, mes, dia, 10), "1", "Curso INSS", "COM. LEAD - AT4", "AT4", False,
                 "cartao_pix", None, D("89.90"), True, cancelada)


@pytest.fixture
def motor(banco, monkeypatch):
    """calcular_mes com cadastros/vendas/janelas falsos; fechamentos no FakeBanco."""
    estado = {"vendas": [], "decisoes": {}, "chamadas": []}

    def ler_vendas(ini, fim, transacoes_extra=frozenset(), ofertas=None, **kw):
        estado["chamadas"].append((ini, fim, set(transacoes_extra), kw))
        fora = kw.get("incluir_extra_fora_do_periodo", False)
        return [v for v in estado["vendas"] if ini <= v.data.date() <= fim or (fora and v.transacao in transacoes_extra)]
    monkeypatch.setattr(com, "ler_cadastros", lambda: Cadastros(decisoes_reembolso=estado["decisoes"]))
    monkeypatch.setattr(com, "ler_vendas", ler_vendas)
    monkeypatch.setattr(com, "ler_janelas", lambda *a, **k: ([], []))
    return estado


def test_estorno_no_primeiro_mes_aberto_com_participacao(banco, motor):
    _congelar(banco, OUT, _linhas_out())
    motor["vendas"] = [_venda("HP-EDI-PREV", 29, cancelada=datetime(2026, 11, 2, 9)),  # ≤ 7 dias: cai
                       _venda("HP-EDI-1", 5),                                           # segue paga
                       _venda("HP-JHE-1", 6, cancelada=datetime(2026, 10, 30)),         # > 7 dias, sem decisão
                       _venda("HP-CANC", 7, cancelada=datetime(2026, 10, 8))]           # congelada já cancelada
    r = snap.calcular_mes(NOV, HOJE)
    est = [l for l in r.linhas if l.situacao == "estorno"]
    assert {(l.transacao, l.papel, l.beneficiario, l.valor) for l in est} == {
        ("HP-EDI-PREV", "venda", "Ediléia", D("-80.00")),
        ("HP-EDI-PREV", "participacao", "Rafael Batista", D("-6.000"))}
    assert all(l.motivo == "estorno de 2026-10" and l.vendedor_codigo == "AT4" for l in est)
    assert not [l for l in r.linhas if l.situacao != "estorno"]  # venda de outubro não vira linha de novembro
    ini, fim, extra, kw = motor["chamadas"][-1]
    assert (ini, fim) == (NOV, date(2026, 11, 30)) and kw == {"incluir_extra_fora_do_periodo": True}
    assert {"HP-EDI-PREV", "HP-EDI-1", "HP-JHE-1"} <= extra and "HP-CANC" not in extra
    # estorno reduz o elegível (resumo, KPIs, tabela, ranking)
    assert resumo_por_beneficiario(est)["Ediléia"]["elegivel"] == D("-80.00")
    k = telas.kpis(r.linhas)
    assert k["elegivel"] == D("-80.00") and k["estorno"] == D("-80.00") and k["vendido"] == 0 and k["qtd"] == 0
    assert k["participacao"] == D("-6.000")
    vend = telas.tabela_vendedores(r.linhas)
    assert vend[0]["codigo"] == "AT4" and vend[0]["elegivel"] == D("-80.00") and vend[0]["qtd"] == 0


def test_estorno_por_decisao_tira(banco, motor):
    _congelar(banco, OUT, [_l("HP-JHE-1", "AT9", "5000", dia=6)])
    motor["vendas"] = [_venda("HP-JHE-1", 6, cancelada=datetime(2026, 10, 30))]
    assert not [l for l in snap.calcular_mes(NOV, HOJE).linhas if l.situacao == "estorno"]
    motor["decisoes"]["HP-JHE-1"] = "tira"
    est = [l for l in snap.calcular_mes(NOV, HOJE).linhas if l.situacao == "estorno"]
    assert [(l.transacao, l.valor) for l in est] == [("HP-JHE-1", D("-200.00"))]


def test_estorno_so_no_primeiro_mes_aberto(banco, motor):
    _congelar(banco, SET, [_l("HP-SET", dia=28, mes=9, sit="prevista")])
    motor["vendas"] = [_venda("HP-SET", 28, cancelada=datetime(2026, 10, 1), mes=9)]
    # outubro aberto: o estorno de setembro é de outubro, não de novembro
    assert not [l for l in snap.calcular_mes(NOV, HOJE).linhas if l.situacao == "estorno"]
    assert [l.motivo for l in snap.calcular_mes(OUT, HOJE).linhas if l.situacao == "estorno"] == ["estorno de 2026-09"]
    # outubro fechado também (sem o estorno): novembro é o primeiro aberto depois dos dois
    _congelar(banco, OUT, [])
    assert [l.motivo for l in snap.calcular_mes(NOV, HOJE).linhas if l.situacao == "estorno"] == ["estorno de 2026-09"]


def test_estorno_nao_duplica_depois_que_o_mes_fecha(banco, motor):
    _congelar(banco, OUT, _linhas_out())
    motor["vendas"] = [_venda("HP-EDI-PREV", 29, cancelada=datetime(2026, 11, 2, 9))]
    nov = snap.calcular_mes(NOV, HOJE)
    assert len([l for l in nov.linhas if l.situacao == "estorno"]) == 2
    _congelar(banco, NOV, nov.linhas)  # novembro fecha com os estornos congelados
    motor["chamadas"].clear()
    dez = snap.calcular_mes(DEZ, datetime(2026, 12, 3))
    assert not [l for l in dez.linhas if l.situacao == "estorno"]
    assert all("HP-EDI-PREV" not in extra for _i, _f, extra, _k in motor["chamadas"])
    # e o congelado de novembro continua com eles (o mês fechado não recalcula)
    r = snap.obter_mes(NOV, hoje=datetime(2026, 12, 3))
    assert r.fechado and len([l for l in r.linhas if l.situacao == "estorno"]) == 2


def test_candidatas_sem_estorno_ja_congelado():
    orig = _l("T1", sit="prevista")
    est = replace(orig, valor=-orig.valor, situacao="estorno", motivo="estorno de 2026-10")
    assert fech.candidatas({OUT: [orig], NOV: [est]}) == []
    assert fech.candidatas({OUT: [orig, _l("T0", sit="elegivel", base="0")]}) == [(OUT, orig)]
    assert fech.meses_do_estorno(DEZ, {OUT, NOV}) == [NOV, OUT]
    assert fech.meses_do_estorno(DEZ, {OUT}) == []


# ---------------------------------------------------------------- escritas em mês fechado
def test_mes_fechado_da_transacao(banco):
    assert com.mes_fechado_da_transacao("HP-EDI-1") is None
    _congelar(banco, OUT, _linhas_out())
    assert com.mes_fechado_da_transacao("HP-EDI-1") == OUT
    assert com.mes_fechado_da_transacao("HP-OUTRA") is None
    banco.fechamentos[OUT]["ativo"] = False  # reaberto: volta a aceitar
    assert com.mes_fechado_da_transacao("HP-EDI-1") is None


_USUARIOS = {"master@teste.local": MASTER, "coord@teste.local": COORD, "edileia@teste.local": AT4}


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
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: _res(mes=mes))
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: _res(mes=mes))
    monkeypatch.setattr(snap, "marcar_desatualizado", lambda mes=None, **kw: desat.append(mes))
    monkeypatch.setattr(rotas, "_hoje", lambda: date(2026, 11, 6))
    monkeypatch.setattr(rotas, "get_launches", lambda: [])
    monkeypatch.setattr(acesso_mod, "acesso_comercial", lambda user, **kw: _USUARIOS.get((user or {}).get("email")))
    monkeypatch.setattr(acesso_mod, "limpar_cache", lambda: None)
    _app_client.desat, _app_client.banco = desat, banco
    _app_client.cookies.clear()
    return _app_client


def _como(c, email, role="comercial"):
    from frontend.auth import _sign_session
    c.cookies.set("session_token", _sign_session("u-" + email, role, ["PI"], email))
    return c


def test_rotas_registradas():
    from frontend.auth import ROUTE_PERMISSIONS, _CMRC_AREA
    assert ROUTE_PERMISSIONS["/comercial/fechar-mes"] == _CMRC_AREA
    assert ROUTE_PERMISSIONS["/comercial/reabrir-mes"] == _CMRC_AREA


@pytest.mark.parametrize("rota", ["/comercial/fechar-mes", "/comercial/reabrir-mes"])
@pytest.mark.parametrize("email,role", [("edileia@teste.local", "comercial"), ("ninguem@teste.local", "leitura")])
def test_vendedor_e_sem_nivel_nao_fecham_nem_reabrem(cli, rota, email, role):
    _congelar(cli.banco, SET, [])
    r = _como(cli, email, role).post(rota, data={"mes": "2026-10" if "fechar" in rota else "2026-09", "motivo": "x"})
    assert r.status_code == 403
    assert cli.banco.escritas() == [] and cli.desat == [] and cli.banco.fechamentos[SET]["ativo"]


def test_coordenador_fecha_pela_rota(cli):
    r = _como(cli, "coord@teste.local").post("/comercial/fechar-mes", data={"mes": "2026-10"})
    assert r.status_code == 303 and r.headers["location"] == "/comercial/comissoes?mes=2026-10&ok=mes_fechado_ok"
    assert cli.banco.fechamentos[OUT]["ativo"] and cli.desat == [NOV]  # o seguinte (estorno) recalcula
    r = _como(cli, "coord@teste.local").post("/comercial/fechar-mes", data={"mes": "2026-10"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-10&erro=ja_fechado"


def test_fechar_pela_rota_com_a_verificar(cli, monkeypatch):
    monkeypatch.setattr(snap, "recalcular_mes", lambda mes, **kw: _res(_linhas_out() + [_l("HP-AV", sit="reembolso_a_verificar")]))
    r = _como(cli, "master@teste.local").post("/comercial/fechar-mes", data={"mes": "2026-10"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-10&erro=tem_a_verificar&qtd=1"
    assert cli.banco.fechamentos == {} and cli.desat == []
    html = _como(cli, "master@teste.local").get(r.headers["location"]).text
    assert "Há 1 venda(s) com reembolso a verificar" in html and 'href="/comercial/inconsistencias?mes=2026-10"' in html


def test_fechar_mes_corrente_pela_rota_recusa(cli):
    r = _como(cli, "master@teste.local").post("/comercial/fechar-mes", data={"mes": "2026-11"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-11&erro=mes_nao_terminou"
    assert _como(cli, "master@teste.local").post("/comercial/fechar-mes", data={"mes": ""}).status_code == 400
    assert cli.banco.escritas() == []


def test_reabrir_exige_motivo_pela_rota(cli):
    _congelar(cli.banco, OUT, _linhas_out())
    r = _como(cli, "master@teste.local").post("/comercial/reabrir-mes", data={"mes": "2026-10", "motivo": "  "})
    assert r.status_code == 400 and cli.banco.escritas() == [] and cli.banco.fechamentos[OUT]["ativo"]
    r = _como(cli, "master@teste.local").post("/comercial/reabrir-mes", data={"mes": "2026-10", "motivo": "erro na base"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-10&ok=mes_reaberto"
    assert cli.banco.fechamentos[OUT]["ativo"] is False and cli.banco.fechamentos[OUT]["motivo_reabertura"] == "erro na base"
    assert cli.desat == [OUT, NOV]
    assert cli.banco.historico[-1]["por"] == "master@teste.local"


_FECHADO_EM_OUT = [
    # (rota, form) — toda escrita com efeito em outubro (fechado)
    ("/comercial/regras/percentuais", {"acao": "versao", "id": "1", "pct": "5", "vigente_de": "2026-10-15"}),
    ("/comercial/regras/percentuais", {"acao": "encerrar", "id": "3", "vigente_de": "2026-10-20"}),
    ("/comercial/regras/percentuais", {"acao": "nova", "plataforma": "tmb", "modalidade": "parcelado", "tipo": "Reativa",
                                       "pct": "1", "vigente_de": "2026-10-01"}),
    ("/comercial/regras/participacoes", {"acao": "versao", "id": "1", "pct_ativa": "1", "pct_reativa": "1",
                                         "vigente_de": "2026-10-10"}),
    ("/comercial/regras/bases", {"acao": "versao", "id": "1", "valor_base": "1500", "categoria": "LEAD",
                                 "vigente_de": "2026-10-02"}),
    ("/comercial/regras/bases", {"acao": "nova", "plataforma": "tmb", "valor_cobrado": "99", "valor_base": "1500",
                                 "categoria": "LEAD", "vigente_de": "2026-10-02"}),
    ("/comercial/regras/metas", {"vendedor_codigo": "AT4", "mes": "2026-10", "valor": "1000"}),
    ("/comercial/bonus", {"vendedor_codigo": "AT4", "mes": "2026-10", "valor": "100"}),
    # janela nova em novembro, mas a automática que ela substitui (05–12/10) é de outubro
    ("/comercial/regras/janelas", {"acao": "gravar", "lancamento": "PBB-OUT-26", "inicio": "2026-11-02",
                                   "fim": "2026-11-09"}),
    # janela nova em outubro para lançamento sem data
    ("/comercial/regras/janelas", {"acao": "gravar", "lancamento": "PI-NOV-26", "inicio": "2026-10-26",
                                   "fim": "2026-11-03"}),
]


@pytest.mark.parametrize("rota,form", _FECHADO_EM_OUT)
def test_escrita_em_mes_fechado_recusada(cli, rota, form):
    _congelar(cli.banco, OUT, _linhas_out())
    r = _como(cli, "master@teste.local").post(rota, data=form)
    assert r.status_code == 303 and "erro=mes_fechado" in r.headers["location"], r.headers.get("location")
    assert cli.banco.escritas() == [] and cli.desat == []


def test_remover_janela_que_volta_para_mes_fechado(cli):
    _congelar(cli.banco, OUT, _linhas_out())
    cli.banco.janelas["PBB-OUT-26"] = {"inicio": datetime(2026, 11, 2), "fim": datetime(2026, 11, 9, 23, 59, 59),
                                       "por": "x"}
    r = _como(cli, "master@teste.local").post("/comercial/regras/janelas", data={"acao": "remover", "lancamento": "PBB-OUT-26"})
    assert "erro=mes_fechado" in r.headers["location"] and "PBB-OUT-26" in cli.banco.janelas


def test_escrita_em_mes_aberto_segue(cli):
    _congelar(cli.banco, OUT, _linhas_out())
    r = _como(cli, "master@teste.local").post("/comercial/regras/percentuais",
                                               data={"acao": "versao", "id": "1", "pct": "5", "vigente_de": "2026-11-01"})
    assert r.headers["location"] == "/comercial/regras?ok=regra_versionada#percentuais"
    assert cli.banco.regras[0]["vigente_ate"] == date(2026, 10, 31)  # véspera, em outubro: o congelado não muda
    assert snap.StoreBanco().fechamento(OUT).linhas == _linhas_out()


@pytest.mark.parametrize("rota,form", [
    ("/comercial/reivindicar", {"transacao": "HP-EDI-1", "vendedor_codigo": "AT4", "mes": "2026-10"}),
    ("/comercial/atribuicoes/aprovar", {"transacao": "HP-EDI-1", "mes": "2026-10"}),
    ("/comercial/atribuir", {"transacao": "HP-EDI-1", "vendedor_codigo": "AT9", "mes": "2026-10"}),
    ("/comercial/reembolso", {"transacao": "HP-EDI-1", "decisao": "tira", "justificativa": "x", "mes": "2026-10"}),
    ("/comercial/ajuste", {"transacao": "HP-EDI-1", "pct": "10", "justificativa": "x", "mes": "2026-10"}),
])
@pytest.mark.parametrize("email", ["master@teste.local", "edileia@teste.local"])
def test_venda_de_mes_fechado_recusada(cli, rota, form, email):
    _congelar(cli.banco, OUT, _linhas_out())
    r = _como(cli, email).post(rota, data=form)
    if email == "edileia@teste.local" and rota != "/comercial/reivindicar":
        assert r.status_code == 403
    else:
        assert r.status_code == 303 and r.headers["location"] == "/comercial/inconsistencias?mes=2026-10&erro=mes_fechado"
    assert cli.banco.escritas() == [] and cli.desat == []


# ---------------------------------------------------------------- telas
def _fechado(linhas=None, bonus=None):
    return ResultadoMes(OUT, _linhas_out() if linhas is None else linhas, [], datetime(2026, 11, 2, 10, 5),
                        fechado=True, fechado_em=datetime(2026, 11, 2, 10, 5), fechado_por="comercial2@aprovasim.com",
                        bonus=bonus or {}, totais={})


def test_tela_mes_fechado_gestor_e_vendedor(cli, monkeypatch):
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: _fechado(bonus={"AT4": {"valor": D("150"), "nome": "Ediléia",
                                                                                     "justificativa": None}}))
    html = _como(cli, "master@teste.local").get("/comercial/comissoes?mes=2026-10").text
    assert "Mês fechado em 02/11 por comercial2@aprovasim.com" in html
    assert 'action="/comercial/reabrir-mes"' in html and 'name="motivo" required' in html
    assert 'action="/comercial/fechar-mes"' not in html and 'action="/comercial/bonus"' not in html
    assert 'action="/comercial/recalcular' not in html and "Total pago" in html
    vend = _como(cli, "edileia@teste.local").get("/comercial/comissoes?mes=2026-10").text
    assert "Mês fechado em 02/11" in vend
    assert "reabrir-mes" not in vend and "fechar-mes" not in vend and "Jheniffer" not in vend
    visao = _como(cli, "master@teste.local").get("/comercial?mes=2026-10").text
    assert "mês fechado em 02/11 por comercial2@aprovasim.com" in visao


def test_tela_mes_aberto_passado_tem_fechar_com_contagens(cli):
    html = _como(cli, "coord@teste.local").get("/comercial/comissoes?mes=2026-10").text
    assert 'action="/comercial/fechar-mes"' in html and "mês aberto" in html
    form = html.split('action="/comercial/fechar-mes"')[1].split(">", 1)[0]
    assert "data-confirma=" in form and "1 venda(s) prevista(s)" in form and "0 inconsistência(s)" in form
    assert "onsubmit" not in form
    vend = _como(cli, "edileia@teste.local").get("/comercial/comissoes?mes=2026-10").text
    assert "fechar-mes" not in vend
    atual = _como(cli, "coord@teste.local").get("/comercial/comissoes?mes=2026-11").text
    assert "fechar-mes" not in atual  # mês corrente não fecha


def test_tela_mostra_estorno(cli, monkeypatch):
    orig = _l("HP-EDI-PREV", sit="prevista", dia=29)
    est = replace(orig, valor=-orig.valor, situacao="estorno", motivo="estorno de 2026-10")
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: _res([_l("HP-NOV-1", dia=3, mes=11), est], mes=NOV))
    html = _como(cli, "master@teste.local").get("/comercial/comissoes?mes=2026-11").text
    assert 'class="cm-chip estorno"' in html and "venda paga no fechamento de 2026-10 e cancelada depois" in html
    assert "-R$" in html or "R$ -" in html or "−" in html
