"""
scripts/corrigir_janelas_e_atribuicao_20260921.py — duas correções de 21/09/26.

Levantamento completo em
`docs/performance/lancamentos/PES-MAI-26/MUDANCAS_PES-MAI-26.md`, itens 4 e 5.

**1. Datas de Pré-Qualificação em `launch_config` (banco operacional).**
`frontend/services/fetch.py::_get_global_start` monta a janela de leitura como
`pre_quali_start_date or captacao_start_date or ...`. Em três lançamentos do TJ-SP
o campo está vazio, então a janela começa na abertura da Captação e os ~14 dias de
Pré-Qualificação somem de toda página e do debriefing. No PES-MAI-26 isso escondia
R$ 89.517,06 — o dashboard mostrava R$ 699.243,27 em vez de R$ 788.760,33.

As datas gravadas aqui são as **reais**, extraídas da coluna `etapa` (que o ETL
passou a gravar em 21/09/26): primeiro e último dia com gasto de Pré-Qualificação.

**2. `lancamento_codigo` errado em 3.166 linhas do Google (banco analytics).**
Seis campanhas do PI-JAN-26 foram pausadas, reaproveitadas e renomeadas para
`[GA][old][captação][...][PI-ABR-26][25.03.26]`. O gasto delas de **29/12/25 a
12/01/26** ficou marcado como PI-ABR-26, mas essa data pertence ao PI-JAN-26
(`dim_lancamentos`: 17/11/25 a 26/01/26). São R$ 389.550,55 creditados no
lançamento errado — o ROAS de 6,08 do PI-JAN-26 é em boa parte artefato disso.

A regra aplicada é a mesma de `etl/launch_resolver.py::resolve_launch_code`: quem
manda é `(prefixo, data)`, não o nome. Move também `google_ads_audiences_daily` e
`google_ads_demographics_daily`, que carregam o mesmo código.

O nome de época dessas campanhas **não é recuperável** — nenhuma linha do banco
guarda o nome que elas tinham no PI-JAN-26. Elas ficam no PI-JAN-26 exibindo o nome
de abril; o congelamento de `etl/campanha_historico.py` impede que isso volte a
acontecer daqui pra frente, mas não desfaz o que já foi regravado.

Uso:
    python scripts/corrigir_janelas_e_atribuicao_20260921.py --dry-run
    python scripts/corrigir_janelas_e_atribuicao_20260921.py
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

# Console do Windows abre em cp1252 e estoura em acento/seta. Reconfigurar aqui
# vale para todo print do script.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "etl"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from db import get_engine, get_users_engine  # noqa: E402  (etl/db.py)

#: Lançamentos do TJ-SP sem data de Pré-Qualificação em `launch_config`.
#: Sem isso a janela de leitura começa na Captação e corta a etapa inteira.
LANCAMENTOS_SEM_PRE_QUALI = ["PES-JAN-26", "PES-MAR-26", "PES-MAI-26"]

#: Atribuição errada: PI-ABR-26 no que é PI-JAN-26.
DE, PARA = "PI-ABR-26", "PI-JAN-26"
#: Fim da janela do PI-JAN-26 em `dim_lancamentos`. Linha do PI-ABR-26 com data
#: até aqui pertence, por data, ao PI-JAN-26.
CORTE = "2026-01-26"
TABELAS_ATRIBUICAO = [
    "google_ads_daily",
    "meta_ads_daily",
    "google_ads_audiences_daily",
    "google_ads_demographics_daily",
]


def _backup(df: pd.DataFrame, nome: str) -> Path:
    destino = ROOT / "outputs" / f"backup_{nome}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    destino.parent.mkdir(exist_ok=True)
    df.to_csv(destino, index=False, encoding="utf-8-sig")
    return destino


# ── 1. datas de Pré-Qualificação ─────────────────────────────────────────────
def datas_reais_de_pre_quali(conn) -> pd.DataFrame:
    """Primeiro e último dia com gasto de Pré-Qualificação, por lançamento."""
    return pd.read_sql(
        text(
            "SELECT lancamento_codigo, MIN(date) AS inicio, MAX(date) AS fim, "
            "       ROUND(SUM(v)::numeric, 2) AS gasto "
            "FROM ( "
            "  SELECT lancamento_codigo, date, spend AS v FROM meta_ads_daily "
            "   WHERE etapa = 'Pré-Qualificação' "
            "  UNION ALL "
            "  SELECT lancamento_codigo, date, cost FROM google_ads_daily "
            "   WHERE etapa = 'Pré-Qualificação' "
            ") t WHERE lancamento_codigo = ANY(:codigos) "
            "GROUP BY 1 ORDER BY 1"
        ),
        conn,
        params={"codigos": LANCAMENTOS_SEM_PRE_QUALI},
    )


def corrigir_janelas(conn_analytics, conn_users, dry_run: bool) -> None:
    datas = datas_reais_de_pre_quali(conn_analytics)
    if datas.empty:
        print("  nenhuma etapa de Pré-Qualificação encontrada — nada a fazer")
        return

    atual = pd.read_sql(
        text(
            "SELECT lancamento_codigo, pre_quali_start_date, pre_quali_end_date "
            "FROM launch_config WHERE lancamento_codigo = ANY(:codigos)"
        ),
        conn_users,
        params={"codigos": LANCAMENTOS_SEM_PRE_QUALI},
    )
    print(f"  antes:\n{atual.to_string(index=False)}\n")

    for _, r in datas.iterrows():
        print(f"  {r.lancamento_codigo}: {r.inicio} a {r.fim}  (R$ {r.gasto:,.2f} de Pré-Quali)")
        if dry_run:
            continue
        conn_users.execute(
            text(
                "UPDATE launch_config SET pre_quali_start_date = :i, pre_quali_end_date = :f "
                "WHERE lancamento_codigo = :c"
            ),
            {"i": r.inicio, "f": r.fim, "c": r.lancamento_codigo},
        )

    if not dry_run:
        print(f"\n  backup do estado anterior: {_backup(atual, 'launch_config_pre_quali')}")


# ── 2. atribuição PI-ABR-26 → PI-JAN-26 ──────────────────────────────────────
def corrigir_atribuicao(conn, dry_run: bool) -> None:
    colisoes = conn.execute(
        text(
            "SELECT COUNT(*) FROM google_ads_daily a "
            "WHERE a.lancamento_codigo = :de AND a.date <= :corte "
            "  AND EXISTS (SELECT 1 FROM google_ads_daily b "
            "              WHERE b.lancamento_codigo = :para AND b.ad_id = a.ad_id AND b.date = a.date)"
        ),
        {"de": DE, "para": PARA, "corte": CORTE},
    ).scalar()
    if colisoes:
        # UNIQUE (ad_id, date, lancamento_codigo): mover criaria duplicata.
        print(f"  ABORTADO: {colisoes} linha(s) colidiriam com a UNIQUE em {PARA}")
        return

    afetadas = pd.read_sql(
        text(
            "SELECT campaign_id, campaign_name, MIN(date) AS d0, MAX(date) AS d1, "
            "       COUNT(*) AS linhas, ROUND(SUM(cost)::numeric, 2) AS gasto "
            "FROM google_ads_daily WHERE lancamento_codigo = :de AND date <= :corte "
            "GROUP BY 1, 2 ORDER BY gasto DESC"
        ),
        conn,
        params={"de": DE, "corte": CORTE},
    )
    if afetadas.empty:
        print("  nada a mover — já corrigido")
        return

    print(f"  {len(afetadas)} campanha(s), R$ {afetadas.gasto.sum():,.2f}, de {DE} para {PARA}:")
    for _, r in afetadas.iterrows():
        print(f"    {r.d0} a {r.d1}  R$ {r.gasto:>12,.2f}  {r.campaign_name[:62]}")

    if dry_run:
        for tabela in TABELAS_ATRIBUICAO:
            n = conn.execute(
                text(f"SELECT COUNT(*) FROM {tabela} WHERE lancamento_codigo = :de AND date <= :corte"),
                {"de": DE, "corte": CORTE},
            ).scalar()
            print(f"    [dry-run] {tabela}: {n} linha(s)")
        return

    print(f"\n  backup: {_backup(afetadas, 'atribuicao_pi_abr_para_pi_jan')}")
    for tabela in TABELAS_ATRIBUICAO:
        r = conn.execute(
            text(
                f"UPDATE {tabela} SET lancamento_codigo = :para "
                f"WHERE lancamento_codigo = :de AND date <= :corte"
            ),
            {"para": PARA, "de": DE, "corte": CORTE},
        )
        print(f"    {tabela}: {r.rowcount} linha(s) movida(s)")


def conferir(conn) -> None:
    print("\n  investimento em mídia depois da correção:")
    for code in (PARA, DE):
        v = conn.execute(
            text(
                "SELECT COALESCE((SELECT SUM(spend) FROM meta_ads_daily WHERE lancamento_codigo = :c), 0) "
                "     + COALESCE((SELECT SUM(cost) FROM google_ads_daily WHERE lancamento_codigo = :c), 0)"
            ),
            {"c": code},
        ).scalar()
        print(f"    {code}: R$ {float(v or 0):,.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que faria, sem gravar")
    args = parser.parse_args()

    engine, users = get_engine(), get_users_engine()
    with engine.begin() as conn, users.begin() as uconn:
        print("\n1. Datas de Pré-Qualificação em launch_config")
        corrigir_janelas(conn, uconn, args.dry_run)

        print(f"\n2. Atribuição {DE} → {PARA} (linhas até {CORTE})")
        corrigir_atribuicao(conn, args.dry_run)

        if not args.dry_run:
            conferir(conn)

    print("\nOK" + (" (dry-run, nada gravado)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
