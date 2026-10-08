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

from datetime import date  # noqa: E402
from types import SimpleNamespace as L  # noqa: E402

from frontend.db_readers.atendimento import agregar  # noqa: E402
from frontend.models import AtendimentoSummary  # noqa: E402


def test_agregar_por_conta_e_por_atendente():
    """Delta separa o período anterior; contas e atendentes somam certo, e o
    atendente lista em quais contas atendeu."""
    r = AtendimentoSummary(dias=2, inicio=date(2026, 10, 7), fim=date(2026, 10, 8))
    diario = [
        L(dia=date(2026, 10, 5), conexao="ivan", atendente_id="a1", enviadas=9, recebidas=9, templates=1),
        L(dia=date(2026, 10, 7), conexao="ivan", atendente_id="a1", enviadas=10, recebidas=8, templates=2),
        L(dia=date(2026, 10, 8), conexao="felipe", atendente_id="a1", enviadas=5, recebidas=4, templates=0),
        L(dia=date(2026, 10, 8), conexao="felipe", atendente_id=None, enviadas=3, recebidas=1, templates=3),
    ]
    abertas = [L(conexao="felipe", atendente_id="a2", abertas=2, aguardando=1, maior_espera=75)]
    nomes = {"a1": {"nome": "Ana", "status": "online"}, "a2": {"nome": "Bia", "status": "offline"}}
    agregar(r, diario, abertas, nomes, {"ivan": "Ivan Neto (Principal)", "felipe": "Felipe Graton (Principal)"})

    assert (r.enviadas, r.recebidas, r.templates) == (18, 13, 5)
    assert (r.enviadas_ant, r.recebidas_ant, r.templates_ant) == (9, 9, 1)
    assert [p["enviadas"] for p in r.serie] == [10, 8]
    contas = {c["nome"]: c for c in r.contas}
    assert contas["Felipe Graton (Principal)"]["total"] == 13
    assert contas["Felipe Graton (Principal)"]["atendentes"] == 1      # "sem atendente" não conta
    assert contas["Felipe Graton (Principal)"]["maior_espera"] == 75
    atend = {a["nome"]: a for a in r.atendentes}
    assert atend["Ana"]["contas"] == ["Felipe Graton (Principal)", "Ivan Neto (Principal)"]
    assert atend["Ana"]["total"] == 27
    assert atend["Bia"]["abertas"] == 2 and atend["Bia"]["total"] == 0
    assert atend["Automação / sem atendente"]["templates"] == 3


def test_agregar_hoje_por_hora_compara_com_ontem():
    from datetime import datetime
    r = AtendimentoSummary(dias=1, inicio=date(2026, 10, 8), fim=date(2026, 10, 8))
    h = lambda d, hh: datetime(2026, 10, d, hh)  # noqa: E731
    pontos = [h(8, x) for x in range(15)]   # 00h..14h
    diario = [
        L(dia=h(7, 9), conexao="ivan", atendente_id="a1", enviadas=4, recebidas=2, templates=1),
        L(dia=h(8, 9), conexao="ivan", atendente_id="a1", enviadas=6, recebidas=3, templates=0),
        L(dia=h(8, 14), conexao="ivan", atendente_id="a1", enviadas=1, recebidas=1, templates=1),
    ]
    agregar(r, diario, [], {}, {"ivan": "Ivan"}, None, pontos)
    assert (r.enviadas, r.enviadas_ant) == (7, 4)
    assert len(r.serie) == 15 and r.serie[9]["enviadas"] == 6 and r.serie[9]["rotulo"] == "09h"
    assert r.serie[0]["rotulo"] == "00h"


def test_agregar_com_conta_escolhida_mantem_a_comparacao_de_todas():
    r = AtendimentoSummary(dias=1, inicio=date(2026, 10, 8), fim=date(2026, 10, 8))
    diario = [
        L(dia=date(2026, 10, 8), conexao="ivan", atendente_id="a1", enviadas=10, recebidas=5, templates=1),
        L(dia=date(2026, 10, 8), conexao="felipe", atendente_id="a2", enviadas=7, recebidas=3, templates=2),
    ]
    abertas = [L(conexao="ivan", atendente_id="a1", abertas=4, aguardando=2, maior_espera=30),
               L(conexao="felipe", atendente_id="a2", abertas=6, aguardando=5, maior_espera=300)]
    nome = {"ivan": "Ivan", "felipe": "Felipe", "mateus": "Mateus"}
    agregar(r, diario, abertas, {}, nome, selecionada="felipe")

    assert (r.enviadas, r.recebidas, r.templates) == (7, 3, 2)
    assert (r.conversas_total, r.aguardando_total) == (6, 5)
    assert [a["nome"] for a in r.atendentes] == ["a2"]
    assert {c["chave"]: c["total"] for c in r.contas} == {"ivan": 15, "felipe": 10, "mateus": 0}


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
