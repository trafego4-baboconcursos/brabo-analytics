"""Ações agendadas nos anúncios (Facebook/Meta), executadas pelo scheduler na hora marcada (Brasília).

Hoje só uma ação existe: trocar o status (PAUSED/ACTIVE) de um anúncio, conjunto ou campanha numa hora certa —
"pausar o AD304 hoje às 22h". Cada pedido é um arquivo `config/acoes/*.json`:

    {"descricao": "...", "executar_em": "2026-11-05T22:00",
     "acoes": [{"plataforma": "meta", "id": "120248677678120014", "nome": "AD304 ...", "status": "PAUSED"}]}

Como na verba diária, os arquivos vêm da `main` do repositório (pedido novo vale sem redeploy) e, se o download
falhar, da imagem. O job roda a cada 5 min e executa o arquivo quando `executar_em` já passou há no máximo
JANELA_MIN minutos: um restart no meio da janela ainda executa, e um arquivo velho nunca re-executa (não desfaz
quem mexeu à mão depois). Dentro da janela, um arquivo só roda uma vez por processo.

Google fica de fora de propósito: "nada automático no Google" (campanhas VIDEO nem aceitam mutação por API).
Status não cascateia: pausar a campanha não pausa os anúncios — o arquivo lista o nível que se quer mudar.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_IMAGEM = RAIZ / "config" / "acoes"
JANELA_MIN = 30
MAX_ACOES = 300
BRASILIA = dt.timezone(dt.timedelta(hours=-3))
STATUS_VALIDOS = ("PAUSED", "ACTIVE")
ID_META = re.compile(r"^\d{10,20}$")

_executados: set[str] = set()


def ler_pedido(caminho: Path) -> dict:
    """Valida o formato. Erro vira ValueError com o motivo; nada é chamado na plataforma antes disso."""
    p = json.loads(caminho.read_text(encoding="utf-8"))
    try:
        quando = dt.datetime.fromisoformat(p["executar_em"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"executar_em ausente ou inválido ({e})") from None
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=BRASILIA)
    acoes = p.get("acoes")
    if not isinstance(acoes, list) or not acoes:
        raise ValueError("lista 'acoes' vazia")
    if len(acoes) > MAX_ACOES:
        raise ValueError(f"{len(acoes)} ações; o limite é {MAX_ACOES}")
    for a in acoes:
        if a.get("plataforma") != "meta":
            raise ValueError(f"plataforma {a.get('plataforma')!r} não suportada (só meta)")
        if not ID_META.match(str(a.get("id", ""))):
            raise ValueError(f"id inválido: {a.get('id')!r}")
        if a.get("status") not in STATUS_VALIDOS:
            raise ValueError(f"status inválido: {a.get('status')!r}")
    return {**p, "executar_em": quando}


def pedidos_na_janela(pasta: Path, agora: dt.datetime) -> tuple[list[tuple[Path, dict]], list[str]]:
    """(pedidos para executar agora, problemas). Pedido da janela que não valida vira problema."""
    rodar, problemas = [], []
    for f in sorted(pasta.glob("*.json")):
        try:
            bruto = json.loads(f.read_text(encoding="utf-8"))
            quando = dt.datetime.fromisoformat(bruto["executar_em"])
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=BRASILIA)
        except (ValueError, OSError, KeyError, TypeError):
            continue  # ilegível: não dá para saber se é da janela; os da janela têm que ler
        if not (quando <= agora < quando + dt.timedelta(minutes=JANELA_MIN)):
            continue
        try:
            rodar.append((f, ler_pedido(f)))
        except ValueError as e:
            problemas.append(f"{f.name}: pedido inválido ({e})")
    return rodar, problemas


def executar(pedido: dict, meta=None) -> list[str]:
    """Aplica cada ação e relê o status. Devolve as falhas (vazio = tudo certo)."""
    if meta is None:
        if str(RAIZ) not in sys.path:
            sys.path.insert(0, str(RAIZ))
        from scripts.ads.meta import Meta
        meta = Meta()
    falhas = []
    for a in pedido["acoes"]:
        try:
            meta.post(a["id"], status=a["status"])
        except Exception as e:  # noqa: BLE001 — uma ação com erro não impede as outras
            falhas.append(f"{a['id']} {a.get('nome', '')}: {e}")
    for a in pedido["acoes"]:
        try:
            lido = meta.get(a["id"], fields="status")["status"]
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{a['id']} {a.get('nome', '')}: releitura falhou ({e})")
            continue
        if lido != a["status"]:
            falhas.append(f"{a['id']} {a.get('nome', '')}: status lido {lido}, pedido {a['status']}")
    return list(dict.fromkeys(falhas))


def rodar_acoes(agora: dt.datetime | None = None, baixar: bool = True, get=None, meta=None) -> dict:
    """Executa os pedidos cuja hora chegou. Devolve {fonte, executados, falhas}."""
    from verba_diaria import _http_get, baixar_planos

    agora = agora or dt.datetime.now(BRASILIA)
    falhas, executados, fonte = [], [], "main"
    with tempfile.TemporaryDirectory() as tmp:
        pasta = PASTA_IMAGEM
        if baixar:
            try:
                baixar_planos(Path(tmp), get or _http_get, pasta_repo="config/acoes")
                pasta = Path(tmp)
            except Exception as e:  # noqa: BLE001 — sem rede/GitHub, cai para a imagem
                fonte = f"imagem (download falhou: {e})"
        else:
            fonte = "imagem"
        pedidos, problemas = pedidos_na_janela(pasta, agora) if pasta.is_dir() else ([], [])
        falhas.extend(problemas)
        for f, pedido in pedidos:
            if f.name in _executados:
                continue
            _executados.add(f.name)
            erros = executar(pedido, meta)
            executados.append(f"{f.name}: {len(pedido['acoes']) - len(erros)}/{len(pedido['acoes'])} ok")
            falhas.extend(f"{f.name}: {e}" for e in erros)
    return {"fonte": fonte, "executados": executados, "falhas": falhas}
