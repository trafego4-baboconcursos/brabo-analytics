"""
ETL: Active Campaign — quem abriu e quem clicou cada campanha → Supabase
(tabela: ac_campaign_engajamento)

A tabela `ac_campaigns` só guarda o agregado (envios, aberturas, cliques), o que
impede cruzar e-mail com venda. Aqui a coleta desce ao contato: para cada
campanha do lançamento, /campaigns/{id}/links devolve os links, e
/linkData?filters[linkid]= devolve quem tocou em cada um.

O link cuja URL é literalmente "open" não é link: é o pixel de abertura. Sem
separar os dois, a contagem de "clique" fica 10-30x inflada — a campanha
"Agenda de Mentoria" de 01/09/26 tem 0 cliques reais e 2.232 aberturas.

O contact_id casa 1:1 com leads.id (é o mesmo id do AC), e é por aí que o
frontend chega no e-mail e daí no comprador.

Uso:
  python etl/etl_ac_engajamento.py --api                          # lançamentos recentes
  python etl/etl_ac_engajamento.py --api --launch-code PES-SET-26
"""
import argparse
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from constants import ac_keywords
from db import get_engine
from http_retry import http_get
from logger import get_logger

load_dotenv()

logger = get_logger("etl.ac_engajamento")

TABLE = "ac_campaign_engajamento"
# Cliques e aberturas continuam pingando depois que o carrinho fecha.
DIAS_APOS_FIM = 45


def _ac_get(path: str, **params) -> dict:
    base_url = os.environ["AC_API_URL"].rstrip("/")
    if "/api/3" not in base_url:
        base_url += "/api/3"
    r = http_get(base_url + "/" + path, headers={"Api-Token": os.environ["AC_API_KEY"]}, params=params)
    return r.json()


def _paginate(path: str, key: str, **params) -> list[dict]:
    out, offset = [], 0
    while True:
        batch = _ac_get(path, limit=100, offset=offset, **params).get(key, [])
        out.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    return out


def launches_to_process(launch_code: str | None) -> list[str]:
    if launch_code:
        return [launch_code.upper()]
    engine = get_engine()
    limite = date.today() - timedelta(days=DIAS_APOS_FIM)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT codigo FROM dim_lancamentos WHERE data_fim >= :lim AND data_inicio <= CURRENT_DATE ORDER BY data_inicio"),
            {"lim": limite},
        ).fetchall()
    return [r[0] for r in rows if re.match(r"^(PBB|PES|PI)-", str(r[0] or ""), re.IGNORECASE)]


def campanhas_do_lancamento(code: str) -> list[tuple[str, str]]:
    """[(campaign_id, nome)] — mesma regra do frontend: janela do lançamento + produto no nome."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT c.id, c.nome_campanha
                FROM ac_campaigns c
                JOIN dim_lancamentos l ON l.codigo = :code
                WHERE DATE(c.data_envio) BETWEEN l.data_inicio AND l.data_fim
                ORDER BY c.data_envio DESC
            """),
            {"code": code},
        ).fetchall()
    kws = ac_keywords(code)
    return [(str(r[0]), r[1] or "") for r in rows if any(k in (r[1] or "").lower() for k in kws)]


def engajamento(code: str, campanhas: list[tuple[str, str]]) -> pd.DataFrame:
    registros: dict[tuple[str, str], dict] = {}
    now = datetime.now(timezone.utc).isoformat()
    for camp_id, nome in campanhas:
        n_ab = n_cl = 0
        for lk in _ac_get(f"campaigns/{camp_id}/links").get("links", []):
            abertura = str(lk.get("link") or "").strip().lower() == "open"
            for r in _paginate("linkData", "linkData", **{"filters[linkid]": str(lk["id"])}):
                cid = r.get("contact")
                if not cid:
                    continue
                reg = registros.setdefault((camp_id, str(cid)), {
                    "lancamento_codigo": code,
                    "campaign_id": camp_id,
                    "campaign_name": nome,
                    "contact_id": str(cid),
                    "abriu": False,
                    "clicou": False,
                    "updated_at": now,
                })
                if abertura:
                    if not reg["abriu"]:
                        n_ab += 1
                    reg["abriu"] = True
                else:
                    if not reg["clicou"]:
                        n_cl += 1
                    reg["clicou"] = True
        logger.info("%s: campanha %s — %d abriram, %d clicaram (%s)", code, camp_id, n_ab, n_cl, nome[:40])
    return pd.DataFrame(list(registros.values()))


def upsert(code: str, df: pd.DataFrame) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                lancamento_codigo TEXT NOT NULL,
                campaign_id       TEXT NOT NULL,
                campaign_name     TEXT,
                contact_id        TEXT NOT NULL,
                abriu             BOOLEAN NOT NULL DEFAULT FALSE,
                clicou            BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at        TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (lancamento_codigo, campaign_id, contact_id)
            )
        """))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_lanc ON {TABLE} (lancamento_codigo)"))
        if df.empty:
            logger.warning("%s: nenhum engajamento encontrado — tabela mantida como está.", code)
            return
        conn.execute(text(f"DELETE FROM {TABLE} WHERE lancamento_codigo = :c"), {"c": code})
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=1000)
    logger.info("%s: %d linhas gravadas em '%s' (%d abriram, %d clicaram)",
                code, len(df), TABLE, int(df["abriu"].sum()), int(df["clicou"].sum()))


def main():
    parser = argparse.ArgumentParser(description="ETL Active Campaign — abertura/clique por contato")
    parser.add_argument("--api", action="store_true", required=True)
    parser.add_argument("--launch-code", metavar="CODE")
    parser.add_argument("--dry-run", action="store_true", help="coleta e relata, não grava")
    args = parser.parse_args()

    codes = launches_to_process(args.launch_code)
    if not codes:
        logger.info("Nenhum lançamento ativo/recente pra processar.")
        return
    for code in codes:
        campanhas = campanhas_do_lancamento(code)
        if not campanhas:
            logger.info("%s: nenhuma campanha de e-mail na janela — pulando.", code)
            continue
        logger.info("%s: %d campanhas", code, len(campanhas))
        df = engajamento(code, campanhas)
        if args.dry_run:
            logger.info("%s (dry-run): %d linhas, %d aberturas, %d cliques — nada gravado.",
                        code, len(df), int(df["abriu"].sum()) if not df.empty else 0,
                        int(df["clicou"].sum()) if not df.empty else 0)
            continue
        upsert(code, df)


if __name__ == "__main__":
    main()
