"""
Coletor do Atendimento Comercial (Unnichat), rodando dentro do site.

Alimenta a página /atendimento. Fica no próprio brabo-analytics para não
criar mais um app no EasyPanel (decisão do Mateus, 08/10/2026). Liga sozinho
no startup quando há pelo menos um UNNICHAT_TOKEN_<CHAVE> e o
UNNICHAT_WEBHOOK_SECRET configurados; sem eles, nada roda.

Fluxo:
  1. POST /api/unnichat/webhook/<chave> (frontend/routes/unnichat.py): a
     automação do Unnichat avisa que um contato teve atendimento. Só grava na
     fila e responde na hora.
  2. Um worker consome a fila: busca mensagens + responsável do contato,
     monta as linhas (mapeamento.py) e grava. Um só, de propósito, pra pesar o
     mínimo no site; a fila no banco segura picos e reinícios de deploy.
     Dentro do worker, até UNNICHAT_PARALELO (3) conversas por vez.
  3. A cada RECOLETA_MINUTOS, conversas com mensagem nos últimos RECOLETA_DIAS
     voltam pra fila. A cada ATENDENTES_MINUTOS, /attendants é sincronizado.

Sistema independente do Backup Unnichat: só conta mensagens, sem texto/mídia.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from logger import get_logger
from frontend.services.unnichat import banco
from frontend.services.unnichat.api import Ritmo, Unnichat
from frontend.services.unnichat.mapeamento import extrair_atendente_atual, montar_linhas

logger = get_logger("unnichat")

_PREFIXO = "UNNICHAT_TOKEN_"


def tokens() -> dict[str, str]:
    """UNNICHAT_TOKEN_IVAN_NETO_PRINCIPAL → chave "ivan_neto_principal"."""
    return {k[len(_PREFIXO):].lower(): v for k, v in os.environ.items() if k.startswith(_PREFIXO) and v}


def segredo_webhook() -> str:
    return os.environ.get("UNNICHAT_WEBHOOK_SECRET", "")


def ligado() -> bool:
    return bool(tokens()) and bool(segredo_webhook())


RECOLETA_MINUTOS = int(os.environ.get("UNNICHAT_RECOLETA_MINUTOS", "30"))
RECOLETA_DIAS = int(os.environ.get("UNNICHAT_RECOLETA_DIAS", "2"))
ATENDENTES_MINUTOS = int(os.environ.get("UNNICHAT_ATENDENTES_MINUTOS", "60"))
REQ_POR_SEGUNDO = float(os.environ.get("UNNICHAT_REQ_POR_SEGUNDO", "4"))
# Conversas processadas ao mesmo tempo. Cada uma segura 1 conexão do banco
# comercial por ~1 s (pool do site: 3 + 2), então 3 é o teto pra não disputar
# com as páginas. Medido em 13/10: ~1,2 s de API + ~1,1 s de banco por conversa.
PARALELO = int(os.environ.get("UNNICHAT_PARALELO", "3"))

ESTADO: dict = {"ligado": False, "processados": 0, "erros": 0, "ultimo_erro": None,
                "atendentes_em": None, "recoleta_em": None}
_API: Unnichat | None = None
_TRAVA_ESTADO = threading.Lock()


def _api() -> Unnichat:
    global _API
    if _API is None:
        _API = Unnichat(tokens(), Ritmo(REQ_POR_SEGUNDO))
    return _API


def processar(item: dict, ids_por_nome: dict | None = None) -> None:
    conexao, contact_id = item["conexao"], item["contact_id"]
    api = _api()
    # As duas chamadas são independentes: em paralelo, a conversa sai na metade do tempo.
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_msgs = ex.submit(api.mensagens, conexao, contact_id)
        f_resp = ex.submit(api.responsavel, conexao, contact_id)
        mensagens, atual = f_msgs.result(), extrair_atendente_atual(f_resp.result())
    linhas, estado = montar_linhas(conexao, contact_id, mensagens,
                                  ids_por_nome if ids_por_nome is not None else banco.ids_por_nome(), atual)
    estado.update(telefone=item.get("telefone"), nome=item.get("nome"))
    banco.gravar_contato(linhas, estado, item.get("id"))


def _um_item(item: dict, ids: dict) -> None:
    try:
        processar(item, ids)   # já dá baixa na fila junto com a gravação
        with _TRAVA_ESTADO:
            ESTADO["processados"] += 1
    except Exception as exc:  # noqa: BLE001 — um contato não pode parar a fila
        logger.exception("Unnichat %s/%s falhou", item["conexao"], item["contact_id"])
        with _TRAVA_ESTADO:
            ESTADO["erros"] += 1
            ESTADO["ultimo_erro"] = f"{item['conexao']}/{item['contact_id']}: {exc}"[:300]
        try:
            banco.falhar(item["id"], str(exc))
        except Exception:
            logger.exception("Unnichat: falha ao registrar erro do item %s", item["id"])


def processar_lote(tamanho: int | None = None) -> int:
    """Processa até `tamanho` itens da fila, PARALELO de cada vez. Devolve quantos pegou."""
    lote = banco.pegar_lote(tamanho or PARALELO * 2)
    if not lote:
        return 0
    ids = banco.ids_por_nome()   # uma leitura por lote, não por conversa
    with ThreadPoolExecutor(max_workers=PARALELO) as ex:
        list(ex.map(lambda it: _um_item(it, ids), lote))
    return len(lote)


def sincronizar_atendentes() -> None:
    por_id: dict[str, dict] = {}
    api = _api()
    for conexao in tokens():
        for a in api.atendentes(conexao):
            if not a.get("id"):
                continue
            linha = por_id.setdefault(str(a["id"]), {
                "atendente_id": str(a["id"]),
                "nome": a.get("name") or " ".join(filter(None, [a.get("firstName"), a.get("lastName")])) or None,
                "email": a.get("email"), "status": a.get("status"), "conexoes": [],
            })
            linha["conexoes"].append(conexao)
        break  # a lista é a mesma em todas as contas (visto em 08/10/2026)
    banco.gravar_atendentes(list(por_id.values()))
    ESTADO["atendentes_em"] = time.strftime("%Y-%m-%d %H:%M:%S")


def recoletar() -> int:
    ativos = banco.contatos_para_recoleta(RECOLETA_DIAS)
    novos = banco.enfileirar(ativos, "recoleta")
    banco.limpar_fila()
    ESTADO["recoleta_em"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return novos


async def _worker() -> None:
    while True:
        try:
            pegou = await asyncio.to_thread(processar_lote)
        except Exception:
            logger.exception("Unnichat: falha ao ler a fila")
            pegou = 0
        await asyncio.sleep(0.2 if pegou else 10)


async def _agendador() -> None:
    ultimo_atendentes = ultimo_recoleta = 0.0
    while True:
        agora = time.monotonic()
        try:
            if agora - ultimo_atendentes >= ATENDENTES_MINUTOS * 60:
                await asyncio.to_thread(sincronizar_atendentes)
                ultimo_atendentes = agora
            if agora - ultimo_recoleta >= RECOLETA_MINUTOS * 60:
                novos = await asyncio.to_thread(recoletar)
                logger.info("Unnichat: recoleta pôs %s conversas na fila", novos)
                ultimo_recoleta = agora
        except Exception:
            logger.exception("Unnichat: agendador falhou; tenta de novo no próximo ciclo")
        await asyncio.sleep(60)


_TAREFAS: list[asyncio.Task] = []


def iniciar() -> None:
    """Chamado no startup do site. Uma vez por processo; sem token, não liga."""
    if _TAREFAS or not ligado():
        if not ligado():
            logger.info("Coletor Unnichat desligado (sem UNNICHAT_TOKEN_* ou UNNICHAT_WEBHOOK_SECRET).")
        return
    try:
        novas = banco.registrar_conexoes(sorted(tokens()))
    except Exception:
        logger.exception("Coletor Unnichat: tabelas da migration 011 indisponíveis; não liga")
        return
    _TAREFAS.extend([asyncio.create_task(_worker()), asyncio.create_task(_agendador())])
    ESTADO["ligado"] = True
    logger.info("Coletor Unnichat ligado: %s contas (%s novas no cadastro).", len(tokens()), novas)
