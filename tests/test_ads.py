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
    # lançamento normal: sem tag de expert, sai do prefixo do código
    assert expert_do_nome("[MA][engajamento][pré-qualificação][quente][reels][PES-NOV-26][19.10.26]") == "ivan"
    assert expert_do_nome("[GA][pré-qualificação][frio][PI-NOV-26][12.10.26]") == "mateus"
    assert expert_do_nome("[MA][cadastro][captação][PBB-AGO-26]") == "felipe"
    assert expert_do_nome("[MA][captação][BV-26][05.10.26]") is None


# ---------------------------------------------------------------------------- auditoria de LPs
from scripts.ads.auditar_lps import codigos_lancamento, normalizar_url, pixels_disparados, problemas_lp  # noqa: E402

_V1A = "https://lp.braboconcursos.com.br/black-vitalicia-26-v1a/"
_LP = "https://lp.braboconcursos.com.br/"
_OFICIAIS = {**{f"{_LP}black-vitalicia-26-{v}/": "VITALICIA-2026" for v in ("v1a", "v3", "v1b")},
             f"{_LP}cadastro-base-forte-v2/": "BASE-FORTE-BV-26"}


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
    assert problemas_lp(_lp(), "BV-26", {"mateus", "felipe"}, oficiais=_OFICIAIS) == []


def test_lp_v3a_com_form_da_black_2025():
    url = "https://lp.braboconcursos.com.br/black-vitalicia-26-v3a/"
    lp = _lp(url, [{"id": "422", "nome": "FORMULÁRIO BLACK 2025 v3 A - BV-25 - Mateus",
                    "tags": ["[BLACK] [LANÇAMENTO] [VITALICIA-2025]"]}])
    probs = problemas_lp(lp, "BV-26", {"mateus"}, oficiais=_OFICIAIS)
    assert "fora da lista oficial do lançamento" in probs
    assert any("outro lançamento" in p for p in probs)
    assert any("nenhuma tag do lançamento" in p for p in probs)


def test_lp_base_forte_aceita_a_tag_dela():
    url = "https://lp.braboconcursos.com.br/cadastro-base-forte-v2/"
    lp = _lp(url, [{"id": "690", "nome": "FORMULÁRIO BASE FORTE [BV-26] - V2", "tags": ["[BASE-FORTE-BV-26]"]}])
    assert problemas_lp(lp, "BV-26", {"ivan"}, oficiais=_OFICIAIS) == []


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


def test_sem_lista_oficial_nao_acusa_fora_da_lista():
    probs = problemas_lp(_lp(), "PI-NOV-26", set())
    assert not any("lista oficial" in p for p in probs)
    assert any("outro lançamento" in p for p in probs)   # o form de exemplo é do BV-26


def test_cls_e_tbt_ruins_alertam():
    probs = problemas_lp(_lp(cls=0.4, tbt_ms=900), "BV-26", set(), oficiais=_OFICIAIS)
    assert any("CLS" in p for p in probs) and any("TBT" in p for p in probs)


def test_obrigado_fora_do_ar_alerta():
    lp = _lp(forms=[{"id": "678", "nome": "FORMULÁRIO [BV-26] - V1A", "tags": ["[BLACK] [LANÇAMENTO] [VITALICIA-2026]"],
                     "obrigado": "https://lp.braboconcursos.com.br/obg-black-vitalicia-26-v1a", "obrigado_status": 404}])
    assert any("HTTP 404" in p for p in problemas_lp(lp, "BV-26", set(), oficiais=_OFICIAIS))


def test_resumo_pagespeed():
    from scripts.ads.auditar_lps import resumo_pagespeed
    audits = {"largest-contentful-paint": {"numericValue": 2600}, "first-contentful-paint": {"numericValue": 1900},
              "cumulative-layout-shift": {"numericValue": 0.01}, "total-blocking-time": {"numericValue": 30},
              "speed-index": {"numericValue": 3000}, "server-response-time": {"numericValue": 120},
              "total-byte-weight": {"numericValue": 2048 * 1024},
              "network-requests": {"details": {"items": [1, 2, 3]}},
              "render-blocking": {"title": "Elimine recursos que bloqueiam", "details": {"type": "opportunity", "overallSavingsMs": 900}}}
    j = {"lighthouseResult": {"categories": {"performance": {"score": 0.95}}, "audits": audits},
         "loadingExperience": {"origin_fallback": True, "metrics": {}},
         "originLoadingExperience": {"metrics": {"CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5, "category": "FAST"},
                                                 "INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "FAST"}}}}
    r = resumo_pagespeed(j)
    assert r["nota"] == 95 and r["lcp"] == 2.6 and r["peso_kb"] == 2048 and r["requisicoes"] == 3
    assert r["oportunidades"][0]["economia_ms"] == 900
    assert r["crux_url"] == {} and r["crux_origem"]["cls"]["p75"] == 0.05 and r["crux_origem"]["inp_ms"]["p75"] == 180


def test_chave_do_print_e_o_caminho_sem_barra():
    from scripts.capturar_lps import chave_da_url
    assert chave_da_url("https://lp.braboconcursos.com.br/black-vitalicia-26-v1a/") == "/black-vitalicia-26-v1a"
    assert chave_da_url("https://lp.braboconcursos.com.br/x?utm_source=y") == "/x"


def test_asset_feed_formato_engajamento():
    padrao = asset_feed_por_posicionamento("video", "1", "2", "t", "https://x/")
    assert padrao["ad_formats"] == ["AUTOMATIC_FORMAT"]
    eng = asset_feed_por_posicionamento("video", "1", "2", "t", "https://x/", formato="SINGLE_VIDEO")
    assert eng["ad_formats"] == ["SINGLE_VIDEO"]


# ---------------------------------------------------------------------------- públicos (SEG-4)
from scripts.ads.publicos import de_outro_produto, lancamento_do_nome, problemas_publico, produto_do_nome  # noqa: E402

ALUNO = "A1"
CAD = {"C1": "[SITE] Cadastrados [PES-NOV-26] - 180D"}


def _pp(inc=None, exc=None, frio=False, tam=None, aluno=ALUNO):
    inc = inc or {}
    return problemas_publico("g", frio=frio, incluidos=inc, excluidos=exc if exc is not None else {ALUNO: "alunos", **CAD},
                             aluno_id=aluno, lancamento="PES-NOV-26", produto="PES",
                             tamanhos=tam if tam is not None else {i: 10_000 for i in inc})


def test_publico_produto_e_lancamento_do_nome():
    assert produto_do_nome("[MA][cadastro][captação][frio][pós-edital][PES-NOV-26][26.10.26]") == "PES"
    assert produto_do_nome("[GA][captação][PI-NOV-26]") == "PI"
    assert lancamento_do_nome("[MA][cadastro][captação][frio][PES-NOV-26][26.10.26]") == "PES-NOV-26"
    assert lancamento_do_nome("[MA][ivan][aquecimento][BV-26]") == "BV-26"


def test_publico_grupo_certo_passa():
    assert _pp(inc={"X": "[Lista] Cadastrados [PES-SET-26]"}) == []


def test_publico_sem_exclusao_de_aluno_e_cadastrado():
    p = _pp(exc={})
    assert any("não exclui alunos" in x for x in p) and any("não exclui cadastrados do PES-NOV-26" in x for x in p)


def test_publico_frio_com_quente_na_inclusao_caso_pes_nov_26():
    # o 00 - Interesses do frio do PES-NOV-26: aluno e cadastrado do lançamento na INCLUSÃO, sem exclusão
    p = _pp(inc={ALUNO: "[M] Lista de Alunos Escrevente 26", **CAD, "E": "[FB] - Envolvimento Todos - 60D"},
            exc={}, frio=True)
    assert any("INCLUI a lista de alunos" in x for x in p)
    assert any("INCLUI cadastrados do próprio lançamento" in x for x in p)
    assert any("frio com 3 público(s) próprio(s)" in x for x in p)


def test_publico_frio_aceita_semelhante():
    assert _pp(inc={"S": "Semelhante (1%) - [M] Lista de Alunos Escrevente 26"}, frio=True) == []


def test_publico_lista_pequena_e_outro_produto():
    p = _pp(inc={"L": "[M] Lista Leads Escrevente", "I": "Lista Todos Alunos INSS"}, tam={"L": 0, "I": 30_000})
    assert any("< 500 dentro do público" in x and "Lista Leads Escrevente" in x for x in p)
    assert any("NÃO ENTREGA" in x for x in _pp(inc={"L": "[M] Lista Leads Escrevente"}, tam={"L": 0}))
    assert any("outro produto" in x and "INSS" in x for x in p)
    assert de_outro_produto("[Lista] Grupo VIP TJSP PES-MAI-26 [BV-26]", "PES") is None
    assert de_outro_produto("[YT] Envolvimento [TODOS] - 60D", "PES") is None   # "TODOS" não é "TJ"


def test_publico_sem_lista_de_aluno_definida_avisa():
    assert any("não definida" in x for x in _pp(aluno=None))


def test_publico_excluir_semelhante_e_erro():
    p = _pp(exc={ALUNO: "alunos", **CAD, "S": "Semelhante (BR, 1%) - [Lista] Alunos BB - 2026"})
    assert any("semelhante não é exclusão" in x for x in p)


def test_publico_regra_so_vale_para_captacao_e_pre_quali():
    from scripts.ads.publicos import conferir_adset_meta, sujeito_a_regra
    assert sujeito_a_regra("[MA][cadastro][captação][frio][PES-NOV-26]")
    assert sujeito_a_regra("[GA][pré-qualificação][quente][PI-NOV-26]")
    assert not sujeito_a_regra("[ENGAJAMENTO] Lembrete [PI-JAN-26] - 05.01.26")
    lembrete = {"name": "00 - Cadastrados", "targeting": {"custom_audiences": [{"id": "C1", "name": CAD["C1"]}]}}
    assert conferir_adset_meta(lembrete, "[ENGAJAMENTO] Lembrete [PES-NOV-26]", {}) == []
