"""
etl/campanha_historico.py — nome da campanha congelado no histórico + etapa gravada.

**O problema.** O upsert dos dois ETLs é `DELETE` da faixa de datas + `append`.
Toda vez que um backfill roda sobre um período antigo, ele regrava as linhas com
o nome **atual** da campanha na API. Então `campaign_name` significava "nome na
última vez que o ETL rodou", não "nome durante o lançamento". Quando uma campanha
é reaproveitada num lançamento novo e renomeada, o histórico do lançamento antigo
passa a exibir o código do lançamento novo.

Aconteceu de verdade: o backfill de 18/09/26 regravou 4.579 linhas de maio do
PES-MAI-26, e R$ 74 mil de Captação do TJ-SP passaram a aparecer como
`[GA][...][old][PES-SET-26][04.09.26]`. Levantamento completo em
`docs/performance/lancamentos/PES-MAI-26/MUDANCAS_PES-MAI-26.md`, item 2.

**A correção, em duas partes.**

1. `nomes_congelados` + `congelar_nomes`: antes do DELETE, lê o nome já gravado
   para cada `(campaign_id, date)` da faixa e devolve esse nome nas linhas que já
   existiam. Linha nova recebe o nome atual da API, normalmente.
2. `classificar`: `etapa`/`temperatura`/`segmento`/`bucket` passam a ser gravados
   junto, derivados do nome **congelado**. Antes eram calculados em tempo de
   leitura a partir do nome vigente — uma campanha reaproveitada que trocasse de
   etapa no nome (`[captação]` → `[matrículas abertas]`) reclassificaria todo o
   histórico em silêncio.

`campaign_id` é a chave certa para isso, e **só** para isso: a mesma campanha
pode pertencer a dois lançamentos (14 casos no banco em 21/09/26), então quem
resolve lançamento continua sendo `(nome, data)` em `launch_resolver.py`.

O congelamento tem escape: `--renomear-campanhas` na linha de comando dos dois
ETLs desliga a parte 1, para quando o nome mudou porque estava **errado** e a
correção deve mesmo se propagar para trás.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_codes import uses_legacy_ad_codes  # noqa: E402  (src/ad_codes.py)
from logger import get_logger  # noqa: E402
from nomenclatura import (  # noqa: E402  (src/nomenclatura.py)
    categorizar_campanha_google,
    categorizar_campanha_meta,
)

logger = get_logger("etl.campanha_historico")

#: Colunas de classificação por plataforma, na ordem em que as funções de
#: `nomenclatura` devolvem a tupla.
COLUNAS_META = ("etapa", "temperatura", "bucket", "segmento")
COLUNAS_GOOGLE = ("etapa", "temperatura", "segmento")


def nomes_congelados(
    conn,
    tabela: str,
    since: str,
    until: str,
    launch_code: str | None = None,
) -> dict[tuple[str, str], str]:
    """`{(campaign_id, date): campaign_name}` do que já está gravado na faixa.

    Precisa rodar **antes** do DELETE e na mesma conexão. Linhas sem
    `campaign_id` ficam de fora: sem chave estável não dá para saber que a linha
    nova é a mesma campanha (é o caso do modo CSV, que não tem id).
    """
    filtro_lancamento = "AND lancamento_codigo = :code" if launch_code else ""
    params: dict[str, object] = {"s": since, "u": until}
    if launch_code:
        params["code"] = launch_code.upper()
    linhas = conn.execute(
        text(
            f"SELECT DISTINCT campaign_id, date, campaign_name FROM {tabela} "
            f"WHERE date BETWEEN :s AND :u AND campaign_id IS NOT NULL "
            f"AND campaign_name IS NOT NULL {filtro_lancamento}"
        ),
        params,
    ).fetchall()
    return {(str(r.campaign_id), str(r.date)): r.campaign_name for r in linhas}


def congelar_nomes(df: pd.DataFrame, mapa: dict[tuple[str, str], str]) -> tuple[pd.DataFrame, int]:
    """Devolve `df` com o nome histórico no lugar do nome atual, e quantos trocou.

    Só mexe onde o par `(campaign_id, date)` já existia **e** o nome mudou.
    """
    if df.empty or not mapa or "campaign_id" not in df.columns:
        return df, 0

    def _historico(row) -> str:
        cid, data = row["campaign_id"], row["date"]
        if cid is None or (isinstance(cid, float) and pd.isna(cid)):
            return row["campaign_name"]
        return mapa.get((str(cid), str(data)), row["campaign_name"])

    novo = df.apply(_historico, axis=1)
    trocados = int((novo != df["campaign_name"]).sum())
    if trocados:
        exemplos = (
            df.loc[novo != df["campaign_name"], "campaign_name"].drop_duplicates().head(3).tolist()
        )
        logger.info(
            "Nome congelado em %d linhas (campanha renomeada depois do período). "
            "Nome atual ignorado, ex.: %s",
            trocados,
            exemplos,
        )
    df = df.copy()
    df["campaign_name"] = novo
    return df, trocados


def classificar(df: pd.DataFrame, plataforma: str) -> pd.DataFrame:
    """Acrescenta `etapa`/`temperatura`/`segmento` (e `bucket` no Meta) ao `df`.

    Classifica a partir de `campaign_name` — que a esta altura já é o nome
    congelado. O `legacy` do Meta sai de `lancamento_codigo` linha a linha, igual
    ao que `frontend/db_readers/ads_meta.py` faz na leitura, para os dois lados
    darem exatamente o mesmo resultado.
    """
    colunas = COLUNAS_META if plataforma == "meta" else COLUNAS_GOOGLE
    if df.empty:
        for coluna in colunas:
            df[coluna] = pd.Series(dtype="object")
        return df

    df = df.copy()
    nomes = df["campaign_name"].fillna("")
    if plataforma == "meta":
        codigos = df["lancamento_codigo"] if "lancamento_codigo" in df.columns else pd.Series([None] * len(df))
        resultado = [
            categorizar_campanha_meta(nome, legacy=uses_legacy_ad_codes(codigo))
            for nome, codigo in zip(nomes, codigos)
        ]
    else:
        resultado = [categorizar_campanha_google(nome) for nome in nomes]

    for i, coluna in enumerate(colunas):
        df[coluna] = [r[i] for r in resultado]
    return df


def _colunas_da_tabela(conn, tabela: str) -> set[str]:
    """Colunas que a tabela realmente tem, para não inserir coluna inexistente."""
    linhas = conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
        {"t": tabela},
    ).fetchall()
    return {r[0] for r in linhas}


def preparar(
    conn,
    df: pd.DataFrame,
    *,
    tabela: str,
    plataforma: str,
    since: str,
    until: str,
    launch_code: str | None = None,
    renomear: bool = False,
) -> pd.DataFrame:
    """Congela o nome (salvo `renomear=True`) e classifica. Chamar antes do DELETE.

    Descarta as colunas de classificação que a tabela ainda não tem. `to_sql`
    monta o INSERT com **todas** as colunas do DataFrame, então mandar `etapa`
    antes de `scripts/migrar_classificacao_campanhas.py` rodar derrubaria o ETL
    inteiro a cada hora com "column etapa does not exist" — e o congelamento de
    nome, que não depende de coluna nova, morreria junto.
    """
    if not renomear:
        try:
            df, _ = congelar_nomes(df, nomes_congelados(conn, tabela, since, until, launch_code))
        except Exception:
            # Congelar nome é uma melhoria do retrato histórico, não um requisito
            # para gravar o dado do dia. Se a leitura prévia falhar, grava com o
            # nome atual — que é exatamente o comportamento anterior a 21/09/26.
            logger.exception("Falha ao ler nomes históricos de %s; gravando com o nome atual", tabela)

    df = classificar(df, plataforma)

    colunas = COLUNAS_META if plataforma == "meta" else COLUNAS_GOOGLE
    try:
        existentes = _colunas_da_tabela(conn, tabela)
    except Exception:
        logger.exception("Falha ao ler colunas de %s; gravando sem classificação", tabela)
        existentes = set()
    ausentes = [c for c in colunas if c not in existentes]
    if ausentes:
        logger.warning(
            "%s ainda não tem %s — rode scripts/migrar_classificacao_campanhas.py. "
            "Gravando sem a classificação; o nome segue congelado.",
            tabela, ", ".join(ausentes),
        )
        df = df.drop(columns=ausentes)
    return df
