"""
ETL: transcreve os vídeos publicados no Meta → ad_transcricoes / ad_transcricao_linhas

Baixa o mp4 do criativo pela Marketing API (`video_id` → `source`) e transcreve
com faster-whisper na CPU. Complementa `etl_legendas.py`, que lê os `.txt`
transcritos à mão.

    python etl/etl_transcrever_meta.py --launch PES-SET-26
    python etl/etl_transcrever_meta.py --launch PES-SET-26 --so-faltantes
    python etl/etl_transcrever_meta.py --launch PES-SET-26 --ads AD119,AD105
    python etl/etl_transcrever_meta.py --launch PES-SET-26 --limite 5 --manter-video
    python etl/etl_transcrever_meta.py --launch PES-SET-26 --pasta "C:/dump_videos"

Por que isto vale mais que preencher a lacuna (achado de 17/09/26):
o vídeo do criativo **é** o anúncio publicado, então a minutagem que sai daqui é
a real. Os `.txt` da pasta `Legendas/` são, em 20 de 29 casos, transcrição da
filmagem crua — múltiplos blocos abrindo todos em `[00:00]`, takes descartados,
metade do roteiro faltando. Re-transcrever daqui promove esses 20 a
`hook_confiavel=True` e leva a análise de gancho de 8,3% para ~67% da verba.

Nunca apaga a transcrição manual: a nova entra como fonte adicional
(`fonte='meta_video:<id>'`) e só ela fica `is_canonica`. As anteriores do mesmo
`ad_code` são rebaixadas, não removidas.

Modo `--pasta` (dump manual): existe porque a API **não libera `source`** de vídeo
em criativo dinâmico — 22 anúncios do PES-SET-26, R$ 97k, incluindo o de maior
gasto (AD347). O conector do Drive também não indexa a subpasta `1- CAPTAÇÃO`
onde eles estão (só o que é compartilhado explicitamente entra no índice). Com os
arquivos numa pasta local, casa por `ADxxx` no nome — que é como o Drive nomeia —
e o que sobrar, por duração.

Pré-requisitos: META_ACCESS_TOKEN no .env · pip install faster-whisper
(não precisa de ffmpeg — o faster-whisper decodifica via PyAV)
"""
import argparse
import os
import re
import sys
import tempfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()
logger = get_logger("etl_transcrever_meta")

API_VERSION = "v22.0"


CORTE_GANCHO = 3.0   # segundos — fronteira do hook_rate do Meta


class FonteIndisponivel(RuntimeError):
    """A API tem o vídeo mas não libera a URL de download (`source`).

    Acontece com vídeo em `asset_feed_spec` (criativo dinâmico): a chamada
    devolve 200 com `title`/`length` e simplesmente omite `source`. É
    permissão, não ausência de vídeo — ver AD347 em 17/09/26."""


# ─────────────────────────────────────────────────────────────────────────────
# Meta: descobrir e baixar o vídeo
# ─────────────────────────────────────────────────────────────────────────────
def _casar_por_codigo(nomes: Mapping[str, object], alvos: list[tuple]) -> dict[str, object]:
    """Casa {nome_de_arquivo: handle} com os `ADxxx` de `alvos`.

    Regra do código: quando o nome traz mais de um `ADxxx`
    (`AD292 - AD269 - Carro dois personagens`), vale o **primeiro** — o
    segundo é o criativo de origem reaproveitado. Sem essa guarda, o AD269
    roubaria o arquivo do AD292 e a transcrição iria pro anúncio errado.

    Um arquivo por `ADxxx`, preferindo `(Feed)`: as variantes de formato têm
    o mesmo áudio, transcrever as três é desperdício."""
    def _prioridade(nome: str) -> tuple:
        b = nome.lower()
        return (0 if "feed" in b else 1 if "story" in b else 2, len(nome))

    achados: dict[str, object] = {}
    usados: set[str] = set()
    for ad_code, *_ in alvos:
        rx = re.compile(rf"\b{ad_code}\b", re.I)
        candidatos = [
            n for n in nomes
            if n not in usados and (m := rx.search(n))
            and not re.search(r"\bAD\d+\b", n[:m.start()], re.I)
        ]
        if candidatos:
            escolhido = min(candidatos, key=_prioridade)
            achados[ad_code] = nomes[escolhido]
            usados.add(escolhido)
    return achados


def _drive_service():
    """Service account do projeto (`drive.readonly`), a mesma das thumbnails."""
    import json as _json  # noqa: PLC0415
    from google.oauth2 import service_account  # noqa: PLC0415
    from googleapiclient.discovery import build  # noqa: PLC0415

    escopos = ["https://www.googleapis.com/auth/drive.readonly"]
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        creds = service_account.Credentials.from_service_account_info(
            _json.loads(sa_json), scopes=escopos)
    else:
        chave = (Path(__file__).parent.parent / "json"
                 / "uplifted-kit-499213-d8-6c09276f2753.json")
        creds = service_account.Credentials.from_service_account_file(
            str(chave), scopes=escopos)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def listar_videos_drive(service, folder_id: str, profundidade: int = 0) -> dict[str, str]:
    """{nome: file_id} de todo vídeo na pasta, descendo até 2 níveis.

    Só metadado — o download é sob demanda, um por vez, porque os masters
    do Drive têm 100–420 MB (o Meta serve ~10 MB do mesmo vídeo)."""
    achados: dict[str, str] = {}
    token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id,name,mimeType)",
            pageToken=token, pageSize=200,
        ).execute()
        for f in resp.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                if profundidade < 2:
                    achados.update(listar_videos_drive(service, f["id"], profundidade + 1))
            elif f["mimeType"].startswith("video/"):
                achados[f["name"]] = f["id"]
        token = resp.get("nextPageToken")
        if not token:
            return achados


def baixar_do_drive(service, file_id: str, destino: Path) -> Path | None:
    """Stream para disco. Nunca carrega o vídeo em memória/contexto."""
    from googleapiclient.http import MediaIoBaseDownload  # noqa: PLC0415

    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    try:
        pedido = service.files().get_media(fileId=file_id)
        with destino.open("wb") as fh:
            baixador = MediaIoBaseDownload(fh, pedido, chunksize=8 * 1024 * 1024)
            concluido = False
            while not concluido:
                _, concluido = baixador.next_chunk()
        return destino
    except Exception:
        logger.exception("Falha ao baixar %s do Drive", file_id)
        destino.unlink(missing_ok=True)
        return None


def casar_arquivos_locais(pasta: Path, alvos: list[tuple]) -> dict[str, Path]:
    """Casa mp4/mov de uma pasta local com os `ADxxx` a transcrever.

    Existe porque a API do Meta não libera `source` de vídeo em criativo
    dinâmico (22 anúncios do PES-SET-26, R$ 97k) e o conector do Drive não
    indexa a subpasta onde eles estão. Com um dump manual, isso resolve.

    Duas chaves, nesta ordem:
      1. `ADxxx` no nome do arquivo — é como o Drive nomeia
         (`AD347 - AD322 - 2P Mais um concurso ... .mp4`). Quando o código
         aparece mais de uma vez no nome, vale o PRIMEIRO: o segundo é o
         criativo de origem que foi reaproveitado, não este anúncio.
      2. duração em segundos (±1,5s), para arquivo sem código no nome — a
         API dá a duração mesmo quando nega o download.

    Só um arquivo por `ADxxx`: Feed/Story/Landscape do mesmo anúncio têm o
    mesmo áudio, então transcrever os três é desperdício. Prefere o Feed."""
    arquivos = [p for p in sorted(pasta.rglob("*"))
                if p.suffix.lower() in (".mp4", ".mov", ".m4v")]
    if not arquivos:
        logger.error("Nenhum mp4/mov em %s", pasta)
        return {}
    achados = {ad: p for ad, p in
               _casar_por_codigo({p.name: p for p in arquivos}, alvos).items()
               if isinstance(p, Path)}
    logger.info("Casados por codigo no nome: %d de %d", len(achados), len(alvos))
    return achados


def casar_por_duracao(restantes: dict[str, float], arquivos: list[Path],
                      tolerancia: float = 1.5) -> dict[str, Path]:
    """Fallback para arquivo sem `ADxxx` no nome: casa pela duração.

    Só aceita quando UM único arquivo cai na tolerância — duas durações
    parecidas viram ambiguidade, e chutar aqui grava a transcrição errada
    no anúncio errado, que é pior que não gravar."""
    from faster_whisper import decode_audio  # noqa: PLC0415

    duracoes: dict[Path, float] = {}
    for p in arquivos:
        try:
            duracoes[p] = len(decode_audio(str(p), sampling_rate=16000)) / 16000
        except Exception:
            logger.warning("Nao foi possivel medir a duracao de %s", p.name)

    achados: dict[str, Path] = {}
    for ad_code, esperada in restantes.items():
        perto = [p for p, d in duracoes.items() if abs(d - esperada) <= tolerancia]
        if len(perto) == 1:
            achados[ad_code] = perto[0]
        elif perto:
            logger.warning("%s (%.1fs): %d arquivos com duracao parecida (%s) - "
                           "ambiguo, deixando de fora", ad_code, esperada, len(perto),
                           ", ".join(p.name[:28] for p in perto))
    return achados


def video_id_do_criativo(creative: dict) -> str | None:
    if not creative:
        return None
    story = creative.get("object_story_spec") or {}
    vid = (story.get("video_data") or {}).get("video_id")
    if vid:
        return str(vid)
    for v in (creative.get("asset_feed_spec") or {}).get("videos") or []:
        if v.get("video_id"):
            return str(v["video_id"])
    return None


def baixar_video(video_id: str, destino: Path) -> tuple[Path, float] | None:
    """Baixa o mp4 do vídeo. Devolve (caminho, duracao_seg) ou None."""
    token = os.environ["META_ACCESS_TOKEN"]
    try:
        r = requests.get(
            f"https://graph.facebook.com/{API_VERSION}/{video_id}",
            params={"access_token": token, "fields": "id,title,length,source"},
            timeout=60,
        )
        meta = r.json()
    except Exception:
        logger.exception("Falha ao consultar video %s", video_id)
        return None
    if "error" in meta:
        logger.warning("Video %s: erro na API (%s)", video_id,
                       (meta.get("error") or {}).get("message"))
        raise FonteIndisponivel("erro na API")
    if not meta.get("source"):
        # HTTP 200, com title/length, mas sem 'source': restricao de permissao
        # (tipico de video em asset_feed_spec, criativo dinamico). Nao e falta
        # de video_id — distinguir importa, senao o relatorio mente.
        logger.warning("Video %s sem 'source' (permissao) - titulo: %s",
                       video_id, str(meta.get("title"))[:60])
        raise FonteIndisponivel("sem source (permissao)")

    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size > 0:
        return destino, float(meta.get("length") or 0)
    try:
        with requests.get(meta["source"], timeout=300, stream=True) as resp:
            resp.raise_for_status()
            with destino.open("wb") as f:
                for pedaco in resp.iter_content(1 << 16):
                    f.write(pedaco)
    except Exception:
        logger.exception("Falha ao baixar video %s", video_id)
        destino.unlink(missing_ok=True)
        return None
    return destino, float(meta.get("length") or 0)


# ─────────────────────────────────────────────────────────────────────────────
# Transcrição
# ─────────────────────────────────────────────────────────────────────────────
def _linhas_do_segmento(seg) -> list[dict]:
    """Segmento do Whisper → uma ou duas linhas.

    Os segmentos saem com ~5s, mas o gancho é medido em 3s: um segmento que
    atravessa a fronteira misturaria o que está dentro e fora do gancho numa
    linha só. Quando isso acontece, parte em 3,0s usando o timestamp por
    palavra. Fora desse caso, o segmento vira uma linha."""
    palavras = list(getattr(seg, "words", None) or [])
    texto = (seg.text or "").strip()
    if not texto:
        return []
    if not palavras or not (seg.start < CORTE_GANCHO < seg.end):
        return [{"t_ini": float(seg.start), "texto": texto}]

    antes = [w for w in palavras if w.start < CORTE_GANCHO]
    depois = [w for w in palavras if w.start >= CORTE_GANCHO]
    if not antes or not depois:
        return [{"t_ini": float(seg.start), "texto": texto}]
    return [
        {"t_ini": float(antes[0].start), "texto": "".join(w.word for w in antes).strip()},
        {"t_ini": float(depois[0].start), "texto": "".join(w.word for w in depois).strip()},
    ]


def transcrever(modelo, mp4: Path) -> tuple[list[dict], float]:
    segs, info = modelo.transcribe(
        str(mp4), language="pt", vad_filter=True,
        condition_on_previous_text=False, word_timestamps=True,
    )
    linhas: list[dict] = []
    for seg in segs:
        linhas.extend(_linhas_do_segmento(seg))
    for i, ln in enumerate(linhas):
        ln["ordem"] = i
        ln["t_ini_seg"] = int(ln["t_ini"])
        ln["n_palavras"] = len(ln["texto"].split())
    duracao = float(getattr(info, "duration", 0) or 0)
    for i, ln in enumerate(linhas):
        prox = linhas[i + 1]["t_ini_seg"] if i + 1 < len(linhas) else None
        ln["t_fim_seg"] = prox if prox is not None else (int(duracao) or None)
        ln["quartil"] = (min(4, int(ln["t_ini"] / duracao * 4) + 1) if duracao > 0 else 1)
        ln["falante"] = None   # Whisper não faz diarização
    return linhas, duracao


# ─────────────────────────────────────────────────────────────────────────────
# Persistência
# ─────────────────────────────────────────────────────────────────────────────
def gravar_com_retry(bloco: dict, linhas: list[dict], tentativas: int = 3) -> None:
    """DNS/pooler do Supabase cai sozinho de vez em quando: a rodada de
    17/09/26 morreu no anuncio 35 de 61 com 'could not translate host name'.
    O trabalho caro (download + transcricao) ja foi feito nesse ponto — nao
    pode ser perdido por um blip de rede."""
    import time  # noqa: PLC0415
    for n in range(1, tentativas + 1):
        try:
            gravar(bloco, linhas)
            return
        except Exception:
            if n == tentativas:
                raise
            espera = 5 * n
            logger.warning("Falha ao gravar %s (tentativa %d/%d); nova tentativa em %ds",
                           bloco["ad_code"], n, tentativas, espera)
            time.sleep(espera)


def gravar(bloco: dict, linhas: list[dict]) -> None:
    import etl_legendas as L  # noqa: PLC0415 — reusa hash e classificação

    agora = datetime.now(timezone.utc)
    sql_t = text("""
        INSERT INTO ad_transcricoes (lancamento_codigo, ad_code, ad_name, fonte, fonte_ordem,
                                     fonte_tipo, is_canonica, hook_confiavel, duracao_seg,
                                     n_linhas, n_palavras, texto_completo, roteiro_hash,
                                     arquivo_origem, updated_at)
        VALUES (:lancamento_codigo, :ad_code, :ad_name, :fonte, :fonte_ordem,
                :fonte_tipo, TRUE, TRUE, :duracao_seg,
                :n_linhas, :n_palavras, :texto_completo, :roteiro_hash,
                :arquivo_origem, :updated_at)
        ON CONFLICT (lancamento_codigo, ad_code, fonte) DO UPDATE SET
            ad_name = EXCLUDED.ad_name, fonte_tipo = EXCLUDED.fonte_tipo,
            is_canonica = TRUE, hook_confiavel = TRUE,
            duracao_seg = EXCLUDED.duracao_seg, n_linhas = EXCLUDED.n_linhas,
            n_palavras = EXCLUDED.n_palavras, texto_completo = EXCLUDED.texto_completo,
            roteiro_hash = EXCLUDED.roteiro_hash, arquivo_origem = EXCLUDED.arquivo_origem,
            updated_at = EXCLUDED.updated_at
        RETURNING id
    """)
    with get_engine().begin() as conn:
        tid = conn.execute(sql_t, {**bloco, "updated_at": agora}).scalar_one()

        # A transcricao manual NAO e apagada — so deixa de ser a canonica.
        conn.execute(text("""
            UPDATE ad_transcricoes SET is_canonica = FALSE, updated_at = :u
            WHERE lancamento_codigo = :l AND ad_code = :a AND id <> :id AND is_canonica
        """), {"u": agora, "l": bloco["lancamento_codigo"], "a": bloco["ad_code"], "id": tid})

        conn.execute(text("DELETE FROM ad_transcricao_linhas"
                          " WHERE transcricao_id = :id AND ordem >= :n"),
                     {"id": tid, "n": len(linhas)})
        for ln in linhas:
            conn.execute(text("""
                INSERT INTO ad_transcricao_linhas (transcricao_id, ordem, t_ini_seg, t_fim_seg,
                                                   quartil, falante, texto, n_palavras)
                VALUES (:id, :ordem, :t_ini_seg, :t_fim_seg, :quartil, :falante, :texto, :n_palavras)
                ON CONFLICT (transcricao_id, ordem) DO UPDATE SET
                    t_ini_seg = EXCLUDED.t_ini_seg, t_fim_seg = EXCLUDED.t_fim_seg,
                    quartil = EXCLUDED.quartil, falante = EXCLUDED.falante,
                    texto = EXCLUDED.texto, n_palavras = EXCLUDED.n_palavras
            """), {"id": tid, **{k: ln[k] for k in
                                 ("ordem", "t_ini_seg", "t_fim_seg", "quartil",
                                  "falante", "texto", "n_palavras")}})

        # Reclassifica com o texto novo. origem='whisper' deixa rastreavel o que
        # saiu de maquina; a curadoria humana continua intocada.
        atributos = L.classificar({**bloco, "linhas": linhas})
        mantidos = [a["valor"] for a in atributos] or [""]
        conn.execute(text("DELETE FROM ad_copy_atributos"
                          " WHERE lancamento_codigo = :l AND ad_code = :a"
                          "   AND origem IN ('auto', 'whisper') AND valor <> ALL(:m)"),
                     {"l": bloco["lancamento_codigo"], "a": bloco["ad_code"], "m": mantidos})
        for a in atributos:
            conn.execute(text("""
                INSERT INTO ad_copy_atributos (lancamento_codigo, ad_code, dimensao, valor,
                                               origem, confianca, updated_at)
                VALUES (:l, :a, :d, :v, 'whisper', NULL, :u)
                ON CONFLICT (lancamento_codigo, ad_code, dimensao, valor) DO UPDATE SET
                    updated_at = EXCLUDED.updated_at
                WHERE ad_copy_atributos.origem <> 'humano'
            """), {"l": bloco["lancamento_codigo"], "a": bloco["ad_code"],
                   "d": a["dimensao"], "v": a["valor"], "u": agora})


# ─────────────────────────────────────────────────────────────────────────────
def alvos(launch: str, so_faltantes: bool, ads: list[str] | None) -> list[tuple]:
    """ADxxx de vídeo do Meta a transcrever, do maior gasto pro menor."""
    filtro = ""
    if so_faltantes:
        filtro = (" AND ad_code NOT IN (SELECT ad_code FROM ad_transcricoes"
                  "   WHERE lancamento_codigo = :l AND hook_confiavel)")
    if ads:
        filtro += " AND ad_code = ANY(:ads)"
    sql = rf"""
        WITH m AS (
            SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) AS ad_code,
                   max(ad_id) AS ad_id, max(ad_name) AS ad_name, sum(spend) AS gasto
            FROM   meta_ads_daily
            WHERE  lancamento_codigo = :l
              AND  upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) ~ '^AD[0-9]+$'
            GROUP  BY 1 HAVING sum(spend) > 0
        )
        SELECT ad_code, ad_id, ad_name, gasto FROM m
        WHERE  ad_code IN (SELECT ad_code FROM ad_copy_textos
                           WHERE lancamento_codigo = :l AND formato = 'video')
        {filtro}
        ORDER BY gasto DESC
    """
    params: dict = {"l": launch}
    if ads:
        params["ads"] = ads
    with get_engine().connect() as conn:
        return conn.execute(text(sql), params).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcreve os videos publicados no Meta")
    ap.add_argument("--launch", required=True)
    ap.add_argument("--so-faltantes", action="store_true",
                    help="pula quem ja tem transcricao com hook_confiavel")
    ap.add_argument("--ads", help="lista de ADxxx separada por virgula")
    ap.add_argument("--limite", type=int, help="processa so os N de maior gasto")
    ap.add_argument("--modelo", default="small", help="small (padrao) | medium | large-v3")
    ap.add_argument("--manter-video", action="store_true",
                    help="nao apaga os mp4 baixados (uns 10 MB cada)")
    ap.add_argument("--pasta", help="pasta local com os mp4, usada em vez de baixar da "
                                    "API; casa por ADxxx no nome e, no que sobrar, por duracao")
    ap.add_argument("--drive-folder", help="id ou URL de pasta do Drive; baixa de la (via "
                                          "service account) o que a API do Meta nao libera")
    ap.add_argument("--dry-run", action="store_true", help="lista os alvos e sai")
    args = ap.parse_args()

    import etl_meta_ads as meta_ads  # noqa: PLC0415

    lista = alvos(args.launch, args.so_faltantes,
                  [a.strip().upper() for a in args.ads.split(",")] if args.ads else None)
    if args.limite:
        lista = lista[:args.limite]
    if not lista:
        logger.error("Nenhum video do Meta a transcrever em %s", args.launch)
        return 1

    total_gasto = sum(float(r[3] or 0) for r in lista)
    print(f"\n{len(lista)} videos a transcrever | R$ {total_gasto:,.0f} de verba")
    if args.dry_run:
        for ad_code, _, _, gasto in lista:
            print(f"  {ad_code:8}{float(gasto):>12,.0f}")
        return 0

    detalhes = meta_ads.fetch_creative_details([str(r[1]) for r in lista])

    # Modo pasta local: casa por ADxxx no nome e, no que sobrar, por duracao
    # (a API da a duracao mesmo dos videos cujo download ela nega).
    # Modo Drive: os masters do Drive são a saída para os vídeos cujo download a
    # API do Meta nega (criativo dinâmico). Só metadado agora; o arquivo vem um
    # por vez dentro do laço, porque cada um tem 100–420 MB.
    drive_svc = None
    drive_por_ad: dict[str, str] = {}
    if args.drive_folder:
        m = re.search(r"/folders/([a-zA-Z0-9_-]+)", args.drive_folder)
        folder_id = m.group(1) if m else args.drive_folder.strip()
        drive_svc = _drive_service()
        try:
            videos = listar_videos_drive(drive_svc, folder_id)
        except Exception:
            logger.exception("Falha ao listar a pasta %s do Drive", folder_id)
            return 1
        drive_por_ad = {ad: fid for ad, fid in
                        _casar_por_codigo(videos, lista).items() if isinstance(fid, str)}
        print(f"Drive: {len(videos)} videos na pasta, {len(drive_por_ad)} casados por ADxxx")
        nao = [r[0] for r in lista if r[0] not in drive_por_ad]
        if nao:
            print("Sem arquivo no Drive: " + ", ".join(nao))

    locais: dict[str, Path] = {}
    if args.pasta:
        pasta = Path(args.pasta)
        if not pasta.is_dir():
            logger.error("Pasta nao encontrada: %s", pasta)
            return 1
        locais = casar_arquivos_locais(pasta, lista)
        faltando = {}
        for ad_code, ad_id, _n, _g in lista:
            if ad_code in locais:
                continue
            vid = video_id_do_criativo((detalhes.get(str(ad_id)) or {}).get("creative") or {})
            if not vid:
                continue
            try:
                d = requests.get(f"https://graph.facebook.com/{API_VERSION}/{vid}",
                                 params={"access_token": os.environ["META_ACCESS_TOKEN"],
                                         "fields": "length"}, timeout=60).json()
            except Exception:
                continue
            if d.get("length"):
                faltando[ad_code] = float(d["length"])
        if faltando:
            sobrando = [p for p in sorted(pasta.rglob("*"))
                        if p.suffix.lower() in (".mp4", ".mov", ".m4v")
                        and p not in set(locais.values())]
            por_dur = casar_por_duracao(faltando, sobrando)
            logger.info("Casados por duracao: %d de %d restantes", len(por_dur), len(faltando))
            locais.update(por_dur)
        print(f"Casados na pasta: {len(locais)} de {len(lista)}")
        nao_casados = [r[0] for r in lista if r[0] not in locais]
        if nao_casados:
            print("Sem arquivo correspondente: " + ", ".join(nao_casados))

    from faster_whisper import WhisperModel  # noqa: PLC0415
    logger.info("Carregando modelo %s (CPU/int8)", args.modelo)
    modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8")

    import hashlib  # noqa: PLC0415
    import etl_legendas as L  # noqa: PLC0415

    cache = Path(tempfile.gettempdir()) / "brabo_videos_meta"
    # Tres motivos distintos de nao transcrever, contados separado: juntar
    # "sem video_id" com "API nao libera o download" me fez diagnosticar
    # errado o AD347 em 17/09/26 (tinha video_id; faltava permissao).
    ok, sem_video_id, sem_source, sem_fala, falhou = [], [], [], [], []
    gasto_por_ad = {r[0]: float(r[3] or 0) for r in lista}

    for i, (ad_code, ad_id, ad_name, _gasto) in enumerate(lista, 1):
        # Um anuncio nunca derruba o lote: depois de 40 min de CPU, perder o
        # resto por causa de um blip de rede num item e inaceitavel.
        try:
            creative = (detalhes.get(str(ad_id)) or {}).get("creative") or {}
            vid = video_id_do_criativo(creative)

            local = locais.get(ad_code)
            drive_id = drive_por_ad.get(ad_code)
            if local is not None:
                # Arquivo da pasta: nunca apagar, é material do usuário.
                mp4, apagar_depois = local, False
                fonte = f"arquivo_local:{local.name}"
            elif drive_id:
                baixado = baixar_do_drive(drive_svc, drive_id,
                                          cache / f"{ad_code}_drive.mp4")
                if not baixado:
                    falhou.append(ad_code)
                    continue
                # Master do Drive tem 100–420 MB: apagar sempre, senão 22
                # vídeos enchem ~2 GB de disco sem ninguém pedir.
                mp4, apagar_depois = baixado, not args.manter_video
                fonte = f"drive:{drive_id}"
            else:
                if not vid:
                    sem_video_id.append(ad_code)
                    continue
                try:
                    baixado = baixar_video(vid, cache / f"{ad_code}_{vid}.mp4")
                except FonteIndisponivel:
                    sem_source.append(ad_code)
                    continue
                if not baixado:
                    falhou.append(ad_code)
                    continue
                mp4, apagar_depois = baixado[0], not args.manter_video
                fonte = f"meta_video:{vid}"

            try:
                linhas, duracao = transcrever(modelo, mp4)
            finally:
                if apagar_depois:
                    mp4.unlink(missing_ok=True)

            if not linhas:
                sem_fala.append(ad_code)
                continue

            texto = "\n".join(ln["texto"] for ln in linhas)
            bloco = {
                "lancamento_codigo": args.launch, "ad_code": ad_code, "ad_name": ad_name,
                "fonte": fonte, "fonte_ordem": 0, "fonte_tipo": "corte_final",
                "is_canonica": True, "hook_confiavel": True,
                "duracao_seg": int(duracao), "n_linhas": len(linhas),
                "n_palavras": sum(ln["n_palavras"] for ln in linhas),
                "texto_completo": texto,
                "roteiro_hash": hashlib.sha1(L._normalizar(texto).encode("utf-8")).hexdigest(),
                "arquivo_origem": (str(mp4) if local is not None
                                   else f"meta_api:video/{vid}"),
            }
            gravar_com_retry(bloco, linhas)
            ok.append(ad_code)
            gancho = " ".join(ln["texto"] for ln in linhas if ln["t_ini"] < CORTE_GANCHO)
            print(f"  [{i}/{len(lista)}] {ad_code} {int(duracao):>4}s "
                  f"{len(linhas):>3} linhas | gancho: {gancho[:64]}", flush=True)
        except Exception:
            logger.exception("Falha em %s; seguindo para o proximo", ad_code)
            falhou.append(ad_code)

    def _verba(ads: list[str]) -> str:
        return f"R$ {sum(gasto_por_ad.get(a, 0) for a in ads):,.0f}"

    print(f"\n{'=' * 70}\nTRANSCRICAO - {args.launch}\n{'=' * 70}")
    for rotulo, ads in (("transcritos", ok), ("sem video_id", sem_video_id),
                        ("API nao libera download", sem_source),
                        ("sem fala detectada", sem_fala), ("falhou", falhou)):
        if ads:
            print(f"  {rotulo:26}{len(ads):>4}  {_verba(ads):>14}")
    if sem_source:
        print(f"\n[!] Sem 'source' na API (video existe, download bloqueado): "
              + ", ".join(sem_source))
    if falhou:
        print("[X] Falhou, ver log: " + ", ".join(falhou))
    # Sai != 0 quando nada foi transcrito: um lote inteiro que falha nao pode
    # terminar parecendo sucesso (licao do cron do PES-SET-26).
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
