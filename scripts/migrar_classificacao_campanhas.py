"""
scripts/migrar_classificacao_campanhas.py — migração única de 21/09/26.

Faz três coisas, nesta ordem, e todas são idempotentes:

1. **Colunas novas** em `meta_ads_daily` (`etapa`, `temperatura`, `bucket`,
   `segmento`) e `google_ads_daily` (`etapa`, `temperatura`, `segmento`), mais
   índice em `campaign_id` nas duas. `ADD COLUMN IF NOT EXISTS`, nada destrutivo.

2. **Restaura o nome histórico** das campanhas que foram renomeadas depois do
   lançamento. A regra é por **era de nome**, não por data do dado: dentro de
   cada `(campaign_id, lancamento_codigo)`, cada nome distinto vira uma era que
   começa no `updated_at` mais antigo em que aquele nome aparece. Uma linha de
   data `D` pertence à era que estava valendo em `D`.

   A primeira tentativa foi "vale o nome da data mais antiga", e o dry-run
   mostrou que erra: na campanha de distribuição do Felipe Graton o prefixo
   `[OLD]` foi posto em 25/08/26 e um backfill já tinha regravado as linhas mais
   antigas com ele, enquanto linhas de dezembro escritas uma hora antes ainda
   tinham o nome original. Quem foi escrito primeiro é que guarda o nome de
   época — a data do dado não diz nada sobre isso.

   Só consegue recuperar o nome antigo quando ele ainda está em alguma linha da
   tabela. Campanha cujo histórico inteiro já foi regravado (as 10 do PBB-JUN-26
   exibindo `[PBB-AGO-26]`) não tem de onde voltar — o nome antigo teria de vir
   do log de alterações do Ads Manager, que este script não consulta.

3. **Preenche a classificação** de todas as linhas a partir do nome (já
   corrigido pelo passo 2), usando `src/nomenclatura.py` — a mesma função que o
   ETL e os readers usam, para os três darem o mesmo resultado.

Uso:
    python scripts/migrar_classificacao_campanhas.py --dry-run   # mostra, não grava
    python scripts/migrar_classificacao_campanhas.py             # aplica

O passo 2 grava um CSV de backup em `outputs/` antes de alterar qualquer nome.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "etl"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from ad_codes import uses_legacy_ad_codes  # noqa: E402
from db import get_engine  # noqa: E402  (etl/db.py)
from nomenclatura import (  # noqa: E402
    categorizar_campanha_google,
    categorizar_campanha_meta,
)

#: Combinações por UPDATE. Mantém a query longe do statement_timeout de 30s.
_LOTE = 200

TABELAS = {
    "meta_ads_daily": {
        "plataforma": "meta",
        "colunas": ["etapa", "temperatura", "bucket", "segmento"],
        "indice": "idx_meta_campaign_id",
    },
    "google_ads_daily": {
        "plataforma": "google",
        "colunas": ["etapa", "temperatura", "segmento"],
        "indice": "idx_google_campaign_id",
    },
}


# ── 1. colunas ───────────────────────────────────────────────────────────────
def criar_colunas(conn, dry_run: bool) -> None:
    for tabela, cfg in TABELAS.items():
        for coluna in cfg["colunas"]:
            sql = f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {coluna} TEXT"
            print(f"  {'[dry-run] ' if dry_run else ''}{sql}")
            if not dry_run:
                conn.execute(text(sql))
        sql = f"CREATE INDEX IF NOT EXISTS {cfg['indice']} ON {tabela} (campaign_id)"
        print(f"  {'[dry-run] ' if dry_run else ''}{sql}")
        if not dry_run:
            conn.execute(text(sql))


# ── 2. nome histórico ────────────────────────────────────────────────────────
def _renomeacoes(conn, tabela: str) -> pd.DataFrame:
    """Uma linha por `(campaign_id, lancamento_codigo, date, campaign_name)` cujo
    nome gravado não bate com a era de nome que valia naquela data.

    Era = janela em que um nome esteve valendo. Começa no `updated_at` mais
    antigo em que aquele nome aparece e termina quando a era seguinte começa.
    Uma linha de data `D` deve carregar o nome da era que continha `D`.
    """
    linhas = conn.execute(
        text(
            f"SELECT campaign_id, lancamento_codigo, date, campaign_name, "
            f"       COUNT(*) AS n, MIN(updated_at) AS upd "
            f"FROM {tabela} "
            f"WHERE campaign_id IS NOT NULL AND campaign_name IS NOT NULL "
            f"  AND lancamento_codigo IS NOT NULL "
            f"GROUP BY campaign_id, lancamento_codigo, date, campaign_name"
        )
    ).fetchall()
    if not linhas:
        return pd.DataFrame()
    df = pd.DataFrame(
        linhas, columns=["campaign_id", "lancamento_codigo", "date", "campaign_name", "n", "upd"]
    )

    # Só interessa quem tem mais de um nome dentro do mesmo lançamento.
    chave = ["campaign_id", "lancamento_codigo"]
    multi = df.groupby(chave)["campaign_name"].nunique()
    multi = multi[multi > 1].index
    if len(multi) == 0:
        return pd.DataFrame()
    df = df.set_index(chave).loc[multi].reset_index()

    saida = []
    for _, grupo in df.groupby(chave):
        eras = (
            grupo.groupby("campaign_name", as_index=False)["upd"].min()
            .sort_values("upd")
            .reset_index(drop=True)
        )
        # Fronteira i = início da era i+1; linha com data anterior à fronteira
        # pertence à era i.
        nomes = eras["campaign_name"].tolist()
        fronteiras = [pd.Timestamp(u).date() for u in eras["upd"].tolist()[1:]]

        def _nome_de_epoca(data) -> str:
            for i, fronteira in enumerate(fronteiras):
                if data < fronteira:
                    return nomes[i]
            return nomes[-1]

        grupo = grupo.copy()
        grupo["nome_correto"] = grupo["date"].map(_nome_de_epoca)
        saida.append(grupo[grupo["campaign_name"] != grupo["nome_correto"]])

    fora = pd.concat(saida) if saida else pd.DataFrame()
    return fora


def restaurar_nomes(conn, dry_run: bool) -> None:
    for tabela in TABELAS:
        df = _renomeacoes(conn, tabela)
        if df.empty:
            print(f"  {tabela}: nenhum nome a restaurar")
            continue

        resumo = (
            df.groupby(["campaign_id", "lancamento_codigo", "campaign_name", "nome_correto"], as_index=False)
            .agg(linhas=("n", "sum"), de=("date", "min"), ate=("date", "max"))
        )
        resumo["linhas"] = resumo["linhas"].astype(int)
        print(f"  {tabela}: {len(resumo)} campanha(s), {int(resumo.linhas.sum())} linha(s)")
        for _, r in resumo.iterrows():
            print(f"    [{r.lancamento_codigo}] {r.de}..{r.ate} ({r.linhas} linhas)")
            print(f"      de : {r.campaign_name}")
            print(f"      pra: {r.nome_correto}")

        if dry_run:
            continue

        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = ROOT / "outputs" / f"backup_nomes_{tabela}_{carimbo}.csv"
        destino.parent.mkdir(exist_ok=True)
        resumo.to_csv(destino, index=False, encoding="utf-8-sig")
        print(f"    backup: {destino}")

        for _, r in resumo.iterrows():
            conn.execute(
                text(
                    f"UPDATE {tabela} SET campaign_name = :novo "
                    f"WHERE campaign_id = :cid AND lancamento_codigo = :code "
                    f"  AND campaign_name = :velho AND date BETWEEN :de AND :ate"
                ),
                {"novo": r.nome_correto, "cid": r.campaign_id, "code": r.lancamento_codigo,
                 "velho": r.campaign_name, "de": r.de, "ate": r.ate},
            )


# ── 3. classificação ─────────────────────────────────────────────────────────
def preencher_classificacao(conn, dry_run: bool) -> None:
    """Grava etapa/temperatura/segmento (e bucket no Meta) em todas as linhas.

    São ~870 combinações distintas de `nome × lançamento` para ~210 mil linhas,
    então classifica cada combinação uma vez em Python e manda um `UPDATE ...
    FROM (VALUES ...)` por lote. Uma linha por combinação em `UPDATE` separado
    custaria 870 varreduras da tabela e estouraria o `statement_timeout` de 30s.
    """
    for tabela, cfg in TABELAS.items():
        combos = conn.execute(
            text(
                f"SELECT DISTINCT campaign_name, lancamento_codigo FROM {tabela} "
                f"WHERE campaign_name IS NOT NULL"
            )
        ).fetchall()
        print(f"  {tabela}: {len(combos)} combinação(ões) nome × lançamento")

        if dry_run:
            for c in combos[:3]:
                print(f"    {c.campaign_name[:68]} -> {_classificar(c.campaign_name, c.lancamento_codigo, cfg['plataforma'])}")
            continue

        colunas = cfg["colunas"]
        atualizadas = 0
        for inicio in range(0, len(combos), _LOTE):
            lote = combos[inicio:inicio + _LOTE]
            valores, params = [], {}
            for i, c in enumerate(lote):
                classificacao = _classificar(c.campaign_name, c.lancamento_codigo, cfg["plataforma"])
                params[f"n{i}"] = c.campaign_name
                params[f"c{i}"] = c.lancamento_codigo
                for j, coluna in enumerate(colunas):
                    params[f"{coluna}{i}"] = classificacao[j]
                campos = ", ".join(f":{coluna}{i}" for coluna in colunas)
                valores.append(f"(:n{i}, :c{i}, {campos})")

            sets = ", ".join(f"{coluna} = m.{coluna}" for coluna in colunas)
            lista_colunas = ", ".join(colunas)
            resultado = conn.execute(
                text(
                    f"UPDATE {tabela} AS t SET {sets} "
                    f"FROM (VALUES {', '.join(valores)}) AS m(nome, codigo, {lista_colunas}) "
                    f"WHERE t.campaign_name = m.nome "
                    f"  AND t.lancamento_codigo IS NOT DISTINCT FROM m.codigo"
                ),
                params,
            )
            atualizadas += resultado.rowcount or 0
        print(f"    {atualizadas} linha(s) classificada(s)")


def _classificar(nome: str, codigo: str | None, plataforma: str) -> tuple:
    if plataforma == "meta":
        return categorizar_campanha_meta(nome, launch_code=codigo, legacy=uses_legacy_ad_codes(codigo))
    return categorizar_campanha_google(nome, launch_code=codigo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que faria, sem gravar")
    parser.add_argument("--pular-nomes", action="store_true",
                        help="Nao restaura nome historico (so colunas + classificacao)")
    args = parser.parse_args()

    engine = get_engine()
    with engine.begin() as conn:
        print("\n1. Colunas e índices")
        criar_colunas(conn, args.dry_run)

        if args.pular_nomes:
            print("\n2. Nome histórico — pulado (--pular-nomes)")
        else:
            print("\n2. Nome histórico das campanhas renomeadas")
            restaurar_nomes(conn, args.dry_run)

        print("\n3. Classificação (etapa/temperatura/segmento)")
        if args.dry_run:
            print("  [dry-run] as colunas ainda não existem; mostrando só a amostra")
        preencher_classificacao(conn, args.dry_run)

    print("\nOK" + (" (dry-run, nada gravado)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
