"""
frontend/db_readers/comercial.py — cadastros do comissionamento do time comercial.

Banco operacional (`_get_users_engine`). Leitura nunca faz DDL: `criar_tabelas()`
é chamado só por quem grava (script de carga, gestão de cadastros).
"""
from __future__ import annotations

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_users_engine
from frontend.services.comercial.modelos import Cadastros  # noqa: F401  (reexportado)
from frontend.services.comercial.tabelas import Participacao, RegraPercentual, ValorBase

logger = get_logger("db")

DDL = [
    """CREATE TABLE IF NOT EXISTS comercial_vendedores (
        codigo text PRIMARY KEY, nome text NOT NULL, user_id integer NULL,
        ativo boolean NOT NULL DEFAULT true, criado_auto boolean NOT NULL DEFAULT false)""",
    """CREATE TABLE IF NOT EXISTS comercial_regras_percentual (
        id integer PRIMARY KEY, plataforma text NOT NULL, modalidade text NOT NULL,
        tipo text NOT NULL, pct numeric NOT NULL, vendedor_codigo text NULL,
        vigente_de date NOT NULL, vigente_ate date NULL,
        criado_por text NULL, criado_em timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS comercial_valores_base (
        id integer PRIMARY KEY, plataforma text NOT NULL, valor_cobrado numeric NOT NULL,
        valor_base numeric NOT NULL, categoria text NOT NULL DEFAULT '',
        vigente_de date NOT NULL, vigente_ate date NULL,
        criado_por text NULL, criado_em timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS comercial_participacoes (
        id integer PRIMARY KEY, beneficiario text NOT NULL, pct_ativa numeric NOT NULL,
        pct_reativa numeric NOT NULL, vigente_de date NOT NULL, vigente_ate date NULL,
        criado_por text NULL, criado_em timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS comercial_atribuicoes (
        transacao text PRIMARY KEY, plataforma text NULL, vendedor_codigo text NOT NULL,
        origem text NOT NULL,   -- 'planilha' | 'reivindicacao' | 'gestor'
        status text NOT NULL,   -- 'aprovada' | 'pendente' | 'recusada'
        pedido_por text NULL, aprovado_por text NULL,
        criado_em timestamptz NOT NULL DEFAULT now(), motivo text NULL)""",
    """CREATE TABLE IF NOT EXISTS comercial_historico (
        id bigserial PRIMARY KEY, tabela text NOT NULL, registro_id text NOT NULL,
        campo text NOT NULL, antes text NULL, depois text NULL, por text NULL,
        em timestamptz NOT NULL DEFAULT now())""",
]


def criar_tabelas() -> None:
    """Cria as tabelas comercial_* (idempotente). Só quem grava chama."""
    with _get_users_engine().begin() as conn:
        for ddl in DDL:
            conn.execute(text(ddl))


def ler_cadastros() -> Cadastros:
    """Cadastros vigentes. Tabela ausente -> Cadastros vazio + warning (sem DDL)."""
    try:
        with _get_users_engine().connect() as conn:
            vend = conn.execute(text("SELECT codigo, nome FROM comercial_vendedores")).fetchall()
            regras = conn.execute(text(
                "SELECT id, plataforma, modalidade, tipo, pct, vendedor_codigo, vigente_de, vigente_ate "
                "FROM comercial_regras_percentual ORDER BY id")).fetchall()
            bases = conn.execute(text(
                "SELECT id, plataforma, valor_cobrado, valor_base, categoria, vigente_de, vigente_ate "
                "FROM comercial_valores_base ORDER BY id")).fetchall()
            parts = conn.execute(text(
                "SELECT id, beneficiario, pct_ativa, pct_reativa, vigente_de, vigente_ate "
                "FROM comercial_participacoes ORDER BY id")).fetchall()
            atrib = conn.execute(text(
                "SELECT transacao, vendedor_codigo FROM comercial_atribuicoes "
                "WHERE status = 'aprovada'")).fetchall()
    except Exception as e:
        if "does not exist" in str(e) and "comercial_" in str(e):
            logger.warning("ler_cadastros: tabelas comercial_* ainda não existem; devolvendo vazio")
            return Cadastros()
        logger.exception("ler_cadastros: falha")
        raise
    return Cadastros(
        vendedores={r[0]: r[1] for r in vend},
        regras=[RegraPercentual(*r) for r in regras],
        valores_base=[ValorBase(*r) for r in bases],
        participacoes=[Participacao(*r) for r in parts],
        atribuicoes={r[0]: r[1] for r in atrib},
    )


def garantir_vendedor(codigo: str) -> str:
    """Devolve o nome do vendedor; se não existir, cria 'Vendedor N' (criado_auto=True)."""
    codigo = codigo.upper()
    numero = codigo.removeprefix("AT")
    with _get_users_engine().begin() as conn:
        conn.execute(text(
            "INSERT INTO comercial_vendedores (codigo, nome, ativo, criado_auto) "
            "VALUES (:c, :n, true, true) ON CONFLICT (codigo) DO NOTHING"),
            {"c": codigo, "n": f"Vendedor {numero}"})
        return conn.execute(text("SELECT nome FROM comercial_vendedores WHERE codigo = :c"),
                            {"c": codigo}).scalar_one()
