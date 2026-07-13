"""Fixtures compartilhadas para os testes do Brabo Analytics."""
import pandas as pd
import pytest
from pathlib import Path


@pytest.fixture
def sample_meta_df():
    """DataFrame mínimo válido para meta_ads_daily."""
    return pd.DataFrame({
        "date": ["2026-04-01", "2026-04-02"],
        "ad_id": ["123", "456"],
        "ad_name": ["AD110 - Teste", "AD111 - Teste"],
        "spend": [100.0, 200.0],
        "impressions": [1000, 2000],
        "clicks": [50, 100],
        "lancamento_codigo": ["PBB-ABR-26", "PBB-ABR-26"],
    })


@pytest.fixture
def sample_leads_df():
    """DataFrame mínimo válido para leads (Active Campaign)."""
    return pd.DataFrame({
        "id": ["1", "2"],
        "email": ["a@test.com", "b@test.com"],
        "created_at": ["2026-04-01", "2026-04-02"],
        "lancamento_codigo": ["PBB-ABR-26", "PBB-ABR-26"],
        "utm_content": ["AD110", "AD111"],
    })


@pytest.fixture
def tmp_csv_dir(tmp_path: Path) -> Path:
    """Diretório temporário com CSVs de teste."""
    return tmp_path
