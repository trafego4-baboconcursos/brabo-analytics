"""As colunas que cada ETL grava têm que existir no banco.

Existe por causa de dois apagões reais, com três dias de intervalo:

- 17/09/26: `etl/budget_alert.py` importava um nome que a refatoração tinha
  movido, e o `scheduler.py` (que o importa no topo) entrou em crash-loop —
  **7h12 sem ETL nenhum**. Coberto por `tests/test_imports.py`.
- 18/09/26: o commit c8c9421 passou a gravar `customer_id` em
  `google_ads_demographics_daily` sem criar a coluna. O passo `google_ads`
  falhou a cada rodada por ~3h, com `UndefinedColumn`, e nada acusou — o import
  estava íntegro, o CI passava, e só apareceu quando alguém olhou o log.

Import saudável não garante schema compatível. Este teste fecha a segunda
lacuna: monta o DataFrame de cada ETL e confere, contra o
`information_schema`, que toda coluna que ele pretende escrever existe.

Como funciona: os builders leem a linha da API com `r.get(...)`, então passar
`[{}]` devolve um DataFrame com as colunas certas e valores nulos, sem tocar em
rede nem em banco. Os `upsert` gravam com `df.to_sql(...)`, que usa exatamente
`df.columns` — é o mesmo conjunto que iria pro INSERT.

Precisa de banco, então roda no marcador `smoke` (o CI não tem banco).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
# etl/ entra no path porque os scripts se importam entre si como módulos soltos
# (`from db import get_engine`), que é como rodam em produção.
if str(_RAIZ / "etl") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "etl"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

# (módulo, função que monta o DataFrame, tabela de destino)
# Só entram builders que aceitam uma linha vazia. Quem precisar de dado real
# para montar as colunas fica de fora — melhor não cobrir do que cobrir errado.
CONTRATOS = [
    ("etl_google_ads", "build_df_from_api", "google_ads_daily"),
    ("etl_google_ads", "build_df_from_pmax_api", "google_ads_daily"),
    ("etl_google_ads", "build_df_from_demographics_api", "google_ads_demographics_daily"),
    ("etl_google_ads", "build_df_from_audiences_api", "google_ads_audiences_daily"),
    ("etl_meta_ads", "build_df_from_api", "meta_ads_daily"),
    ("etl_meta_ads", "build_df_from_demographics_api", "meta_ads_demographics_daily"),
    ("etl_meta_ads", "build_df_from_region_api", "meta_ads_region_daily"),
]

# Os upsert acrescentam esta coluna depois do builder, então ela conta como
# escrita mesmo não aparecendo no DataFrame montado aqui.
_ACRESCENTADAS = {"updated_at"}


@pytest.fixture(scope="module")
def colunas_do_banco():
    from sqlalchemy import text  # noqa: PLC0415

    from frontend.db import _get_engine  # noqa: PLC0415

    with _get_engine().connect() as conn:
        linhas = conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )).fetchall()
    mapa: dict[str, set[str]] = {}
    for tabela, coluna in linhas:
        mapa.setdefault(tabela, set()).add(coluna)
    return mapa


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("modulo", "funcao", "tabela"), CONTRATOS,
    ids=[f"{m}.{f}->{t}" for m, f, t in CONTRATOS],
)
def test_colunas_do_etl_existem_no_banco(modulo, funcao, tabela, colunas_do_banco):
    import importlib  # noqa: PLC0415

    assert tabela in colunas_do_banco, f"tabela '{tabela}' não existe no banco"

    df = getattr(importlib.import_module(modulo), funcao)([{}])
    escritas = set(df.columns) | _ACRESCENTADAS
    faltando = sorted(escritas - colunas_do_banco[tabela])

    assert not faltando, (
        f"{modulo}.{funcao} grava em '{tabela}' coluna(s) que não existem no banco: {faltando}.\n"
        f"O ETL vai falhar com UndefinedColumn a cada rodada.\n"
        f"Corrija com ALTER TABLE e registre em etl/schema.sql — foi o que aconteceu "
        f"com customer_id em 18/09/26."
    )
