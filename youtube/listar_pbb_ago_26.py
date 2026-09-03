#!/usr/bin/env python3
"""
Lista todos os vídeos/shorts do canal (públicos, não-listados e privados)
cujo título contém um termo de busca (default: PBB-AGO-26).

Uso:
  python listar_pbb_ago_26.py
  python listar_pbb_ago_26.py --termo "PBB-AGO-26"

Na primeira execução vai abrir o navegador pra login — entre com a conta
Google que é dona ou gerente do canal "Felipe Graton - Brabo Concursos".
Salva um token separado (token_owner.json) pra não mexer no token_bb.json
que o atualizar_bb.py já usa.
"""

import argparse
import os
import sys
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), "client_secrets.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token_owner.json")


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


def main():
    if sys.stdout and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--termo", default="PBB-AGO-26")
    args = parser.parse_args()

    youtube = autenticar()

    ch = youtube.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
    print(f"Autenticado como canal: {ch['snippet']['title']} ({ch['id']})\n")
    uploads_playlist = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    page_token = None
    while True:
        params = {"part": "snippet", "playlistId": uploads_playlist, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        resp = youtube.playlistItems().list(**params).execute()
        for item in resp.get("items", []):
            sn = item["snippet"]
            videos.append({"video_id": sn["resourceId"]["videoId"], "titulo": sn["title"]})
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.15)

    print(f"Total de vídeos no canal: {len(videos)}")

    matches = [v for v in videos if args.termo.lower() in v["titulo"].lower()]
    print(f"Vídeos com '{args.termo}' no título: {len(matches)}\n")
    for v in matches:
        print(f"https://youtu.be/{v['video_id']}  |  {v['titulo']}")


if __name__ == "__main__":
    main()
