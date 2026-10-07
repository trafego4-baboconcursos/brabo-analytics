"""Página /atendimento (Atendimento Comercial do Unnichat) — o que dá pra testar sem banco.

O papel "comercial" é o único que não enxerga o marketing: a home leva direto
pro atendimento e qualquer outra página devolve 403. A leitura em si depende do
banco comercial e fica no smoke (``tests/test_frontend_smoke.py``).
"""
import os

import pytest

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

from frontend.db_readers.atendimento import conexoes_do_usuario  # noqa: E402


@pytest.mark.parametrize("products, esperado", [
    (["ALL"], ["INSS", "TJ", "BB", "PERPETUO"]),
    (None, ["INSS", "TJ", "BB", "PERPETUO"]),
    (["PI"], ["INSS"]),
    (["PES", "PBB"], ["TJ", "BB"]),
    (["PERPETUO"], ["PERPETUO"]),
    (["XYZ"], []),
])
def test_conexoes_do_usuario(products, esperado):
    assert conexoes_do_usuario(products) == esperado


@pytest.fixture(scope="module")
def client_comercial():
    from fastapi.testclient import TestClient

    from frontend.app import app
    from frontend.auth import _sign_session

    with TestClient(app, follow_redirects=False) as c:
        c.cookies.set("session_token", _sign_session("u-teste", "comercial", ["PI"], "comercial@teste.local"))
        yield c


def test_comercial_home_vai_pro_atendimento(client_comercial):
    resp = client_comercial.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/atendimento"


@pytest.mark.parametrize("pagina", ["/calendario", "/meta", "/vendas", "/settings", "/debriefing"])
def test_comercial_nao_ve_marketing(client_comercial, pagina):
    assert client_comercial.get(pagina).status_code == 403


def test_atendimento_liberado_so_pros_papeis_certos():
    from frontend.auth import ROUTE_PERMISSIONS

    assert sorted(ROUTE_PERMISSIONS["/atendimento"]) == ["admin", "analista", "comercial"]
