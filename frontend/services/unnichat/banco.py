"""
Gravação do coletor do Unnichat no banco comercial (SUPABASE_USERS_URL).

Usa a mesma engine do site (`_get_users_engine`): o guard de somente-leitura
dela só barra hotmart/tmb, e o coletor faz poucas operações curtas, então não
vale abrir outro pool no banco comercial. Tabelas da migration 011
(src/db/migrations/011_atendimento_unnichat.sql).
"""
from __future__ import annotations

from sqlalchemy import bindparam, text

from frontend.db import _get_users_engine
from frontend.services.unnichat.mapeamento import normalizar_nome

MAX_TENTATIVAS = 3


def enfileirar(itens: list[dict], origem: str) -> int:
    if not itens:
        return 0
    with _get_users_engine().begin() as conn:
        res = conn.execute(text("""
            INSERT INTO unnichat_atendimento_fila (conexao, contact_id, telefone, nome, origem)
            VALUES (:conexao, :contact_id, :telefone, :nome, :origem)
            ON CONFLICT (conexao, contact_id) WHERE status IN ('pendente', 'processando') DO NOTHING
        """), [{"telefone": None, "nome": None, **i, "origem": origem} for i in itens])
        return res.rowcount or 0


def pegar_lote(tamanho: int) -> list[dict]:
    with _get_users_engine().begin() as conn:
        # Item preso em "processando" (site reiniciou no meio) volta pra fila.
        conn.execute(text("""
            UPDATE unnichat_atendimento_fila SET status = 'pendente', atualizado_em = now()
             WHERE status = 'processando' AND atualizado_em < now() - interval '15 minutes'
        """))
        return [dict(r._mapping) for r in conn.execute(text("""
            UPDATE unnichat_atendimento_fila f SET status = 'processando', atualizado_em = now()
              FROM (SELECT id FROM unnichat_atendimento_fila WHERE status = 'pendente'
                     ORDER BY id LIMIT :n FOR UPDATE SKIP LOCKED) p
             WHERE f.id = p.id
         RETURNING f.id, f.conexao, f.contact_id, f.telefone, f.nome, f.tentativas
        """), {"n": tamanho})]


def concluir(item_id: int) -> None:
    with _get_users_engine().begin() as conn:
        conn.execute(text("UPDATE unnichat_atendimento_fila SET status = 'feito', erro = NULL, atualizado_em = now() WHERE id = :id"),
                     {"id": item_id})


def falhar(item_id: int, erro: str) -> None:
    with _get_users_engine().begin() as conn:
        conn.execute(text("""
            UPDATE unnichat_atendimento_fila
               SET tentativas = tentativas + 1, erro = :erro, atualizado_em = now(),
                   status = CASE WHEN tentativas + 1 >= :max THEN 'erro' ELSE 'pendente' END
             WHERE id = :id
        """), {"erro": erro[:500], "max": MAX_TENTATIVAS, "id": item_id})


def limpar_fila() -> None:
    with _get_users_engine().begin() as conn:
        conn.execute(text("DELETE FROM unnichat_atendimento_fila WHERE status = 'feito' AND atualizado_em < now() - interval '7 days'"))


def contatos_para_recoleta(dias: int) -> list[dict]:
    """Conversas com mensagem nos últimos `dias`: voltam pra fila pra contagem
    acompanhar a conversa sem depender de novo webhook."""
    with _get_users_engine().connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text("""
            SELECT conexao, contact_id, telefone, nome FROM unnichat_contatos
             WHERE ultima_msg_em > now() - make_interval(days => :dias)
        """), {"dias": dias})]


def registrar_conexoes(chaves: list[str]) -> int:
    """Conta com token que ainda não está no cadastro entra com nome = chave;
    o admin troca pelo nome do Unnichat ("Ivan Neto (Principal)")."""
    if not chaves:
        return 0
    with _get_users_engine().begin() as conn:
        res = conn.execute(text("INSERT INTO unnichat_conexoes (chave, nome) VALUES (:c, :c) ON CONFLICT (chave) DO NOTHING"),
                           [{"c": c} for c in chaves])
        return res.rowcount or 0


def ids_por_nome() -> dict[str, str]:
    with _get_users_engine().connect() as conn:
        return {normalizar_nome(r.nome): r.atendente_id for r in conn.execute(
            text("SELECT atendente_id, nome FROM unnichat_atendentes WHERE nome IS NOT NULL"))}


def gravar_atendentes(linhas: list[dict]) -> None:
    if not linhas:
        return
    with _get_users_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO unnichat_atendentes (atendente_id, nome, email, status, conexoes, atualizado_em)
            VALUES (:atendente_id, :nome, :email, :status, :conexoes, now())
            ON CONFLICT (atendente_id) DO UPDATE SET
                nome = EXCLUDED.nome, email = EXCLUDED.email, status = EXCLUDED.status,
                conexoes = (SELECT ARRAY(SELECT DISTINCT unnest(unnichat_atendentes.conexoes || EXCLUDED.conexoes))),
                atualizado_em = now()
        """).bindparams(bindparam("conexoes")), linhas)


def gravar_contato(linhas: list[dict], estado: dict) -> None:
    with _get_users_engine().begin() as conn:
        if linhas:
            conn.execute(text("""
                INSERT INTO unnichat_mensagens
                    (conexao, message_id, contact_id, enviada_em, direcao, origem, atendente_id, tipo, is_template)
                VALUES (:conexao, :message_id, :contact_id, :enviada_em, :direcao, :origem, :atendente_id, :tipo, :is_template)
                ON CONFLICT (conexao, message_id) DO UPDATE SET
                    origem = EXCLUDED.origem, atendente_id = EXCLUDED.atendente_id, tipo = EXCLUDED.tipo,
                    is_template = EXCLUDED.is_template, coletada_em = now()
            """), linhas)
        conn.execute(text("""
            INSERT INTO unnichat_contatos
                (conexao, contact_id, telefone, nome, atendente_id, ultima_msg_em, ultima_msg_de,
                 ultima_msg_cliente_em, atualizado_em)
            VALUES (:conexao, :contact_id, :telefone, :nome, :atendente_id,
                    :ultima_msg_em, :ultima_msg_de, :ultima_msg_cliente_em, now())
            ON CONFLICT (conexao, contact_id) DO UPDATE SET
                telefone = COALESCE(EXCLUDED.telefone, unnichat_contatos.telefone),
                nome = COALESCE(EXCLUDED.nome, unnichat_contatos.nome),
                atendente_id = EXCLUDED.atendente_id, ultima_msg_em = EXCLUDED.ultima_msg_em,
                ultima_msg_de = EXCLUDED.ultima_msg_de,
                ultima_msg_cliente_em = EXCLUDED.ultima_msg_cliente_em, atualizado_em = now()
        """), {"telefone": None, "nome": None, **estado})
