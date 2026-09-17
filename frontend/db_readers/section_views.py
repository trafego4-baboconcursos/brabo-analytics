"""
frontend/db_readers/section_views.py — Visualizações de seções por página
(banco operacional).

Guarda o que o painel "Seções" do design system monta no navegador: ordem das
seções, quais estão ocultas, quais estão recolhidas e os apelidos/tags que a
pessoa deu a cada uma. Até 17/09/26 isso vivia só no localStorage — cada
navegador com a sua, e a "Padrão" era a ordem crua do template, só editável
mexendo no HTML.

Dois escopos:
  - 'global': visualizações da equipe. A marcada com `is_padrao` é a que
    qualquer pessoa abre na primeira visita à página. Só admin/analista
    escreve nelas.
  - 'user':   visualizações pessoais, uma coleção por e-mail.

A tabela é criada pela migration 010 (rodada à mão no SQL Editor, como o resto
do schema). Enquanto ela não existir, tudo aqui responde "indisponível" em vez
de estourar — o front cai de volta no localStorage sozinho.
"""
from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import text

from frontend.db import _get_users_engine
from logger import get_logger

logger = get_logger("db")

# Quem pode mexer nas visualizações da equipe (inclusive na "Padrão").
PAPEIS_GLOBAL = {"admin", "analista"}

_tabela_ok = False
_ultima_checagem = 0.0
_INTERVALO_RECHECAGEM = 60.0


class SectionViewErro(Exception):
    """Pedido inválido ou sem permissão — o chamador vira em 4xx."""


def _tabela_existe() -> bool:
    """A migration 010 já rodou?

    Só o SIM fica em cache. O NÃO é rechecado a cada minuto de propósito: um
    tropeço de conexão não pode desligar o recurso até o próximo deploy — foi
    o que aconteceu no primeiro teste, com a tabela já criada e o app jurando
    que não existia."""
    global _tabela_ok, _ultima_checagem
    if _tabela_ok:
        return True
    agora = time.monotonic()
    if agora - _ultima_checagem < _INTERVALO_RECHECAGEM:
        return False
    _ultima_checagem = agora
    try:
        with _get_users_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM section_views LIMIT 1"))
        _tabela_ok = True
    except Exception as e:
        logger.warning("section_views indisponível (%s) — rode src/db/migrations/010_section_views.sql", e)
    return _tabela_ok


_COLUNAS = "id, nome, escopo, user_email, is_padrao, estado, atualizado_em, atualizado_por"


def _linha(row) -> dict[str, Any]:
    estado = row[5]
    if isinstance(estado, str):           # driver sem decode automático de jsonb
        estado = json.loads(estado)
    return {
        "id":             int(row[0]),
        "nome":           row[1],
        "escopo":         row[2],
        "user_email":     row[3],
        "is_padrao":      bool(row[4]),
        "estado":         estado,
        "atualizado_em":  row[6].isoformat() if row[6] else None,
        "atualizado_por": row[7],
    }


def list_section_views(pagina: str, email: str) -> dict[str, Any]:
    """Visualizações visíveis para essa pessoa: todas as globais + as dela."""
    if not _tabela_existe():
        return {"disponivel": False, "views": []}
    with _get_users_engine().connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT {_COLUNAS} FROM section_views "
                " WHERE pagina = :pagina "
                "   AND (escopo = 'global' OR LOWER(user_email) = LOWER(:email)) "
                " ORDER BY is_padrao DESC, escopo, LOWER(nome)"
            ),
            {"pagina": pagina, "email": email or ""},
        ).fetchall()
    return {"disponivel": True, "views": [_linha(r) for r in rows]}


def save_section_view(pagina: str, escopo: str, nome: str, estado: dict,
                      user: dict, is_padrao: bool = False) -> dict[str, Any]:
    """Cria ou sobrescreve (mesmo nome, mesmo escopo) uma visualização."""
    if not _tabela_existe():
        raise SectionViewErro("Visualizações no banco ainda não estão disponíveis (migration 010 não rodou).")
    nome = (nome or "").strip()
    if not nome:
        raise SectionViewErro("Dê um nome à visualização.")
    if len(nome) > 60:
        raise SectionViewErro("Nome muito longo (máx. 60 caracteres).")
    if escopo not in ("global", "user"):
        raise SectionViewErro("Escopo inválido.")
    if not isinstance(estado, dict) or not estado.get("order"):
        raise SectionViewErro("Estado da visualização vazio.")
    if escopo == "global" and user.get("role") not in PAPEIS_GLOBAL:
        raise SectionViewErro("Só admin ou analista salva visualização da equipe.")
    if is_padrao and escopo != "global":
        raise SectionViewErro("Só visualização da equipe pode ser a padrão.")

    params = {
        "pagina": pagina,
        "escopo": escopo,
        "email": "" if escopo == "global" else (user.get("email") or ""),
        "nome": nome,
        "estado": json.dumps(estado),
        "autor": user.get("email") or "",
        "padrao": bool(is_padrao),
    }
    with _get_users_engine().connect() as conn:
        if is_padrao:
            conn.execute(
                text("UPDATE section_views SET is_padrao = FALSE WHERE pagina = :pagina AND is_padrao"),
                {"pagina": pagina},
            )
        row = conn.execute(
            text(
                "INSERT INTO section_views (pagina, escopo, user_email, nome, estado, is_padrao, atualizado_por) "
                "VALUES (:pagina, :escopo, :email, :nome, CAST(:estado AS JSONB), :padrao, :autor) "
                "ON CONFLICT (pagina, escopo, user_email, LOWER(nome)) DO UPDATE SET "
                "    estado = EXCLUDED.estado, "
                # salvar por cima nunca tira o título de padrão de quem já é
                "    is_padrao = section_views.is_padrao OR EXCLUDED.is_padrao, "
                "    nome = EXCLUDED.nome, "
                "    atualizado_em = NOW(), "
                "    atualizado_por = EXCLUDED.atualizado_por "
                f"RETURNING {_COLUNAS}"
            ),
            params,
        ).fetchone()
        conn.commit()
    return _linha(row)


def _carregar(conn, view_id: int):
    return conn.execute(
        text(f"SELECT {_COLUNAS}, pagina FROM section_views WHERE id = :id"),
        {"id": view_id},
    ).fetchone()


def _exigir_permissao(row, user: dict) -> None:
    escopo, dono = row[2], (row[3] or "")
    if escopo == "global":
        if user.get("role") not in PAPEIS_GLOBAL:
            raise SectionViewErro("Só admin ou analista mexe nas visualizações da equipe.")
    elif dono.lower() != (user.get("email") or "").lower():
        raise SectionViewErro("Essa visualização é de outra pessoa.")


def rename_section_view(view_id: int, nome: str, user: dict) -> dict[str, Any]:
    if not _tabela_existe():
        raise SectionViewErro("Visualizações no banco ainda não estão disponíveis.")
    nome = (nome or "").strip()
    if not nome:
        raise SectionViewErro("O nome não pode ficar vazio.")
    if len(nome) > 60:
        raise SectionViewErro("Nome muito longo (máx. 60 caracteres).")
    with _get_users_engine().connect() as conn:
        row = _carregar(conn, view_id)
        if not row:
            raise SectionViewErro("Visualização não encontrada.")
        _exigir_permissao(row, user)
        try:
            novo = conn.execute(
                text(
                    "UPDATE section_views SET nome = :nome, atualizado_em = NOW(), atualizado_por = :autor "
                    f"WHERE id = :id RETURNING {_COLUNAS}"
                ),
                {"id": view_id, "nome": nome, "autor": user.get("email") or ""},
            ).fetchone()
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "section_views_uniq" in str(e):
                raise SectionViewErro("Já existe uma visualização com esse nome.") from e
            raise
    return _linha(novo)


def set_section_view_padrao(view_id: int, user: dict) -> dict[str, Any]:
    """Promove uma visualização da equipe a padrão da página (troca a anterior)."""
    if not _tabela_existe():
        raise SectionViewErro("Visualizações no banco ainda não estão disponíveis.")
    if user.get("role") not in PAPEIS_GLOBAL:
        raise SectionViewErro("Só admin ou analista define a padrão da página.")
    with _get_users_engine().connect() as conn:
        row = _carregar(conn, view_id)
        if not row:
            raise SectionViewErro("Visualização não encontrada.")
        if row[2] != "global":
            raise SectionViewErro("Só visualização da equipe pode ser a padrão.")
        conn.execute(
            text("UPDATE section_views SET is_padrao = FALSE "
                 " WHERE pagina = :pagina AND is_padrao AND id <> :id"),
            {"pagina": row[8], "id": view_id},
        )
        novo = conn.execute(
            text(
                "UPDATE section_views SET is_padrao = TRUE, atualizado_em = NOW(), atualizado_por = :autor "
                f"WHERE id = :id RETURNING {_COLUNAS}"
            ),
            {"id": view_id, "autor": user.get("email") or ""},
        ).fetchone()
        conn.commit()
    return _linha(novo)


def delete_section_view(view_id: int, user: dict) -> None:
    if not _tabela_existe():
        raise SectionViewErro("Visualizações no banco ainda não estão disponíveis.")
    with _get_users_engine().connect() as conn:
        row = _carregar(conn, view_id)
        if not row:
            return
        _exigir_permissao(row, user)
        conn.execute(text("DELETE FROM section_views WHERE id = :id"), {"id": view_id})
        conn.commit()
