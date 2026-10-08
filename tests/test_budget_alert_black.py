"""Alerta de orçamento na Black — classificar com o código do lançamento.

Achado em 08/10/26: o alerta chamava o classificador SEM o código do
lançamento, então a BV-26 era lida com o vocabulário de lançamento normal. As
30 campanhas ativas de Aquecimento viravam "Outros", nenhuma etapa contava como
ativa, e o alerta anunciou Aquecimento "encerrado, R$ 0,00" — e depois calou,
porque marcou a etapa como pausada. WhatsApp (verba manual) e Reserva também
saíam como "encerradas, R$ 0,00".

Sem banco e sem API: as consultas são trocadas por dados em memória.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))

ba = pytest.importorskip("budget_alert")

AQUEC_META = "[MA][ivan][envolvimento][aquecimento][alunos][novos][reels][BV-26][06.10.26]"
AQUEC_GOOGLE = "[GA][trio][mateus][engajamento][aquecimento][alunos][BV-26][23.09.26]"
HOJE = date(2026, 10, 8)


def test_campanha_de_aquecimento_conta_como_etapa_ativa():
    """O caso que calou o alerta: Aquecimento no ar, lido como 'Outros'."""
    assert ba._etapa_ativa("Aquecimento", "BV-26", {AQUEC_META: "ACTIVE"}, {})
    assert ba._etapa_ativa("Aquecimento", "BV-26", {}, {AQUEC_GOOGLE: "ENABLED"})


def test_campanha_pausada_nao_conta_como_ativa():
    assert not ba._etapa_ativa("Aquecimento", "BV-26", {AQUEC_META: "PAUSED"}, {})


@pytest.fixture
def sem_rede(monkeypatch):
    """Troca APIs e banco por memória. Devolve o gasto do banco por etapa."""
    gasto_banco: dict[str, dict] = {}
    monkeypatch.setattr(ba, "fetch_meta_status", lambda ids: {AQUEC_META: "ACTIVE"})
    monkeypatch.setattr(ba, "fetch_google_status", lambda ids: {})
    monkeypatch.setattr(ba, "fetch_insights", lambda *a, **k: [])
    monkeypatch.setattr(ba, "fetch_report", lambda *a, **k: [])
    monkeypatch.setattr(ba, "fetch_pmax_report", lambda *a, **k: [])
    monkeypatch.setattr(ba, "_gasto_db_periodo", lambda codigo, ini, fim: gasto_banco)
    return gasto_banco


def _cfg():
    return {
        "meta_ad_account_ids": ["act_1"], "google_ad_account_ids": [],
        "carrinho_end_date": "2026-10-30",
        "etapas": [
            {"nome": "Aquecimento", "start_date": "2026-09-21", "end_date": "2026-10-04", "total": 65000},
            {"nome": "WhatsApp", "start_date": "2026-09-29", "end_date": "2026-10-30", "total": 153700,
             "buckets": [{"tipo": "manual", "pct": 100}]},
            {"nome": "Reserva", "start_date": "2026-09-21", "end_date": "2026-10-30", "total": 6300},
        ],
    }


def test_black_reporta_aquecimento_com_o_gasto_acumulado(sem_rede):
    sem_rede["Aquecimento"] = {"spend_meta": 21212.54, "spend_google": 6706.88}
    msg, erros = ba._processar_lancamento("BV-26", _cfg(), HOJE, {})
    assert erros == []
    assert "*Aquecimento*" in msg
    assert "R$ 27.919,42" in msg
    assert "encerradas" not in msg


def test_etapa_sem_gasto_nao_e_anunciada_como_encerrada(sem_rede):
    """WhatsApp e Reserva nunca têm campanha: silêncio, não 'encerrada R$ 0,00'."""
    sem_rede["Aquecimento"] = {"spend_meta": 1000.0, "spend_google": 0.0}
    estado: dict = {}
    msg, _ = ba._processar_lancamento("BV-26", _cfg(), HOJE, estado)
    assert "WhatsApp" not in msg
    assert "Reserva" not in msg
    assert estado["BV-26"]["WhatsApp"] == "paused"


def test_etapa_que_gastou_e_parou_continua_sendo_anunciada(sem_rede, monkeypatch):
    """A guarda só cala o R$ 0,00 — encerramento de verdade continua avisando."""
    monkeypatch.setattr(ba, "fetch_meta_status", lambda ids: {AQUEC_META: "PAUSED"})
    sem_rede["Aquecimento"] = {"spend_meta": 5000.0, "spend_google": 0.0}
    msg, _ = ba._processar_lancamento("BV-26", _cfg(), HOJE, {})
    assert "*Aquecimento* — 🔴 campanhas pausadas/encerradas" in msg
    assert "R$ 5.000,00" in msg
