"""
ETL: relatório pós-transmissão do YouTube Studio (CSV) → Supabase.

Enquanto a API do YouTube não está conectada, os dados das aulas vêm do export
manual do Studio. Este script lê a pasta do lançamento:

    analises/[PI-AGO-26]/Youtube/
        Aula 1/
            liveViewership_*.csv     ← curva minuto a minuto (obrigatório)
            liveEngagements_*.csv    ← chat/reações por tipo (opcional)
        Aula 2/
            *.zip                    ← o zip que o Studio baixa, lido direto

Grava em duas tabelas:
  - youtube_live_curva   — a série minuto a minuto (a API não entrega isso)
  - youtube_aulas_stats  — os agregados derivados da curva (pico simultâneo,
                           quantos ficaram até o fim, duração, chat, reações),
                           com fonte='manual'

O que a curva NÃO tem (views totais, watch time, retenção média, likes,
comments, live vs replay, video_id) continua vindo do ETL da API
(etl_youtube_analytics.py) ou do export do Modo avançado. Por isso o upsert
aqui só toca as colunas que ele realmente mede — não zera o resto.

Uso:
    python etl/etl_youtube_csv.py --launch-code PI-AGO-26
    python etl/etl_youtube_csv.py --launch-code PI-AGO-26 --dry-run
"""
import argparse
import csv
import io
import re
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from db import get_engine  # noqa: E402
from logger import get_logger  # noqa: E402

load_dotenv()
logger = get_logger("etl_youtube_csv")

BASE_ANALISES = Path(__file__).parent.parent / "analises"

# O Studio exporta os cabeçalhos no idioma da conta. Mapeia para nome interno.
COL_VIEWERSHIP = {
    "posição na transmissão ao vivo (segundos)": "posicao_seg",
    "live stream position (seconds)":            "posicao_seg",
    "espectadores simultâneos na transmissão":   "simultaneos",
    "concurrent viewers":                        "simultaneos",
    "mensagens do chat ao vivo":                 "chat_msgs",
    "live chat messages":                        "chat_msgs",
    "média de espectadores simultâneos":         "media_simult",
    "average concurrent viewers":                "media_simult",
    "envolvimentos ao vivo":                     "envolvimentos",
    "live engagements":                          "envolvimentos",
    "reações":                                   "reacoes",
    "reactions":                                 "reacoes",
}


def _norm(s: str) -> str:
    return (s or "").strip().lstrip("﻿").lower()


def _to_int(v) -> int:
    try:
        return int(float(str(v).replace(",", ".").strip() or 0))
    except (TypeError, ValueError):
        return 0


# ─── Leitura dos arquivos ────────────────────────────────────────────────────

def _iter_csvs(aula_dir: Path):
    """Devolve (nome_do_arquivo, texto) de cada CSV da pasta, abrindo zips."""
    for p in sorted(aula_dir.iterdir()):
        if p.suffix.lower() == ".csv":
            yield p.name, p.read_text(encoding="utf-8-sig", errors="replace")
        elif p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for info in z.infolist():
                    if info.filename.lower().endswith(".csv"):
                        raw = z.read(info)
                        yield info.filename, raw.decode("utf-8-sig", errors="replace")


def _parse_viewership(texto: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(texto))
    linhas = []
    for row in reader:
        rec = {"posicao_seg": None, "simultaneos": 0, "media_simult": 0,
               "chat_msgs": 0, "envolvimentos": 0, "reacoes": 0}
        for k, v in row.items():
            interno = COL_VIEWERSHIP.get(_norm(k))
            if interno:
                rec[interno] = _to_int(v)
        if rec["posicao_seg"] is not None:
            linhas.append(rec)
    return linhas


def _parse_engagements(texto: str) -> dict[str, int]:
    """Totais por tipo de envolvimento (Mensagens de chat / Reações)."""
    reader = csv.DictReader(io.StringIO(texto))
    totais: dict[str, int] = {}
    for row in reader:
        tipo = valor = None
        for k, v in row.items():
            kn = _norm(k)
            if "tipo de envolvimento" in kn or "engagement type" in kn:
                tipo = _norm(v)
            elif "envolvimentos ao vivo" in kn or "live engagements" in kn:
                valor = _to_int(v)
        if tipo and valor is not None:
            totais[tipo] = totais.get(tipo, 0) + valor
    return totais


def coletar(launch_code: str) -> list[dict]:
    """Lê analises/[LAUNCH]/Youtube/Aula N/ e devolve uma entrada por aula."""
    pasta = BASE_ANALISES / f"[{launch_code}]" / "Youtube"
    if not pasta.exists():
        pasta = BASE_ANALISES / f"[{launch_code}]" / "YouTube"
    if not pasta.exists():
        logger.error("Pasta não encontrada: %s", pasta)
        return []

    aulas = []
    for aula_dir in sorted(pasta.iterdir()):
        if not aula_dir.is_dir():
            continue
        m = re.search(r"(\d+)", aula_dir.name)
        if not m:
            logger.warning("Pasta sem número de aula, ignorada: %s", aula_dir.name)
            continue
        aula_num = int(m.group(1))

        curva: list[dict] = []
        engaj: dict[str, int] = {}
        titulo = ""
        for nome, texto in _iter_csvs(aula_dir):
            base = Path(nome).name
            if base.lower().startswith("liveviewership"):
                curva = _parse_viewership(texto)
                titulo = _titulo_do_arquivo(base)
            elif base.lower().startswith("liveengagements"):
                engaj = _parse_engagements(texto)
                titulo = titulo or _titulo_do_arquivo(base)

        if not curva:
            logger.warning("Aula %d sem liveViewership_*.csv — ignorada", aula_num)
            continue

        picos = [r["simultaneos"] for r in curva]
        aulas.append({
            "aula_num":     aula_num,
            "titulo":       titulo,
            "curva":        curva,
            "duration_sec": max(r["posicao_seg"] for r in curva),
            "peak":         max(picos),
            "viewers_fim":  curva[-1]["simultaneos"],
            "chat_msgs":    sum(r["chat_msgs"] for r in curva),
            "reacoes":      sum(r["reacoes"] for r in curva)
                            or next((v for k, v in engaj.items() if "rea" in k), 0),
        })
    return sorted(aulas, key=lambda a: a["aula_num"])


def video_ids_configurados(launch_code: str) -> dict[int, str]:
    """{aula_num: video_id} do config do lançamento (banco → YAML).

    Reaproveita o mesmo `_load_videos` do ETL da API para não existirem duas
    listas de video_id divergentes. A ordem da lista define o número da aula,
    igual ao que o ETL da API faz.
    """
    try:
        from etl_youtube_analytics import _load_videos
        aulas, _ = _load_videos(launch_code)
    except Exception as e:
        logger.debug("Sem video_ids configurados para %s: %s", launch_code, e)
        return {}
    return {i: a["id"] for i, a in enumerate(aulas, start=1) if a.get("id")}


def _titulo_do_arquivo(nome: str) -> str:
    """'liveViewership_Transmissões ao vivo TITULO.csv' → 'TITULO'."""
    t = Path(nome).stem
    t = re.sub(r"^live(Viewership|Engagements)_", "", t, flags=re.I)
    t = re.sub(r"^Transmiss[õo]es ao vivo\s*", "", t, flags=re.I)
    t = re.sub(r"^Live streams?\s*", "", t, flags=re.I)
    return t.strip()


# ─── Gravação ────────────────────────────────────────────────────────────────

def gravar(launch_code: str, aulas: list[dict]) -> None:
    engine = get_engine()
    ids_cfg = video_ids_configurados(launch_code)
    with engine.begin() as conn:
        for a in aulas:
            # Com o video_id configurado, a linha já nasce com a chave real —
            # é o que liga a thumb e o link do card ao vídeo. Sem ele, uma
            # chave estável derivada da aula segura o UNIQUE(launch_code,
            # video_id) até a configuração aparecer.
            placeholder = f"manual-aula-{a['aula_num']}"
            video_id = ids_cfg.get(a["aula_num"], placeholder)
            if video_id != placeholder:
                # Promove a linha antiga em vez de duplicar a aula.
                conn.execute(
                    text("DELETE FROM youtube_aulas_stats "
                         "WHERE launch_code = :c AND video_id = :p"),
                    {"c": launch_code, "p": placeholder},
                )
            conn.execute(text("""
                INSERT INTO youtube_aulas_stats (
                    launch_code, video_id, aula_num, titulo, duration_sec,
                    peak_concurrent, viewers_fim, chat_msgs, reacoes,
                    fonte, fetched_at
                ) VALUES (
                    :launch_code, :video_id, :aula_num, :titulo, :duration_sec,
                    :peak, :viewers_fim, :chat_msgs, :reacoes,
                    'manual', NOW()
                )
                ON CONFLICT (launch_code, video_id) DO UPDATE SET
                    aula_num        = EXCLUDED.aula_num,
                    titulo          = EXCLUDED.titulo,
                    duration_sec    = EXCLUDED.duration_sec,
                    peak_concurrent = EXCLUDED.peak_concurrent,
                    viewers_fim     = EXCLUDED.viewers_fim,
                    chat_msgs       = EXCLUDED.chat_msgs,
                    reacoes         = EXCLUDED.reacoes,
                    fonte           = 'manual',
                    fetched_at      = NOW()
            """), {
                "launch_code": launch_code, "video_id": video_id,
                "aula_num": a["aula_num"], "titulo": a["titulo"],
                "duration_sec": a["duration_sec"], "peak": a["peak"],
                "viewers_fim": a["viewers_fim"], "chat_msgs": a["chat_msgs"],
                "reacoes": a["reacoes"],
            })

            conn.execute(
                text("DELETE FROM youtube_live_curva WHERE launch_code = :c AND aula_num = :n"),
                {"c": launch_code, "n": a["aula_num"]},
            )
            conn.execute(text("""
                INSERT INTO youtube_live_curva (
                    launch_code, aula_num, posicao_seg, simultaneos,
                    media_simult, chat_msgs, envolvimentos, reacoes
                ) VALUES (
                    :launch_code, :aula_num, :posicao_seg, :simultaneos,
                    :media_simult, :chat_msgs, :envolvimentos, :reacoes
                )
            """), [
                {"launch_code": launch_code, "aula_num": a["aula_num"], **r}
                for r in a["curva"]
            ])

    logger.info("Gravado: %d aulas, %d pontos de curva",
                len(aulas), sum(len(a["curva"]) for a in aulas))


def main():
    ap = argparse.ArgumentParser(description="Ingere o relatório pós-transmissão do YouTube Studio")
    ap.add_argument("--launch-code", required=True, help="Ex.: PI-AGO-26")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que leria")
    args = ap.parse_args()

    aulas = coletar(args.launch_code)
    if not aulas:
        logger.error("Nada para gravar.")
        sys.exit(1)

    for a in aulas:
        ret = (a["viewers_fim"] / a["peak"] * 100) if a["peak"] else 0
        logger.info(
            "Aula %d | %s | %dmin | pico %s | fim %s (%.0f%%) | chat %s | reações %s",
            a["aula_num"], a["titulo"][:45], a["duration_sec"] // 60,
            f"{a['peak']:,}".replace(",", "."), f"{a['viewers_fim']:,}".replace(",", "."),
            ret, f"{a['chat_msgs']:,}".replace(",", "."), f"{a['reacoes']:,}".replace(",", "."),
        )

    if args.dry_run:
        logger.info("--dry-run: nada gravado.")
        return
    gravar(args.launch_code, aulas)


if __name__ == "__main__":
    main()
