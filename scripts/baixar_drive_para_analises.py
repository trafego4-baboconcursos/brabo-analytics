"""Baixa do Google Drive os backups de lançamentos antigos para analises/[LANÇAMENTO]/<fonte>/.

Primeira vez (uma só, abre o navegador para você autorizar a LEITURA do Drive):
    python etl/get_gtm_token.py --drive          # grava GOOGLE_DRIVE_REFRESH_TOKEN no .env

Uso:
    python scripts/baixar_drive_para_analises.py --listar                     # só mostra o que baixaria
    python scripts/baixar_drive_para_analises.py --baixar                     # baixa (pula o que já existe com o mesmo tamanho)
    python scripts/baixar_drive_para_analises.py --baixar --pasta ID --pasta ID2   # outras pastas-raiz

Cada subpasta vira um lançamento: pelo código no nome ("PES-AGO-25 (pós-edital)", "INSS - Reabertura | PI-JUL-25")
ou por "<produto> - <mês>" (INSS/TJSP/BB + mês, ano = 2025). Os arquivos vão para `Active Campaign/` — a pasta de
leads da hierarquia que já existe em analises/ (Meta Ads, Google Ads, Active Campaign, Hotmart, TMB, Typeform).
Só leitura no Drive. Nunca imprime token.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASTAS_RAIZ = [
    "15D7C-lmegA0MXoE-Z0stMPsHjyQIE6gd",   # "Listas de Leads - 2025": INSS/TJSP/BB por mês
    "1g8uy8rd2gfJJOl5_Vrgbwz_l-NeM27Ma",   # pasta-mãe com uma pasta por lançamento de 2025 (PI-JUL-25, PBB-AGO-25...)
]
DESTINO = "Active Campaign"
PRODUTO = {"INSS": "PI", "TJSP": "PES", "TJ-SP": "PES", "BB": "PBB"}
MES = {"janeiro": "JAN", "fevereiro": "FEV", "marco": "MAR", "abril": "ABR", "maio": "MAI", "junho": "JUN",
       "julho": "JUL", "agosto": "AGO", "setembro": "SET", "outubro": "OUT", "novembro": "NOV", "dezembro": "DEZ"}
RX_CODIGO = re.compile(r"\b((?:PI|PES|PBB)-[A-Z]{3}-\d{2}|BV-\d{2})\b", re.I)


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def lancamento_da_pasta(nome: str, ano: int = 2025) -> str | None:
    """'INSS - Janeiro ' → PI-JAN-25 · 'TJSP - Março' → PES-MAR-25 · 'PBB-AGO-25' → PBB-AGO-25 · 'x' → None."""
    m = RX_CODIGO.search(nome or "")
    if m:
        return m.group(1).upper()
    limpo = _sem_acento((nome or "").strip()).lower()
    partes = [p.strip() for p in re.split(r"\s*-\s*", limpo, maxsplit=1)]
    if len(partes) == 2 and partes[1]:
        prod = PRODUTO.get(partes[0].upper())
        mes = MES.get(partes[1].split()[0])
        if prod and mes:
            return f"{prod}-{mes}-{str(ano)[-2:]}"
    return None


def nome_seguro(nome: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", nome).strip()


def _token() -> str:
    import requests
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    for v in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_DRIVE_REFRESH_TOKEN"):
        if not os.environ.get(v):
            sys.exit(f"Falta {v} no .env. Rode antes:  python etl/get_gtm_token.py --drive")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_DRIVE_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=60)
    if not r.ok:
        sys.exit(f"Não consegui renovar o acesso ao Drive (HTTP {r.status_code}). Refaça: python etl/get_gtm_token.py --drive")
    return r.json()["access_token"]


def _filhos(tok: str, pasta: str) -> list[dict]:
    import requests

    out, pagina = [], None
    while True:
        params = {"q": f"'{pasta}' in parents and trashed = false", "pageSize": 200,
                  "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime)",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if pagina:
            params["pageToken"] = pagina
        r = requests.get("https://www.googleapis.com/drive/v3/files", headers={"Authorization": f"Bearer {tok}"},
                         params=params, timeout=60)
        r.raise_for_status()
        d = r.json()
        out += d.get("files", [])
        pagina = d.get("nextPageToken")
        if not pagina:
            return out


def _baixar(tok: str, arq: dict, destino: Path) -> None:
    import requests

    with requests.get(f"https://www.googleapis.com/drive/v3/files/{arq['id']}", headers={"Authorization": f"Bearer {tok}"},
                      params={"alt": "media", "supportsAllDrives": "true"}, stream=True, timeout=300) as r:
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as fh:
            for bloco in r.iter_content(1 << 20):
                fh.write(bloco)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--baixar", action="store_true")
    ap.add_argument("--pasta", action="append", help="id de pasta-raiz (repetível); padrão: as duas conhecidas")
    a = ap.parse_args()
    if not (a.listar or a.baixar):
        ap.error("use --listar ou --baixar")
    tok = _token()
    pasta_tipo = "application/vnd.google-apps.folder"
    total = baixados = pulados = 0
    sem_lanc: list[str] = []
    for raiz in (a.pasta or PASTAS_RAIZ):
        for sub in (f for f in _filhos(tok, raiz) if f["mimeType"] == pasta_tipo):
            cod = lancamento_da_pasta(sub["name"])
            if not cod:
                sem_lanc.append(sub["name"])
                continue
            fila = [sub["id"]]
            while fila:
                for arq in _filhos(tok, fila.pop()):
                    if arq["mimeType"] == pasta_tipo:
                        fila.append(arq["id"])
                        continue
                    if arq["mimeType"].startswith("application/vnd.google-apps."):
                        continue   # planilha/documento nativo: não baixa como arquivo
                    total += 1
                    dest = ROOT / "analises" / f"[{cod}]" / DESTINO / nome_seguro(arq["name"])
                    if dest.exists() and dest.stat().st_size == int(arq.get("size") or -1):
                        pulados += 1
                        continue
                    kb = int(arq.get("size") or 0) / 1024
                    print(f"{'baixa' if a.baixar else 'baixaria'}: [{cod}]/{DESTINO}/{arq['name']} ({kb:,.0f} KB)")
                    if a.baixar:
                        _baixar(tok, arq, dest)
                        baixados += 1
    print(f"\narquivos: {total} | baixados: {baixados} | já existiam: {pulados}")
    if sem_lanc:
        print("pastas sem lançamento identificado (ignoradas):", "; ".join(sem_lanc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
