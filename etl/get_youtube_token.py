"""
Gera o YOUTUBE_REFRESH_TOKEN para a YouTube Analytics API.

Modos de uso:

  # Modo local (você mesmo autoriza):
  python etl/get_youtube_token.py

  # Modo remoto — PASSO 1: gera URL para mandar ao Felipe
  python etl/get_youtube_token.py --gerar-url

  # Modo remoto — PASSO 2: Felipe envia a URL de retorno, você cola aqui
  python etl/get_youtube_token.py --trocar-codigo "http://localhost:8081/?code=4/0Ax..."
"""
import os
import re
import sys
import json
import argparse
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PORT = 8081
REDIRECT_URI = f"http://localhost:{PORT}"

SCOPES = " ".join([
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
])


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family:sans-serif;text-align:center;padding:80px;background:#0f172a;color:#fff">
            <h2 style="color:#22c55e">YouTube autorizado com sucesso!</h2>
            <p>Pode fechar esta janela e voltar ao terminal.</p>
            </body></html>""")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Erro: codigo de autorizacao nao encontrado.")

    def log_message(self, *_):
        pass


def _update_env(refresh_token: str, env_var: str = "YOUTUBE_REFRESH_TOKEN"):
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print(f"AVISO: .env nao encontrado em {env_path}")
        return
    content = env_path.read_text(encoding="utf-8")
    pattern = rf"^({re.escape(env_var)}=).*$"
    replacement = f"{env_var}={refresh_token}"
    if re.search(pattern, content, re.MULTILINE):
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\n{env_var}={refresh_token}\n"
    env_path.write_text(new_content, encoding="utf-8")
    print(f"[OK] .env atualizado com {env_var}")


def _load_credentials() -> tuple[str, str]:
    secrets_path = Path(__file__).parent.parent / "youtube" / "client_secrets.json"
    if secrets_path.exists():
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        installed = data.get("installed") or data.get("web") or {}
        cid = installed.get("client_id", "")
        csecret = installed.get("client_secret", "")
        if cid and csecret:
            print(f"[OK] Usando credenciais de {secrets_path.name}")
            return cid, csecret
    cid     = os.environ.get("GOOGLE_ADS_CLIENT_ID", "")
    csecret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")
    return cid, csecret


def _build_auth_url(client_id: str) -> str:
    return "https://accounts.google.com/o/oauth2/auth?" + urlencode({
        "client_id":     client_id,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    })


def _exchange_code(code: str, client_id: str, client_secret: str) -> str | None:
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  REDIRECT_URI,
            "grant_type":    "authorization_code",
        },
    )
    try:
        r.raise_for_status()
        res = r.json()
        token = res.get("refresh_token")
        if not token:
            print("AVISO: nenhum refresh_token retornado.")
            print("Se ja autorizou antes, va em Conta Google > Seguranca > Apps com acesso e remova o app.")
            print(res)
        return token
    except Exception as e:
        print(f"Erro: {e}\n{r.text}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Gera YOUTUBE_REFRESH_TOKEN")
    parser.add_argument("--gerar-url", action="store_true",
                        help="Gera URL de autorizacao para enviar a outra pessoa")
    parser.add_argument("--trocar-codigo", metavar="URL",
                        help="Cola aqui a URL de retorno recebida apos autorizacao remota")
    parser.add_argument("--env-var", default="YOUTUBE_REFRESH_TOKEN",
                        help="Nome da variavel gravada no .env (default: YOUTUBE_REFRESH_TOKEN). "
                             "Use um nome proprio (ex: YOUTUBE_REFRESH_TOKEN_MATEUS) pra nao "
                             "sobrescrever o token do canal principal ao autorizar outro canal.")
    parser.add_argument("--nome", default="",
                        help="Nome da pessoa/canal sendo autorizado, so pra exibir nas instrucoes")
    args = parser.parse_args()

    client_id, client_secret = _load_credentials()
    if not client_id or not client_secret:
        sys.exit("Erro: credenciais nao encontradas. Coloque youtube/client_secrets.json ou defina GOOGLE_ADS_CLIENT_ID/SECRET no .env")

    # ── Modo: trocar código recebido ──────────────────────────────────────────
    if args.trocar_codigo:
        url = args.trocar_codigo.strip()
        params = parse_qs(urlparse(url).query)
        code = (params.get("code") or [None])[0]
        if not code:
            sys.exit(f"Erro: nao encontrei 'code=' na URL fornecida.\nURL recebida: {url}")
        print(f"Codigo extraido: {code[:20]}...")
        token = _exchange_code(code, client_id, client_secret)
        if token:
            _update_env(token, args.env_var)
            print("\nAutorizacao concluida! Agora execute:")
            print("  .venv\\Scripts\\python etl/etl_youtube_analytics.py --launch-code PBB-JUN-26\n")
        return

    auth_url = _build_auth_url(client_id)

    # ── Modo: gerar URL para enviar ───────────────────────────────────────────
    if args.gerar_url:
        quem = args.nome or "a pessoa"
        print("\n" + "="*60)
        print(f"ENVIE ESTA URL PARA {quem.upper()} (WhatsApp/email):")
        print("="*60)
        print(auth_url)
        print("="*60)
        print(f"""
Instrucoes para {quem}:
1. Abra o link acima no navegador
2. Faca login com a conta Google do canal do YouTube dele(a)
3. Autorize o acesso
4. O navegador vai mostrar erro de conexao (normal!)
5. Copie a URL COMPLETA da barra de endereco e envie de volta

Depois que receber a URL, rode:
  .venv\\Scripts\\python etl/get_youtube_token.py --trocar-codigo "URL_RECEBIDA" --env-var {args.env_var}
""")
        return

    # ── Modo local (padrao) ───────────────────────────────────────────────────
    print(f"Iniciando servidor OAuth na porta {PORT}...")
    try:
        server = HTTPServer(("localhost", PORT), OAuthCallbackHandler)
    except OSError as e:
        sys.exit(f"Erro: porta {PORT} ocupada — {e}")

    print(f"\nAbrindo navegador para autorizacao YouTube...\n")
    webbrowser.open(auth_url)
    server.handle_request()

    if not OAuthCallbackHandler.auth_code:
        sys.exit("Falha: codigo de autorizacao nao recebido.")

    print("Trocando codigo por refresh token...")
    token = _exchange_code(OAuthCallbackHandler.auth_code, client_id, client_secret)
    if token:
        _update_env(token, args.env_var)
        print("\nAutorizacao concluida! Agora execute:")
        print("  .venv\\Scripts\\python etl/etl_youtube_analytics.py --launch-code PBB-JUN-26\n")


if __name__ == "__main__":
    main()
