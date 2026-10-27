import pandas as pd

from frontend.db_readers.whatsapp_eventos import _picos, _varredura


def _ev(ts, grupo, ent_sai, numero):
    return {"timestamp": pd.Timestamp(ts, tz="UTC"), "nome_grupo": grupo, "ent_sai": ent_sai, "numero_lead": numero}


def test_varredura_conta_pessoa_ativa_em_qualquer_grupo():
    df = pd.DataFrame([
        _ev("2026-10-22 13:00", "G1", "Entrou", "A"),
        _ev("2026-10-22 13:05", "G2", "Entrou", "A"),   # A em dois grupos
        _ev("2026-10-22 14:00", "G1", "Entrou", "B"),
        _ev("2026-10-23 13:00", "G1", "Saiu", "A"),     # A ainda está no G2
        _ev("2026-10-23 15:00", "G1", "Saiu", "B"),     # B saiu de vez
        _ev("2026-10-25 13:00", "G2", "Saiu", "A"),     # A saiu de vez; 24/10 sem evento
    ])
    r = _varredura(df)
    assert r["resumo"]["total"] == 2
    assert r["resumo"]["total_limpo"] == 0
    assert r["resumo"]["grupos"] == 2
    dias = {l["data"]: l for l in r["diario"]}
    assert list(dias) == ["2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"]  # dia sem evento entra na série
    assert (dias["2026-10-22"]["entradas"], dias["2026-10-22"]["leads_no_dia"]) == (2, 2)
    assert (dias["2026-10-23"]["saidas"], dias["2026-10-23"]["leads_no_dia"]) == (2, 1)
    assert dias["2026-10-24"]["leads_no_dia"] == 1   # herda o saldo do dia anterior
    assert dias["2026-10-25"]["leads_no_dia"] == 0
    assert dias["2026-10-23"]["relacao"] == -2


def test_varredura_reentrada_nao_conta_pessoa_nova_nem_duplica_ativo():
    df = pd.DataFrame([
        _ev("2026-10-22 13:00", "G1", "Entrou", "A"),
        _ev("2026-10-23 13:00", "G1", "Saiu", "A"),
        _ev("2026-10-24 13:00", "G1", "Entrou", "A"),   # voltou
    ])
    r = _varredura(df)
    assert r["resumo"]["total"] == 1 and r["resumo"]["total_limpo"] == 1
    assert sum(l["entradas"] for l in r["diario"]) == 1


def test_dia_usa_fuso_de_brasilia():
    # 01:30 UTC de 23/10 ainda é 22/10 às 22:30 em Brasília
    r = _varredura(pd.DataFrame([_ev("2026-10-23 01:30", "G1", "Entrou", "A")]))
    assert r["diario"][0]["data"] == "2026-10-22"


def test_picos():
    p = _picos([
        {"data": "2026-10-22", "leads_no_dia": 5, "saidas": 1},
        {"data": "2026-10-23", "leads_no_dia": 9, "saidas": 4},
        {"data": "2026-10-24", "leads_no_dia": 7, "saidas": 2},
    ])
    assert p["leads_no_dia"] == {"valor": 9, "data": "2026-10-23"}
    assert p["saidas"] == {"valor": 4, "data": "2026-10-23"}


def test_erro_de_banco_nao_vira_sem_grupos(monkeypatch):
    """Um estouro de tempo no banco não pode virar "lançamento sem grupos" (o card guardava isso por 1h)."""
    import pytest
    from frontend import cache
    from frontend.db_readers import whatsapp_eventos as we

    def _estoura(code):
        raise RuntimeError("canceling statement due to statement timeout")

    monkeypatch.setattr(we, "_calcular", _estoura)
    monkeypatch.setattr(cache, "_get_or_compute", lambda code, chave, compute, ttl=None: compute())
    assert we.ler("PES-NOV-26") == {}                    # leitores de tela seguem sem quebrar
    with pytest.raises(RuntimeError):
        we.ler("PES-NOV-26", propagar=True)              # quem guarda em cache precisa saber que falhou
    with pytest.raises(RuntimeError):
        we.resumo_wa("PES-NOV-26")
