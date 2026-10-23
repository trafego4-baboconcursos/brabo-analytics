"""
Utilitário de retry HTTP para os scripts ETL.

Envolve requests.get / requests.post com backoff exponencial via tenacity.
Uso:
    from http_retry import http_get, http_post

    resp = http_get(url, params=params)   # levanta HTTPError após 3 tentativas
"""
import re

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

_log = logging.getLogger("etl.http_retry")

# O `requests` põe a URL COMPLETA (com ?access_token=...) na mensagem de HTTPError/ConnectionError, e o tenacity
# repete essa mensagem no log a cada nova tentativa. Resultado: o token da Meta ia parar nos logs do ETL e em
# qualquer saída de erro (descoberto em 23/10/26). Aqui toda mensagem sai mascarada.
_SEGREDO = re.compile(r"((?:access_token|client_secret|refresh_token|developer[-_]token|api[-_]key)=)[^&\s\"']+", re.I)


def mascarar(texto) -> str:
    return _SEGREDO.sub(lambda m: m.group(1) + "***", str(texto))


class _FiltroSegredo(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mascarar(record.getMessage())
        record.args = ()
        return True


_log.addFilter(_FiltroSegredo())


def _sem_segredo(exc: requests.RequestException) -> requests.RequestException:
    novo = type(exc)(mascarar(exc))
    novo.response = getattr(exc, "response", None)
    novo.request = getattr(exc, "request", None)
    return novo

_RETRY_POLICY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((requests.HTTPError, requests.Timeout, requests.ConnectionError)),
    before_sleep=before_sleep_log(_log, logging.WARNING),
    reraise=True,
)


@retry(**_RETRY_POLICY)
def http_get(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 60)
    try:
        resp = requests.get(url, **kwargs)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise _sem_segredo(e) from None   # `from None`: o traceback não carrega a exceção original (com o token)
    return resp


@retry(**_RETRY_POLICY)
def http_post(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 60)
    try:
        resp = requests.post(url, **kwargs)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise _sem_segredo(e) from None
    return resp
