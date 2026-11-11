import pandas as pd

from frontend.db_readers import whatsapp_eventos as we


def _ev(ts, numero, ent="Entrou", grupo="G1"):
    return {"timestamp": pd.Timestamp(ts, tz="UTC"), "nome_grupo": grupo, "ent_sai": ent,
            "numero_lead": numero, "nome_campanha": "Projeto INSS [PI-NOV-26]"}


def _banco(eventos):
    """Simula o banco: devolve tudo, ou só timestamp >= desde, e registra as chamadas."""
    chamadas = []

    def consultar(code, desde=None):
        chamadas.append(desde)
        df = pd.DataFrame(eventos, columns=["timestamp", "nome_grupo", "ent_sai", "numero_lead", "nome_campanha"])
        return df if desde is None else df[df["timestamp"] >= desde].reset_index(drop=True)
    return consultar, chamadas


def _ordenado(df):
    return df.sort_values(["timestamp", "numero_lead"]).reset_index(drop=True)


def test_segunda_leitura_so_busca_a_janela_final_e_bate_com_a_completa(monkeypatch):
    we.reset_eventos_cache()
    eventos = [_ev("2026-10-22 10:00", "1"), _ev("2026-11-01 10:00", "2"), _ev("2026-11-10 10:00", "3")]
    consultar, chamadas = _banco(eventos)
    monkeypatch.setattr(we, "_consultar", consultar)

    we._carregar("PI-NOV-26")
    eventos.append(_ev("2026-11-11 09:00", "4"))
    eventos.append(_ev("2026-11-10 08:00", "5"))               # chegou atrasado, mas dentro da janela
    df = we._carregar("PI-NOV-26")

    assert chamadas[0] is None                                   # 1ª: completa
    assert chamadas[1] == pd.Timestamp("2026-11-10 07:00", tz="UTC")  # 2ª: max - 3 h
    assert _ordenado(df).equals(_ordenado(pd.DataFrame(eventos)))


def test_evento_apagado_dentro_da_janela_some(monkeypatch):
    we.reset_eventos_cache()
    eventos = [_ev("2026-10-22 10:00", "1"), _ev("2026-11-10 10:00", "2"), _ev("2026-11-10 11:00", "3")]
    consultar, _ = _banco(eventos)
    monkeypatch.setattr(we, "_consultar", consultar)
    we._carregar("PI-NOV-26")
    eventos.pop(1)
    assert sorted(we._carregar("PI-NOV-26")["numero_lead"]) == ["1", "3"]


def test_recarga_completa_depois_do_prazo(monkeypatch):
    we.reset_eventos_cache()
    consultar, chamadas = _banco([_ev("2026-11-10 10:00", "1")])
    monkeypatch.setattr(we, "_consultar", consultar)
    we._carregar("PI-NOV-26")
    ts, df = we._eventos["PI-NOV-26"]
    we._eventos["PI-NOV-26"] = (ts - we._RECARGA_TOTAL - 1, df)
    we._carregar("PI-NOV-26")
    assert chamadas == [None, None]


def test_lancamento_sem_eventos_nao_fica_preso_no_incremental(monkeypatch):
    we.reset_eventos_cache()
    consultar, chamadas = _banco([])
    monkeypatch.setattr(we, "_consultar", consultar)
    assert we._carregar("PES-NOV-26").empty
    assert we._carregar("PES-NOV-26").empty
    assert chamadas == [None, None]                              # vazio não tem "max": relê completo


def test_falha_mantem_o_que_estava_guardado(monkeypatch):
    import pytest
    we.reset_eventos_cache()
    consultar, _ = _banco([_ev("2026-11-10 10:00", "1")])
    monkeypatch.setattr(we, "_consultar", consultar)
    we._carregar("PI-NOV-26")

    def estoura(code, desde=None):
        raise RuntimeError("timeout")
    monkeypatch.setattr(we, "_consultar", estoura)
    with pytest.raises(RuntimeError):
        we._carregar("PI-NOV-26")
    assert len(we._eventos["PI-NOV-26"][1]) == 1
