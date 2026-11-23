"""Preenche a aba VENDAS da planilha "Anúncios - [LANC]" com as vendas atribuídas por anúncio pelo banco.

Usa a mesma atribuição do painel (frontend/services/attribution.py, vendas do banco operacional via read_vendas):
só a etapa Captação, separada por plataforma (Vendas FB = Meta, Vendas YT = Google). Vendas TK fica 0 até o TikTok
entrar na atribuição. Mantém o cabeçalho e a fórmula de B2 ("Vendas Totais"); apaga e regrava A2:A e C2:E.
Ver docs/performance/playbooks/PADRAO_PLANILHAS_LANCAMENTO.md. Sem --apply só mostra o que gravaria.

    python scripts/planilha_vendas_anuncios.py PI-NOV-26 <ID_ANUNCIOS> [--apply]
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(RAIZ / ".env")
import logging  # noqa: E402

logging.disable(logging.WARNING)

ap = argparse.ArgumentParser()
ap.add_argument("lancamento")
ap.add_argument("anuncios_id")
ap.add_argument("--apply", action="store_true")
a = ap.parse_args()

from frontend.core import get_launches  # noqa: E402
from frontend.db_readers import read_vendas  # noqa: E402
from frontend.services.attribution import _sales_attribution  # noqa: E402

launch = next(x for x in get_launches() if x.code == a.lancamento)
vendas = read_vendas(a.lancamento)
attr = _sales_attribution(launch, vendas)
por_etapa = attr["por_criativo_canal_por_etapa"]
fb = por_etapa.get("Meta Ads", {}).get("Captação", {})
yt = por_etapa.get("Google Ads", {}).get("Captação", {})

tok = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    "refresh_token": os.environ["GOOGLE_SHEETS_REFRESH_TOKEN"], "grant_type": "refresh_token"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
BASE = f"https://sheets.googleapis.com/v4/spreadsheets/{a.anuncios_id}"

# nome completo do anúncio como aparece nas extrações (a busca da planilha é por LEFT(nome;5)&"*")
nomes = {}
for aba in ("EXTRACAO-BM", "EXTRACAO-GA"):
    for r in requests.get(f"{BASE}/values/'{aba}'!A2:A", headers=H).json().get("values", []):
        if r and r[0][:2] == "AD":
            nomes.setdefault(r[0][:5], r[0])

qtd = lambda d, c: d.get(c, {}).get("vendas", 0)
codigos = sorted(set(fb) | set(yt), key=lambda c: -(qtd(fb, c) + qtd(yt, c)))
linhas = [[nomes.get(c, c), qtd(fb, c), qtd(yt, c), 0] for c in codigos]
fora = [c for c in codigos if c not in nomes]

print(f"{a.lancamento}: {vendas.total_vendas} vendas no banco, {attr['total_rastreado']} rastreadas")
print(f"VENDAS: {len(linhas)} anúncios · FB {sum(l[1] for l in linhas)} · YT {sum(l[2] for l in linhas)}")
if fora:
    print("com venda mas sem gasto na extração da captação (não aparecem na aba principal):", fora)
for l in linhas[:5]:
    print("  ", l)
if not a.apply:
    sys.exit("[dry-run] nada gravado")

atual = requests.get(f"{BASE}/values/VENDAS!A1:E", headers=H, params={"valueRenderOption": "FORMULA"}).json().get("values", [])
bk = RAIZ / "outputs" / f"backup_planilha_anuncios_{a.lancamento}_VENDAS_{datetime.now():%Y%m%d_%H%M}.json"
bk.write_text(json.dumps(atual, ensure_ascii=False), encoding="utf-8")
n = len(linhas) + 1
requests.post(f"{BASE}/values:batchClear", headers=H, json={"ranges": ["VENDAS!A2:A", "VENDAS!C2:E"]}).raise_for_status()
requests.post(f"{BASE}/values:batchUpdate", headers=H, json={"valueInputOption": "RAW", "data": [
    {"range": f"VENDAS!A2:A{n}", "values": [[l[0]] for l in linhas]},
    {"range": f"VENDAS!C2:E{n}", "values": [l[1:] for l in linhas]}]}).raise_for_status()
print("gravado · backup:", bk.name)
