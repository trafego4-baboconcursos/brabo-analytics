"""Área Comercial — Visão geral, Comissões (+ Excel) e Ranking (Task 5, fase 2).

Sem banco: `snapshot.obter_mes`/`telas.calcular_periodo` e `acesso.acesso_comercial` são
trocados por fakes. O isolamento do vendedor é testado nas duas pontas: no builder (camada de
serviço) e no HTML que sai da rota.
"""
import os

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

import dataclasses
import io  # noqa: E402
from datetime import date, datetime  # noqa: E402
from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402

from frontend.services.comercial import acesso as acesso_mod  # noqa: E402
from frontend.services.comercial import snapshot as snap  # noqa: E402
from frontend.services.comercial import telas  # noqa: E402
from frontend.services.comercial.acesso import AcessoComercial  # noqa: E402
from frontend.services.comercial.calculo import LinhaComissao  # noqa: E402
from frontend.services.comercial.snapshot import ResultadoMes  # noqa: E402

VENDEDORES = {"AT13": "Izabela", "AT4": "Ediléia", "AT9": "Jheniffer", "AT11": "Priscila"}


def _l(transacao, codigo, tipo="Ativa", base="1000", pct="0.04", sit="elegivel", papel="venda",
       beneficiario=None, motivo=None, manual=False, dia=5):
    base_d = D(base) if base is not None else None
    pct_d = D(pct) if pct is not None else None
    valor = base_d * pct_d if (base_d is not None and pct_d is not None
                               and sit in ("elegivel", "prevista", "reembolso_a_verificar")) else D("0")
    return LinhaComissao(
        transacao=transacao, plataforma="hotmart", papel=papel,
        beneficiario=beneficiario or VENDEDORES.get(codigo, "(sem vendedor)"),
        vendedor_codigo=codigo, data=datetime(2026, 10, dia, 10, 30), tipo=tipo,
        modalidade="Cartão 12x", categoria="Lead", valor_base=base_d, pct=pct_d, valor=valor,
        situacao=sit, motivo=motivo, regra_id=1, atribuicao_manual=manual,
    )


def _linhas():
    return [
        _l("HP-IZA-1", "AT13", base="2000"),                              # 80
        _l("HP-IZA-2", "AT13", tipo="Reativa", base="1000", pct="0.0075"),  # 7,50
        _l("HP-EDI-1", "AT4", base="1477"),                               # 59,08
        _l("HP-EDI-2", "AT4", tipo="Reativa", base="1477", pct="0.0075", sit="prevista", manual=True),  # 11,0775
        _l("HP-EDI-3", "AT4", sit="cancelada"),
        _l("HP-JHE-1", "AT9", base="3000"),                               # 120
        _l("HP-JHE-2", "AT9", base="500", sit="reembolso_a_verificar"),   # 20
        _l("HP-PRI-1", "AT11", base="1500"),                              # 60
        _l("HP-SEM-1", None, base=None, pct=None, sit="inconsistente", motivo="sem_codigo"),
        _l("HP-EDI-1", "AT4", base="1477", pct="0.005", papel="participacao", beneficiario="Rafael Batista"),
        _l("HP-JHE-1", "AT9", base="3000", pct="0.005", papel="participacao", beneficiario="Rafael Batista"),
    ]


SEM_DATA = [("PES-OUT-26", frozenset({"123"}), frozenset())]
GERADO = datetime(2026, 11, 6, 9, 42)
MASTER = AcessoComercial("master", None)
AT4 = AcessoComercial("vendedor", "AT4")


def _res():
    return ResultadoMes(date(2026, 10, 1), _linhas(), SEM_DATA, GERADO)


# ---------------------------------------------------------------- builders (serviço)
def test_linhas_visiveis_vendedor_so_as_proprias_vendas():
    ls = telas.linhas_visiveis(_linhas(), AT4)
    assert {l.transacao for l in ls} == {"HP-EDI-1", "HP-EDI-2", "HP-EDI-3"}
    assert all(l.papel == "venda" for l in ls)


def test_linhas_visiveis_vendedor_ignora_filtro_de_outro():
    ls = telas.linhas_visiveis(_linhas(), AT4, vendedor="AT9")
    assert {l.vendedor_codigo for l in ls} == {"AT4"}


def test_linhas_visiveis_gestor_filtra_vendedor():
    ls = telas.linhas_visiveis(_linhas(), MASTER, vendedor="AT9")
    assert {l.transacao for l in ls} == {"HP-JHE-1", "HP-JHE-2"}
    assert {l.papel for l in ls} == {"venda", "participacao"}


def test_linhas_visiveis_sem_acesso_nada():
    assert telas.linhas_visiveis(_linhas(), None) == []


def test_kpis_somam_so_vendas_com_valor():
    k = telas.kpis(_linhas())
    assert k["elegivel"] == D("80") + D("7.5") + D("59.08") + D("120") + D("60")
    assert k["prevista"] == D("1477") * D("0.0075") + D("20")
    assert k["vendido"] == D("2000") + D("1000") + D("1477") * 2 + D("3000") + D("500") + D("1500")
    assert k["total"] == k["elegivel"]
    assert k["bonus"] is None
    assert k["inconsistencias"] == 1  # só o reembolso a verificar; sem_codigo não é pendência (Ruling 10)
    assert k["sem_codigo"] == 1
    assert k["participacao"] == (D("1477") + D("3000")) * D("0.005")


def test_tabela_vendedores_quatro_com_ativa_reativa_e_detalhe():
    tab = telas.tabela_vendedores(_linhas())
    assert [v["nome"] for v in tab] == ["Jheniffer", "Izabela", "Ediléia", "Priscila"]  # por total
    edi = next(v for v in tab if v["codigo"] == "AT4")
    assert edi["vendido_ativa"] == D("1477") and edi["vendido_reativa"] == D("1477")
    assert edi["com_ativa"] == D("59.08") and edi["com_reativa"] == D("1477") * D("0.0075")
    assert edi["elegivel"] == D("59.08") and edi["prevista"] == D("1477") * D("0.0075")
    assert {d.transacao for d in edi["detalhe"]} == {"HP-EDI-1", "HP-EDI-2", "HP-EDI-3"}


def test_tabela_participacoes_separada():
    p = telas.tabela_participacoes(_linhas())
    assert [x["nome"] for x in p] == ["Rafael Batista"]
    assert p[0]["total"] == (D("1477") + D("3000")) * D("0.005")


def test_ranking_gestor_tem_comissao_e_ordena():
    r = telas.ranking(_linhas(), MASTER, "vendido")
    assert r["mostra_comissao"] is True
    assert [x["nome"] for x in r["linhas"]] == ["Jheniffer", "Izabela", "Ediléia", "Priscila"]
    assert [x["pos"] for x in r["linhas"]] == [1, 2, 3, 4]
    assert r["linhas"][0]["qtd"] == 2 and r["linhas"][0]["vendido"] == D("3500")
    r = telas.ranking(_linhas(), MASTER, "comissao")
    assert r["linhas"][0]["nome"] == "Jheniffer" and r["linhas"][1]["nome"] == "Izabela"


def test_ranking_vendedor_sem_comissao_e_sem_ordem_por_comissao():
    r = telas.ranking(_linhas(), AT4, "comissao")
    assert r["mostra_comissao"] is False
    assert r["ordem"] == "vendido"  # ordenar por comissão revelaria a comissão dos outros
    assert all("comissao" not in x for x in r["linhas"])
    assert len(r["linhas"]) == 4  # o ranking é de todos


def test_ranking_vendedora_ve_so_posicao_e_nome_das_outras():
    rk = telas.ranking(_linhas(), AT4, "qtd")
    outras = [r for r in rk["linhas"] if r["codigo"] != "AT4"]
    assert len(outras) == 3 and all(set(r) == {"codigo", "nome", "pos"} for r in outras)
    minha = next(r for r in rk["linhas"] if r["codigo"] == "AT4")
    assert minha["vendido"] > 0 and "qtd" in minha and rk["ordem"] == "vendido"
    assert [r["pos"] for r in rk["linhas"]] == [1, 2, 3, 4]  # posição real, calculada antes do corte


def test_ranking_gestor_continua_vendo_tudo():
    rk = telas.ranking(_linhas(), MASTER, "qtd")
    assert all("vendido" in r and "comissao" in r for r in rk["linhas"])


def test_view_ranking_vendedora_sem_barra_nas_outras():
    v = telas.view_ranking(_res(), telas.resolver_periodo("2026-10", None, None, date(2026, 11, 6)), AT4, "qtd")
    assert all("barra" not in r for r in v["linhas"] if r["codigo"] != "AT4")


def test_resolver_periodo():
    hoje = date(2026, 11, 6)
    p = telas.resolver_periodo(None, None, None, hoje)
    assert (p.inicio, p.fim, p.mes) == (date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 1))
    p = telas.resolver_periodo("2026-10", None, None, hoje)
    assert (p.inicio, p.fim, p.livre) == (date(2026, 10, 1), date(2026, 10, 31), False)
    p = telas.resolver_periodo(None, "2026-10-01", "2026-10-15", hoje, gestor=True)
    assert (p.inicio, p.fim, p.livre, p.mes) == (date(2026, 10, 1), date(2026, 10, 15), True, None)
    assert p.query == "inicio=2026-10-01&fim=2026-10-15"
    p = telas.resolver_periodo(None, "2026-08-01", "2026-10-31", hoje, gestor=True)  # 92 dias: ok
    assert p.livre


@pytest.mark.parametrize("mes,inicio,fim,gestor", [
    ("lixo", None, None, True),
    ("2025-12", None, None, True),               # antes de 2026-01
    ("2026-12", None, None, True),               # depois do mês corrente
    (None, "2026-10-15", "2026-10-01", True),    # invertido
    (None, "2026-07-01", "2026-10-31", True),    # > 92 dias
    (None, "2026-10-01", None, True),            # incompleto
    (None, "2026-10-01", "lixo", True),
    (None, "2026-10-01", "2026-10-15", False),   # período livre só para gestor
])
def test_resolver_periodo_invalido(mes, inicio, fim, gestor):
    with pytest.raises(telas.PeriodoInvalido):
        telas.resolver_periodo(mes, inicio, fim, date(2026, 11, 6), gestor=gestor)


def test_mes_do_codigo_e_alertas_proximos():
    assert telas.mes_do_codigo("PES-NOV-26") == date(2026, 11, 1)
    assert telas.mes_do_codigo("BV-26") is None
    sem = [("PES-OUT-26", frozenset(), frozenset()), ("PI-SET-26", frozenset(), frozenset()),
           ("PBB-JAN-25", frozenset(), frozenset()), ("BV-26", frozenset(), frozenset()),
           ("PI-AGO-26", frozenset(), frozenset())]
    p = telas.resolver_periodo("2026-10", None, None, date(2026, 11, 6))
    perto, antigos = telas.separar_sem_data(sem, p)
    assert [a[0] for a in perto] == ["BV-26", "PES-OUT-26", "PI-SET-26"]
    assert [a[0] for a in antigos] == ["PBB-JAN-25", "PI-AGO-26"]


def test_sem_codigo_em_massa_nao_vira_inconsistencia():
    organicas = [_l(f"HP-ORG-{i}", None, base=None, pct=None, sit="inconsistente", motivo="sem_codigo")
                 for i in range(823)]
    outras = [_l("HP-C-1", "AT4", base=None, pct=None, sit="inconsistente", motivo="conflito_codigo"),
              _l("HP-C-2", "AT4", base=None, pct=None, sit="inconsistente", motivo="sem_valor_base"),
              _l("HP-C-3", "AT4", base=None, pct=None, sit="inconsistente", motivo="sem_regra")]
    k = telas.kpis(organicas + outras)
    assert (k["inconsistencias"], k["sem_codigo"]) == (3, 823)


def test_xlsx_neutraliza_formula():
    from openpyxl import load_workbook
    l = _l("=HYPERLINK(\"x\")", "AT4", beneficiario="+cmd")
    view = {"vendedores": telas.tabela_vendedores([l]), "participacoes": [], "linhas": [l]}
    wb = load_workbook(io.BytesIO(telas.planilha_xlsx(view)))
    linha = next(wb["Vendas"].iter_rows(min_row=2, values_only=True))
    assert linha[0] == "'=HYPERLINK(\"x\")" and linha[3] == "'+cmd"
    assert next(wb["Resumo"].iter_rows(min_row=2, values_only=True))[0] == "'+cmd"
    assert telas.celula_segura("-1") == "'-1" and telas.celula_segura("@x") == "'@x"
    assert telas.celula_segura("ok") == "ok" and telas.celula_segura(D("-1")) == D("-1")


def test_xlsx_rotula_linha_ia_sem_comissao():
    from openpyxl import load_workbook
    l = dataclasses.replace(_l("T-IA", None, beneficiario="Camila"), papel="ia")
    view = {"vendedores": [], "participacoes": [], "linhas": [l]}
    wb = load_workbook(io.BytesIO(telas.planilha_xlsx(view)))
    assert next(wb["Vendas"].iter_rows(min_row=2, values_only=True))[2] == "IA (sem comissão)"


def test_formatadores_decimais():
    from frontend.formatters import fmt_brl_exato, fmt_pct_taxa
    assert fmt_brl_exato(D("1234.565")) == "R$ 1.234,57"  # ROUND_HALF_UP
    assert fmt_brl_exato(None) == "—"
    assert fmt_pct_taxa(D("0.04")) == "4%"
    assert fmt_pct_taxa(D("0.0075")) == "0,75%"
    assert fmt_pct_taxa(None) == "—"


# ---------------------------------------------------------------- rotas
_USUARIOS = {
    "master@teste.local": MASTER,
    "edileia@teste.local": AT4,
}


@pytest.fixture(scope="module")
def _app_client():
    from fastapi.testclient import TestClient

    from frontend.app import app

    with TestClient(app, follow_redirects=False) as c:  # startup uma vez só (tenta o banco)
        yield c


@pytest.fixture
def cli(_app_client, monkeypatch):
    import frontend.routes.comercial as rotas

    chamadas = {"obter": [], "livre": [], "desat": []}

    def fake_obter(mes, **kw):
        chamadas["obter"].append(mes)
        return _res()

    def fake_livre(inicio, fim, hoje=None):
        chamadas["livre"].append((inicio, fim))
        return ResultadoMes(inicio, _linhas(), [], GERADO)

    monkeypatch.setattr(snap, "obter_mes", fake_obter)
    monkeypatch.setattr(telas, "calcular_periodo", fake_livre)
    # bônus/meta (Task 7a) são lidos na hora da tela: sem banco aqui
    monkeypatch.setattr(telas, "ler_extras", lambda periodo, acesso: (None, None) if periodo.livre else ({}, {}))
    monkeypatch.setattr(telas, "ler_vendedores_ativos", lambda: [])
    import frontend.db_readers.comercial as _com_db
    monkeypatch.setattr(_com_db, "ler_metas_mes",
                        lambda mes, vendedor_codigo=None: {"AT4": {"nome": "Ediléia", "valor": D("2000")},
                                                           "AT9": {"nome": "Jheniffer", "valor": D("3000")}})
    monkeypatch.setattr(snap, "ler_guardado", lambda mes, **kw: None)  # acumulado: sem banco
    monkeypatch.setattr(snap, "marcar_desatualizado", lambda mes=None, **kw: chamadas["desat"].append(mes))
    monkeypatch.setattr(rotas, "_hoje", lambda: date(2026, 11, 6))  # janela de meses estável
    monkeypatch.setattr(rotas, "get_launches", lambda: [])  # sem banco: evita a espera do connect
    monkeypatch.setattr(acesso_mod, "acesso_comercial",
                        lambda user, **kw: _USUARIOS.get((user or {}).get("email")))
    _app_client.chamadas = chamadas
    _app_client.cookies.clear()
    return _app_client


def _como(c, email, role="comercial"):
    from frontend.auth import _sign_session
    c.cookies.set("session_token", _sign_session("u-" + email, role, ["PI"], email))
    return c


def test_rotas_registradas_com_area_comercial():
    from frontend.auth import ROUTE_PERMISSIONS, _CMRC_AREA
    for p in ("/comercial", "/comercial/comissoes", "/comercial/comissoes.xlsx",
              "/comercial/ranking", "/comercial/desempenho", "/comercial/recalcular"):
        assert ROUTE_PERMISSIONS[p] == _CMRC_AREA


@pytest.mark.parametrize("pagina", ["/comercial", "/comercial/comissoes", "/comercial/ranking",
                                    "/comercial/desempenho", "/comercial/comissoes.xlsx"])
def test_sem_nivel_403(cli, pagina):
    resp = _como(cli, "ninguem@teste.local", "leitura").get(pagina)
    assert resp.status_code == 403
    assert "permissão" in resp.text


def test_trafego_barrado_no_middleware(cli):
    assert _como(cli, "master@teste.local", "trafego").get("/comercial").status_code == 403


def test_master_comissoes_ve_quatro_vendedores(cli):
    resp = _como(cli, "master@teste.local").get("/comercial/comissoes?mes=2026-10")
    assert resp.status_code == 200, resp.text[:500]
    html = resp.text
    for nome in VENDEDORES.values():
        assert nome in html
    assert "Rafael Batista" in html  # participação, só para gestor
    assert "dados de 06/11 09:42" in html
    assert "Em validação" in html
    assert "Comissão elegível" in html and "Prevista" in html and "Bônus" in html and "Total a pagar" in html
    assert "R$ 326,58" in html  # elegível: 80 + 7,50 + 59,08 + 120 + 60
    assert cli.chamadas["obter"] == [date(2026, 10, 1)]


def test_vendedor_comissoes_so_ediléia(cli):
    resp = _como(cli, "edileia@teste.local").get("/comercial/comissoes?mes=2026-10&vendedor=AT9")
    assert resp.status_code == 200
    html = resp.text
    assert "Ediléia" in html and "HP-EDI-1" in html
    for outro in ("Izabela", "Jheniffer", "Priscila", "Rafael Batista", "HP-JHE", "HP-IZA", "HP-SEM"):
        assert outro not in html
    assert "R$ 59,08" in html


@pytest.mark.parametrize("url", ["/comercial?mes=2025-12", "/comercial/comissoes?mes=2027-01",
                                 "/comercial/ranking?mes=lixo", "/comercial/desempenho?mes=lixo",
                                 "/comercial/comissoes.xlsx?inicio=2026-01-01&fim=2026-10-31"])
def test_periodo_fora_da_janela_400(cli, url):
    resp = _como(cli, "master@teste.local").get(url)
    assert resp.status_code == 400
    assert "Período" in resp.text or "período" in resp.text
    assert cli.chamadas["obter"] == [] and cli.chamadas["livre"] == []


def test_periodo_livre_vendedor_400(cli):
    resp = _como(cli, "edileia@teste.local").get("/comercial/comissoes?inicio=2026-10-01&fim=2026-10-15")
    assert resp.status_code == 400
    assert cli.chamadas["livre"] == []


def test_recalcular_mes_fora_da_janela_400(cli):
    resp = _como(cli, "master@teste.local").post("/comercial/recalcular?mes=2024-01")
    assert resp.status_code == 400
    assert cli.chamadas["desat"] == []


def test_comissoes_periodo_livre_calcula_ao_vivo(cli):
    resp = _como(cli, "master@teste.local").get("/comercial/comissoes?inicio=2026-10-01&fim=2026-10-15")
    assert resp.status_code == 200
    assert cli.chamadas["livre"] == [(date(2026, 10, 1), date(2026, 10, 15))]
    assert cli.chamadas["obter"] == []


def test_visao_geral_kpis_top3_alerta(cli):
    resp = _como(cli, "master@teste.local").get("/comercial?mes=2026-10")
    assert resp.status_code == 200
    html = resp.text
    assert "dados de 06/11 09:42" in html
    assert "PES-OUT-26" in html  # alerta de lançamento sem data (mês do período)
    assert "cm-alerta" in html
    assert "Recalcular" in html
    assert "Em validação" in html
    assert "Total vendido" in html and "Inconsistências" in html
    top = html[html.index("Top 3"):]
    assert top.index("Jheniffer") < top.index("Izabela") < top.index("Ediléia")
    assert "Priscila" not in top[:top.index("</ol>")]


def test_visao_geral_sem_data_antigo_so_recolhido(cli, monkeypatch):
    antigos = [("PBB-JAN-25", frozenset({"1"}), frozenset()), ("PI-FEV-26", frozenset(), frozenset({"2"}))]
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: ResultadoMes(date(2026, 10, 1), _linhas(), antigos, GERADO))
    html = _como(cli, "master@teste.local").get("/comercial?mes=2026-10").text
    assert 'class="cm-alerta"' not in html  # nada perto do período: sem bloco vermelho
    assert "<details" in html and "2 lançamentos antigos sem data" in html
    assert "PBB-JAN-25" in html[html.index("<details"):]


def test_visao_geral_vendedor_sem_recalcular_nem_alerta(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial?mes=2026-10").text
    assert "Recalcular" not in html
    assert "PES-OUT-26" not in html
    assert "HP-JHE" not in html


def test_ranking_vendedor_sem_coluna_comissao(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial/ranking?mes=2026-10&ordem=comissao").text
    tabela = html[html.index("<table"):html.index("</table>")]
    assert "Comissão" not in tabela
    for nome in VENDEDORES.values():
        assert nome in tabela
    assert "HP-" not in html


def test_ranking_master_com_coluna_comissao(cli):
    html = _como(cli, "master@teste.local").get("/comercial/ranking?mes=2026-10").text
    tabela = html[html.index("<table"):html.index("</table>")]
    assert "Comissão" in tabela


def test_menu_mostra_itens_comerciais(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial/ranking").text
    assert 'href="/comercial/comissoes"' in html and 'href="/comercial/ranking"' in html
    assert 'href="/atendimento"' not in html  # Atendimento é só do gestor (10/11/26)
    assert "Reivindicações" in html and "Inconsistências" not in html
    master = _como(cli, "master@teste.local").get("/comercial/ranking").text
    assert 'href="/atendimento"' in master and "Inconsistências" in master


def test_xlsx_planilha_valida(cli):
    from openpyxl import load_workbook
    resp = _como(cli, "master@teste.local").get("/comercial/comissoes.xlsx?mes=2026-10")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    wb = load_workbook(io.BytesIO(resp.content))
    resumo = wb["Resumo"]
    assert [c.value for c in resumo[1]] == telas.CABECALHO_RESUMO
    vendas = wb["Vendas"]
    assert [c.value for c in vendas[1]] == telas.CABECALHO_VENDAS
    valores = [r for r in vendas.iter_rows(min_row=2, values_only=True)]
    # venda sem código AT é do marketing: fica fora da planilha (10/11/26)
    assert len(valores) == len([l for l in _linhas() if l.motivo != "sem_codigo"])
    col_com = telas.CABECALHO_VENDAS.index("Comissão")
    assert all(isinstance(r[col_com], (int, float)) for r in valores)


def test_xlsx_vendedor_so_proprias(cli):
    from openpyxl import load_workbook
    resp = _como(cli, "edileia@teste.local").get("/comercial/comissoes.xlsx?mes=2026-10")
    wb = load_workbook(io.BytesIO(resp.content))
    trans = {r[0] for r in wb["Vendas"].iter_rows(min_row=2, values_only=True)}
    assert trans == {"HP-EDI-1", "HP-EDI-2", "HP-EDI-3"}
    nomes = {r[0] for r in wb["Resumo"].iter_rows(min_row=2, values_only=True)}
    assert nomes == {"Ediléia"}


def test_recalcular_vendedor_403(cli):
    resp = _como(cli, "edileia@teste.local").post("/comercial/recalcular?mes=2026-10")
    assert resp.status_code == 403
    assert cli.chamadas["desat"] == []


def test_recalcular_master_marca_e_volta(cli):
    resp = _como(cli, "master@teste.local").post("/comercial/recalcular?mes=2026-10",
                                                   data={"voltar": "/comercial/comissoes?mes=2026-10"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/comercial/comissoes?mes=2026-10"
    assert cli.chamadas["desat"] == [date(2026, 10, 1)]


def test_recalcular_nao_redireciona_pra_fora(cli):
    resp = _como(cli, "master@teste.local").post("/comercial/recalcular?mes=2026-10",
                                                   data={"voltar": "https://evil.example/x"})
    assert resp.headers["location"] == "/comercial?mes=2026-10"


# ---------------------------------------------------------------- Desempenho (Task 4)
def test_desempenho_abre_para_gestor_e_vendedora(cli):
    assert _como(cli, "master@teste.local").get("/comercial/desempenho?mes=2026-10").status_code == 200
    assert _como(cli, "edileia@teste.local").get("/comercial/desempenho").status_code == 200


def test_desempenho_vendedora_nao_ve_meta_do_time_nem_ia(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial/desempenho?mes=2026-10").text
    assert "Meta do time" in html and "Atendente IA" not in html and "Contribuição" in html
    assert "R$ 5.000,00" in html  # meta do time: soma de todas, número geral
    for outro in ("Jheniffer", "Izabela", "Priscila", "AT9", "AT13", "AT11", "HP-"):
        assert outro not in html


def test_desempenho_gestor_ve_todas_e_a_ia_a_parte(cli, monkeypatch):
    linhas = _linhas() + [_l("HP-IA-1", None, base="700", papel="ia", beneficiario="Camila")]
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: ResultadoMes(mes, linhas, SEM_DATA, GERADO))
    html = _como(cli, "master@teste.local").get("/comercial/desempenho?mes=2026-10").text
    for nome in VENDEDORES.values():
        assert nome in html
    assert "Atendente IA" in html and "Camila" in html


def test_vendedora_nao_compara_intervalo(cli):
    r = _como(cli, "edileia@teste.local").get("/comercial/desempenho?cinicio=2026-09-01&cfim=2026-09-30")
    assert r.status_code == 400


def test_desempenho_comparacao_invalida_400(cli):
    assert _como(cli, "master@teste.local").get("/comercial/desempenho?comparar=lixo").status_code == 400


def test_desempenho_vendedora_sem_venda_ve_contribuicao_zerada(cli, monkeypatch):
    sem = [l for l in _linhas() if l.vendedor_codigo != "AT4"]
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: ResultadoMes(mes, sem, SEM_DATA, GERADO))
    html = _como(cli, "edileia@teste.local").get("/comercial/desempenho?mes=2026-10").text
    assert "Contribuição" in html and "0%" in html and "Jheniffer" not in html


def test_desempenho_intervalo_livre_sem_meta(cli):
    html = _como(cli, "master@teste.local").get("/comercial/desempenho?inicio=2026-10-01&fim=2026-10-15").text
    assert "meta é mensal: escolha um mês" in html


def test_desempenho_sem_acesso_comercial_403(cli):
    assert _como(cli, "ninguem@teste.local", "leitura").get("/comercial/desempenho").status_code == 403


def test_menu_tem_desempenho(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial/ranking").text
    assert 'href="/comercial/desempenho"' in html
    assert html.index('href="/comercial/ranking"') < html.index('href="/comercial/desempenho"')


def test_serie_do_grafico_vai_em_json_nao_em_js_inline(cli):
    html = _como(cli, "master@teste.local").get("/comercial/desempenho?mes=2026-10").text
    assert 'type="application/json"' in html and "JSON.parse" in html
    assert "chart.js@4.4.0" in html


def test_rota_ranking_e_visao_vendedora_sem_valores_de_outra(cli):
    # outras: Jheniffer 3.500 (meta 3.000), Izabela 3.000, Priscila 1.500; Ediléia (AT4) 2.954
    for url in ("/comercial/ranking?mes=2026-10", "/comercial?mes=2026-10"):
        html = _como(cli, "edileia@teste.local").get(url).text
        nomes = ("Jheniffer", "Izabela", "Priscila") if "ranking" in url else ("Jheniffer", "Izabela")  # Top 3
        for nome in nomes:
            assert nome in html, (url, nome)                  # nome aparece
        for valor in ("3.500,00", "3.000,00", "1.500,00"):
            assert valor not in html, (url, valor)            # valor de outra não
        assert "2.954,00" in html, url                        # o dela sim
        assert html.count("vendidos em") <= 1, url            # Top 3 da Visão: só a própria linha


@pytest.mark.parametrize("ordem", ["qtd", "meta", "comissao"])
def test_rota_ranking_vendedora_ordem_pedida_vira_vendido(cli, ordem):
    html = _como(cli, "edileia@teste.local").get(f"/comercial/ranking?mes=2026-10&ordem={ordem}").text
    assert html.index("Jheniffer") < html.index("Izabela") < html.index("Ediléia") < html.index("Priscila")
    assert 'aria-current="true">Vendido' in html


# ---------------------------------------------------------------- Visão geral: todas as vendas (11/11/26)
def test_todas_as_vendas_uma_por_venda_mais_recente_primeiro():
    ls = _linhas() + [_l("HP-IA-1", None, papel="ia", beneficiario="Camila (IA)", dia=20)]
    vendas = telas.todas_as_vendas(telas.linhas_visiveis(ls, MASTER))
    trans = [l.transacao for l in vendas]
    assert "HP-SEM-1" not in trans                       # marketing fora
    assert trans.count("HP-EDI-1") == 1                  # participação não repete a venda
    assert trans[0] == "HP-IA-1"                         # mais recente primeiro; IA entra
    assert len(trans) == 9


def test_todas_as_vendas_vendedora_so_as_dela():
    vendas = telas.todas_as_vendas(telas.linhas_visiveis(_linhas(), AT4))
    assert {l.transacao for l in vendas} == {"HP-EDI-1", "HP-EDI-2", "HP-EDI-3"}


def test_visao_geral_tabela_de_todas_as_vendas(cli):
    html = _como(cli, "master@teste.local").get("/comercial?mes=2026-10").text
    sec = html[html.index("Todas as vendas do período"):]
    assert "(8)" in sec[:80]
    for t in ("HP-IZA-1", "HP-JHE-2", "HP-PRI-1", "HP-EDI-3"):
        assert t in sec
    assert "HP-SEM-1" not in sec
    assert "/comercial/comissoes.xlsx?mes=2026-10" in sec
    assert 'id="cm-vendas-busca"' in sec
    assert "cm-chip manual" in sec                       # HP-EDI-2 atribuída à mão


def test_visao_geral_vendedora_ve_so_as_proprias_vendas(cli):
    html = _como(cli, "edileia@teste.local").get("/comercial?mes=2026-10").text
    sec = html[html.index("Suas vendas no período"):]
    assert "HP-EDI-1" in sec and "HP-EDI-2" in sec
    assert "HP-JHE" not in sec and "HP-IZA" not in sec and "HP-PRI" not in sec
    assert ">Vendedora<" not in sec
