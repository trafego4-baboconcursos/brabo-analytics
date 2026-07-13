-- Migration 003: Sistema de usuários multi-tenant com controle de acesso
-- Execute no Supabase Studio (SQL Editor) ou via psql

-- Extensão necessária para gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Tabela de usuários ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'leitura'
                  CHECK (role IN ('admin', 'analista', 'trafego', 'leitura')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- ── Escopo de produto por usuário ──────────────────────────────────────────────
-- product = prefixo do código: 'PBB' | 'PES' | 'PI' | 'PERPETUO' | 'ALL'
CREATE TABLE IF NOT EXISTS user_product_access (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product TEXT NOT NULL,
    PRIMARY KEY (user_id, product)
);

-- ── Links de convite ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invite_links (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token       TEXT UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    email       TEXT,                        -- pré-preenche o campo e-mail
    role        TEXT NOT NULL DEFAULT 'leitura'
                CHECK (role IN ('admin', 'analista', 'trafego', 'leitura')),
    products    TEXT[] NOT NULL DEFAULT '{"ALL"}',
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    expires_at  TIMESTAMPTZ,                 -- NULL = sem expiração
    used_at     TIMESTAMPTZ,                 -- NULL = ainda válido
    used_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_users_email         ON users(email);
CREATE INDEX IF NOT EXISTS idx_invite_token        ON invite_links(token);
CREATE INDEX IF NOT EXISTS idx_user_product_user   ON user_product_access(user_id);
