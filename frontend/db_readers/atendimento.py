"""
frontend/db_readers/atendimento.py — Atendimento Comercial do Unnichat (/atendimento).

Lê o banco COMERCIAL (`SUPABASE_USERS_URL`), não o analítico: as tabelas de
`src/db/migrations/011_atendimento_unnichat.sql` moram lá, alimentadas pelo
coletor do Unnichat (serviço próprio no EasyPanel, fora deste repo).

Para não repetir o egress de setembro, a página nunca lê `unnichat_mensagens`
linha a linha: KPIs, série diária e ranking saem da view agregada
`vw_unnichat_atendimento_diario`, e as conversas abertas de `unnichat_contatos`
(uma linha por conversa, com limite).

Conexão do Unnichat ↔ produto do usuário: INSS = PI, TJ = PES, BB = PBB,
PERPETUO = PERPETUO. O mesmo `user_product_access` que filtra os lançamentos
filtra as conexões aqui.
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

# Ordem de exibição = ordem dos produtos no resto do painel.
CONEXAO_POR_PRODUTO: dict[str, str] = {
    "PI": "INSS",
    "PES": "TJ",
    "PBB": "BB",
    "PERPETUO": "PERPETUO",
}
CONEXAO_LABELS: dict[str, str] = {
    "INSS": "INSS",
    "TJ": "TJ",
    "BB": "BB",
    "PERPETUO": "Perpétuo",
}
PERIODOS = (7, 15, 30)
_LIMITE_CONVERSAS = 200


def conexoes_do_usuario(products: list[str] | None) -> list[str]:
    """Conexões que o usuário pode ver, a partir dos produtos liberados pra ele."""
    products = products or ["ALL"]
    if "ALL" in products:
        return list(CONEXAO_POR_PRODUTO.values())
    return [c for p, c in CONEXAO_POR_PRODUTO.items() if p in products]


def _tabelas_existem(conn) -> bool:
    row = conn.execute(text(
        "SELECT to_regclass('public.vw_unnichat_atendimento_diario') IS NOT NULL"
        "   AND to_regclass('public.unnichat_contatos') IS NOT NULL"
        "   AND to_regclass('public.unnichat_atendentes') IS NOT NULL"
    )).scalar()
    return bool(row)


def read_atendimento(dias: int, conexoes: list[str], hoje: date | None = None) -> AtendimentoSummary:
    dias = dias if dias in PERIODOS else PERIODOS[0]
    hoje = hoje or datetime.now(_TZ).date()
    inicio = hoje - timedelta(days=dias - 1)
    inicio_ant = inicio - timedelta(days=dias)
    resumo = AtendimentoSummary(dias=dias, inicio=inicio, fim=hoje)
    if not conexoes:
        return resumo

    params = {"conexoes": list(conexoes), "inicio": inicio, "inicio_ant": inicio_ant, "fim": hoje}
    expanding = [bindparam("conexoes", expanding=True)]

    with _get_users_engine().connect() as conn:
        if not _tabelas_existem(conn):
            logger.info("read_atendimento: tabelas do Unnichat ainda não criadas no banco comercial")
            return resumo

        nomes = {
            r.atendente_id: {"nome": r.nome or r.atendente_id, "status": r.status}
            for r in conn.execute(text(
                "SELECT atendente_id, nome, status FROM unnichat_atendentes"
            ))
        }

        diario = conn.execute(text(
            """
            SELECT dia, atendente_id,
                   SUM(enviadas)::int AS enviadas, SUM(recebidas)::int AS recebidas,
                   SUM(templates)::int AS templates
              FROM vw_unnichat_atendimento_diario
             WHERE conexao IN :conexoes AND dia BETWEEN :inicio_ant AND :fim
             GROUP BY dia, atendente_id
            """
        ).bindparams(*expanding), params).fetchall()

        conversas = conn.execute(text(
            """
            SELECT conexao, contact_id, telefone, nome, atendente_id,
                   ultima_msg_em, ultima_msg_de, aberta
              FROM unnichat_contatos
             WHERE conexao IN :conexoes AND aberta IS NOT FALSE
             ORDER BY (ultima_msg_de = 'cliente') DESC, ultima_msg_em ASC NULLS LAST
             LIMIT :limite
            """
        ).bindparams(*expanding), {**params, "limite": _LIMITE_CONVERSAS}).fetchall()

        abertas_por = {
            r.atendente_id: {"abertas": r.abertas, "aguardando": r.aguardando, "maior_espera": r.maior_espera}
            for r in conn.execute(text(
                """
                SELECT atendente_id,
                       COUNT(*)::int AS abertas,
                       COUNT(*) FILTER (WHERE ultima_msg_de = 'cliente')::int AS aguardando,
                       (MAX(EXTRACT(EPOCH FROM now() - ultima_msg_em) / 60)
                            FILTER (WHERE ultima_msg_de = 'cliente'))::int AS maior_espera
                  FROM unnichat_contatos
                 WHERE conexao IN :conexoes AND aberta IS NOT FALSE
                 GROUP BY atendente_id
                """
            ).bindparams(*expanding), params)
        }

        contagem = conn.execute(text(
            """
            SELECT COUNT(*) AS abertas,
                   COUNT(*) FILTER (WHERE ultima_msg_de = 'cliente') AS aguardando,
                   COUNT(*) FILTER (WHERE ultima_msg_de = 'cliente'
                                      AND ultima_msg_em < now() - interval '1 hour') AS aguardando_1h,
                   BOOL_OR(aberta IS NOT NULL) AS aberta_conhecida,
                   MAX(atualizado_em) AS ultima_coleta
              FROM unnichat_contatos
             WHERE conexao IN :conexoes AND aberta IS NOT FALSE
            """
        ).bindparams(*expanding), params).one()

    if not diario and not contagem.abertas:
        return resumo
    resumo.coleta_ativa = True

    # ── KPIs, série e ranking ─────────────────────────────────────────────────
    serie = {inicio + timedelta(days=i): {"enviadas": 0, "recebidas": 0} for i in range(dias)}
    por_atendente: dict[str | None, dict] = {}
    for r in diario:
        if r.dia >= inicio:
            resumo.enviadas += r.enviadas
            resumo.recebidas += r.recebidas
            resumo.templates += r.templates
            ponto = serie[r.dia]
            ponto["enviadas"] += r.enviadas
            ponto["recebidas"] += r.recebidas
            a = por_atendente.setdefault(r.atendente_id, {"enviadas": 0, "recebidas": 0, "templates": 0})
            a["enviadas"] += r.enviadas
            a["recebidas"] += r.recebidas
            a["templates"] += r.templates
        else:
            resumo.enviadas_ant += r.enviadas
            resumo.recebidas_ant += r.recebidas
            resumo.templates_ant += r.templates
    resumo.serie = [{"dia": d, **v} for d, v in serie.items()]

    agora = datetime.now(_TZ)
    for c in conversas:
        espera = None
        if c.ultima_msg_de == "cliente" and c.ultima_msg_em:
            espera = max(0, int((agora - c.ultima_msg_em).total_seconds() // 60))
        info = nomes.get(c.atendente_id, {})
        resumo.conversas.append({
            "conexao": CONEXAO_LABELS.get(c.conexao, c.conexao),
            "contato": c.nome or c.telefone or c.contact_id,
            "telefone": c.telefone,
            "atendente": info.get("nome") or ("Sem atendente" if not c.atendente_id else c.atendente_id),
            "ultima_msg_de": c.ultima_msg_de,
            "ultima_msg_em": c.ultima_msg_em,
            "espera_min": espera,
        })

    for aid in set(por_atendente) | set(abertas_por):
        info = nomes.get(aid, {})
        m = por_atendente.get(aid, {"enviadas": 0, "recebidas": 0, "templates": 0})
        o = abertas_por.get(aid, {"abertas": 0, "aguardando": 0, "maior_espera": None})
        resumo.atendentes.append({
            "nome": info.get("nome") or ("Sem atendente" if not aid else aid),
            "status": info.get("status"),
            "total": m["enviadas"] + m["recebidas"],
            **m, **o,
        })
    resumo.atendentes.sort(key=lambda a: a["total"], reverse=True)

    resumo.conversas_total = contagem.abertas or 0
    resumo.aguardando_total = contagem.aguardando or 0
    resumo.aguardando_1h = contagem.aguardando_1h or 0
    resumo.aberta_conhecida = bool(contagem.aberta_conhecida)
    # Fuso de São Paulo aqui, não no template: o servidor roda em UTC.
    resumo.ultima_coleta = contagem.ultima_coleta.astimezone(_TZ) if contagem.ultima_coleta else None
    return resumo
