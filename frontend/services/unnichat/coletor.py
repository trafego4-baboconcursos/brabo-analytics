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
  3. A cada RECOLETA_MINUTOS, conversas com mensagem nos últimos RECOLETA_DIAS
     voltam pra fila. A cada ATENDENTES_MINUTOS, /attendants é sincronizado.

Sistema independente do Backup Unnichat: só conta mensagens, sem texto/mídia.
"""
from __future__ import annotations

import asyncio
import os
import time

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

ESTADO: dict = {"ligado": False, "processados": 0, "erros": 0, "ultimo_erro": None,
                "atendentes_em": None, "recoleta_em": None}
_API: Unnichat | None = None


def _api() -> Unnichat:
    global _API
    if _API is None:
        _API = Unnichat(tokens(), Ritmo(REQ_POR_SEGUNDO))
    return _API


def processar(item: dict) -> None:
    conexao, contact_id = item["conexao"], item["contact_id"]
    api = _api()
    mensagens = api.mensagens(conexao, contact_id)
    atual = extrair_atendente_atual(api.responsavel(conexao, contact_id))
    linhas, estado = montar_linhas(conexao, contact_id, mensagens, banco.ids_por_nome(), atual)
    estado.update(telefone=item.get("telefone"), nome=item.get("nome"))
    banco.gravar_contato(linhas, estado)


def processar_lote(tamanho: int = 5) -> int:
    """Processa até `tamanho` itens da fila. Devolve quantos pegou."""
    lote = banco.pegar_lote(tamanho)
    for item in lote:
        try:
            processar(item)
            banco.concluir(item["id"])
            ESTADO["processados"] += 1
        except Exception as exc:  # noqa: BLE001 — um contato não pode parar a fila
            logger.exception("Unnichat %s/%s falhou", item["conexao"], item["contact_id"])
            ESTADO["erros"] += 1
            ESTADO["ultimo_erro"] = f"{item['conexao']}/{item['contact_id']}: {exc}"[:300]
            try:
                banco.falhar(item["id"], str(exc))
            except Exception:
                logger.exception("Unnichat: falha ao registrar erro do item %s", item["id"])
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
        await asyncio.sleep(1 if pegou else 10)


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
