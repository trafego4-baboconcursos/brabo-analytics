"""
server.py — Password-protected local HTTP server for Brabo Analytics.

Usage:
    .venv\\Scripts\\python.exe frontend/server.py

Environment variables (all optional):
    BRABO_USER   login username  (default: brabo)
    BRABO_PASS   login password  (default: pbb2026)
    PORT         TCP port        (default: 5000)

Opens http://localhost:PORT — credentials via HTTP Basic Auth.
Navigating to / redirects to /analises/index.html automatically.
"""

import base64
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT  = Path(__file__).resolve().parent.parent   # workspace root
PORT  = int(os.environ.get("PORT", "5000"))
USER  = os.environ.get("BRABO_USER", "brabo")
PASS_ = os.environ.get("BRABO_PASS", "pbb2026")
REALM = "Brabo Analytics"

# Pre-compute expected Basic Auth token
_EXPECTED_TOKEN = base64.b64encode(f"{USER}:{PASS_}".encode("utf-8")).decode("ascii")


class BraboHandler(SimpleHTTPRequestHandler):
    """Serves files from ROOT with HTTP Basic Auth."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # ── Auth guard ────────────────────────────────────────────────────────────

    def _authorized(self) -> bool:
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return False
        token = auth_header[6:].strip()
        # Constant-time comparison to prevent timing attacks
        import hmac
        return hmac.compare_digest(token, _EXPECTED_TOKEN)

    def _send_auth_required(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        body = b"Unauthorized"
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── Request handlers ──────────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802
        if not self._authorized():
            self._send_auth_required()
            return
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/analises/index.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def do_HEAD(self):  # noqa: N802
        if not self._authorized():
            self._send_auth_required()
            return
        if self.path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/analises/index.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_HEAD()

    def log_message(self, fmt, *args):  # noqa: N802
        print(f"  {self.address_string()}  {fmt % args}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), BraboHandler)
    print("=" * 52)
    print(f"  Brabo Analytics — servidor local")
    print(f"  URL  : http://localhost:{PORT}")
    print(f"  Login: {USER} / {PASS_}")
    print(f"  Root : {ROOT}")
    print("  Ctrl+C para parar.")
    print("=" * 52)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
