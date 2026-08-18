"""
Utilitário de retry HTTP para os scripts ETL.

Envolve requests.get / requests.post com backoff exponencial via tenacity.
Uso:
    from http_retry import http_get, http_post

    resp = http_get(url, params=params)   # levanta HTTPError após 3 tentativas
"""
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
    resp = requests.get(url, **kwargs)
    resp.raise_for_status()
    return resp


@retry(**_RETRY_POLICY)
def http_post(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 60)
    resp = requests.post(url, **kwargs)
    resp.raise_for_status()
    return resp
