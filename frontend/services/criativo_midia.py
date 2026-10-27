"""
frontend/services/criativo_midia.py — mídia de UM criativo (imagem, carrossel ou vídeo) para o modal de preview.

O modal usado em todas as páginas com criativos (`openVideoModalFromEl`, static/js/modal-video.js) pedia só uma URL de iframe:
imagem do próprio site caía no `X-Frame-Options: DENY` ("conexão recusada"), carrossel mostrava uma capa só e o título era o
código curto. Aqui montamos o que existe de cada anúncio, na ordem de qualidade:

  1. Drive do lançamento (`launch_config.drive_folder_url`): pasta `ADxxx - ...` = carrossel (capa + "Card N"); arquivo
     `ADxxx - ....mp4` (vários: Feed/Story) = vídeo, tocado pelo player do Drive; imagem solta = imagem.
  2. Meta (`ad_creatives`): bytes da imagem/miniatura gravados no banco (a URL do CDN expira).
  3. YouTube (`google_ads_daily.video_id`): vídeo do anúncio do Google, embutido.

Se o anúncio não existe no lançamento da página (ex.: "validado" de um lançamento anterior), procura nos lançamentos mais recentes.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.db_readers.launches import read_launch_config

logger = get_logger("db")

_TTL_INDICE = 3600      # a pasta do Drive muda pouco durante o lançamento
_TTL_MANIFESTO = 600
_MAX_PROFUNDIDADE = 5   # ex.: Criativos > Captação > CARROSSÉIS > PÓS-EDITAL > "ADxxx - Cards" > arquivos
_MAX_LANCAMENTOS_FALLBACK = 5

_VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
_AD_RE = re.compile(r"\bAD[A-Z]{0,3}-?[A-Z]{0,3}\d+\b", re.IGNORECASE)
_CARD_RE = re.compile(r"\bcard\s*(\d+)", re.IGNORECASE)
_NUM_FINAL_RE = re.compile(r"(\d+)\s*$")
_FORMATO_RE = re.compile(r"\b(\d{3,4})\s*[xX]\s*(\d{3,4})\b")

_indice_cache: dict[str, tuple[float, dict]] = {}
_manifesto_cache: dict[str, tuple[float, dict | None]] = {}
# ids de arquivo que o índice já viu: /api/drive-image só serve estes (não vira um proxy de qualquer arquivo da conta de serviço)
ARQUIVOS_PERMITIDOS: set[str] = set()


def _drive_service():
    from google.oauth2 import service_account  # noqa: PLC0415
    from googleapiclient.discovery import build  # noqa: PLC0415

    escopos = ["https://www.googleapis.com/auth/drive.readonly"]
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json), scopes=escopos)
    else:
        chave = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "json",
                                              "uplifted-kit-499213-d8-6c09276f2753.json"))
        creds = service_account.Credentials.from_service_account_file(chave, scopes=escopos)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _listar(servico, pasta_id: str) -> list[dict]:
    itens, token = [], None
    while True:
        r = servico.files().list(
            q=f"'{pasta_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=token, pageSize=200,
        ).execute()
        itens.extend(r.get("files", []))
        token = r.get("nextPageToken")
        if not token:
            return itens


def _e_pasta(f: dict) -> bool:
    return f["mimeType"] == "application/vnd.google-apps.folder"


def _tipo_arquivo(f: dict) -> str | None:
    if f["mimeType"].startswith("image/"):
        return "image"
    if f["mimeType"].startswith("video/") or f["name"].lower().endswith(_VIDEO_EXT):
        return "drive_video"
    return None


def _ordem(nome: str) -> int:
    """Posição do quadro: "Card N" pelo número; o arquivo com o código do anúncio e sem "Card" (a capa) vem primeiro."""
    base = re.sub(r"\.\w+$", "", nome)
    m = _CARD_RE.search(base)
    if m:
        return int(m.group(1))
    if _AD_RE.search(base):
        return 0
    m = _NUM_FINAL_RE.search(base)
    return int(m.group(1)) if m else 999


def _codigo(nome: str) -> str | None:
    m = _AD_RE.search(nome or "")
    return m.group(0).upper() if m else None


def _indexar_drive(launch_code: str) -> dict[str, dict]:
    """{ad_code: {"nome": str, "imagens": [item], "videos": [item]}} varrendo a pasta do lançamento (cache 1h)."""
    agora = time.time()
    c = _indice_cache.get(launch_code)
    if c and agora - c[0] < _TTL_INDICE:
        return c[1]

    url = (read_launch_config(launch_code) or {}).get("drive_folder_url") or ""
    m = re.search(r"/folders/([\w-]+)", url)
    ads: dict[str, dict] = {}
    if m:
        servico = _drive_service()

        def entrada(ad: str, nome_ad: str) -> dict:
            return ads.setdefault(ad, {"nome": nome_ad, "imagens": [], "videos": []})

        def adicionar(ad: str, f: dict, nome_ad: str) -> None:
            tipo = _tipo_arquivo(f)
            if not tipo:
                return
            ARQUIVOS_PERMITIDOS.add(f["id"])
            e = entrada(ad, nome_ad)
            lista = e["imagens" if tipo == "image" else "videos"]
            if any(x["nome"] == f["name"] for x in lista):   # a mesma arte em duas pastas (cópia) não vira dois quadros
                return
            lista.append({"kind": tipo, "id": f["id"], "nome": f["name"]})

        def varrer(pasta_id: str, nivel: int) -> None:
            for f in _listar(servico, pasta_id):
                if _e_pasta(f):
                    ad = _codigo(f["name"])
                    if ad:  # pasta do anúncio (carrossel): tudo dentro é dele, mesmo sem o código no nome ("Card 2")
                        for g in _listar(servico, f["id"]):
                            if not _e_pasta(g):
                                adicionar(ad, g, f["name"].strip())
                    elif nivel < _MAX_PROFUNDIDADE:
                        varrer(f["id"], nivel + 1)
                else:
                    ad = _codigo(f["name"])
                    if ad:
                        adicionar(ad, f, re.sub(r"\.\w+$", "", f["name"]).strip())

        try:
            varrer(m.group(1), 1)
        except Exception:
            logger.exception("criativo_midia: falha ao varrer o Drive de %s", launch_code)
            if c:           # devolve o índice antigo em vez de esconder a mídia por um erro passageiro
                return c[1]
        for e in ads.values():
            e["imagens"].sort(key=lambda i: (_ordem(i["nome"]), i["nome"]))
            e["videos"].sort(key=lambda i: i["nome"])
    _indice_cache[launch_code] = (agora, ads)
    return ads


def _meta(launch_code: str, ad_code: str) -> dict | None:
    with _get_engine().connect() as conn:
        r = conn.execute(
            text("""SELECT ad_name, (image_data IS NOT NULL) AS tem_img, (thumb_data IS NOT NULL) AS tem_thumb, image_url, thumbnail_url
                    FROM ad_creatives WHERE platform = 'meta' AND lancamento_codigo = :c AND ad_code = :a
                    ORDER BY updated_at DESC LIMIT 1"""),
            {"c": launch_code, "a": ad_code},
        ).fetchone()
    if not r:
        return None
    nome, tem_img, tem_thumb, image_url, thumb_url = r
    if tem_img:
        src = f"/api/meta-creative/{launch_code}/{ad_code}/image"
    elif tem_thumb:
        src = f"/api/meta-creative/{launch_code}/{ad_code}/thumb"
    elif image_url or thumb_url:
        src = image_url or thumb_url
    else:
        return None
    return {"nome": nome, "item": {"kind": "image", "src": src, "nome": "Imagem do anúncio (Meta)"}}


def _youtube(launch_code: str, ad_code: str) -> dict | None:
    with _get_engine().connect() as conn:
        r = conn.execute(
            text("""SELECT ad_name, video_id FROM google_ads_daily
                    WHERE lancamento_codigo = :c AND ad_name ILIKE :p AND video_id IS NOT NULL AND video_id <> ''
                    ORDER BY date DESC LIMIT 1"""),
            {"c": launch_code, "p": f"{ad_code}%"},
        ).fetchone()
    if not r:
        return None
    return {"nome": r[0], "item": {"kind": "youtube", "src": f"https://www.youtube.com/embed/{r[1]}", "nome": "Vídeo (YouTube)"}}


def _montar(launch_code: str, ad_code: str) -> dict | None:
    """Mídia do anúncio num lançamento só; None se não há nada."""
    itens: list[dict] = []
    nome = None
    fonte = []

    drive = _indexar_drive(launch_code).get(ad_code)
    if drive:
        nome = drive["nome"]
        for v in drive["videos"]:
            itens.append({"kind": "drive_video", "src": f"https://drive.google.com/file/d/{v['id']}/preview", "nome": v["nome"]})
        for i in drive["imagens"]:
            itens.append({"kind": "image", "src": f"/api/drive-image/{i['id']}", "nome": i["nome"]})
        if itens:
            fonte.append("drive")

    yt = _youtube(launch_code, ad_code)
    if yt and not any(i["kind"] == "drive_video" for i in itens):
        itens.insert(0, yt["item"])
        nome = nome or yt["nome"]
        fonte.append("youtube")

    meta = _meta(launch_code, ad_code)
    if meta:
        nome = meta["nome"] or nome      # o nome oficial do anúncio é o da plataforma
        if not any(i["kind"] == "image" for i in itens):
            itens.append(meta["item"])
            fonte.append("meta")

    if not itens:
        return None
    imagens = [i for i in itens if i["kind"] == "image"]
    tem_video = any(i["kind"] != "image" for i in itens)
    formatos = len(imagens) > 1 and all(_FORMATO_RE.search(i["nome"]) for i in imagens)
    if formatos:   # a mesma arte em 1080x1080, 1080x1350... não é carrossel: vira variantes, com o feed (4:5) primeiro
        for i in imagens:
            i["rotulo"] = "x".join(_FORMATO_RE.search(i["nome"]).groups())
        imagens.sort(key=lambda i: (i["rotulo"] != "1080x1350", i["rotulo"] != "1080x1080", i["rotulo"]))
        itens = [i for i in itens if i["kind"] != "image"] + imagens
    tipo = "video" if tem_video else ("imagem" if formatos or len(imagens) <= 1 else "carrossel")
    return {"ad_code": ad_code, "launch_origem": launch_code, "nome": nome, "tipo": tipo, "fonte": fonte, "itens": itens}


def resolver(launch_code: str, ad_code: str) -> dict | None:
    """Manifesto de mídia do anúncio (cache 10 min). `launch_code` é o da página; se nada for achado nele,
    tenta os lançamentos mais recentes onde o mesmo código apareceu (anúncio validado de lançamento anterior)."""
    ad_code = (ad_code or "").strip().upper()
    launch_code = (launch_code or "").strip().upper()
    chave = f"{launch_code}::{ad_code}"
    c = _manifesto_cache.get(chave)
    if c and time.time() - c[0] < _TTL_MANIFESTO:
        return c[1]

    res = _montar(launch_code, ad_code) if launch_code else None
    if res is None:
        with _get_engine().connect() as conn:
            outros = [r[0] for r in conn.execute(
                text("""SELECT lancamento_codigo FROM ad_creatives WHERE ad_code = :a AND lancamento_codigo <> :ex
                        GROUP BY 1 ORDER BY MAX(updated_at) DESC LIMIT :n"""),
                {"a": ad_code, "ex": launch_code, "n": _MAX_LANCAMENTOS_FALLBACK},
            ).fetchall()]
        for cod in outros:
            res = _montar(cod, ad_code)
            if res:
                break
    _manifesto_cache[chave] = (time.time(), res)
    return res


def url_imagem_drive(file_id: str, largura: int = 1400) -> str | None:
    """URL da imagem do Drive em tamanho de visualização (thumbnailLink redimensionado)."""
    meta = _drive_service().files().get(fileId=file_id, fields="thumbnailLink").execute()
    link = meta.get("thumbnailLink") or ""
    return re.sub(r"=s\d+$", f"=s{int(largura)}", link) if link else None
