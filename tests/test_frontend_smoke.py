"""Testes de fumaça do frontend.

Duas camadas:

1. ``test_templates_compilam`` — compila todos os templates Jinja com o
   ambiente real do app (filtros ``brl``/``num``/``pct`` registrados).
   Não precisa de banco; roda sempre, inclusive no CI.

2. ``TestPaginas`` (marker ``smoke``) — loga com as credenciais legadas e
   verifica que cada página autenticada responde 200. Exercita as rotas de
   ponta a ponta contra o banco configurado no ``.env``; no CI (sem banco)
   é excluído com ``pytest -m "not smoke"``.

As variáveis de ambiente são definidas ANTES de importar ``frontend.app``:
como ``load_dotenv`` não sobrescreve variáveis já presentes, o login legado
usa estas credenciais dummy mesmo quando existe um ``.env`` local.
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Carrega o .env local ANTES dos defaults: com .env presente (dev), valem as
# credenciais/banco reais; sem .env (CI), entram os dummies abaixo.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# O aquecimento grava debriefing_snapshot no banco REAL — o .env local aponta
# pra produção. Sem isto, rodar a suíte reescreve os snapshots de produção com o
# código do checkout, e quem abrir o dashboard vê números calculados por código
# não revisado. Aconteceu em 15/09/26 e custou horas de diagnóstico errado (ver
# docs/sistema/ARQUITETURA.md). Como efeito colateral bom, /debriefing passa a
# ser exercitado pelo caminho ao vivo, que é onde os 500 aparecem.
os.environ["PRE_WARM_CACHE"] = "false"

os.environ.setdefault("BRABO_USER", "smoke@teste.local")
os.environ.setdefault("BRABO_PASS", "smoke-senha-teste")
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "frontend" / "templates"

# Páginas autenticadas que todo lançamento deve conseguir abrir sem 500.
PAGINAS = [
    "/",
    "/calendario",
    "/funil",
    "/insights",
    "/debriefing",
    "/debriefing?modo=slides",  # modo apresentação (botão "Gerar PDF")
    "/comparativo",
    "/meta",
    "/google",
    "/criativos",
    "/leads",
    "/crm-campanhas",
    "/meta-audiences",
    "/google-audiences",
    "/pesquisas",
    "/typeform",  # link legado — redireciona pra /pesquisas
    "/vendas",
    "/hotmart",
    "/tmb",
    "/comparativo-v1-v2",
]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from frontend.app import app

    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture(scope="module")
def client_logado(client):
    resp = client.post(
        "/login",
        data={"email": os.environ["BRABO_USER"], "password": os.environ["BRABO_PASS"]},
    )
    assert resp.status_code == 303, f"login falhou: {resp.status_code}"
    assert resp.headers.get("location") == "/", "login não redirecionou para /"
    return client


def test_templates_compilam():
    """Todos os templates compilam no ambiente Jinja real do app."""
    from frontend.core import templates

    erros = []
    for tpl in sorted(TEMPLATES_DIR.glob("*.html")):
        try:
            templates.env.get_template(tpl.name)
        except Exception as e:  # noqa: BLE001 — queremos listar todos os erros
            erros.append(f"{tpl.name}: {e}")
    assert not erros, "Templates com erro de sintaxe:\n" + "\n".join(erros)


@pytest.mark.smoke
class TestPaginas:
    def test_sem_login_redireciona(self, client):
        resp = client.get("/")
        assert resp.status_code in (302, 303, 307), (
            f"página sem login deveria redirecionar, retornou {resp.status_code}"
        )
        assert "/login" in resp.headers.get("location", "")

    @pytest.mark.parametrize("pagina", PAGINAS)
    def test_pagina_responde_200(self, client_logado, pagina):
        resp = client_logado.get(pagina, follow_redirects=True)
        assert resp.status_code == 200, f"{pagina} retornou {resp.status_code}"
        assert "<html" in resp.text.lower(), f"{pagina} não retornou HTML"
