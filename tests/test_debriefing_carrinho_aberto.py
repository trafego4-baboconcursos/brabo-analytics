"""Debriefing com carrinho aberto re-aquece o snapshot (15/10/26)."""
from datetime import date, timedelta

import frontend.routes.analytics as an


def test_carrinho_aberto_pela_janela(monkeypatch):
    hoje = date.today()
    monkeypatch.setattr(an, "_launch_cfg", lambda c: {"carrinho_start_date": hoje - timedelta(days=1),
                                                       "carrinho_end_date": hoje + timedelta(days=1)})
    assert an._carrinho_aberto("X") is True
    monkeypatch.setattr(an, "_launch_cfg", lambda c: {"carrinho_start_date": hoje + timedelta(days=2),
                                                       "carrinho_end_date": hoje + timedelta(days=5)})
    assert an._carrinho_aberto("X") is False
    monkeypatch.setattr(an, "_launch_cfg", lambda c: {})
    assert an._carrinho_aberto("X") is False


def test_reaquecimento_tem_intervalo_minimo(monkeypatch):
    chamadas = []
    import frontend.services.prewarm as pw
    monkeypatch.setattr(pw, "schedule_warm", lambda *a, **k: chamadas.append(a))
    an._ULTIMO_REAQUECIMENTO.clear()
    an._reaquecer_com_carrinho_aberto("X")
    an._reaquecer_com_carrinho_aberto("X")
    assert len(chamadas) == 1
