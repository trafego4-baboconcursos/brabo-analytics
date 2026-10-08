"""Carrega a régua de alunos (quem é aluno de quem) no banco analytics.

POR QUE EXISTE. A página /whatsapp precisa dizer quantos membros dos grupos são
aluno e quantos não são. Até 08/10/26 essa conta era feita à mão, a partir de
arquivos (itens 141 e 180 do MUDANCAS_BV-26), e a página não mostrava nada.
Aqui a régua vira a tabela `aluno_regua`, e o leitor
`frontend/db_readers/whatsapp_alunos.py` cruza os membros com ela.

DE ONDE VEM (pasta `analises/<lanc>/publico/aluno-api/`, fora do git — dado pessoal):
  - `plataforma_classificacao_<AAAAMMDD>.csv` — API da plataforma de cursos:
    email, phone, expert (INSS/TJSP/BB), situacao (vitalício | ativo (prazo) |
    ex-aluno), validade, compra_12m. A régua de aluno vem da PLATAFORMA, nunca
    do Active Campaign.
  - `ALUNO-<EXPERT>-EX-ALUNO*.csv` — listas de ex-aluno exportadas do Active.
    Só acrescentam ex-aluno; nunca fazem de ninguém aluno ativo.

A régua é uma FOTO da data do arquivo. Quem comprar depois não aparece como
aluno até a régua ser recarregada — a página mostra a data da régua por isso.

Recarregar substitui a régua inteira (é uma foto, não um histórico).

Uso:
    python scripts/carregar_regua_alunos.py --pasta "analises/bv-26/publico/aluno-api" --dry-run
    python scripts/carregar_regua_alunos.py --pasta "analises/bv-26/publico/aluno-api"
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

TABELA = "aluno_regua"

# Lista de comandos, nunca dividida por ";" (ver etl/historico_utm.py).
_DDL = [
    f"""CREATE TABLE IF NOT EXISTS {TABELA} (
        email          text        NOT NULL DEFAULT '',
        telefone_norm  text,
        expert         text        NOT NULL,
        situacao       text        NOT NULL,
        validade       text,
        compra_12m     boolean,
        origem         text        NOT NULL,
        referencia     date        NOT NULL,
        carregado_em   timestamptz NOT NULL DEFAULT now()
    )""",
    f"CREATE INDEX IF NOT EXISTS idx_{TABELA}_tel ON {TABELA} (telefone_norm)",
    f"CREATE INDEX IF NOT EXISTS idx_{TABELA}_email ON {TABELA} (email)",
]

_EXPERT_DO_ARQUIVO = {"INSS": "INSS", "TJSP": "TJSP", "BB": "BB"}


def _norm_tel(valor) -> str | None:
    """DDD + 8 últimos dígitos — a mesma regra de whatsapp_groups._norm_phone,
    que ignora o DDI 55 e o nono dígito. É o que casa número de grupo (que às
    vezes vem sem o 9) com cadastro."""
    from frontend.db_readers.whatsapp_groups import _norm_phone  # noqa: PLC0415
    return _norm_phone(valor)


def _ler_plataforma(pasta: Path) -> tuple[pd.DataFrame, date]:
    arquivos = sorted(pasta.glob("plataforma_classificacao_*.csv"))
    if not arquivos:
        raise SystemExit(f"nenhum plataforma_classificacao_*.csv em {pasta}")
    arq = arquivos[-1]
    achado = re.search(r"(\d{8})", arq.name)
    if not achado:
        raise SystemExit(f"{arq.name}: sem data AAAAMMDD no nome — é ela que vira a data da régua")
    ref = datetime.strptime(achado.group(1), "%Y%m%d").date()
    df = pd.read_csv(arq, dtype=str)
    out = pd.DataFrame({
        "email": df["email"].fillna("").str.strip().str.lower(),
        "telefone_norm": df["phone"].map(_norm_tel),
        "expert": df["expert"].str.strip().str.upper(),
        "situacao": df["situacao"].str.strip(),
        "validade": df.get("validade"),
        "compra_12m": df["compra_12m"].map({"True": True, "False": False}),
        "origem": "api_plataforma",
    })
    print(f"  {arq.name}: {len(out):,} linhas (referência {ref:%d/%m/%Y})")
    return out, ref


def _ler_ex_alunos_ac(pasta: Path) -> pd.DataFrame:
    partes = []
    for arq in sorted(pasta.glob("ALUNO-*-EX-ALUNO*.csv")):
        expert = _EXPERT_DO_ARQUIVO.get(arq.name.split("-")[1].upper())
        if not expert:
            print(f"  ignorado (expert desconhecido): {arq.name}")
            continue
        df = pd.read_csv(arq, dtype=str)
        partes.append(pd.DataFrame({
            "email": df["Email"].fillna("").str.strip().str.lower(),
            "telefone_norm": df["Phone"].map(_norm_tel),
            "expert": expert,
            "situacao": "ex-aluno",
            "validade": None,
            "compra_12m": None,
            "origem": "ac_ex_aluno",
        }))
        print(f"  {arq.name}: {len(df):,} linhas")
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pasta", required=True, help="pasta aluno-api com os CSVs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pasta = (_RAIZ / args.pasta) if not Path(args.pasta).is_absolute() else Path(args.pasta)
    print(f"régua de alunos a partir de {pasta}:")
    plataforma, ref = _ler_plataforma(pasta)
    ex = _ler_ex_alunos_ac(pasta)
    regua = pd.concat([plataforma, ex], ignore_index=True)
    regua = regua[(regua["email"] != "") | regua["telefone_norm"].notna()]
    regua = regua.drop_duplicates(subset=["email", "telefone_norm", "expert", "situacao", "origem"])
    regua["referencia"] = ref

    print(f"\ntotal: {len(regua):,} linhas | por situação: {regua['situacao'].value_counts().to_dict()}")
    print(f"com telefone: {regua['telefone_norm'].notna().sum():,} | com e-mail: {(regua['email'] != '').sum():,}")
    if args.dry_run:
        print("(dry-run, nada gravado)")
        return 0

    from psycopg2.extras import execute_values  # noqa: PLC0415
    from frontend.db import _get_engine  # noqa: PLC0415

    colunas = ["email", "telefone_norm", "expert", "situacao", "validade",
               "compra_12m", "origem", "referencia"]
    tuplas = [tuple(None if pd.isna(v) else v for v in linha)
              for linha in regua[colunas].itertuples(index=False, name=None)]
    with _get_engine().begin() as conn:
        conn.execute(text("SET LOCAL statement_timeout = '300s'"))
        for comando in _DDL:
            conn.execute(text(comando))
        apagadas = conn.execute(text(f"DELETE FROM {TABELA}")).rowcount
        # execute_values manda milhares de linhas por comando. Com text() +
        # lista de dicts o driver faz uma ida e volta por linha: 88 mil
        # viagens ao Supabase estouraram 400 s sem gravar nada (08/10/26).
        cursor = conn.connection.cursor()
        execute_values(cursor, f"INSERT INTO {TABELA} ({', '.join(colunas)}) VALUES %s",
                       tuplas, page_size=5000)
    print(f"gravado: {len(tuplas):,} linhas (substituiu {apagadas:,})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
