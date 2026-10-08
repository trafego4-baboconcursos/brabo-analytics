"""
Regras de transformação: mensagem crua da API do Unnichat → linhas das tabelas.

Funções puras (sem rede, sem banco), testadas em tests/test_unnichat_coletor.py.

O formato vem de 39.017 mensagens reais arquivadas pelo Backup Unnichat no
banco comercial (perfil tirado em 07/10/2026):

    senderBy   user (atendente) 25.662 · contact (cliente) 12.321 · platform 1.034
    type       message, button, template, cta-url, image, audio, info, document,
               video, sticker, contact-card, note
    platform   sempre type=info: eventos do sistema, como
               "Conversa atribuída automaticamente ao <Nome>"
               "Conversa atribuída pela ação em massa para <Nome>"
               "A conversa foi transferida por <Nome>"
               "A conversa foi atribuída por <Nome>"
               "Lembrete para o contato: ..."

Nenhum evento de "conversa finalizada" aparece, e o /assign mantém o
responsável semanas depois da última mensagem (22 de 23 conversas paradas desde
setembro, teste de 08/10/2026). Por isso "conversa aberta" é definida pelo
tempo: o cliente escreveu nas últimas 24h (janela de atendimento do WhatsApp).
O coletor só grava `ultima_msg_cliente_em`; a página aplica a janela.

Campo `origin` das mensagens enviadas (visto na API em 08/10/2026):
    vazio = atendente · "automation" = automação · "schedule" = agendada.
Mensagem de automação não conta pra atendente nenhum (atendente_id = None).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

DIRECAO = {"user": "enviada", "contact": "recebida"}
ORIGEM = {"automation": "automacao", "schedule": "agendada"}   # o resto é atendente

# Evento que diz PARA QUEM a conversa foi.
_ATRIBUIDA_PARA = re.compile(
    r"^conversa atribu[ií]da (?:automaticamente ao|automaticamente a|pela a[cç][aã]o em massa para)\s+(.+?)\s*$",
    re.IGNORECASE,
)
# Evento que muda o dono sem dizer o novo (só quem fez a ação).
_MUDOU_SEM_DESTINO = re.compile(
    r"^a conversa foi (?:transferida|atribu[ií]da) por\s+.+$",
    re.IGNORECASE,
)


def normalizar_nome(nome: str | None) -> str:
    """Compara nomes ignorando acento, caixa e espaço sobrando."""
    if not nome:
        return ""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def parse_data(valor) -> datetime | None:
    """Data da mensagem. A API manda ISO 8601 em UTC (ex. 2026-09-18T17:04:23.706Z);
    número é tratado como epoch em milissegundos."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return datetime.fromtimestamp(valor / 1000, tz=timezone.utc)
    texto = str(valor).strip().replace("Z", "+00:00")
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return data if data.tzinfo else data.replace(tzinfo=timezone.utc)


def evento_de_atribuicao(texto: str | None) -> tuple[str, str | None] | None:
    """('para', nome) quando o texto diz o novo dono; ('mudou', None) quando
    o dono mudou sem dizer pra quem; None quando não é evento de atribuição."""
    texto = (texto or "").strip()
    m = _ATRIBUIDA_PARA.match(texto)
    if m:
        return ("para", m.group(1))
    if _MUDOU_SEM_DESTINO.match(texto):
        return ("mudou", None)
    return None


def montar_linhas(
    conexao: str,
    contact_id: str,
    mensagens: list[dict],
    ids_por_nome: dict[str, str],
    atendente_atual: str | None,
) -> tuple[list[dict], dict]:
    """Linhas de unnichat_mensagens + o estado da conversa para unnichat_contatos.

    Atendente de cada mensagem = quem atendia naquela hora, pelos eventos de
    sistema. Trecho desconhecido no FIM da conversa (depois de uma mudança sem
    destino, ou a conversa toda quando não há evento) = responsável atual
    (atendente_atual). Trecho desconhecido antes de um evento = None.
    """
    ordenadas = sorted(
        (m for m in mensagens if parse_data(m.get("date"))),
        key=lambda m: parse_data(m.get("date")),
    )

    # Primeiro passo: dono vigente em cada posição.
    dono: list[str | None] = []
    atual: str | None = None
    # Começa desconhecido: conversa sem nenhum evento de atribuição vira um
    # trecho só, que fica com o responsável atual. Com eventos, o trecho antes
    # do primeiro continua None (automação antes de cair num atendente).
    desconhecido = True
    for m in ordenadas:
        if m.get("senderBy") == "platform":
            ev = evento_de_atribuicao(m.get("message"))
            if ev and ev[0] == "para":
                atual = ids_por_nome.get(normalizar_nome(ev[1]))
                desconhecido = atual is None
            elif ev and ev[0] == "mudou":
                atual, desconhecido = None, True
        dono.append(atual if not desconhecido else "?")

    # Segundo passo: o último trecho desconhecido é o responsável atual.
    for i in range(len(dono) - 1, -1, -1):
        if dono[i] != "?":
            break
        dono[i] = atendente_atual
    dono = [None if d == "?" else d for d in dono]

    linhas: list[dict] = []
    ultima: dict | None = None
    ultima_cliente: dict | None = None
    for m, atendente in zip(ordenadas, dono):
        direcao = DIRECAO.get(m.get("senderBy"))
        if not direcao or not m.get("id"):
            continue
        origem = "cliente" if direcao == "recebida" else ORIGEM.get(m.get("origin"), "atendente")
        linhas.append({
            "conexao": conexao,
            "message_id": str(m["id"]),
            "contact_id": contact_id,
            "enviada_em": parse_data(m.get("date")),
            "direcao": direcao,
            "origem": origem,
            "atendente_id": None if origem == "automacao" else atendente,
            "tipo": m.get("type"),
            "is_template": m.get("type") == "template",
        })
        ultima = linhas[-1]
        if direcao == "recebida":
            ultima_cliente = linhas[-1]

    estado = {
        "conexao": conexao,
        "contact_id": contact_id,
        "atendente_id": atendente_atual,
        "ultima_msg_em": ultima["enviada_em"] if ultima else None,
        "ultima_msg_de": ("atendente" if ultima["direcao"] == "enviada" else "cliente") if ultima else None,
        "ultima_msg_cliente_em": ultima_cliente["enviada_em"] if ultima_cliente else None,
    }
    return linhas, estado


def extrair_atendente_atual(resposta: dict | None) -> str | None:
    """Id do responsável em GET /contact/{id}/assign. A doc não descreve a
    resposta; aceita os formatos mais prováveis até vermos um JSON real."""
    if not isinstance(resposta, dict):
        return None
    dado = resposta.get("data", resposta)
    if isinstance(dado, list):
        dado = dado[0] if dado else None
    if not isinstance(dado, dict):
        return None
    for chave in ("attendantId", "userId", "id"):
        if dado.get(chave):
            return str(dado[chave])
    for chave in ("attendant", "user"):
        if isinstance(dado.get(chave), dict) and dado[chave].get("id"):
            return str(dado[chave]["id"])
    return None
