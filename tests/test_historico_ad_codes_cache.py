from frontend.db_readers import ads_meta


def _limpar():
    ads_meta._historico_codes_cache.clear()


def test_historico_e_lido_uma_vez_e_o_cache_nao_vaza_mutacao(monkeypatch):
    _limpar()
    leituras = []

    def ler(code):
        leituras.append(code)
        return {"AD001", "AD002"}

    monkeypatch.setattr(ads_meta, "_ler_historico_ad_codes", ler)
    a = ads_meta.get_historico_ad_codes("PES-NOV-26")
    a.add("MUTADO")                                   # quem recebe o conjunto não pode sujar o cache
    b = ads_meta.get_historico_ad_codes("PES-NOV-26")
    assert leituras == ["PES-NOV-26"]                 # a segunda chamada saiu do cache
    assert b == {"AD001", "AD002"}


def test_falha_de_leitura_nao_e_cacheada_e_serve_o_ultimo_bom(monkeypatch):
    _limpar()
    respostas = iter([{"AD001"}, None, {"AD001", "AD003"}])
    monkeypatch.setattr(ads_meta, "_ler_historico_ad_codes", lambda code: next(respostas))

    assert ads_meta.get_historico_ad_codes("PI-NOV-26") == {"AD001"}
    # força a expiração: a próxima leitura falha e o último valor bom continua valendo
    codigo, (_, valor) = "PI-NOV-26", ads_meta._historico_codes_cache["PI-NOV-26"]
    ads_meta._historico_codes_cache[codigo] = (0.0, valor)
    assert ads_meta.get_historico_ad_codes("PI-NOV-26") == {"AD001"}
    # a falha não foi gravada como "sem anúncios": a seguinte lê de novo e atualiza
    assert ads_meta.get_historico_ad_codes("PI-NOV-26") == {"AD001", "AD003"}


def test_falha_sem_valor_anterior_devolve_vazio_sem_cachear(monkeypatch):
    _limpar()
    monkeypatch.setattr(ads_meta, "_ler_historico_ad_codes", lambda code: None)
    assert ads_meta.get_historico_ad_codes("PBB-NOV-26") == set()
    assert "PBB-NOV-26" not in ads_meta._historico_codes_cache
