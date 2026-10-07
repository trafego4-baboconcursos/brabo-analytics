"""Testes das partes puras de scripts/ads (sem chamar as plataformas)."""
import hashlib
import json

from scripts.ads import padroes as P
from scripts.ads.google import identificadores_google
from scripts.ads.meta import (
    _serializar, asset_feed_por_posicionamento, expert_do_nome, linha_hash, links_do_criativo,
    problemas_adset, problemas_anuncios, targeting_padrao, telefone_e164,
)


def sha(v):
    return hashlib.sha256(v.encode()).hexdigest()


def test_serializar_transforma_dict_e_lista_em_json():
    d = _serializar({"a": {"b": 1}, "c": [1, 2], "d": "x", "e": None})
    assert d == {"a": '{"b": 1}', "c": "[1, 2]", "d": "x"}
    assert json.loads(d["a"]) == {"b": 1}


def test_telefone_e164():
    assert telefone_e164("(11) 98888-7777") == "5511988887777"
    assert telefone_e164("5511988887777") == "5511988887777"
    assert telefone_e164(11988887777.0) == "5511988887777"
    assert telefone_e164("55999998888") == "5555999998888"   # DDD 55 com 11 dígitos
    assert telefone_e164("") == ""


def test_linha_hash_normaliza_como_o_meta_pede():
    l = linha_hash({"email": " Fulano@Gmail.com ", "phone": "11 98888-7777", "first_name": "José", "last_name": "D'Ávila"})
    assert l[0] == sha("fulano@gmail.com")
    assert l[1] == sha("5511988887777")
    assert l[2] == sha("jose") and l[3] == sha("davila") and l[4] == sha("br")


def test_identificadores_google_separa_email_e_telefone():
    ids = identificadores_google([{"email": "A@b.com", "phone": "11988887777"}, {"email": "sem-arroba"}])
    assert ids == [{"email_address": sha("a@b.com")}, {"phone_number": sha("+5511988887777")}]


def test_asset_feed_por_posicionamento_tem_o_que_o_meta_exige():
    s = asset_feed_por_posicionamento("image", "hashFEED", "hashSTORY", "texto", "https://lp/x")
    assert s["optimization_type"] == "PLACEMENT" and s["ad_formats"] == ["AUTOMATIC_FORMAT"]
    assert s["call_to_action_types"] == ["LEARN_MORE"]
    regras = s["asset_customization_rules"]
    assert [r["priority"] for r in regras] == [1, 2]
    assert all({"image_label", "body_label", "link_url_label"} <= r.keys() for r in regras)
    assert "facebook_positions" not in regras[1]["customization_spec"]          # regra 2 = padrão
    assert len(s["bodies"][0]["adlabels"]) == 2 and len(s["link_urls"][0]["adlabels"]) == 2


def test_targeting_padrao():
    t = targeting_padrao(["1"], ["2"], sao_paulo=True, reels=True)
    assert (t["age_min"], t["age_max"]) == (25, 55)
    assert t["geo_locations"] == P.GEO_SAO_PAULO
    assert t["targeting_automation"] == {"advantage_audience": 0}
    assert t["instagram_positions"] == ["story", "reels"]


def test_problemas_adset():
    ok = {"name": "00", "end_time": "2026-10-05", "targeting": {"age_min": 25, "age_max": 55,
          "targeting_automation": {"advantage_audience": 0}}}
    assert problemas_adset(ok, "[MA][mateus][captação]") == []
    ruim = {"name": "00", "targeting": {"age_min": 18, "age_max": 65, "facebook_positions": ["feed", "story"]}}
    p = problemas_adset(ruim, "[MA][mateus][reels]")
    assert len(p) == 4   # idade, advantage, fim, reels com feed


def test_problemas_anuncios():
    bom = {"name": "AD1", "tracking_specs": [{"action.type": ["offsite_conversion"], "fb_pixel": ["608"]}],
           "creative": {"url_tags": P.UTM_META, "object_story_spec": {"link_data": {"link": "https://lp/x/"}}}}
    assert problemas_anuncios([bom], "608") == []
    ruim = {"name": "AD2", "tracking_specs": [], "creative": {"url_tags": "",
            "asset_feed_spec": {"link_urls": [{"website_url": "https://lp/x?utm_source=fb"}]}}}
    assert len(problemas_anuncios([ruim], "608")) == 3


def test_links_do_criativo_cobre_os_formatos():
    c = {"object_story_spec": {"link_data": {"link": "a", "child_attachments": [{"link": "b"}]},
                               "video_data": {"call_to_action": {"value": {"link": "c"}}}},
         "asset_feed_spec": {"link_urls": [{"website_url": "d"}]}}
    assert sorted(links_do_criativo(c)) == ["a", "b", "c", "d"]


def test_expert_do_nome():
    assert expert_do_nome("[MA][trio][ivan][captação]") == "ivan"
    assert expert_do_nome("[MA][M][aquecimento]") is None
