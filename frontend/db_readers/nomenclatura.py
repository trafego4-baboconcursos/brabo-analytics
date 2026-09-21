"""
frontend/db_readers/nomenclatura.py — re-export de ``src/nomenclatura.py``.

A classificação por nome de campanha passou a ser escrita pelo ETL (colunas
``etapa``/``temperatura``/``segmento`` em ``meta_ads_daily``/``google_ads_daily``),
então ela precisa viver onde os dois lados alcançam: ``src/``, junto de
``constants.py`` e ``ad_codes.py``. Este módulo continua existindo porque oito
pontos do frontend e o ``etl/budget_alert.py`` importam daqui — mover o arquivo
sem deixar a ponte quebraria todos de uma vez, sem ganho nenhum.
"""
from __future__ import annotations

from src.nomenclatura import (  # noqa: F401
    BUCKET_MAP,
    ETAPA_MAP_GOOGLE,
    ETAPA_MAP_META,
    MODIFIER_MAP,
    TEMPERATURA_MAP_GOOGLE,
    TEMPERATURA_MAP_META,
    categorizar_campanha_google,
    categorizar_campanha_meta,
)

__all__ = [
    "BUCKET_MAP",
    "ETAPA_MAP_GOOGLE",
    "ETAPA_MAP_META",
    "MODIFIER_MAP",
    "TEMPERATURA_MAP_GOOGLE",
    "TEMPERATURA_MAP_META",
    "categorizar_campanha_google",
    "categorizar_campanha_meta",
]
