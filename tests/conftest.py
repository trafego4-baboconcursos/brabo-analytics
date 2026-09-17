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

# ── Isolamento do cache em memória ─────────────────────────────────────────────
# `frontend/cache.py::_CACHE` é um dicionário de MÓDULO: sem limpar entre os
# testes, ele é compartilhado pela sessão inteira do pytest. Isso tornava os
# testes de caracterização instáveis — passavam sozinhos e falhavam na suíte, com
# um conjunto de falhas diferente a cada rodada (10 numa, 4 na seguinte), porque
# um teste lia o valor que outro tinha deixado no cache. Pior: `_get_or_compute`
# faz stale-while-revalidate, então o valor devolvido dependia até do tempo entre
# um teste e outro. Isolar derrubou as falhas de 10 para 4.
#
# Tentei limpar só o lançamento sob teste (`_invalidate(codigo)`), pra preservar
# o cache dos outros e recomputar menos: ficou PIOR, 24 falhas. Vários readers
# guardam estado fora do `_CACHE` (caches de módulo próprios, como o
# `_typeform_forms_cache`) ou sob chaves que o `_invalidate` não casa. Limpeza
# completa é o que funciona — medido em 17/09/26, não mudar sem remedir.
@pytest.fixture(autouse=True)
def _cache_limpo():
    from frontend import cache as _cache

    _cache._CACHE.clear()
    _cache._STORED_AT.clear()
    yield
    _cache._CACHE.clear()
    _cache._STORED_AT.clear()
