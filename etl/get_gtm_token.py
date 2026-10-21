"""
Gera o GTM_REFRESH_TOKEN (OAuth, leitura) para a Google Tag Manager API
e a PageSpeed Insights API.

Reaproveita o mesmo OAuth client do Google Ads (GOOGLE_ADS_CLIENT_ID /
GOOGLE_ADS_CLIENT_SECRET). Execute uma vez por conta Google que precisa
ser autorizada:

    python etl/get_gtm_token.py                      # grava GTM_REFRESH_TOKEN
    python etl/get_gtm_token.py --env-var GTM_REFRESH_TOKEN_OUTRA
    python etl/get_gtm_token.py --sheets             # grava GOOGLE_SHEETS_REFRESH_TOKEN
                                                     # (leitura e escrita nas planilhas do Drive)

No navegador, faça login com a conta Google que tem acesso ao(s)
container(s) GTM das LPs (permissao Leitura basta).
"""

import os
import sys
import re
import argparse
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

PORT = 8080
REDIRECT_URI = f"http://localhost:{PORT}"
# openid: a PageSpeed Insights API aceita OAuth com esse escopo (dispensa API key)
SCOPE = "https://www.googleapis.com/auth/tagmanager.readonly openid"
SCOPE_SHEETS = "https://www.googleapis.com/auth/spreadsheets openid"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<html><body style='font-family:sans-serif;background:#121212;"
                "color:#fff;text-align:center;padding-top:100px'>"
                "<h1 style='color:#4CAF50'>Autorizacao GTM concluida!</h1>"
                "<p>Pode fechar esta pagina e voltar ao terminal.</p>"
                "</body></html>".encode("utf-8")
            )
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("Erro: codigo de autorizacao nao encontrado.".encode("utf-8"))

    def log_message(self, *args):
        pass


def update_env_file(env_var: str, refresh_token: str) -> bool:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print(f"Erro: arquivo .env nao encontrado em {env_path}")
        return False

    content = env_path.read_text(encoding="utf-8")
    pattern = rf"^({re.escape(env_var)}=).*$"
    replacement = f"{env_var}={refresh_token}"

    if re.search(pattern, content, re.MULTILINE):
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\n{env_var}={refresh_token}\n"

    env_path.write_text(new_content, encoding="utf-8")
    print(f" [OK] .env atualizado: {env_var}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-var", default=None,
                        help="Nome da variavel gravada no .env (default: GTM_REFRESH_TOKEN, "
                             "ou GOOGLE_SHEETS_REFRESH_TOKEN com --sheets)")
    parser.add_argument("--sheets", action="store_true",
                        help="Escopo do Google Sheets (escrita) em vez do GTM")
    args = parser.parse_args()
    scope = SCOPE_SHEETS if args.sheets else SCOPE
    args.env_var = args.env_var or ("GOOGLE_SHEETS_REFRESH_TOKEN" if args.sheets else "GTM_REFRESH_TOKEN")

    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Erro: GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET nao definidos no .env")

    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    })

    print(f"Iniciando servidor local na porta {PORT}...")
    try:
        server = HTTPServer(("localhost", PORT), OAuthCallbackHandler)
    except OSError as e:
        sys.exit(f"Erro: porta {PORT} ocupada. Detalhes: {e}")

    print("Abrindo o navegador... Faca login com a conta Google que tem acesso ao GTM.")
    print(f"\nSe nao abrir automaticamente, cole no navegador:\n\n{auth_url}\n")
    webbrowser.open(auth_url)
    server.handle_request()

    if not OAuthCallbackHandler.auth_code:
        sys.exit("Falha ao obter o codigo de autorizacao.")

    print("Codigo recebido! Trocando por refresh token...")
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": OAuthCallbackHandler.auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    r.raise_for_status()
    refresh_token = r.json().get("refresh_token")
    if refresh_token:
        update_env_file(args.env_var, refresh_token)
        print("Autenticacao GTM concluida com sucesso!")
    else:
        print("Aviso: nenhum refresh_token retornado.")
        print("Se ja autorizou antes, remova o app em Conta Google > Seguranca > "
              "Apps com acesso e tente de novo.")
        print(r.json())


if __name__ == "__main__":
    main()
