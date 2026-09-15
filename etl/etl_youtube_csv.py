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

def _nome_zip_ok(info: zipfile.ZipInfo) -> str:
    """O Studio grava o nome sem a flag de UTF-8, e o zipfile decodifica como
    cp437 — "Orgânicos.csv" chega como "Org+ónicos.csv". Desfaz isso."""
    nome = info.filename
    if not (info.flag_bits & 0x800):
        try:
            return nome.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return nome


def _iter_csvs(aula_dir: Path):
    """(nome_do_zip | None, nome_do_csv, texto) de cada CSV da pasta.

    O nome do zip carrega o período do export ("Conteúdo 2026-08-18_2026-09-15
    ..."), que não aparece em lugar nenhum dentro do arquivo.
    """
    for p in sorted(aula_dir.iterdir()):
        if p.suffix.lower() == ".csv":
            yield None, p.name, p.read_text(encoding="utf-8-sig", errors="replace")
        elif p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for info in z.infolist():
                    if info.filename.lower().endswith(".csv"):
                        raw = z.read(info)
                        yield p.name, _nome_zip_ok(info), raw.decode("utf-8-sig", errors="replace")


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


# ─── Relatório "Retenção de público" ─────────────────────────────────────────
#
# Um arquivo por corte de público. O Studio nomeia a coluna do corte, e é ela
# que identifica o arquivo com segurança — o nome do arquivo varia com o
# idioma da conta e com a codificação do zip.
COL_SEGMENTO = {
    "status da inscrição":                       {"inscrito": "inscrito", "não inscrito": "nao_inscrito"},
    "subscription status":                       {"subscribed": "inscrito", "not subscribed": "nao_inscrito"},
    "espectadores novos e recorrentes":          {"novos espectadores": "novo", "espectadores recorrentes": "recorrente"},
    "público por comportamento de visualização": {"novos espectadores": "novo_comport",
                                                  "espectadores casuais": "casual",
                                                  "espectadores recorrentes": "frequente"},
    "tipo de público":                           {"orgânicos": "trafego_organico", "pagos": "trafego_pago"},
}

# Arquivos de um corte só (a coluna não diz qual é) — identificados por um
# pedaço do nome que sobrevive a qualquer codificação.
SEG_POR_NOME = [("discovery", "anuncio_discovery"), ("pul", "anuncio_pulavel"), ("nicos", "organicos")]


def _parse_retencao(nome: str, texto: str) -> dict[str, list[dict]]:
    """{segmento: [{posicao_pct, retencao_pct, vs_outros_pct}]}"""
    reader = csv.DictReader(io.StringIO(texto))
    cols = reader.fieldnames or []
    if not cols or "posição no vídeo" not in _norm(cols[0]) and "video position" not in _norm(cols[0]):
        return {}

    col_seg = next((c for c in cols if _norm(c) in COL_SEGMENTO), None)
    col_ret = next((c for c in cols if "retenção absoluta" in _norm(c) or "absolute audience retention" in _norm(c)), None)
    col_vs = next((c for c in cols if "em comparação" in _norm(c) or "compared to" in _norm(c)), None)
    if not col_ret:
        return {}

    if col_seg:
        mapa = COL_SEGMENTO[_norm(col_seg)]
        seg_fixo = None
    else:
        base = _norm(nome)
        seg_fixo = next((s for chave, s in SEG_POR_NOME if chave in base), "todos")
        # "Todos.csv" não tem coluna de comparação; os de um corte só têm.
        if col_vs is None:
            seg_fixo = "todos"
        mapa = {}

    saida: dict[str, list[dict]] = {}
    for row in reader:
        seg = seg_fixo or mapa.get(_norm(row.get(col_seg, "")))
        if not seg:
            continue
        try:
            pos = int(float(row[cols[0]]))
            ret = float(row[col_ret] or 0)
        except (TypeError, ValueError):
            continue
        vs = None
        if col_vs:
            try:
                vs = float(row[col_vs])
            except (TypeError, ValueError):
                vs = None
        saida.setdefault(seg, []).append({"posicao_pct": pos, "retencao_pct": ret, "vs_outros_pct": vs})
    return saida


def _parse_atividade(texto: str) -> list[dict]:
    """"Atividade detalhada": quantos começaram/pararam em cada posição."""
    reader = csv.DictReader(io.StringIO(texto))
    cols = reader.fieldnames or []
    if not cols or "começaram a assistir" not in " ".join(_norm(c) for c in cols):
        return []
    c_ini = next((c for c in cols if "começaram" in _norm(c)), None)
    c_fim = next((c for c in cols if "pararam" in _norm(c)), None)
    c_vez = next((c for c in cols if "número de vezes" in _norm(c)), None)
    linhas = []
    for row in reader:
        try:
            pos = int(float(row[cols[0]]))
        except (TypeError, ValueError):
            continue
        linhas.append({
            "posicao_pct":     pos,
            "comecaram":       _to_int(row.get(c_ini)) if c_ini else 0,
            "pararam":         _to_int(row.get(c_fim)) if c_fim else 0,
            "vezes_assistido": _to_int(row.get(c_vez)) if c_vez else 0,
        })
    return linhas


# ─── Relatório "Conteúdo" ────────────────────────────────────────────────────

def _parse_conteudo(texto: str) -> dict:
    """Linha "Total" do relatório de conteúdo: views, watch time, impressões
    e CTR **do período exportado** — não do vídeo inteiro."""
    reader = csv.DictReader(io.StringIO(texto))
    cols = reader.fieldnames or []
    if not cols or _norm(cols[0]) not in ("conteúdo", "content"):
        return {}
    for row in reader:
        if _norm(row.get(cols[0], "")) not in ("total", ""):
            continue
        achar = lambda *ts: next((c for c in cols if any(t in _norm(c) for t in ts)), None)  # noqa: E731
        c_views = achar("visualizações", "views")
        c_watch = achar("tempo de exibição", "watch time")
        c_imp = achar("impressões", "impressions")
        c_ctr = achar("taxa de cliques", "click-through")
        return {
            "views_periodo":   _to_int(row.get(c_views)) if c_views else 0,
            "watch_periodo_h": float(str(row.get(c_watch, 0) or 0).replace(",", ".")) if c_watch else 0.0,
            "impressoes":      _to_int(row.get(c_imp)) if c_imp else 0,
            "ctr_thumb":       float(str(row.get(c_ctr, 0) or 0).replace(",", ".")) if c_ctr else 0.0,
        }
    return {}


def _periodo_do_zip(nome_zip: str) -> tuple[str | None, str | None]:
    """"Conteúdo 2026-08-18_2026-09-15 Titulo.zip" → (2026-08-18, 2026-09-15)."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})[_ ](\d{4}-\d{2}-\d{2})", nome_zip or "")
    return (m.group(1), m.group(2)) if m else (None, None)


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
        retencao: dict[str, list[dict]] = {}
        atividade: list[dict] = []
        conteudo: dict = {}
        periodo: tuple[str | None, str | None] = (None, None)
        periodo_ret: tuple[str | None, str | None] = (None, None)
        titulo = ""
        for nome_zip, nome, texto in _iter_csvs(aula_dir):
            base = Path(nome).name
            low = base.lower()
            if low.startswith("liveviewership"):
                curva = _parse_viewership(texto)
                titulo = _titulo_do_arquivo(base)
            elif low.startswith("liveengagements"):
                engaj = _parse_engagements(texto)
                titulo = titulo or _titulo_do_arquivo(base)
            elif low.startswith("dados da tabela") or low.startswith("table data"):
                dados = _parse_conteudo(texto)
                if dados:
                    conteudo = dados
                    periodo = _periodo_do_zip(nome_zip or "")
            else:
                # Os arquivos de retenção variam de nome com o idioma e a
                # codificação do zip; deixa o parser decidir pelo cabeçalho.
                ativ = _parse_atividade(texto)
                if ativ:
                    atividade = ativ
                    periodo_ret = _periodo_do_zip(nome_zip or "")
                    continue
                segs = _parse_retencao(base, texto)
                for seg, pontos in segs.items():
                    if pontos:
                        retencao[seg] = pontos
                if segs:
                    periodo_ret = periodo_ret if periodo_ret[0] else _periodo_do_zip(nome_zip or "")

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
            "retencao":     retencao,
            "atividade":    atividade,
            # Soma de "começaram a assistir" = visualizações que o relatório de
            # retenção mediu. NÃO é o público da live: esse relatório mede o
            # vídeo (com replay), e na Aula 3 do PI-AGO-26 ele dá menos views
            # que o pico simultâneo ao vivo.
            "visualizacoes_video": sum(p["comecaram"] for p in atividade),
            "periodo_ini":  periodo[0],
            "periodo_fim":  periodo[1],
            "retencao_ini": periodo_ret[0],
            "retencao_fim": periodo_ret[1],
            **conteudo,
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
                    visualizacoes_video, retencao_ini, retencao_fim, impressoes, ctr_thumb,
                    periodo_ini, periodo_fim, views_periodo, watch_periodo_h,
                    fonte, fetched_at
                ) VALUES (
                    :launch_code, :video_id, :aula_num, :titulo, :duration_sec,
                    :peak, :viewers_fim, :chat_msgs, :reacoes,
                    :visualizacoes_video, :retencao_ini, :retencao_fim, :impressoes, :ctr_thumb,
                    :periodo_ini, :periodo_fim, :views_periodo, :watch_periodo_h,
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
                    -- COALESCE: um export sem o relatório de conteúdo não
                    -- apaga o que outro já tinha trazido.
                    visualizacoes_video = COALESCE(NULLIF(EXCLUDED.visualizacoes_video, 0), youtube_aulas_stats.visualizacoes_video),
                    retencao_ini    = COALESCE(EXCLUDED.retencao_ini, youtube_aulas_stats.retencao_ini),
                    retencao_fim    = COALESCE(EXCLUDED.retencao_fim, youtube_aulas_stats.retencao_fim),
                    impressoes      = COALESCE(NULLIF(EXCLUDED.impressoes, 0), youtube_aulas_stats.impressoes),
                    ctr_thumb       = COALESCE(NULLIF(EXCLUDED.ctr_thumb, 0), youtube_aulas_stats.ctr_thumb),
                    periodo_ini     = COALESCE(EXCLUDED.periodo_ini, youtube_aulas_stats.periodo_ini),
                    periodo_fim     = COALESCE(EXCLUDED.periodo_fim, youtube_aulas_stats.periodo_fim),
                    views_periodo   = COALESCE(NULLIF(EXCLUDED.views_periodo, 0), youtube_aulas_stats.views_periodo),
                    watch_periodo_h = COALESCE(NULLIF(EXCLUDED.watch_periodo_h, 0), youtube_aulas_stats.watch_periodo_h),
                    fonte           = 'manual',
                    fetched_at      = NOW()
            """), {
                "launch_code": launch_code, "video_id": video_id,
                "aula_num": a["aula_num"], "titulo": a["titulo"],
                "duration_sec": a["duration_sec"], "peak": a["peak"],
                "viewers_fim": a["viewers_fim"], "chat_msgs": a["chat_msgs"],
                "reacoes": a["reacoes"],
                "visualizacoes_video": a.get("visualizacoes_video", 0),
                "retencao_ini": a.get("retencao_ini"),
                "retencao_fim": a.get("retencao_fim"),
                "impressoes": a.get("impressoes", 0),
                "ctr_thumb": a.get("ctr_thumb", 0.0),
                "periodo_ini": a.get("periodo_ini"),
                "periodo_fim": a.get("periodo_fim"),
                "views_periodo": a.get("views_periodo", 0),
                "watch_periodo_h": a.get("watch_periodo_h", 0.0),
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

            if a.get("retencao"):
                conn.execute(
                    text("DELETE FROM youtube_video_retencao WHERE launch_code = :c AND aula_num = :n"),
                    {"c": launch_code, "n": a["aula_num"]},
                )
                conn.execute(text("""
                    INSERT INTO youtube_video_retencao (
                        launch_code, aula_num, segmento, posicao_pct,
                        retencao_pct, vs_outros_pct
                    ) VALUES (
                        :launch_code, :aula_num, :segmento, :posicao_pct,
                        :retencao_pct, :vs_outros_pct
                    )
                """), [
                    {"launch_code": launch_code, "aula_num": a["aula_num"], "segmento": seg, **p}
                    for seg, pontos in a["retencao"].items() for p in pontos
                ])

            if a.get("atividade"):
                conn.execute(
                    text("DELETE FROM youtube_video_atividade WHERE launch_code = :c AND aula_num = :n"),
                    {"c": launch_code, "n": a["aula_num"]},
                )
                conn.execute(text("""
                    INSERT INTO youtube_video_atividade (
                        launch_code, aula_num, posicao_pct,
                        comecaram, pararam, vezes_assistido
                    ) VALUES (
                        :launch_code, :aula_num, :posicao_pct,
                        :comecaram, :pararam, :vezes_assistido
                    )
                """), [
                    {"launch_code": launch_code, "aula_num": a["aula_num"], **p}
                    for p in a["atividade"]
                ])

    logger.info(
        "Gravado: %d aulas, %d pontos de curva ao vivo, %d pontos de retenção, %d de atividade",
        len(aulas),
        sum(len(a["curva"]) for a in aulas),
        sum(len(p) for a in aulas for p in a.get("retencao", {}).values()),
        sum(len(a.get("atividade", [])) for a in aulas),
    )


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
