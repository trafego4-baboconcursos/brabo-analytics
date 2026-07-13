"""
frontend/db_readers/users.py — Gestão de usuários e convites (banco operacional).
"""
from __future__ import annotations

import datetime
from sqlalchemy import text
from logger import get_logger
from frontend.db import _get_users_engine

logger = get_logger("db")

PRODUCT_LABELS: dict[str, str] = {
    "PBB": "Banco do Brasil",
    "PES": "TJ-SP",
    "PI":  "INSS",
    "PERPETUO": "Perpétuo",
    "ALL": "Todos",
}

ROLE_LABELS: dict[str, str] = {
    "admin":    "Admin",
    "analista": "Analista",
    "trafego":  "Tráfego",
    "leitura":  "Leitura",
}


def _users_table_exists() -> bool:
    try:
        with _get_users_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM users LIMIT 1"))
        return True
    except Exception:
        return False


def get_user_by_email(email: str) -> dict | None:
    with _get_users_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, email, name, password_hash, role, is_active FROM users WHERE LOWER(email) = LOWER(:email)"),
            {"email": email},
        ).fetchone()
        if not row:
            return None
        user_id = str(row[0])
        products = [
            r[0] for r in conn.execute(
                text("SELECT product FROM user_product_access WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchall()
        ]
    return {
        "id": user_id,
        "email": row[1],
        "name": row[2],
        "password_hash": row[3],
        "role": row[4],
        "is_active": row[5],
        "products": products or ["ALL"],
    }


def get_user_by_id(user_id: str) -> dict | None:
    with _get_users_engine().connect() as conn:
        row = conn.execute(
            text("SELECT id, email, name, role, is_active FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).fetchone()
        if not row:
            return None
        products = [
            r[0] for r in conn.execute(
                text("SELECT product FROM user_product_access WHERE user_id = :uid"),
                {"uid": str(row[0])},
            ).fetchall()
        ]
    return {
        "id": str(row[0]),
        "email": row[1],
        "name": row[2],
        "role": row[3],
        "is_active": row[4],
        "products": products or ["ALL"],
    }


def list_users() -> list[dict]:
    with _get_users_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT id, email, name, role, is_active, created_at, last_login_at FROM users ORDER BY created_at"
        )).fetchall()
        result = []
        for row in rows:
            uid = str(row[0])
            products = [
                r[0] for r in conn.execute(
                    text("SELECT product FROM user_product_access WHERE user_id = :uid"),
                    {"uid": uid},
                ).fetchall()
            ]
            result.append({
                "id": uid,
                "email": row[1],
                "name": row[2],
                "role": row[3],
                "role_label": ROLE_LABELS.get(row[3], row[3]),
                "is_active": row[4],
                "created_at": str(row[5])[:10] if row[5] else None,
                "last_login_at": str(row[6])[:10] if row[6] else None,
                "products": products or ["ALL"],
                "products_label": ", ".join(PRODUCT_LABELS.get(p, p) for p in (products or ["ALL"])),
            })
    return result


def create_user(email: str, name: str, password_hash: str, role: str,
                products: list[str], created_by: str | None = None) -> str:
    with _get_users_engine().connect() as conn:
        row = conn.execute(
            text("""
                INSERT INTO users (email, name, password_hash, role, created_by)
                VALUES (:email, :name, :hash, :role, :created_by)
                RETURNING id
            """),
            {"email": email, "name": name, "hash": password_hash,
             "role": role, "created_by": created_by},
        ).fetchone()
        user_id = str(row[0])
        for product in (products or ["ALL"]):
            conn.execute(
                text("INSERT INTO user_product_access (user_id, product) VALUES (:uid, :product) ON CONFLICT DO NOTHING"),
                {"uid": user_id, "product": product},
            )
        conn.commit()
    return user_id


def update_user(user_id: str, role: str | None = None, is_active: bool | None = None,
                products: list[str] | None = None) -> None:
    with _get_users_engine().connect() as conn:
        if role is not None:
            conn.execute(
                text("UPDATE users SET role = :role WHERE id = :uid"),
                {"role": role, "uid": user_id},
            )
        if is_active is not None:
            conn.execute(
                text("UPDATE users SET is_active = :active WHERE id = :uid"),
                {"active": is_active, "uid": user_id},
            )
        if products is not None:
            conn.execute(text("DELETE FROM user_product_access WHERE user_id = :uid"), {"uid": user_id})
            for product in (products or ["ALL"]):
                conn.execute(
                    text("INSERT INTO user_product_access (user_id, product) VALUES (:uid, :product) ON CONFLICT DO NOTHING"),
                    {"uid": user_id, "product": product},
                )
        conn.commit()


def update_last_login(user_id: str) -> None:
    try:
        with _get_users_engine().connect() as conn:
            conn.execute(text("UPDATE users SET last_login_at = NOW() WHERE id = :uid"), {"uid": user_id})
            conn.commit()
    except Exception:
        logger.debug("Falha ao atualizar last_login para user_id=%s", user_id)


def bootstrap_admin_if_needed(email: str, name: str, password_hash: str) -> bool:
    """Cria o primeiro admin se a tabela existir e estiver vazia. Retorna True se criou."""
    try:
        if not _users_table_exists():
            return False
        with _get_users_engine().connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            if count and count > 0:
                return False
        create_user(email, name, password_hash, "admin", ["ALL"], None)
        return True
    except Exception:
        logger.exception("Falha no bootstrap do admin")
        return False


def create_invite(role: str, products: list[str], email: str | None = None,
                  created_by: str | None = None, expires_hours: int | None = 72) -> dict:
    import uuid as _uuid
    token = str(_uuid.uuid4())
    with _get_users_engine().connect() as conn:
        row = conn.execute(
            text(
                "INSERT INTO invite_links (token, email, role, products, created_by, expires_at) "
                "VALUES (:token, :email, :role, :products, :created_by, "
                + ("NOW() + :h * INTERVAL '1 hour'" if expires_hours else "NULL")
                + ") RETURNING id, token, email, role, products, created_at, expires_at"
            ),
            {"token": token, "email": email, "role": role,
             "products": products or ["ALL"],
             "created_by": created_by,
             **( {"h": expires_hours} if expires_hours else {} )},
        ).fetchone()
        conn.commit()
    return {
        "id": str(row[0]),
        "token": row[1],
        "email": row[2],
        "role": row[3],
        "products": list(row[4]) if row[4] else ["ALL"],
        "created_at": str(row[5])[:16] if row[5] else None,
        "expires_at": str(row[6])[:16] if row[6] else None,
    }


def get_invite(token: str) -> dict | None:
    with _get_users_engine().connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, token, email, role, products, expires_at, used_at
                FROM invite_links
                WHERE token = :token
            """),
            {"token": token},
        ).fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "token": row[1],
        "email": row[2],
        "role": row[3],
        "products": list(row[4]) if row[4] else ["ALL"],
        "expires_at": row[5],
        "used_at": row[6],
        "is_used": row[6] is not None,
        "is_expired": row[5] is not None and row[5] < datetime.datetime.now(datetime.timezone.utc),
    }


def use_invite(token: str, user_id: str) -> None:
    with _get_users_engine().connect() as conn:
        conn.execute(
            text("UPDATE invite_links SET used_at = NOW(), used_by = :uid WHERE token = :token"),
            {"uid": user_id, "token": token},
        )
        conn.commit()


def list_invites() -> list[dict]:
    with _get_users_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT il.id, il.token, il.email, il.role, il.products,
                   il.created_at, il.expires_at, il.used_at,
                   u.name AS created_by_name
            FROM invite_links il
            LEFT JOIN users u ON u.id = il.created_by
            ORDER BY il.created_at DESC
        """)).fetchall()
    result = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for row in rows:
        expires_at = row[6]
        used_at    = row[7]
        result.append({
            "id": str(row[0]),
            "token": row[1],
            "email": row[2] or "—",
            "role": row[3],
            "role_label": ROLE_LABELS.get(row[3], row[3]),
            "products": list(row[4]) if row[4] else ["ALL"],
            "products_label": ", ".join(PRODUCT_LABELS.get(p, p) for p in (list(row[4]) if row[4] else ["ALL"])),
            "created_at": str(row[5])[:10] if row[5] else None,
            "expires_at": str(expires_at)[:10] if expires_at else "Sem expiração",
            "is_used": used_at is not None,
            "is_expired": expires_at is not None and expires_at < now,
            "created_by_name": row[8] or "sistema",
        })
    return result


def delete_invite(invite_id: str) -> None:
    with _get_users_engine().connect() as conn:
        conn.execute(text("DELETE FROM invite_links WHERE id = :id"), {"id": invite_id})
        conn.commit()
