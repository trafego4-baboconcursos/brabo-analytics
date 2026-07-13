#!/usr/bin/env python3
"""
Atualiza a descrição de todos os vídeos do canal UCc4HH365cSFhzCzIPFRg2ag.
Uso:
  python atualizar_bb.py --dry-run   # lista vídeos sem alterar
  python atualizar_bb.py             # aplica a nova descrição
"""

import argparse
import csv
import os
import time
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Configurações ────────────────────────────────────────────────────────────

CHANNEL_ID = "UCc4HH365cSFhzCzIPFRg2ag"

NOVA_DESCRICAO = """*Felipe Graton* — Estratégias para Concursos Públicos

Participe do Projeto Banco do Brasil: https://lp.braboconcursos.com.br/projeto-bb-jun-26-v2

✅ Inscreva-se no canal
🔔 Ative o sininho para receber novos conteúdos
💬 Deixe seu comentário!

Aprovado no MPSP e no TJSP (duas vezes com mais de 90% de acerto), compartilho técnicas de estudo, motivação e cuidados com a saúde física e mental para quem está na jornada de aprovação.

Fale com meu time 👉 https://wa.me/5516991166666
"""

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), "client_secrets.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token_bb.json")
LOG_FILE = os.path.join(os.path.dirname(__file__), "log_bb.csv")
DELAY_ENTRE_REQUESTS = 0.5  # segundos

# ── Autenticação ─────────────────────────────────────────────────────────────

def autenticar():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ── Busca de vídeos ───────────────────────────────────────────────────────────

def buscar_todos_videos(youtube):
    videos = []
    page_token = None
    print("Buscando vídeos do canal...")
    while True:
        params = {
            "part": "id,snippet",
            "channelId": CHANNEL_ID,
            "type": "video",
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = youtube.search().list(**params).execute()
        for item in resp.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "titulo": item["snippet"]["title"],
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(DELAY_ENTRE_REQUESTS)

    print(f"Total de vídeos encontrados: {len(videos)}\n")
    return videos

# ── Atualização de descrição ──────────────────────────────────────────────────

def atualizar_video(youtube, video_id, titulo, dry_run):
    # Busca dados completos do vídeo para preservar título, tags e categoria
    detalhe = youtube.videos().list(
        part="snippet",
        id=video_id,
    ).execute()

    items = detalhe.get("items", [])
    if not items:
        return "VIDEO_NOT_FOUND"

    snippet = items[0]["snippet"]
    snippet["description"] = NOVA_DESCRICAO

    if dry_run:
        return "DRY_RUN"

    youtube.videos().update(
        part="snippet",
        body={"id": video_id, "snippet": snippet},
    ).execute()
    return "OK"

# ── Log CSV ───────────────────────────────────────────────────────────────────

def iniciar_log():
    escrever_cabecalho = not os.path.exists(LOG_FILE)
    f = open(LOG_FILE, "a", newline="", encoding="utf-8")
    writer = csv.writer(f)
    if escrever_cabecalho:
        writer.writerow(["video_id", "titulo", "status", "timestamp"])
    return f, writer

# ── Main ──────────────────────────────────────────────────────────────────────

def carregar_ja_atualizados():
    atualizados = set()
    if not os.path.exists(LOG_FILE):
        return atualizados
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "OK":
                atualizados.add(row["video_id"])
    return atualizados


def main():
    import sys
    if sys.stdout and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Atualiza descrição dos vídeos do canal BB.")
    parser.add_argument("--dry-run", action="store_true", help="Lista vídeos sem alterar nada.")
    parser.add_argument("--pular-atualizados", action="store_true", help="Pula vídeos já com status OK no log.")
    args = parser.parse_args()

    youtube = autenticar()
    videos = buscar_todos_videos(youtube)

    if args.pular_atualizados:
        ja_feitos = carregar_ja_atualizados()
        antes = len(videos)
        videos = [v for v in videos if v["video_id"] not in ja_feitos]
        print(f"Pulando {antes - len(videos)} já atualizados. Restam {len(videos)} vídeos.\n")

    total = len(videos)

    log_f, log_writer = iniciar_log()

    for i, video in enumerate(videos, 1):
        vid = video["video_id"]
        titulo = video["titulo"]
        label = "[DRY-RUN]" if args.dry_run else "Atualizando"
        print(f"[{i}/{total}] {label}: {titulo[:70]}...")

        try:
            status = atualizar_video(youtube, vid, titulo, args.dry_run)
        except HttpError as e:
            status = f"ERRO_HTTP_{e.resp.status}"
            print(f"  ⚠ Erro HTTP {e.resp.status} no vídeo {vid}: {e}")
        except Exception as e:
            status = "ERRO"
            print(f"  ⚠ Erro inesperado no vídeo {vid}: {e}")

        log_writer.writerow([vid, titulo, status, datetime.now(timezone.utc).isoformat()])
        log_f.flush()

        time.sleep(DELAY_ENTRE_REQUESTS)

    log_f.close()
    acao = "listados (dry-run)" if args.dry_run else "atualizados"
    print(f"\n✅ Concluído! {total} vídeos {acao}. Log salvo em: {LOG_FILE}")


if __name__ == "__main__":
    main()
