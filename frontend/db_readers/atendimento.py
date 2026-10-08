"""
frontend/db_readers/atendimento.py — Atendimento Comercial do Unnichat (/atendimento).

Lê o banco COMERCIAL (`SUPABASE_USERS_URL`), não o analítico: as tabelas de
`src/db/migrations/011_atendimento_unnichat.sql` moram lá, alimentadas pelo
coletor do Unnichat (serviço próprio no EasyPanel, fora deste repo).

Para não repetir o egress de setembro, a página nunca lê `unnichat_mensagens`
linha a linha: KPIs, série diária e rankings saem da view agregada
`vw_unnichat_atendimento_diario`, e as conversas abertas de `unnichat_contatos`
(uma linha por conversa, com limite).

Conversa aberta = o cliente escreveu nas últimas 24h (janela de atendimento do
WhatsApp). O Unnichat não marca conversa finalizada e mantém o responsável por
semanas, então o tempo é o único sinal confiável (teste de 08/10/2026).

Conta = conexão do Unnichat = um número de WhatsApp (Ivan Neto (Principal),
Felipe Graton (B1)…), cadastrada em `unnichat_conexoes`. O que importa pro
Comercial é em qual conta o atendimento aconteceu (Mateus, 08/10/2026), não o
produto: toda conta ativa aparece pra quem tem acesso à página.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

from logger import get_logger
from frontend.db import _get_users_engine
from frontend.models import AtendimentoSummary

logger = get_logger("db")

_TZ = ZoneInfo("America/Sao_Paulo")

PERIODOS = (7, 15, 30)
_LIMITE_CONVERSAS = 200
_ZERO = {"enviadas": 0, "recebidas": 0, "templates": 0}
_SEM_ABERTAS = {"abertas": 0, "aguardando": 0, "maior_espera": None}


def _tabelas_existem(conn) -> bool:
    row = conn.execute(text(
        "SELECT to_regclass('public.vw_unnichat_atendimento_diario') IS NOT NULL"
        "   AND to_regclass('public.unnichat_contatos') IS NOT NULL"
        "   AND to_regclass('public.unnichat_atendentes') IS NOT NULL"
        "   AND to_regclass('public.unnichat_conexoes') IS NOT NULL"
    )).scalar()
    return bool(row)


def _somar(alvo: dict, r) -> None:
    alvo["enviadas"] += r.enviadas
    alvo["recebidas"] += r.recebidas
    alvo["templates"] += r.templates


def agregar(
    resumo: AtendimentoSummary, diario, abertas, nomes: dict, nome_conexao: dict,
    selecionada: str | None = None,
) -> None:
    """Monta totais, série, ranking por atendente e por conta.

    `diario`: linhas (dia, conexao, atendente_id, enviadas, recebidas, templates)
    desde o início do período ANTERIOR (para o delta). `abertas`: linhas
    (conexao, atendente_id, abertas, aguardando, maior_espera) de agora.

    A comparação por conta usa sempre TODAS as contas (é o seletor da página);
    totais, série e ranking por atendente usam só a `selecionada`, ou todas
    quando nenhuma foi escolhida.
    """
    def conta(r) -> bool:
        return selecionada is None or r.conexao == selecionada

    inicio, dias = resumo.inicio, resumo.dias
    serie = {inicio + timedelta(days=i): {"enviadas": 0, "recebidas": 0} for i in range(dias)}
    por_atendente: dict = {}
    por_conta: dict = {}
    for r in diario:
        if r.dia >= inicio:
            _somar(por_conta.setdefault(r.conexao, {**_ZERO, "atendentes": set()}), r)
            if r.atendente_id:
                por_conta[r.conexao]["atendentes"].add(r.atendente_id)
        if not conta(r):
            continue
        if r.dia < inicio:
            resumo.enviadas_ant += r.enviadas
            resumo.recebidas_ant += r.recebidas
            resumo.templates_ant += r.templates
            continue
        resumo.enviadas += r.enviadas
        resumo.recebidas += r.recebidas
        resumo.templates += r.templates
        serie[r.dia]["enviadas"] += r.enviadas
        serie[r.dia]["recebidas"] += r.recebidas
        a = por_atendente.setdefault(r.atendente_id, {**_ZERO, "contas": set()})
        _somar(a, r)
        a["contas"].add(r.conexao)
    resumo.serie = [{"dia": d, **v} for d, v in serie.items()]

    abertas_atendente: dict = {}
    abertas_conta: dict = {}
    for r in abertas:
        alvos = [(r.conexao, abertas_conta)]
        if conta(r):
            alvos.append((r.atendente_id, abertas_atendente))
            por_atendente.setdefault(r.atendente_id, {**_ZERO, "contas": set()})["contas"].add(r.conexao)
            resumo.conversas_total += r.abertas
            resumo.aguardando_total += r.aguardando
        for chave, alvo in alvos:
            o = alvo.setdefault(chave, dict(_SEM_ABERTAS))
            o["abertas"] += r.abertas
            o["aguardando"] += r.aguardando
            if r.maior_espera is not None:
                o["maior_espera"] = max(o["maior_espera"] or 0, r.maior_espera)

    for aid, m in por_atendente.items():
        info = nomes.get(aid, {})
        resumo.atendentes.append({
            "nome": info.get("nome") or ("Automação / sem atendente" if not aid else aid),
            "status": info.get("status"),
            "enviadas": m["enviadas"], "recebidas": m["recebidas"], "templates": m["templates"],
            "total": m["enviadas"] + m["recebidas"],
            "contas": sorted(nome_conexao.get(c, c) for c in m["contas"]),
            **abertas_atendente.get(aid, _SEM_ABERTAS),
        })
    resumo.atendentes.sort(key=lambda a: (a["total"], a["abertas"]), reverse=True)

    for chave in set(por_conta) | set(abertas_conta) | set(nome_conexao):
        m = por_conta.get(chave, {**_ZERO, "atendentes": set()})
        resumo.contas.append({
            "chave": chave,
            "nome": nome_conexao.get(chave, chave),
            "enviadas": m["enviadas"], "recebidas": m["recebidas"], "templates": m["templates"],
            "total": m["enviadas"] + m["recebidas"],
            "atendentes": len(m["atendentes"]),
            **abertas_conta.get(chave, _SEM_ABERTAS),
        })
    resumo.contas.sort(key=lambda c: (c["total"], c["abertas"]), reverse=True)


def read_atendimento(dias: int, conexao: str | None = None, hoje: date | None = None) -> AtendimentoSummary:
    """`conexao` = chave da conta escolhida no filtro; chave desconhecida é ignorada."""
    dias = dias if dias in PERIODOS else PERIODOS[0]
    hoje = hoje or datetime.now(_TZ).date()
    inicio = hoje - timedelta(days=dias - 1)
    inicio_ant = inicio - timedelta(days=dias)
    resumo = AtendimentoSummary(dias=dias, inicio=inicio, fim=hoje)

    with _get_users_engine().connect() as conn:
        if not _tabelas_existem(conn):
            logger.info("read_atendimento: tabelas do Unnichat ainda não criadas no banco comercial")
            return resumo
        resumo.tabelas_ok = True

        resumo.conexoes = [tuple(r) for r in conn.execute(text(
            "SELECT chave, nome FROM unnichat_conexoes WHERE ativa ORDER BY nome"
        ))]
        nome_conexao = dict(resumo.conexoes)
        todas = list(nome_conexao)
        if not todas:
            return resumo
        if conexao in nome_conexao:
            resumo.conexao = conexao
        escolhidas = [resumo.conexao] if resumo.conexao else todas

        params = {"conexoes": todas, "inicio_ant": inicio_ant, "fim": hoje}
        so_escolhidas = {**params, "conexoes": escolhidas}
        expanding = [bindparam("conexoes", expanding=True)]

        nomes = {
            r.atendente_id: {"nome": r.nome or r.atendente_id, "status": r.status}
            for r in conn.execute(text("SELECT atendente_id, nome, status FROM unnichat_atendentes"))
        }

        diario = conn.execute(text(
            """
            SELECT dia, conexao, atendente_id,
                   SUM(enviadas)::int AS enviadas, SUM(recebidas)::int AS recebidas,
                   SUM(templates)::int AS templates
              FROM vw_unnichat_atendimento_diario
             WHERE conexao IN :conexoes AND dia BETWEEN :inicio_ant AND :fim
             GROUP BY dia, conexao, atendente_id
            """
        ).bindparams(*expanding), params).fetchall()

        abertas = conn.execute(text(
            """
            SELECT conexao, atendente_id,
                   COUNT(*)::int AS abertas,
                   COUNT(*) FILTER (WHERE ultima_msg_de = 'cliente')::int AS aguardando,
                   (MAX(EXTRACT(EPOCH FROM now() - ultima_msg_em) / 60)
                        FILTER (WHERE ultima_msg_de = 'cliente'))::int AS maior_espera
              FROM unnichat_contatos
             WHERE conexao IN :conexoes AND ultima_msg_cliente_em > now() - interval '24 hours'
             GROUP BY conexao, atendente_id
            """
        ).bindparams(*expanding), params).fetchall()

        conversas = conn.execute(text(
            """
            SELECT conexao, contact_id, telefone, nome, atendente_id,
                   ultima_msg_em, ultima_msg_de
              FROM unnichat_contatos
             WHERE conexao IN :conexoes AND ultima_msg_cliente_em > now() - interval '24 hours'
             ORDER BY (ultima_msg_de = 'cliente') DESC, ultima_msg_em ASC NULLS LAST
             LIMIT :limite
            """
        ).bindparams(*expanding), {**so_escolhidas, "limite": _LIMITE_CONVERSAS}).fetchall()

        contagem = conn.execute(text(
            """
            SELECT COUNT(*) FILTER (WHERE ultima_msg_de = 'cliente'
                                      AND ultima_msg_em < now() - interval '1 hour') AS aguardando_1h,
                   MAX(atualizado_em) AS ultima_coleta
              FROM unnichat_contatos
             WHERE conexao IN :conexoes AND ultima_msg_cliente_em > now() - interval '24 hours'
            """
        ).bindparams(*expanding), so_escolhidas).one()

    if not diario and not abertas:
        return resumo
    resumo.coleta_ativa = True
    agregar(resumo, diario, abertas, nomes, nome_conexao, resumo.conexao)

    agora = datetime.now(_TZ)
    for c in conversas:
        espera = None
        if c.ultima_msg_de == "cliente" and c.ultima_msg_em:
            espera = max(0, int((agora - c.ultima_msg_em).total_seconds() // 60))
        info = nomes.get(c.atendente_id, {})
        resumo.conversas.append({
            "conexao": nome_conexao.get(c.conexao, c.conexao),
            "contato": c.nome or c.telefone or c.contact_id,
            "telefone": c.telefone,
            "atendente": info.get("nome") or ("Sem atendente" if not c.atendente_id else c.atendente_id),
            "ultima_msg_de": c.ultima_msg_de,
            "ultima_msg_em": c.ultima_msg_em,
            "espera_min": espera,
        })

    resumo.aguardando_1h = contagem.aguardando_1h or 0
    # Fuso de São Paulo aqui, não no template: o servidor roda em UTC.
    resumo.ultima_coleta = contagem.ultima_coleta.astimezone(_TZ) if contagem.ultima_coleta else None
    return resumo
