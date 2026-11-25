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
