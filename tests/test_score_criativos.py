from frontend.services import score_criativos as sc


def test_nota_nos_pontos_da_regua():
    m = 76.67
    assert sc.nota_custo_lead_a(m, m) == 50
    assert sc.nota_custo_lead_a(1.5 * m, m) == 25
    assert sc.nota_custo_lead_a(m / 1.5, m) == 75


def test_nota_bate_com_o_pes_nov_26():          # números do mockup aprovado
    m = 76.67
    assert sc.nota_custo_lead_a(188.26, m) == 0   # AD385, limitado em 0
    assert sc.nota_custo_lead_a(36.44, m) == 96   # AD210
    assert sc.nota_custo_lead_a(37.26, m) == 94   # AD393
    assert sc.nota_custo_lead_a(1.0, m) == 100    # limitado em 100


def test_notas_por_anuncio_mediana_so_com_30_leads_a():
    r = sc.notas_por_anuncio(
        {"AD1": 3000.0, "AD2": 6000.0, "AD3": 9000.0, "AD4": 500.0, "AD5": 800.0, "AD6": 0.0},
        {"AD1": 100, "AD2": 100, "AD3": 100, "AD4": 29, "AD6": 50},
    )
    assert r["mediana"] == 60.0
    a = r["anuncios"]
    assert a["AD2"]["nota"] == 50 and a["AD2"]["custo_a"] == 60.0 and a["AD2"]["motivo"] is None
    assert a["AD4"] == {"nota": None, "leads_a": 29, "custo_a": 500.0 / 29, "motivo": "poucos_leads_a"}
    assert a["AD5"]["nota"] is None and a["AD5"]["motivo"] == "sem_leads" and a["AD5"]["leads_a"] == 0
    assert a["AD6"]["nota"] is None and a["AD6"]["motivo"] == "sem_gasto"


def test_notas_sem_nenhum_anuncio_com_30_leads_a():
    r = sc.notas_por_anuncio({"AD1": 1000.0}, {"AD1": 10})
    assert r["mediana"] is None
    assert r["anuncios"]["AD1"]["nota"] is None and r["anuncios"]["AD1"]["motivo"] == "poucos_leads_a"


# ── Tarefa 2: leads A por anúncio e compradores num lugar só ──────────────────────────────────────────────────
import pandas as pd


def test_contar_leads_a_por_anuncio():
    leads = pd.DataFrame({"email": ["a", "b", "c", "d", "e"],
                          "faixa_pesquisa": ["A", "A", "B", "C", "A"]})
    assert sc.contar_leads_a(leads, {"a": "AD1", "b": "AD1", "c": "AD1", "d": "AD2"}) == {"AD1": 2}


def test_leads_a_none_quando_ninguem_respondeu(monkeypatch):
    from frontend.services import lead_score as ls
    monkeypatch.setattr(ls, "obter_leads_do_lancamento",
                        lambda code: pd.DataFrame({"email": ["a"], "respondeu": [0], "faixa_pesquisa": ["C"]}))
    monkeypatch.setattr(sc, "_ad_por_email", lambda code: {"a": "AD1"})
    assert sc._leads_a_por_anuncio_sem_cache("X") is None


def test_leads_e_criativos_usam_a_mesma_funcao_de_compradores(monkeypatch):
    """/criativos e /leads dividem a entrada de cache `lead_score_leads`: os dois têm de chamar `obter_leads` com o
    mesmo conjunto de compradores (hotmart | tmb), senão um comprador vazio envenenaria a /leads."""
    from types import SimpleNamespace
    from frontend.db_readers import sales
    from frontend.routes import leads as rl
    from frontend.services import lead_score as ls

    monkeypatch.setattr(sales, "read_vendas", lambda code: SimpleNamespace(
        emails_hotmart={"h@x"}, emails_tmb={"t@x"}))
    recebidos = []

    def falso_obter_leads(code, emails_compradores):
        recebidos.append(set(emails_compradores))
        return pd.DataFrame({"email": ["a"], "respondeu": [1], "faixa_pesquisa": ["A"]})

    monkeypatch.setattr(ls, "obter_leads", falso_obter_leads)
    monkeypatch.setattr(sc, "_ad_por_email", lambda code: {"a": "AD1"})

    rl._score_leads_df("X")
    assert sc._leads_a_por_anuncio_sem_cache("X") == {"AD1": 1}
    assert recebidos == [{"h@x", "t@x"}, {"h@x", "t@x"}]


# ── Tarefa 3: rota JSON /criativos/score ──────────────────────────────────────────────────────────────────────
import pytest
from types import SimpleNamespace


@pytest.fixture(scope="module")
def client_trafego():
    from fastapi.testclient import TestClient

    from frontend.app import app
    from frontend.auth import _sign_session

    with TestClient(app, follow_redirects=False) as c:
        c.cookies.set("session_token", _sign_session("u-teste", "trafego", ["PES"], "t@teste.local"))
        yield c


def _fakes_da_rota(monkeypatch, leads_a, lancamento=True):
    from frontend.routes import media

    async def _dados(launch, **k):
        return {"meta": None, "google": None, "vendas": None}

    monkeypatch.setattr(media, "get_launches", lambda: [])
    monkeypatch.setattr(media, "resolve_launch",
                        lambda code, launches: SimpleNamespace(code="PES-NOV-26") if lancamento else None)
    monkeypatch.setattr(media, "_fetch_all_data", _dados)
    monkeypatch.setattr(media, "_creative_overview",
                        lambda *a, **k: {"rows": [{"ad_code": "AD1", "gasto": 3000.0}]})
    monkeypatch.setattr(sc, "leads_a_por_anuncio", lambda code: leads_a)


def test_rota_score_devolve_notas(client_trafego, monkeypatch):
    _fakes_da_rota(monkeypatch, {"AD1": 50})
    r = client_trafego.get("/criativos/score?launch_code=PES-NOV-26")
    assert r.status_code == 200
    j = r.json()
    assert j["pontuavel"] is True and j["mediana"] == 60.0 and j["anuncios"]["AD1"]["nota"] == 50


def test_rota_score_sem_pesquisa_pontuavel(client_trafego, monkeypatch):
    _fakes_da_rota(monkeypatch, None)
    assert client_trafego.get("/criativos/score?launch_code=PI-JAN-26").json() == {"pontuavel": False}


def test_rota_score_lancamento_inexistente(client_trafego, monkeypatch):
    _fakes_da_rota(monkeypatch, {"AD1": 50}, lancamento=False)
    r = client_trafego.get("/criativos/score?launch_code=XXX")
    assert r.status_code == 200 and r.json() == {"pontuavel": False}


def test_rota_score_falha_devolve_500(client_trafego, monkeypatch):
    _fakes_da_rota(monkeypatch, {"AD1": 50})

    def _boom(code):
        raise RuntimeError("x")

    monkeypatch.setattr(sc, "leads_a_por_anuncio", _boom)
    r = client_trafego.get("/criativos/score?launch_code=PES-NOV-26")
    assert r.status_code == 500 and r.json() == {"erro": "falha ao calcular"}


def test_rota_score_black_codigo_legado(client_trafego, monkeypatch):
    from frontend.routes import media
    _fakes_da_rota(monkeypatch, {"AD1": 50})
    monkeypatch.setattr(media, "resolve_launch", lambda code, launches: SimpleNamespace(code="BV-25"))

    def _nao_deve_chamar(code):
        raise AssertionError("chamada pesada antes do retorno antecipado")

    monkeypatch.setattr(sc, "leads_a_por_anuncio", _nao_deve_chamar)
    r = client_trafego.get("/criativos/score?launch_code=BV-25")
    assert r.status_code == 200 and r.json() == {"pontuavel": False, "motivo": "codigo_legado"}


def test_rota_score_erro_de_leitura_da_plataforma_devolve_500(client_trafego, monkeypatch):
    from frontend.routes import media
    _fakes_da_rota(monkeypatch, {"AD1": 50})

    async def _dados(launch, **k):
        return {"meta": None, "google": None, "vendas": None, "_errors": ["meta: timeout"]}

    monkeypatch.setattr(media, "_fetch_all_data", _dados)
    r = client_trafego.get("/criativos/score?launch_code=PES-NOV-26")
    assert r.status_code == 500 and r.json() == {"erro": "falha ao calcular"}


def test_rota_score_tem_permissao_de_midia():
    from frontend.auth import ROUTE_PERMISSIONS, _MEDIA
    assert ROUTE_PERMISSIONS["/criativos/score"] == _MEDIA
