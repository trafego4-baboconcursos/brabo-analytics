"""
ETL: Calendário Operacional → dim_etapas (Supabase)

Parseia o HTML SISTEMA_CALENDARIO_2026.html e popula a tabela dim_etapas
com as datas exatas de cada etapa por lançamento.

Uso:
    python etl/etl_calendario.py
    python etl/etl_calendario.py --html "analises/[PBB-ABR-26]/SISTEMA_CALENDARIO_2026.html"
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from db import get_engine
from sqlalchemy import text

HTML_DEFAULT = Path(__file__).parent.parent / "analises" / "[PBB-ABR-26]" / "SISTEMA_CALENDARIO_2026.html"

TABLE = "dim_etapas"

# Normaliza os nomes de etapa do HTML para o padrão do sistema
ETAPA_NORM = {
    "pre-quali":        "Pré-Qualificação",
    "captação":         "Captação",
    "captacao":         "Captação",
    "lembrete":         "Lembrete",
    "depoimento":       "Depoimento",
    "aulas semana 0":   "Aulas no Ar",
    "aulas no ar":      "Aulas no Ar",
    "replay":           "Replay",
    "carrinho aberto":  "Matrículas Abertas",
    "matrículas abertas": "Matrículas Abertas",
}

ORDEM_ETAPA = {
    "Pré-Qualificação":  1,
    "Captação":          2,
    "Lembrete":          3,
    "Depoimento":        4,
    "Aulas no Ar":       5,
    "Replay":            6,
    "Matrículas Abertas": 7,
}


def parse_date(s: str):
    """Converte DD/MM/YYYY → date."""
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def normalize_etapa(raw: str) -> str:
    key = raw.strip().lower()
    return ETAPA_NORM.get(key, raw.strip())


def parse_html(html_path: Path) -> list[dict]:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # Localiza a tabela de agenda (tem data-launch nos <tr>)
    rows = []
    for tr in soup.find_all("tr", attrs={"data-launch": True}):
        launch_code = tr["data-launch"].strip().upper()
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue

        # Etapa está no <span class="stage ..."> dentro do 3º td
        stage_span = tds[2].find("span", class_="stage")
        if not stage_span:
            continue
        etapa_raw = stage_span.get_text(strip=True)
        etapa = normalize_etapa(etapa_raw)

        data_inicio = parse_date(tds[6].get_text(strip=True))
        data_fim    = parse_date(tds[7].get_text(strip=True))

        if not data_inicio or not data_fim:
            continue

        duracao = (data_fim - data_inicio).days + 1
        ordem   = ORDEM_ETAPA.get(etapa, 99)

        rows.append({
            "lancamento_codigo": launch_code,
            "etapa":             etapa,
            "ordem":             ordem,
            "data_inicio":       str(data_inicio),
            "data_fim":          str(data_fim),
            "duracao_dias":      duracao,
            "updated_at":        datetime.now(timezone.utc).isoformat(),
        })

    return rows


def create_table_if_needed(engine):
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id                SERIAL PRIMARY KEY,
                lancamento_codigo TEXT NOT NULL,
                etapa             TEXT NOT NULL,
                ordem             INTEGER,
                data_inicio       DATE NOT NULL,
                data_fim          DATE NOT NULL,
                duracao_dias      INTEGER,
                updated_at        TIMESTAMPTZ,
                UNIQUE (lancamento_codigo, etapa)
            )
        """))


def upsert(rows: list[dict], engine):
    if not rows:
        print("  Nenhum dado para gravar.")
        return
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {TABLE}"))
        conn.execute(
            text(f"""
                INSERT INTO {TABLE}
                    (lancamento_codigo, etapa, ordem, data_inicio, data_fim, duracao_dias, updated_at)
                VALUES
                    (:lancamento_codigo, :etapa, :ordem, :data_inicio, :data_fim, :duracao_dias, :updated_at)
            """),
            rows,
        )
    print(f"  OK: {len(rows)} etapas gravadas em '{TABLE}'")


def main():
    parser = argparse.ArgumentParser(description="ETL Calendário → dim_etapas")
    parser.add_argument("--html", metavar="FILE", default=str(HTML_DEFAULT),
                        help="Caminho para SISTEMA_CALENDARIO_2026.html")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {html_path}")
        sys.exit(1)

    print(f"[Calendário] Parseando: {html_path.name}")
    rows = parse_html(html_path)
    print(f"  {len(rows)} linhas encontradas")

    engine = get_engine()
    create_table_if_needed(engine)
    upsert(rows, engine)

    # Mostra resumo por lançamento
    from collections import defaultdict
    por_lancamento = defaultdict(list)
    for r in rows:
        por_lancamento[r["lancamento_codigo"]].append(r["etapa"])
    for codigo, etapas in sorted(por_lancamento.items()):
        print(f"  {codigo}: {', '.join(etapas)}")


if __name__ == "__main__":
    main()
