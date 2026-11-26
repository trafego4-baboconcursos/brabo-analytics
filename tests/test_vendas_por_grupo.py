"""Vendas atribuídas por conjunto (Facebook/Meta) e grupo (Google) — CPA da página /publicos."""
from frontend.db_readers import publicos as R
from frontend.services.vendas_por_grupo import casador_de_grupos, ligar_vendas, numero_do_grupo, slug

CAMP_M = "[MA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]"
CAMP_G = "[GA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]"
GRUPOS = [
    ("meta", CAMP_M, "01 - Cadastrados anteriores", "m1"),
    ("meta", CAMP_M, "04 - Viu vídeos (captação PES-NOV-26 + pré-quali PES-SET-26 50%)", "m4"),
    ("meta", "[MA][cadastro][captação][quente][reels][PES-NOV-26][26.10.26]", "01 - Cadastrados anteriores", "r1"),
    ("google", CAMP_G, "08 - Envolvimento todos 365D", "g8"),
]


def utm(source, campaign, content):
    return {"source": source, "medium": "", "campaign": campaign, "content": content, "term": ""}


def test_slug_e_numero_do_grupo():
    assert slug("08 - Envolvimento todos 365D") == slug("08-envolvimento-todos-365d")
    assert slug("Viu vídeos") == slug("viu videos")
    assert numero_do_grupo("04 - Viu vídeos PES-SET-26") == "04"
    assert numero_do_grupo("Lookalike 1%") is None


def test_liga_pelo_par_campanha_e_conjunto_e_pelo_slug_do_google():
    bu = {"a@x": utm("facebook", CAMP_M, "01 - Cadastrados anteriores"),
          "b@x": utm("google", CAMP_G, "08-envolvimento-todos-365d")}
    r = ligar_vendas(bu, {"a@x": 2, "b@x": 1}, {"a@x": 3000.0, "b@x": 1500.0}, GRUPOS)
    assert r.por_grupo[("meta", "m1")] == (2, 3000.0)     # mesmo nome em outra campanha (r1) não confunde
    assert r.por_grupo[("google", "g8")] == (1, 1500.0)
    assert r.ligadas == {"meta": 2, "google": 1} and r.sem_grupo == {}


def test_conjunto_renomeado_casa_pelo_numero_dentro_da_campanha():
    bu = {"a@x": utm("facebook", CAMP_M, "04 - Viu vídeos PES-SET-26 (captação + pré-quali 50%)")}   # nome antigo
    r = ligar_vendas(bu, {}, {"a@x": 900.0}, GRUPOS)
    assert r.por_grupo[("meta", "m4")] == (1, 900.0)


def test_sem_campanha_casa_pelo_nome_so_se_for_unico_no_lancamento():
    bu = {"a@x": utm("google", "", "08-envolvimento-todos-365d"),      # nome único: liga
          "b@x": utm("facebook", "", "01 - Cadastrados anteriores"),    # está em 2 campanhas: não liga
          "c@x": utm("facebook", CAMP_M, "unichat_comentario"),         # não é conjunto
          "d@x": utm("hotmart", "", "")}                                 # nem Meta nem Google: fora da conta
    r = ligar_vendas(bu, {}, {}, GRUPOS)
    assert r.por_grupo == {("google", "g8"): (1, 0.0)}
    assert r.ligadas == {"google": 1} and r.sem_grupo == {"meta": 2}
    assert r.cobertura("meta") == 0.0 and r.cobertura("google") == 100.0 and r.cobertura("tiktok") is None


def test_cpa_e_soma_das_vendas_no_publico():
    usos = [{"plataforma": "meta", "conta": "act_1", "campanha_id": "c1", "campanha_nome": CAMP_M, "campanha_status": "ACTIVE",
             "grupo_id": g, "grupo_nome": g, "grupo_status": "ACTIVE", "publico_id": "1", "publico_nome": "P",
             "publico_tipo": "ENGAJAMENTO", "papel": "inclui"} for g in ("a1", "a2")]
    d = {("meta", "a1"): R.Desempenho(0, 0, 1000, 50, vendas=4, receita=8000),
         ("meta", "a2"): R.Desempenho(0, 0, 500, 10, vendas=0)}
    v = R.montar_visao("PES-NOV-26", usos, {}, d, {}, None)
    p = v.publicos[0]
    assert (p.desempenho.vendas, p.desempenho.receita) == (4, 8000) and p.desempenho.cpa == 1500 / 4
    assert d[("meta", "a1")].cpa == 250 and d[("meta", "a2")].cpa is None
    assert d[("meta", "a1")].roas == 8.0


REF = ("meta", "[MA][captação][PES-NOV-26] Frio", "04 - Interesse", "111")


def test_casador_pelo_par_campanha_e_nome():
    c = casador_de_grupos([REF])
    assert c("facebook", "paid", "[MA][captação][PES-NOV-26] Frio", "04 - Interesse") == ("meta", "111")


def test_casador_conjunto_renomeado_casa_pelo_numero():
    c = casador_de_grupos([REF])
    assert c("facebook", "paid", "[MA][captação][PES-NOV-26] Frio", "04 - Interesse renomeado") == ("meta", "111")


def test_casador_nome_repetido_em_campanhas_diferentes_sem_campanha_da_none():
    c = casador_de_grupos([REF, ("meta", "[MA][captação][PES-NOV-26] Quente", "04 - Interesse", "222")])
    assert c("facebook", "paid", "", "04 - Interesse") is None


def test_casador_canal_fora_de_meta_e_google_da_none():
    c = casador_de_grupos([REF])
    assert c("email", "", "newsletter", "04 - Interesse") is None
