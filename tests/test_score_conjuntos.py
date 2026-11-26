"""Conta pura das notas por conjunto, par anúncio×conjunto, público e segmento (sem banco)."""
from frontend.services.score_conjuntos import montar_score, somar_unidades

GASTO = {"meta:1": 3000, "meta:2": 6000, "google:9": 2000, "meta:5": 500}
LEADS = {"meta:1": 60, "meta:2": 40, "google:9": 20}


def _montar(**kw):
    args = dict(gasto_grupo=GASTO, leads_grupo=LEADS, gasto_par={}, leads_par={}, info_grupo={},
                publicos={}, segmentos={}, nomes_meta={}, cobertura_leads_a=None)
    args.update(kw)
    return montar_score(**args)


def test_nota_do_conjunto_usa_mediana_dos_conjuntos():
    r = _montar()
    assert r["mediana_conjunto"] == 100
    c = r["conjuntos"]
    assert c["meta:1"]["nota"] == 93
    assert c["meta:2"]["nota"] == 25
    assert c["meta:1"]["gasto"] == 3000
    assert c["google:9"]["motivo"] == "poucos_leads_a"
    assert c["meta:5"]["motivo"] == "sem_leads"
    assert c["meta:5"]["nota"] is None
    assert c["meta:1"]["plataforma"] == "" and c["meta:1"]["nome"] == ""


def test_conjunto_carrega_info_do_grupo():
    r = _montar(info_grupo={"meta:1": {"plataforma": "meta", "campanha": "C", "nome": "N"}})
    assert (r["conjuntos"]["meta:1"]["plataforma"], r["conjuntos"]["meta:1"]["campanha"],
            r["conjuntos"]["meta:1"]["nome"]) == ("meta", "C", "N")


def test_par_usa_mediana_de_todos_os_pares():
    r = _montar(
        gasto_par={"meta:1|AD1": 4000, "meta:1|AD2": 2000, "meta:2|AD1": 6000, "meta:2|AD3": 3000,
                   "meta:zz|AD1": 10},
        leads_par={"meta:1|AD1": 60, "meta:1|AD2": 20, "meta:2|AD1": 40, "meta:2|AD3": 30})
    assert r["mediana_par"] == 100
    a = r["conjuntos"]["meta:1"]["anuncios"]
    assert a["AD1"]["nota"] == 75
    assert a["AD1"]["gasto"] == 4000
    assert a["AD2"]["motivo"] == "poucos_leads_a"
    assert "AD3" in r["conjuntos"]["meta:2"]["anuncios"]
    assert "meta:zz" not in r["conjuntos"]


def test_somar_unidades_conta_cada_conjunto_uma_vez():
    gasto, leads = somar_unidades({"meta:p1": {"meta:1", "meta:2"}, "meta:p2": {"meta:x"}}, GASTO, LEADS)
    assert gasto["meta:p1"] == 9000 and leads["meta:p1"] == 100
    assert gasto["meta:p2"] == 0 and leads["meta:p2"] == 0


def test_publico_so_com_conjuntos_sem_gasto_de_captacao():
    r = _montar(publicos={"meta:p9": {"meta:x"}, "meta:p1": {"meta:1", "meta:2"}},
                segmentos={"Seg": {"google:9"}}, nomes_meta={"Nome": {"meta:1"}})
    assert r["publicos"]["meta:p9"]["motivo"] == "sem_gasto"
    assert r["publicos"]["meta:p1"]["gasto"] == 9000
    assert r["segmentos_google"]["Seg"]["gasto"] == 2000
    assert r["conjuntos_meta_por_nome"]["Nome"]["gasto"] == 3000
    assert "mediana_publico" in r and "mediana_segmento" in r and "mediana_nome_meta" in r


def test_cobertura_passa_direto():
    assert _montar(cobertura_leads_a=0.8)["cobertura_leads_a"] == 0.8
