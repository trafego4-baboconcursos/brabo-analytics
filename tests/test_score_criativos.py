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
