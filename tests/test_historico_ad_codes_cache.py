from frontend.db_readers import ads_meta


def _limpar():
    ads_meta.reset_historico_cache()


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


def test_codigos_e_nomes_compartilham_uma_leitura_e_o_reset_esquece(monkeypatch):
    _limpar()
    leituras = []
    monkeypatch.setattr(ads_meta, "_ler_nomes_anteriores",
                        lambda code: leituras.append(code) or ["AD010 - x", "AD-FE02 - y"])
    assert ads_meta.get_historico_ad_codes("BV-26") == {"AD10"}   # _normalize_ad_code tira o zero
    assert set(ads_meta.get_historico_ad_nomes("BV-26")) == {"AD-FE02"}
    assert leituras == ["BV-26"]                      # a segunda função não foi ao banco
    ads_meta.reset_historico_cache()
    ads_meta.get_historico_ad_codes("BV-26")
    assert leituras == ["BV-26", "BV-26"]


def test_historico_de_nomes_tambem_e_cacheado(monkeypatch):
    _limpar()
    leituras = []

    def ler(code):
        leituras.append(code)
        return ["AD-IV09 - Caixinha de pergunta", "AD-FE02 - Tudo em 1 min"]

    monkeypatch.setattr(ads_meta, "_ler_nomes_anteriores", ler)
    a = ads_meta.get_historico_ad_nomes("BV-26")
    a.setdefault("AD-IV09", set()).add("MUTADO")
    b = ads_meta.get_historico_ad_nomes("BV-26")
    assert leituras == ["BV-26"]
    assert "MUTADO" not in b["AD-IV09"]
    assert set(b) == {"AD-IV09", "AD-FE02"}


def test_nomes_anteriores_filtra_prefixo_por_faixa(monkeypatch):
    chamadas = []

    class _Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params):
            chamadas.append((str(sql), params))
            class _R:
                def fetchall(self_inner): return [("AD001 - x",)]
            return _R()

    class _Engine:
        def connect(self): return _Conn()

    monkeypatch.setattr(ads_meta, "_get_engine", lambda: _Engine())
    assert ads_meta._ler_nomes_anteriores("PI-NOV-26") == ["AD001 - x", "AD001 - x"]
    sql, params = chamadas[0]
    assert "ILIKE" not in sql
    assert params == {"code": "PI-NOV-26", "ini": "PI-", "fim": "PI."}
    assert ads_meta._ler_nomes_anteriores("") == []
