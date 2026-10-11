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


# ---------------------------------------------------------------------------- auditoria de LPs
from scripts.ads.auditar_lps import codigos_lancamento, normalizar_url, pixels_disparados, problemas_lp  # noqa: E402

_V1A = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1a/"


def _lp(url=_V1A, forms=None, **kw):
    base = {"url": url, "status": 200, "final": url, "gtm": {"GTM-KHKZXK7L"},
            "pixels": {"608218362997432", "990033038146806"}, "nota": 95, "lcp": 2.6,
            "forms": forms if forms is not None else
            [{"id": "678", "nome": "FORMULÁRIO [BV-26] - V1A", "tags": ["[BLACK] [LANÇAMENTO] [VITALICIA-2026]"]}]}
    return base | kw


def test_normalizar_url_tira_query_e_poe_barra():
    assert normalizar_url("https://LP.braboconcursos.com.br/black-vitalicia-26-v1a?utm_source=x#f") == _V1A


def test_codigos_lancamento():
    assert codigos_lancamento("FORMULÁRIO BLACK 2025 v3 A - BV-25 - Mateus") == {"BV-25"}
    assert codigos_lancamento("[PES-SET-26] form") == {"PES-SET-26"}


def test_pixel_por_get_e_por_post():
    reqs = ["https://www.facebook.com/tr/?id=608218362997432&ev=PageView",
            "https://www.facebook.com/tr/ id=990033038146806&ev=PageView&dl=x",
            'https://www.facebook.com/tr/ ------B\r\nContent-Disposition: form-data; name="id"\r\n\r\n111\r\n']
    assert pixels_disparados(reqs) == {"608218362997432", "990033038146806", "111"}


def test_lp_certa_sem_alerta():
    assert problemas_lp(_lp(), "BV-26", {"mateus", "felipe"}) == []


def test_lp_v3a_com_form_da_black_2025():
    url = "https://lp.braboconcursos.com.br/black-vitalicia-26-v3a/"
    lp = _lp(url, [{"id": "422", "nome": "FORMULÁRIO BLACK 2025 v3 A - BV-25 - Mateus",
                    "tags": ["[BLACK] [LANÇAMENTO] [VITALICIA-2025]"]}])
    probs = problemas_lp(lp, "BV-26", {"mateus"})
    assert "fora da lista oficial do lançamento" in probs
    assert any("outro lançamento" in p for p in probs)
    assert any("nenhuma tag do lançamento" in p for p in probs)


def test_lp_base_forte_aceita_a_tag_dela():
    url = "https://lp.braboconcursos.com.br/cadastro-base-forte-v2/"
    lp = _lp(url, [{"id": "690", "nome": "FORMULÁRIO BASE FORTE [BV-26] - V2", "tags": ["[BASE-FORTE-BV-26]"]}])
    assert problemas_lp(lp, "BV-26", {"ivan"}) == []


def test_lp_lenta_sem_gtm_e_sem_pixel():
    probs = problemas_lp(_lp(gtm=set(), pixels=set(), nota=30, lcp=6.2), "BV-26", {"felipe"})
    assert len(probs) == 4


def test_obrigado_fora_do_gatilho_de_lead():
    lp = _lp(forms=[{"id": "422", "nome": "FORMULÁRIO [BV-26] - V3", "tags": ["[BLACK] [LANÇAMENTO] [VITALICIA-2026]"],
                     "obrigado": "https://lp.braboconcursos.com.br/obg-black-vitalicia-25-v3a"}])
    probs = problemas_lp(lp, "BV-26", set(), ["/obg-black-vitalicia-26", "/obg-base-forte-v"])
    assert any("não dispara Lead" in p for p in probs)
    lp["forms"][0]["obrigado"] = "https://lp.braboconcursos.com.br/obg-black-vitalicia-26-v3"
    assert problemas_lp(lp, "BV-26", set(), ["/obg-black-vitalicia-26"]) == []


def test_lead_por_pagina_baixo_alerta():
    real = {"cliques": 4295, "lpv": 1938, "leads": 52, "lead_por_lpv": 2.7, "taxa": 45.1}
    assert any("lead por página" in p for p in problemas_lp(_lp(real=real), "BV-26", set()))
    assert problemas_lp(_lp(real=real | {"lpv": 50}), "BV-26", set()) == []


def test_gatilhos_de_lead_da_versao_gtm():
    versao = {
        "tag": [{"name": "Tag - Meta Pixel - Leads - Lançamentos", "firingTriggerId": ["1", "2"]},
                {"name": "Tag - Meta Pixel - Lançamentos", "firingTriggerId": ["2147479553"]},
                {"name": "Conversão pausada", "paused": True, "firingTriggerId": ["3"]}],
        "trigger": [
            {"triggerId": "1", "filter": [{"type": "contains", "parameter": [
                {"key": "arg0", "value": "{{Page URL}}"}, {"key": "arg1", "value": "/obg-black-vitalicia-26"}]}]},
            {"triggerId": "2", "filter": [{"type": "contains", "parameter": [
                {"key": "arg0", "value": "{{Page URL}}"}, {"key": "arg1", "value": "/obg-base-forte-v"}]}]},
            {"triggerId": "3", "filter": [{"type": "contains", "parameter": [
                {"key": "arg0", "value": "{{Page URL}}"}, {"key": "arg1", "value": "/nao-conta"}]}]}],
    }
    from scripts.ads.auditar_lps import gatilhos_de_lead
    assert gatilhos_de_lead(versao) == ["/obg-base-forte-v", "/obg-black-vitalicia-26"]
