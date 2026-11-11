from frontend.db_readers import launches


def _limpar():
    launches._autodetect_cache.clear()


def test_autodetect_le_uma_vez_e_nao_vaza_mutacao(monkeypatch):
    _limpar()
    leituras = []
    monkeypatch.setattr(launches, "_ler_autodetect",
                        lambda code: leituras.append(code) or {"meta_leads": 10})
    a = launches.autodetect_launch_data("PI-NOV-26")
    a["meta_leads"] = 999                              # quem recebe não suja o cache
    b = launches.autodetect_launch_data("PI-NOV-26")
    assert leituras == ["PI-NOV-26"]
    assert b == {"meta_leads": 10}


def test_autodetect_falha_nao_e_cacheada(monkeypatch):
    _limpar()
    respostas = iter([None, {"meta_leads": 5}])
    monkeypatch.setattr(launches, "_ler_autodetect", lambda code: next(respostas))
    assert launches.autodetect_launch_data("PES-NOV-26") == {}
    assert "PES-NOV-26" not in launches._autodetect_cache
    assert launches.autodetect_launch_data("PES-NOV-26") == {"meta_leads": 5}


def test_autodetect_expira(monkeypatch):
    _limpar()
    leituras = []
    monkeypatch.setattr(launches, "_ler_autodetect", lambda code: leituras.append(code) or {})
    launches.autodetect_launch_data("PBB-NOV-26")
    ts, valor = launches._autodetect_cache["PBB-NOV-26"]
    launches._autodetect_cache["PBB-NOV-26"] = (ts - launches._AUTODETECT_TTL - 1, valor)
    launches.autodetect_launch_data("PBB-NOV-26")
    assert leituras == ["PBB-NOV-26", "PBB-NOV-26"]
