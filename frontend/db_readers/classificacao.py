"""
frontend/db_readers/classificacao.py — lê a classificação gravada pelo ETL.

Desde 21/09/26 `etapa`/`temperatura`/`segmento` (e `bucket`, no Meta) são
gravadas por `etl/campanha_historico.py` a partir do nome **congelado** da
campanha, em vez de calculadas a cada leitura a partir do nome vigente. Uma
campanha reaproveitada e renomeada trocando de etapa reclassificava todo o
histórico em silêncio; agora o retrato fica preso ao que era na época.

Este módulo é a ponte entre os dois regimes, e ele precisa dos dois ao mesmo
tempo por duas razões:

- **Ordem de deploy.** As colunas podem ainda não existir em produção (a
  migração é `scripts/migrar_classificacao_campanhas.py`). `com_classificacao`
  pergunta ao banco quais existem antes de montar o `SELECT`.
- **Linha antiga.** Mesmo com a coluna criada, linha nunca reprocessada fica com
  `NULL`. `aplicar_classificacao` preenche essas a partir do nome, exatamente
  como antes — então a página nunca mostra "Outros" por falta de migração.
"""
from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

from frontend.db import colunas_da_tabela

#: Colunas de classificação por plataforma, na ordem em que `src/nomenclatura.py`
#: devolve a tupla. Precisa bater com `etl/campanha_historico.py`.
CLASSIFICACAO_META: tuple[str, ...] = ("etapa", "temperatura", "bucket", "segmento")
CLASSIFICACAO_GOOGLE: tuple[str, ...] = ("etapa", "temperatura", "segmento")


def com_classificacao(cols: str, tabela: str, colunas: Sequence[str]) -> str:
    """`cols` acrescido das colunas de classificação que existem em `tabela`."""
    disponiveis = colunas_da_tabela(tabela)
    extras = [c for c in colunas if c in disponiveis]
    return f"{cols}, {', '.join(extras)}" if extras else cols


def aplicar_classificacao(
    df: pd.DataFrame,
    colunas: Sequence[str],
    categorizar: Callable[[str], tuple],
) -> pd.DataFrame:
    """Garante `colunas` no `df`, usando o valor gravado e calculando o resto.

    Calcula só para as linhas que precisam: se a migração já rodou e o ETL já
    reprocessou o período, nenhuma chamada a `categorizar` acontece.
    """
    if df.empty:
        for coluna in colunas:
            if coluna not in df.columns:
                df[coluna] = pd.Series(dtype="object")
        return df

    df = df.copy()
    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = None

    faltando = df[list(colunas)].isna().any(axis=1)
    if faltando.any():
        nomes = df.loc[faltando, "campaign_name"].fillna("")
        calculado = [categorizar(nome) for nome in nomes]
        for i, coluna in enumerate(colunas):
            df.loc[faltando, coluna] = [r[i] for r in calculado]

    for coluna in colunas:
        df[coluna] = df[coluna].fillna("Outros")
    return df
