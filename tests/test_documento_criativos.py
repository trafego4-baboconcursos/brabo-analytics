import datetime as dt

from scripts.ads.documento_criativos import codigo_ad, documento_md, nome_publico_viu, papel_do_video, tipo_da_campanha


def test_papel_pelo_nome_e_pela_ordem():
    assert papel_do_video("AD043 - Estúdio Brabo - PI-NOV-26 (feed)", 0) == "feed"
    assert papel_do_video("sem marca", 2) == "story"
    assert papel_do_video("", 5) == "vídeo 6"


def test_tipo_e_nome_do_publico():
    assert tipo_da_campanha("[GA][cadastro][captação][quente][principal][PI-NOV-26][02.11.26]") == "principal"
    assert tipo_da_campanha("[GA][cadastro][captação][específico][potencial][PI-NOV-26][02.11.26]") == "potencial"
    assert nome_publico_viu("potencial", "PI-NOV-26") == "Viu Captação - Potencial - [PI-NOV-26] - 540D"
    assert codigo_ad("AD174 - Novo estúdio brabo - PI-NOV-26") == "AD174"


def test_publico_junta_climas_sem_repetir_e_ignora_imagem():
    ad = {"nome": "AD174 - X", "videos": {"horizontal": "h1", "feed": "f1", "story": "s1"}}
    google = [
        {"nome": "[GA][cadastro][captação][quente][principal][PI-NOV-26][02.11.26]", "id": 1, "status": "PAUSED",
         "ads": {"AD174": ad, "AD219": {"nome": "AD219 - img", "videos": {}}}},
        {"nome": "[GA][cadastro][captação][frio][principal][PI-NOV-26][02.11.26]", "id": 2, "status": "PAUSED",
         "ads": {"AD174": ad}},
    ]
    md = documento_md("PI-NOV-26", google, [], dt.datetime(2026, 11, 1, 22, 0))
    bloco = md.split("### Viu Captação - Principal - [PI-NOV-26] - 540D")[1].split("```")[1]
    assert bloco.split() == ["h1", "f1", "s1"]
    assert "Imagem: AD219 - img" in md
    assert "https://youtu.be/f1" in md
