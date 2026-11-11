"""Link de nova senha (11/11/26): token assinado, uso único (morre quando a senha muda),
validade, rota pública /senha/{token} e geração só por admin. Tema visível para todos."""
from __future__ import annotations

import uuid

import pytest

from frontend import auth

UID = str(uuid.uuid4())


def _user(hash_="hash-antigo", ativo=True):
    return {"id": UID, "email": "rh1@teste.local", "name": "Joyce", "is_active": ativo, "password_hash": hash_}


def test_token_vale_e_morre_quando_a_senha_muda():
    tok = auth.gerar_token_senha(UID, "hash-antigo", agora=1000)
    assert auth.ler_token_senha(tok, lambda i: _user(), agora=1001)["email"] == "rh1@teste.local"
    assert auth.ler_token_senha(tok, lambda i: _user("hash-novo"), agora=1001) is None  # já usado


def test_token_vence_e_nao_aceita_adulteracao_nem_inativo():
    tok = auth.gerar_token_senha(UID, "h", horas=48, agora=0)
    assert auth.ler_token_senha(tok, lambda i: _user("h"), agora=48 * 3600 + 1) is None
    uid, exp, sig = tok.rsplit(".", 2)
    assert auth.ler_token_senha(f"{uid}.{int(exp) + 9999}.{sig}", lambda i: _user("h"), agora=1) is None
    assert auth.ler_token_senha(tok, lambda i: _user("h", ativo=False), agora=1) is None
    assert auth.ler_token_senha("lixo", lambda i: _user("h"), agora=1) is None
    assert auth.ler_token_senha(tok, lambda i: None, agora=1) is None


@pytest.fixture
def cli(monkeypatch):
    from fastapi.testclient import TestClient

    from frontend.app import app
    from frontend.db_readers import users

    estado = {"hash": "hash-antigo", "gravado": []}
    monkeypatch.setattr(users, "get_user_para_senha",
                        lambda i: _user(estado["hash"]) if i == UID else None)

    def gravar(i, h):
        estado["hash"] = h
        estado["gravado"].append(i)
    monkeypatch.setattr(users, "update_password", gravar)
    with TestClient(app, follow_redirects=False) as c:
        c.estado = estado
        yield c


def test_rota_publica_troca_a_senha_uma_vez(cli):
    tok = auth.gerar_token_senha(UID, "hash-antigo")
    r = cli.get(f"/senha/{tok}")
    assert r.status_code == 200 and "rh1@teste.local" in r.text and 'action="/senha/' in r.text
    r = cli.post(f"/senha/{tok}", data={"password": "12345678", "confirm_password": "123"})
    assert "não coincidem" in r.text and cli.estado["gravado"] == []
    r = cli.post(f"/senha/{tok}", data={"password": "curta", "confirm_password": "curta"})
    assert "8 caracteres" in r.text and cli.estado["gravado"] == []
    r = cli.post(f"/senha/{tok}", data={"password": "senhanova1", "confirm_password": "senhanova1"})
    assert r.status_code == 303 and r.headers["location"] == "/login?senha=1"
    assert cli.estado["gravado"] == [UID]
    from frontend.core import _verify_password
    assert _verify_password("senhanova1", cli.estado["hash"])
    r = cli.get(f"/senha/{tok}")  # mesmo link de novo: morto
    assert "Link indisponível" in r.text and 'action="/senha/' not in r.text
    r = cli.post(f"/senha/{tok}", data={"password": "outrasenha", "confirm_password": "outrasenha"})
    assert cli.estado["gravado"] == [UID]


def test_login_mostra_aviso_de_senha_salva(cli):
    assert "Senha salva" in cli.get("/login?senha=1").text


def test_link_so_admin_gera(cli):
    from frontend.auth import _sign_session
    cli.cookies.set("session_token", _sign_session("u1", "comercial", ["ALL"], "x@teste.local"))
    r = cli.post(f"/api/users/{UID}/link-senha")
    assert r.status_code == 403
    cli.cookies.set("session_token", _sign_session("u2", "admin", ["ALL"], "adm@teste.local"))
    r = cli.post(f"/api/users/{UID}/link-senha")
    d = r.json()
    assert r.status_code == 200 and d["ok"] and "/senha/" in d["url"] and d["email"] == "rh1@teste.local"
    assert auth.ler_token_senha(d["url"].rsplit("/senha/", 1)[1], lambda i: _user(cli.estado["hash"]))
    assert cli.post(f"/api/users/{uuid.uuid4()}/link-senha").status_code == 404


def test_tema_fora_do_bloco_de_admin():
    from pathlib import Path
    src = Path("frontend/templates/base.html").read_text(encoding="utf-8")
    admin_ini = src.index("{% if current_user and current_user.role == 'admin' %}")
    admin_fim = src.index("{% endif %}", src.index('id="bs-etl-last-sync"'))
    tema = src.index('id="bs-theme-picker"')
    assert not (admin_ini < tema < admin_fim)  # o seletor não está mais só para admin
    assert src.rindex("{% if current_user %}", 0, tema) > admin_fim
