-- Migration 011: Atendimento Comercial (Unnichat) — página /atendimento.
--
-- Rodar no Supabase > SQL Editor do banco OPERACIONAL (SUPABASE_USERS_URL), que
-- é o comercial_project. Decisão de 07/10/2026: é dado do time comercial, e o
-- banco analítico (marketing_project) é o que estourou o egress em setembro.
-- Idempotente.
--
-- Quem escreve nas tabelas: o coletor do Unnichat (serviço próprio no
-- EasyPanel, fora deste repo). O dashboard só lê, e só pela view agregada + as
-- duas tabelas pequenas (atendentes e contatos) — nunca varre
-- unnichat_mensagens linha a linha.
--
-- Texto das mensagens NÃO é guardado aqui: a página só conta. Conversa
-- completa é assunto do Backup Unnichat, outro sistema, que usa as tabelas
-- unnichat_message_backups / unnichat_backup_queue neste mesmo banco.

-- ── Papel "comercial" ─────────────────────────────────────────────────────────
-- Só enxerga /atendimento. Sem isto, o convite com esse papel é criado mas
-- quebra ao ser aceito (users_role_check recusa o INSERT).
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN ('admin', 'analista', 'trafego', 'leitura', 'comercial'));
ALTER TABLE invite_links DROP CONSTRAINT IF EXISTS invite_links_role_check;
ALTER TABLE invite_links ADD CONSTRAINT invite_links_role_check
    CHECK (role IN ('admin', 'analista', 'trafego', 'leitura', 'comercial'));

-- ── Tabelas do coletor ────────────────────────────────────────────────────────
-- Atendentes, como GET /attendants devolve. A conta do Unnichat é uma só para
-- todas as conexões (o atendente traz tenant.connections), então o id é global.
create table if not exists unnichat_atendentes (
    atendente_id  text primary key,
    nome          text,
    email         text,
    status        text,                 -- online | offline
    conexoes      text[],               -- INSS | TJ | BB | PERPETUO
    atualizado_em timestamptz not null default now()
);

-- Uma linha por mensagem, sem o conteúdo.
-- atendente_id em mensagem RECEBIDA = o atendente responsável pelo contato no
-- momento da coleta (a API não diz "para quem" o cliente escreveu). Em mensagem
-- ENVIADA = quem enviou, se a API informar; senão também o responsável.
-- Qual dos dois vale é o ponto "a validar" do briefing.
create table if not exists unnichat_mensagens (
    conexao       text not null,
    message_id    text not null,
    contact_id    text not null,
    enviada_em    timestamptz not null,
    direcao       text not null check (direcao in ('enviada', 'recebida')),
    atendente_id  text,
    tipo          text,                 -- "type" cru da API (text, audio, template…)
    is_template   boolean not null default false,
    coletada_em   timestamptz not null default now(),
    primary key (conexao, message_id)
);

create index if not exists idx_unnichat_mensagens_enviada_em
    on unnichat_mensagens (enviada_em);

-- Estado atual de cada conversa: alimenta "conversas abertas" e "aguardando
-- resposta". aberta = null enquanto não soubermos como a API indica conversa
-- finalizada; a página trata null como "aberta, a validar".
create table if not exists unnichat_contatos (
    conexao        text not null,
    contact_id     text not null,
    telefone       text,
    nome           text,
    atendente_id   text,                -- responsável atual (GET /contact/{id}/assign)
    ultima_msg_em  timestamptz,
    ultima_msg_de  text check (ultima_msg_de in ('cliente', 'atendente')),
    aberta         boolean,
    atualizado_em  timestamptz not null default now(),
    primary key (conexao, contact_id)
);

create index if not exists idx_unnichat_contatos_abertos
    on unnichat_contatos (conexao) where aberta is not false;

-- O que a página lê para KPIs, série diária e ranking: uma linha por
-- dia × conexão × atendente. Dia no fuso de São Paulo, como o resto do painel.
create or replace view vw_unnichat_atendimento_diario as
select
    (enviada_em at time zone 'America/Sao_Paulo')::date as dia,
    conexao,
    atendente_id,
    count(*) filter (where direcao = 'enviada')                 as enviadas,
    count(*) filter (where direcao = 'recebida')                as recebidas,
    count(*) filter (where direcao = 'enviada' and is_template) as templates
from unnichat_mensagens
group by 1, 2, 3;
