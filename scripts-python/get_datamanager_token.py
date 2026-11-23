"""
Script para obter o Refresh Token do Google Ads + Data Manager API.
Fluxo OAuth sem PKCE para evitar incompatibilidade de sessão.
"""

import os
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv, set_key
import requests

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

CLIENT_ID = os.getenv("GOOGLE_ADS_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_ADS_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERRO: GOOGLE_ADS_CLIENT_ID ou GOOGLE_ADS_CLIENT_SECRET não configurados no .env")
    exit(1)

REDIRECT_URI = "http://localhost:8080"

SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/datamanager"
]

params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": " ".join(SCOPES),
    "access_type": "offline",
    "prompt": "consent",
}

auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

print("=" * 75)
print("AUTENTICAÇÃO GOOGLE ADS + DATA MANAGER API")
print("=" * 75)
print("1. Abra este link no seu navegador (Ctrl + Clique ou copie e cole):")
print("\n" + auth_url + "\n")
print("=" * 75)
print("2. Faça o login e clique em 'Permitir/Continuar'.")
print("   Quando a página cair em 'ERR_CONNECTION_REFUSED' no localhost:")
print("   👉 COPIE A URL COMPLETA da barra de endereços do navegador")
print("   👉 E COLE AQUI ABAIXO:")
print("=" * 75)

user_input = input("\nCole a URL completa (ou o código): ").strip()

# Extrai o parâmetro 'code' caso o usuário cole a URL inteira
if "code=" in user_input:
    parsed = urllib.parse.urlparse(user_input)
    query_params = urllib.parse.parse_qs(parsed.query)
    code = query_params.get("code", [user_input])[0]
else:
    code = user_input

token_url = "https://oauth2.googleapis.com/token"
payload = {
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}

resp = requests.post(token_url, data=payload)
res_json = resp.json()

if "refresh_token" in res_json:
    new_token = res_json["refresh_token"]
    print("\n" + "=" * 75)
    print("✅ REFRESH TOKEN GERADO COM SUCESSO!")
    print("=" * 75)
    print(new_token)
    print("=" * 75)
    
    set_key(str(env_path), "GOOGLE_ADS_REFRESH_TOKEN", new_token)
    print("\n✅ O arquivo .env foi atualizado automaticamente com o novo token!")
else:
    print("\n❌ Erro ao trocar o código pelo Refresh Token:")
    print(res_json)
