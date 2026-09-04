"""
ETL: Active Campaign — cliques no PDF do ebook → Supabase (tabela: ac_ebook_clicks)

"Baixou o ebook" = clicou no link do PDF dentro do e-mail da automação do
lançamento (ex.: "Guia Completo INSS | PI-AGO-26"). O AC não expõe isso como
tag/lista; sai contato a contato por /linkData. Achado no fechamento do
PI-AGO-26 (04/09/26): 6.459 contatos clicaram, 196 compraram.

Como acha os links de cada lançamento:
  1. automações cujo nome contém o código (GET /automations?search=CODE)
     + campanhas cujo nome contém o código;
  2. campanhas ligadas a essas automações;
  3. links dessas campanhas cuja URL é um PDF (.pdf) ou arquivo do Drive.

Uso:
  python etl/etl_ac_ebook.py --api                       # lançamentos ativos/recentes
  python etl/etl_ac_ebook.py --api --launch-code PI-AGO-26
"""
import os
import sys
import argparse
import re
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get

load_dotenv()

logger = get_logger("etl.ac_ebook")

TABLE = "ac_ebook_clicks"
PDF_RE = re.compile(r"\.pdf(\?|$)|drive\.google\.com/file/", re.IGNORECASE)
# Quantos dias depois do fim do lançamento ainda vale reprocessar (cliques
# tardios no e-mail do guia).
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
        data = _ac_get(path, limit=100, offset=offset, **params)
        batch = data.get(key, [])
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


def _all_campaigns() -> list[dict]:
    return _paginate("campaigns", "campaigns")


def ebook_links_for_launch(code: str, campaigns: list[dict]) -> list[dict]:
    """[{campaign_id, campaign_name, link_id, link_url}] dos PDFs do lançamento."""
    code_up = code.upper()
    autos = _ac_get("automations", search=code, limit=100).get("automations", [])
    auto_ids = {str(a["id"]) for a in autos if code_up in str(a.get("name", "")).upper()}
    alvo = [
        c for c in campaigns
        if str(c.get("automation")) in auto_ids or code_up in str(c.get("name", "")).upper()
    ]
    links = []
    for c in alvo:
        for lk in _ac_get(f"campaigns/{c['id']}/links").get("links", []):
            url = str(lk.get("link") or "")
            if url.startswith("ftp://") or not PDF_RE.search(url):
                continue
            links.append({
                "campaign_id": str(c["id"]),
                "campaign_name": c.get("name", ""),
                "link_id": str(lk["id"]),
                "link_url": url,
            })
    logger.info("%s: %d automações, %d campanhas, %d links de PDF", code, len(auto_ids), len(alvo), len(links))
    return links


def clicks_for_links(code: str, links: list[dict]) -> pd.DataFrame:
    records = []
    now = datetime.now(timezone.utc).isoformat()
    for lk in links:
        rows = _paginate("linkData", "linkData", **{"filters[linkid]": lk["link_id"]})
        for r in rows:
            cid = r.get("contact")
            if not cid:
                continue
            records.append({
                "lancamento_codigo": code,
                "campaign_id": lk["campaign_id"],
                "campaign_name": lk["campaign_name"],
                "link_id": lk["link_id"],
                "link_url": lk["link_url"],
                "contact_id": str(cid),
                "clicked_at": r.get("tstamp") or r.get("cdate"),
                "updated_at": now,
            })
        logger.info("%s: link %s - %d cliques", code, lk["link_id"], len(rows))
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates(subset=["lancamento_codigo", "link_id", "contact_id"], keep="last")
    return df


def upsert(code: str, df: pd.DataFrame) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                lancamento_codigo TEXT NOT NULL,
                campaign_id       TEXT,
                campaign_name     TEXT,
                link_id           TEXT NOT NULL,
                link_url          TEXT,
                contact_id        TEXT NOT NULL,
                clicked_at        TIMESTAMPTZ,
                updated_at        TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (lancamento_codigo, link_id, contact_id)
            )
        """))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_lanc ON {TABLE} (lancamento_codigo)"))
        if df.empty:
            logger.warning("%s: nenhum clique encontrado — tabela mantida como está.", code)
            return
        conn.execute(text(f"DELETE FROM {TABLE} WHERE lancamento_codigo = :c"), {"c": code})
    df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("%s: %d cliques gravados em '%s'", code, len(df), TABLE)


def main():
    parser = argparse.ArgumentParser(description="ETL Active Campaign — cliques no ebook")
    parser.add_argument("--api", action="store_true", required=True)
    parser.add_argument("--launch-code", metavar="CODE")
    args = parser.parse_args()

    codes = launches_to_process(args.launch_code)
    if not codes:
        logger.info("Nenhum lançamento ativo/recente pra processar.")
        return
    campaigns = _all_campaigns()
    for code in codes:
        links = ebook_links_for_launch(code, campaigns)
        if not links:
            logger.info("%s: sem link de PDF em automação/campanha com o código — pulando.", code)
            continue
        upsert(code, clicks_for_links(code, links))


if __name__ == "__main__":
    main()
