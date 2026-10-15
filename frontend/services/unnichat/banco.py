"""
Gravação do coletor do Unnichat no banco comercial (SUPABASE_USERS_URL).

Usa a mesma engine do site (`_get_users_engine`): o guard de somente-leitura
dela só barra hotmart/tmb, e o coletor faz poucas operações curtas, então não
vale abrir outro pool no banco comercial. Tabelas da migration 011
(src/db/migrations/011_atendimento_unnichat.sql).
"""
from __future__ import annotations

from psycopg2.extras import execute_values
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
        # Aviso do webhook e pedido do botão "Atualizar agora" passam na frente
        # da recoleta automática, que põe centenas de conversas na fila de uma vez.
        return [dict(r._mapping) for r in conn.execute(text("""
            UPDATE unnichat_atendimento_fila f SET status = 'processando', atualizado_em = now()
              FROM (SELECT id FROM unnichat_atendimento_fila WHERE status = 'pendente'
                     ORDER BY (origem IN ('webhook', 'manual')) DESC, id
                     LIMIT :n FOR UPDATE SKIP LOCKED) p
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


def pedir_atualizacao(conexoes: list[str], horas: int) -> int:
    """Botão "Atualizar agora" da página: põe na fila, com prioridade, as
    conversas das `conexoes` com mensagem nas últimas `horas`. Conversa que já
    estava esperando na fila pela recoleta é promovida em vez de duplicada.
    Devolve quantas conversas desse pedido ainda faltam processar."""
    params = {"conexoes": conexoes, "horas": horas}
    recentes = """
        SELECT conexao, contact_id FROM unnichat_contatos
         WHERE conexao IN :conexoes AND ultima_msg_em > now() - make_interval(hours => :horas)
    """
    with _get_users_engine().begin() as conn:
        conn.execute(text(f"""
            INSERT INTO unnichat_atendimento_fila (conexao, contact_id, telefone, nome, origem)
            SELECT k.conexao, k.contact_id, k.telefone, k.nome, 'manual'
              FROM unnichat_contatos k JOIN ({recentes}) r USING (conexao, contact_id)
            ON CONFLICT (conexao, contact_id) WHERE status IN ('pendente', 'processando') DO NOTHING
        """).bindparams(bindparam("conexoes", expanding=True)), params)
        conn.execute(text(f"""
            UPDATE unnichat_atendimento_fila f SET origem = 'manual'
              FROM ({recentes}) r
             WHERE f.status = 'pendente' AND f.origem = 'recoleta'
               AND f.conexao = r.conexao AND f.contact_id = r.contact_id
        """).bindparams(bindparam("conexoes", expanding=True)), params)
    return atualizacao_pendente(conexoes)


def atualizacao_pendente(conexoes: list[str]) -> int:
    """Quantas conversas pedidas pelo botão ainda não foram processadas."""
    with _get_users_engine().connect() as conn:
        return conn.execute(text("""
            SELECT COUNT(*) FROM unnichat_atendimento_fila
             WHERE origem = 'manual' AND status IN ('pendente', 'processando') AND conexao IN :conexoes
        """).bindparams(bindparam("conexoes", expanding=True)), {"conexoes": conexoes}).scalar() or 0


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


def gravar_contato(linhas: list[dict], estado: dict, fila_id: int | None = None) -> None:
    """Grava as mensagens e o estado da conversa; com `fila_id`, dá baixa no
    item da fila na mesma transação (uma ida ao banco a menos por conversa)."""
    with _get_users_engine().begin() as conn:
        if linhas:
            # Uma ida ao banco por conversa (execute_values), não uma por mensagem:
            # com o banco em us-west-2, gravar mensagem a mensagem levava ~3,5 s por
            # conversa e travava o botão "Atualizar agora" e a recoleta (13/10/2026).
            # O WHERE do DO UPDATE pula a mensagem que não mudou, então reler a
            # conversa a cada 30 min não regrava nada à toa.
            with conn.connection.cursor() as cur:
                execute_values(cur, """
                    INSERT INTO unnichat_mensagens
                        (conexao, message_id, contact_id, enviada_em, direcao, origem, atendente_id, tipo, is_template)
                    VALUES %s
                    ON CONFLICT (conexao, message_id) DO UPDATE SET
                        origem = EXCLUDED.origem, atendente_id = EXCLUDED.atendente_id, tipo = EXCLUDED.tipo,
                        is_template = EXCLUDED.is_template, coletada_em = now()
                    WHERE (unnichat_mensagens.origem, unnichat_mensagens.atendente_id,
                           unnichat_mensagens.tipo, unnichat_mensagens.is_template)
                          IS DISTINCT FROM (EXCLUDED.origem, EXCLUDED.atendente_id, EXCLUDED.tipo, EXCLUDED.is_template)
                """, [(l["conexao"], l["message_id"], l["contact_id"], l["enviada_em"], l["direcao"],
                       l["origem"], l["atendente_id"], l["tipo"], l["is_template"]) for l in linhas],
                    page_size=1000)
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
        if fila_id is not None:
            conn.execute(text("UPDATE unnichat_atendimento_fila SET status = 'feito', erro = NULL, atualizado_em = now() WHERE id = :id"),
                         {"id": fila_id})
