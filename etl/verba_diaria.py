"""Verba diária das campanhas (Meta + Google), aplicada pelo scheduler às 00h05 (Brasília).

Tira o job do GitHub Actions, que atrasava a verba do dia (docs/projetos/PLANO_CRON_VERBA_EASYPANEL.md).
Aplica TODO plano `config/orcamentos/*.json` cujo `aplicar_em` é hoje, com `scripts/ajustar_verba_lista.py`.

Os planos são baixados da `main` do repositório (público) para uma pasta temporária, assim um plano novo vale
sem redeploy do scheduler. Só entra arquivo `*.json` da pasta `config/orcamentos`, com URL do próprio repositório,
e o plano ainda passa por `ler_plano` (formato) antes de qualquer chamada às plataformas. Se o download falhar,
usa os planos que foram na imagem. Aplicar duas vezes o mesmo plano é seguro (valores absolutos).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_IMAGEM = RAIZ / "config" / "orcamentos"
REPO = "trafego4-baboconcursos/brabo-analytics"
URL_LISTA = f"https://api.github.com/repos/{REPO}/contents/config/orcamentos?ref=main"
PREFIXO_RAW = f"https://raw.githubusercontent.com/{REPO}/"
NOME_VALIDO = re.compile(r"^[A-Za-z0-9._-]+\.json$")
TIMEOUT_PLANO_S = 1200


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "brabo-scheduler"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — URL fixa do repositório
        return r.read()


def baixar_planos(destino: Path, get=_http_get, pasta_repo: str = "config/orcamentos") -> list[Path]:
    """Baixa os `.json` de `pasta_repo` da `main`. Ignora o que não for arquivo do próprio repositório.
    Também usado por acoes_agendadas.py (config/acoes)."""
    url_lista = URL_LISTA.replace("config/orcamentos", pasta_repo)
    baixados = []
    for item in json.loads(get(url_lista)):
        nome, url = item.get("name", ""), item.get("download_url") or ""
        if item.get("type") != "file" or not NOME_VALIDO.match(nome) or not url.startswith(PREFIXO_RAW):
            continue
        caminho = destino / nome
        caminho.write_bytes(get(url))
        baixados.append(caminho)
    if not baixados:
        raise RuntimeError("a lista de planos da main veio vazia")
    return baixados


def planos_do_dia(pasta: Path, hoje: dt.date) -> tuple[list[Path], list[str]]:
    """(planos para aplicar hoje, problemas). Plano de hoje que não passa na validação vira problema."""
    from scripts.ajustar_verba_lista import ler_plano

    aplicar, problemas = [], []
    for f in sorted(pasta.glob("*.json")):
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("aplicar_em") != hoje.isoformat():
                continue
        except (ValueError, OSError):
            continue  # arquivo ilegível não é de hoje que se saiba; os de hoje têm que ler
        try:
            ler_plano(f)
            aplicar.append(f)
        except ValueError as e:
            problemas.append(f"{f.name}: plano inválido ({e})")
    return aplicar, problemas


def tetos() -> tuple[float, float]:
    """(teto por campanha, teto do dia somando os planos), em R$. Calibrados em 04/11/26: maior campanha
    ~R$ 7.800, dia de pico ~R$ 90 mil. Sobe-se por variável de ambiente quando o orçamento crescer de verdade."""
    return (float(os.environ.get("VERBA_MAX_CAMPANHA", 15000)), float(os.environ.get("VERBA_MAX_DIA", 150000)))


def aplicar_tetos(planos: list[Path]) -> tuple[list[Path], list[str]]:
    """Barra o que passa dos tetos: um erro de digitação (7500 -> 75000) não chega às plataformas.
    Plano barrado não é aplicado e vira falha (alerta). Se a soma do dia estoura, NENHUM plano do dia roda."""
    max_camp, max_dia = tetos()
    ok, barrados, total = [], [], 0.0
    for p in planos:
        camps = json.loads(p.read_text(encoding="utf-8"))["campanhas"]
        acima = [c for c in camps if c["valor"] > max_camp]
        if acima:
            nomes = ", ".join(f"{c['id']} R$ {c['valor']:,.2f}" for c in acima[:5])
            barrados.append(f"{p.name}: BARRADO — campanha acima do teto de R$ {max_camp:,.0f}/dia ({nomes})")
            continue
        ok.append(p)
        total += sum(c["valor"] for c in camps)
    if total > max_dia:
        barrados.append(f"BARRADOS todos os planos do dia — soma R$ {total:,.2f} acima do teto de R$ {max_dia:,.0f}/dia")
        return [], barrados
    return ok, barrados


def aplicar_verba_do_dia(hoje: dt.date | None = None, baixar: bool = True, get=_http_get,
                         rodar=subprocess.run) -> dict:
    """Aplica os planos de hoje. Devolve {fonte, planos, falhas, saida}; `falhas` vazio = tudo certo."""
    if hoje is None:
        from scripts.ajustar_verba_lista import hoje_brasilia
        hoje = hoje_brasilia()
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))

    falhas, saida, fonte = [], [], "main"
    with tempfile.TemporaryDirectory() as tmp:
        pasta = PASTA_IMAGEM
        if baixar:
            try:
                baixar_planos(Path(tmp), get)
                pasta = Path(tmp)
            except Exception as e:  # noqa: BLE001 — sem rede/GitHub, cai para a imagem
                fonte = f"imagem (download falhou: {e})"
        else:
            fonte = "imagem"
        planos, problemas = planos_do_dia(pasta, hoje)
        falhas.extend(problemas)
        planos, barrados = aplicar_tetos(planos)
        falhas.extend(barrados)
        for p in planos:
            try:
                r = rodar([sys.executable, "-m", "scripts.ajustar_verba_lista", "--arquivo", str(p)],
                          capture_output=True, text=True, encoding="utf-8", errors="ignore",
                          timeout=TIMEOUT_PLANO_S, cwd=str(RAIZ))
            except subprocess.TimeoutExpired:
                falhas.append(f"{p.name}: estourou {TIMEOUT_PLANO_S // 60} min")
                continue
            saida.append(f"=== {p.name}\n{(r.stdout or '').strip()}")
            if r.returncode != 0:
                falhas.append(f"{p.name}: saiu com código {r.returncode}\n{(r.stderr or '')[-800:]}")
    return {"fonte": fonte, "planos": [p.name for p in planos], "falhas": falhas, "saida": "\n".join(saida)}
