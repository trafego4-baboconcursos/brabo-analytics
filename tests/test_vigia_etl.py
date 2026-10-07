"""Vigia do ETL — a regra de "parado" e a cadência das mensagens.

O vigia mora no site porque o ETL parado não consegue avisar que parou. Desde
07/10/26 isso pesa mais: o histórico de UTM por lançamento só registra o que o
ETL vê, então ETL parado = cadastros sem histórico, em silêncio. Estes testes
não tocam banco nem Slack.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import frontend.services.vigia_etl as v

AGORA = datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)


def _frescas(ref=AGORA, **atraso_h):
    """Todas as fontes com carga há 10 min de `ref`, salvo o atraso pedido."""
    base = {f: ref - timedelta(minutes=10) for f in v.LIMITES_H}
    for fonte, horas in atraso_h.items():
        base[fonte] = None if horas is None else ref - timedelta(hours=horas)
    return base


def test_tudo_em_dia_nao_acusa():
    assert v.avaliar(_frescas(), AGORA - timedelta(minutes=10), AGORA) == []


def test_fonte_alem_do_limite_acusa_etl_parado():
    problemas = v.avaliar(_frescas(active_campaign=4), AGORA - timedelta(hours=4), AGORA)
    assert [p["fonte"] for p in problemas] == ["active_campaign"]
    assert "Active Campaign sem carga desde" in problemas[0]["texto"]


def test_dentro_do_limite_nao_acusa():
    """Meta carrega a cada 30 min; 1h30 de atraso ainda está dentro dos 2h."""
    assert v.avaliar(_frescas(meta_ads=1.5), AGORA, AGORA) == []


def test_fonte_que_nunca_carregou_acusa():
    problemas = v.avaliar(_frescas(google_ads=None), AGORA, AGORA)
    assert problemas[0]["texto"] == "Google Ads sem carga desde nunca"


def test_ac_carrega_mas_historico_nao_grava():
    """O estado real de 07/10/26 às 16:24: site novo, ETL com código antigo."""
    problemas = v.avaliar(_frescas(), AGORA - timedelta(hours=5), AGORA)
    assert [p["tipo"] for p in problemas] == ["historico_parado"]
    assert "histórico de UTM não é gravado" in problemas[0]["texto"]


def test_tabela_do_historico_ausente_nao_acusa_historico():
    assert v.avaliar(_frescas(), None, AGORA) == []


def test_ac_parado_nao_duplica_com_historico_parado():
    """Com o AC parado, o histórico parado é consequência: um aviso só."""
    problemas = v.avaliar(_frescas(active_campaign=5), AGORA - timedelta(hours=5), AGORA)
    assert [p["tipo"] for p in problemas] == ["etl_parado"]


@pytest.fixture
def vigia(monkeypatch):
    """checar_e_avisar com banco e Slack trocados por memória."""
    enviadas: list[str] = []
    estado = {"ultimas": _frescas(), "historico": AGORA - timedelta(minutes=10)}
    monkeypatch.setattr(v, "_ler_estado_banco", lambda: (estado["ultimas"], estado["historico"]))
    monkeypatch.setattr(v, "_enviar_slack", lambda msg: enviadas.append(msg) or True)
    monkeypatch.setattr(v, "ESTADO", {"problemas": [], "checado_em": None, "desde": None, "avisado_em": None})
    return estado, enviadas


def test_mensagem_ao_parar_lembrete_e_normalizacao(vigia):
    estado, enviadas = vigia

    v.checar_e_avisar(AGORA)
    assert enviadas == []                                   # tudo em dia: silêncio

    estado["ultimas"] = _frescas(active_campaign=4)
    estado["historico"] = AGORA - timedelta(hours=4)
    v.checar_e_avisar(AGORA)
    assert len(enviadas) == 1 and "ETL parado" in enviadas[0]

    v.checar_e_avisar(AGORA + timedelta(hours=1))
    assert len(enviadas) == 1                               # sem spam a cada 15 min

    v.checar_e_avisar(AGORA + timedelta(hours=v.LEMBRETE_H))
    assert len(enviadas) == 2 and "Lembrete" in enviadas[1]

    depois = AGORA + timedelta(hours=v.LEMBRETE_H, minutes=15)
    estado["ultimas"] = _frescas(depois)
    estado["historico"] = depois - timedelta(minutes=10)
    v.checar_e_avisar(depois)
    assert len(enviadas) == 3 and "normalizado" in enviadas[2]
    assert v.ESTADO["problemas"] == []


def test_estado_alimenta_a_faixa_da_tela(vigia):
    estado, _ = vigia
    estado["ultimas"] = _frescas(google_ads=3)
    v.checar_e_avisar(AGORA)
    assert [p["fonte"] for p in v.ESTADO["problemas"]] == ["google_ads"]
