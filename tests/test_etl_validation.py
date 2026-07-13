"""Testes para etl/validation.py — funções puras sem dependência de DB."""
import sys
import logging
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

from validation import validate_dataframe

_logger = logging.getLogger("test")


class TestValidateDataframe:
    def test_valid_df_returns_true(self, sample_meta_df):
        cols = ["date", "ad_id", "spend"]
        assert validate_dataframe(sample_meta_df, cols, "test", _logger) is True

    def test_empty_df_returns_false(self):
        df = pd.DataFrame()
        assert validate_dataframe(df, ["col"], "test", _logger) is False

    def test_missing_required_col_returns_false(self, sample_meta_df):
        assert validate_dataframe(sample_meta_df, ["coluna_inexistente"], "test", _logger) is False

    def test_multiple_missing_cols_returns_false(self, sample_meta_df):
        missing = ["coluna_a", "coluna_b"]
        assert validate_dataframe(sample_meta_df, missing, "test", _logger) is False

    def test_partial_null_below_threshold_passes(self):
        df = pd.DataFrame({"a": [1, None], "b": [1, 2]})
        assert validate_dataframe(df, ["a", "b"], "test", _logger) is True

    def test_high_null_percentage_still_returns_true(self):
        """Alta % de nulos gera WARNING mas não bloqueia o upsert."""
        df = pd.DataFrame({"a": [None, None, None, 1], "b": [1, 2, 3, 4]})
        result = validate_dataframe(df, ["a", "b"], "test", _logger)
        assert result is True  # retorna True mas loga warning

    def test_all_required_cols_present_passes(self, sample_leads_df):
        cols = ["id", "email", "created_at", "lancamento_codigo"]
        assert validate_dataframe(sample_leads_df, cols, "leads", _logger) is True
