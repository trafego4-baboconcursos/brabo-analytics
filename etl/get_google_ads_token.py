import os
import sys
import re
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from pathlib import Path
from dotenv import load_dotenv

# Adiciona o diretorio pai ao path para importar modulos
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carrega .env
load_dotenv()

PORT = 8080
REDIRECT_URI = f"http://localhost:{PORT}"

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
            self.wfile.write("""
            <html>
            <head>
                <title>Autorizado com sucesso!</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                        text-align: center;
                        background: #121212;
                        color: #ffffff;
                        padding-top: 100px;
                    }
                    .card {
                        background: #1e1e1e;
                        border-radius: 8px;
                        padding: 30px;
                        display: inline-block;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                        max-width: 500px;
                    }
                    h1 { color: #4CAF50; }
                    p { font-size: 16px; line-height: 1.5; color: #b3b3b3; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Autorizacao concluida!</h1>
                    <p>O token foi recebido com sucesso. Voce ja pode fechar esta pagina e voltar ao terminal.</p>
                </div>
            </body>
            </html>
            """.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("Erro: Codigo de autorizacao nao encontrado.".encode("utf-8"))

def update_env_file(refresh_token: str):
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print(f"Erro: Arquivo .env nao encontrado em {env_path}")
        return False
    
    content = env_path.read_text(encoding="utf-8")
    
    # Procura por GOOGLE_ADS_REFRESH_TOKEN=...
    pattern = r"^(GOOGLE_ADS_REFRESH_TOKEN=).*$"
    replacement = f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}"
    
    if re.search(pattern, content, re.MULTILINE):
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\nGOOGLE_ADS_REFRESH_TOKEN={refresh_token}\n"
        
    env_path.write_text(new_content, encoding="utf-8")
    print(" [OK] .env atualizado com sucesso!")
    return True

def main():
    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("Erro: GOOGLE_ADS_CLIENT_ID ou GOOGLE_ADS_CLIENT_SECRET nao definidos no .env")
        sys.exit(1)
        
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/adwords",
        "access_type": "offline",
        "prompt": "consent"
    })
    
    print(f"Iniciando servidor local na porta {PORT}...")
    try:
        server = HTTPServer(("localhost", PORT), OAuthCallbackHandler)
    except OSError as e:
        print(f"Erro: Nao foi possivel iniciar o servidor local na porta {PORT}. Detalhes: {e}")
        print("Verifique se nenhuma outra aplicacao esta usando a porta 8080.")
        sys.exit(1)
        
    print(f"Tentando abrir o navegador com a URL de autorizacao...")
    print(f"\nCaso nao abra automaticamente, copie e cole este link no seu navegador:\n\n{auth_url}\n")
    
    webbrowser.open(auth_url)
    
    # Espera por uma unica requisicao do redirect
    server.handle_request()
    
    if OAuthCallbackHandler.auth_code:
        print("Codigo de autorizacao recebido! Trocando por refresh token...")
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
        try:
            r.raise_for_status()
            res = r.json()
            refresh_token = res.get("refresh_token")
            if refresh_token:
                update_env_file(refresh_token)
                print("Autenticacao concluida com sucesso!")
            else:
                print("Aviso: Nenhum refresh_token retornado.")
                print("Se voce ja autorizou anteriormente, va em sua Conta Google > Seguranca > Apps com acesso a conta, remova o app e tente novamente.")
                print(res)
        except Exception as e:
            print(f"Erro na troca do token: {e}")
            if r.text:
                print(r.text)
    else:
        print("Falha ao obter o codigo de autorizacao.")

if __name__ == "__main__":
    main()
