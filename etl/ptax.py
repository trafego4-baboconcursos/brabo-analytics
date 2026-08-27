"""
etl/ptax.py — Cotação PTAX (Banco Central) do dólar, pra converter custo em
USD do WhatsApp Business API pro valor em R$ no dia do faturamento (não a
cotação de hoje). Fonte oficial: Olinda/BCB, série "CotacaoDolarDia".

BCB não cotiza fim de semana/feriado — nesses dias recua até achar o último
dia útil anterior (mesmo critério que qualquer conversão contábil usa).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

_cache: dict[str, float] = {}


def get_ptax_venda(date_str: str) -> float | None:
    """cotacaoVenda (PTAX) na data (YYYY-MM-DD), ou do último dia útil
    anterior. None se a API falhar ou não achar cotação em 10 dias."""
    if date_str in _cache:
        return _cache[date_str]

    d = datetime.strptime(date_str, "%Y-%m-%d")
    for _ in range(10):
        mmddyyyy = d.strftime("%m-%d-%Y")
        url = (
            "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            f"CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{mmddyyyy}'&$format=json"
        )
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            values = r.json().get("value", [])
        except Exception:
            return None
        if values:
            rate = float(values[-1]["cotacaoVenda"])
            _cache[date_str] = rate
            return rate
        d -= timedelta(days=1)
    return None
