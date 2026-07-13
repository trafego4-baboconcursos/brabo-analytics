"""
Validação de DataFrames antes do upsert no Supabase.

Uso:
    from validation import validate_dataframe

    if not validate_dataframe(df, required_cols=["date", "ad_id", "spend"], label="Meta Ads", logger=logger):
        return  # pula o upsert
"""
from __future__ import annotations

import logging
import pandas as pd


def validate_dataframe(
    df: pd.DataFrame,
    required_cols: list[str],
    label: str,
    logger: logging.Logger,
    null_warn_threshold: float = 50.0,
) -> bool:
    """Valida um DataFrame antes do upsert.

    Retorna False (e loga o motivo) se:
    - df estiver vazio
    - faltarem colunas obrigatórias

    Loga WARNING se alguma coluna obrigatória tiver mais de
    `null_warn_threshold`% de nulos.
    """
    if df.empty:
        logger.warning("[%s] DataFrame vazio — upsert ignorado", label)
        return False

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.error("[%s] Colunas obrigatórias ausentes: %s", label, missing)
        return False

    null_pct = df[required_cols].isnull().mean() * 100
    for col, pct in null_pct.items():
        if pct > null_warn_threshold:
            logger.warning(
                "[%s] Coluna '%s' tem %.1f%% de valores nulos", label, col, pct
            )

    logger.info("[%s] Validação OK — %d linhas prontas para upsert", label, len(df))
    return True
