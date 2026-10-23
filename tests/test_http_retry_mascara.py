"""O token da Meta não pode aparecer em mensagem de erro nem no log de nova tentativa do ETL (23/10/26)."""
import logging
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))
hr = pytest.importorskip("http_retry")

SEGREDO = "EAAXtokenMuitoSecreto123"


def test_mascarar_remove_os_valores_sensiveis():
    t = f"500 Server Error for url: https://graph.facebook.com/v22.0/act_1/insights?access_token={SEGREDO}&fields=a,b&client_secret=xyz"
    m = hr.mascarar(t)
    assert SEGREDO not in m and "xyz" not in m
    assert "access_token=***&fields=a,b" in m and "client_secret=***" in m


def test_http_get_levanta_erro_sem_o_token_e_sem_encadear_o_original(monkeypatch):
    class R:
        status_code = 500
        def raise_for_status(self):
            raise requests.HTTPError(f"500 for url: https://x/y?access_token={SEGREDO}&a=1", response=self)

    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(hr.http_get.retry, "wait", lambda *a, **k: 0)          # sem esperar entre tentativas
    monkeypatch.setattr(hr.http_get.retry, "sleep", lambda s: None)
    with pytest.raises(requests.HTTPError) as ei:
        hr.http_get("https://x/y", params={})
    assert SEGREDO not in str(ei.value)
    assert ei.value.__cause__ is None and ei.value.__suppress_context__


def test_log_de_retry_sai_mascarado(monkeypatch, caplog):
    class R:
        status_code = 500
        def raise_for_status(self):
            raise requests.HTTPError(f"500 for url: https://x/y?access_token={SEGREDO}", response=self)

    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(hr.http_get.retry, "sleep", lambda s: None)
    with caplog.at_level(logging.WARNING, logger="etl.http_retry"):
        with pytest.raises(requests.HTTPError):
            hr.http_get("https://x/y")
    assert caplog.records, "esperava o log de nova tentativa"
    assert all(SEGREDO not in r.getMessage() for r in caplog.records)
