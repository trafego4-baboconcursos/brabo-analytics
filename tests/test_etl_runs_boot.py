"""Boot do scheduler: fecha rodadas órfãs do etl_runs e mede a última rodada ok (SQLite em memória)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import etl_runs  # noqa: E402


@pytest.fixture()
def engine(monkeypatch):
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE etl_runs (id INTEGER PRIMARY KEY, source TEXT, started_at TEXT, "
                       "finished_at TEXT, status TEXT, rows_upserted INTEGER, error_message TEXT)"))
    monkeypatch.setattr(etl_runs, "_engine", lambda: eng)
    return eng


def _inserir(eng, source, status, finished=None):
    with eng.begin() as c:
        c.execute(text("INSERT INTO etl_runs (source, started_at, finished_at, status) VALUES (:s, :a, :f, :st)"),
                  {"s": source, "a": "2026-11-10 10:00:00", "f": finished, "st": status})


def test_encerrar_orfas_fecha_so_as_que_estao_running(engine):
    _inserir(engine, "active_campaign", "running")
    _inserir(engine, "instagram", "running")
    _inserir(engine, "meta_ads", "ok", "2026-11-10 10:05:00")
    assert etl_runs.encerrar_orfas() == 2
    with engine.connect() as c:
        linhas = c.execute(text("SELECT source, status, error_message FROM etl_runs ORDER BY id")).fetchall()
    assert [l[1] for l in linhas] == ["error", "error", "ok"]
    assert "reiniciou" in linhas[0][2]
    assert etl_runs.encerrar_orfas() == 0          # idempotente


def test_minutos_desde_ultimo_ok(engine):
    agora = datetime.now(timezone.utc)
    _inserir(engine, "active_campaign", "ok", (agora - timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S"))
    _inserir(engine, "instagram", "error", (agora - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"))
    m = etl_runs.minutos_desde_ultimo_ok(("active_campaign", "instagram"))
    assert 24 < m < 27                              # só conta rodada ok
    assert etl_runs.minutos_desde_ultimo_ok(("whatsapp",)) is None   # nunca rodou ok


def test_banco_indisponivel_nao_derruba_o_boot(monkeypatch):
    def quebrado():
        raise RuntimeError("sem banco")
    monkeypatch.setattr(etl_runs, "_engine", quebrado)
    assert etl_runs.encerrar_orfas() == 0
    assert etl_runs.minutos_desde_ultimo_ok(("active_campaign",)) is None
