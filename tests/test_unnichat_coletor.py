"""Coletor do Unnichat dentro do site: regras de mapeamento (formato real das
mensagens) e o webhook que a automação do Unnichat chama."""
import os

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
from datetime import datetime, timezone

import pytest

from frontend.services.unnichat.mapeamento import (
    evento_de_atribuicao, extrair_atendente_atual, montar_linhas, normalizar_nome, parse_data,
)

IDS = {"edileia melo": "a-edi", "jheniffer alves": "a-jhe", "izabela nogueira": "a-iza"}


def msg(i, quem, tipo="message", texto="", minuto=0):
    return {"id": f"m{i}", "senderBy": quem, "type": tipo, "message": texto,
            "date": f"2026-09-18T17:{minuto:02d}:00.000Z"}


def test_parse_data():
    assert parse_data("2026-09-18T17:04:23.706Z") == datetime(2026, 9, 18, 17, 4, 23, 706000, tzinfo=timezone.utc)
    assert parse_data(1_758_214_800_000).tzinfo is not None
    assert parse_data("") is None and parse_data("lixo") is None


def test_normalizar_nome():
    assert normalizar_nome("  Edilêia   MELO ") == "edileia melo"


@pytest.mark.parametrize("texto, esperado", [
    ("Conversa atribuída automaticamente ao Edilêia Melo", ("para", "Edilêia Melo")),
    ("Conversa atribuída pela ação em massa para Izabela Nogueira", ("para", "Izabela Nogueira")),
    ("A conversa foi transferida por Jheniffer Alves", ("mudou", None)),
    ("A conversa foi atribuída por Izabela Nogueira", ("mudou", None)),
    ("Lembrete para o contato: 3", None),
])
def test_evento_de_atribuicao(texto, esperado):
    assert evento_de_atribuicao(texto) == esperado


def test_atendente_por_trecho_da_conversa():
    mensagens = [
        msg(1, "user", "template", minuto=1),                    # automação, antes de atribuir
        msg(2, "contact", minuto=2),
        msg(3, "platform", "info", "Conversa atribuída automaticamente ao Edilêia Melo", 3),
        msg(4, "user", minuto=4),
        msg(5, "contact", minuto=5),
        msg(6, "platform", "info", "A conversa foi transferida por Edilêia Melo", 6),
        msg(7, "user", minuto=7),
        msg(8, "contact", minuto=8),
    ]
    linhas, estado = montar_linhas("TJ", "c1", list(reversed(mensagens)), IDS, atendente_atual="a-jhe")
    por_id = {l["message_id"]: l for l in linhas}

    assert "m3" not in por_id and "m6" not in por_id          # sistema não conta
    assert por_id["m1"]["atendente_id"] is None and por_id["m1"]["is_template"]
    assert por_id["m2"]["atendente_id"] is None
    assert por_id["m4"]["atendente_id"] == "a-edi" and por_id["m4"]["direcao"] == "enviada"
    assert por_id["m5"]["atendente_id"] == "a-edi" and por_id["m5"]["direcao"] == "recebida"
    # depois da transferência sem destino: o responsável atual
    assert por_id["m7"]["atendente_id"] == "a-jhe" and por_id["m8"]["atendente_id"] == "a-jhe"
    assert estado["ultima_msg_de"] == "cliente" and estado["atendente_id"] == "a-jhe"
    assert estado["ultima_msg_cliente_em"] == parse_data("2026-09-18T17:08:00.000Z")


def test_transferencia_no_meio_vira_desconhecido_ate_nova_atribuicao():
    mensagens = [
        msg(1, "platform", "info", "Conversa atribuída automaticamente ao Edilêia Melo", 1),
        msg(2, "platform", "info", "A conversa foi transferida por Edilêia Melo", 2),
        msg(3, "user", minuto=3),
        msg(4, "platform", "info", "Conversa atribuída pela ação em massa para Izabela Nogueira", 4),
        msg(5, "user", minuto=5),
    ]
    linhas, _ = montar_linhas("INSS", "c2", mensagens, IDS, atendente_atual="a-iza")
    por_id = {l["message_id"]: l for l in linhas}
    assert por_id["m3"]["atendente_id"] is None
    assert por_id["m5"]["atendente_id"] == "a-iza"


def test_nome_desconhecido_cai_no_responsavel_atual_se_for_o_ultimo_trecho():
    mensagens = [
        msg(1, "platform", "info", "Conversa atribuída automaticamente ao Pessoa Nova", 1),
        msg(2, "user", minuto=2),
    ]
    linhas, _ = montar_linhas("BB", "c3", mensagens, IDS, atendente_atual="a-nova")
    assert linhas[0]["atendente_id"] == "a-nova"


def test_conversa_sem_evento_fica_com_o_responsavel_atual():
    linhas, _ = montar_linhas("TJ", "c5", [msg(1, "contact", minuto=1), msg(2, "user", minuto=2)], IDS, "a-edi")
    assert [l["atendente_id"] for l in linhas] == ["a-edi", "a-edi"]


def test_origem_automacao_nao_conta_pro_atendente():
    mensagens = [
        msg(1, "platform", "info", "Conversa atribuída automaticamente ao Edilêia Melo", 1),
        {**msg(2, "user", "button", minuto=2), "origin": "automation"},
        {**msg(3, "user", "template", minuto=3), "origin": "schedule"},
        msg(4, "user", minuto=4),
        msg(5, "contact", minuto=5),
    ]
    linhas, _ = montar_linhas("TJ", "c6", mensagens, IDS, "a-edi")
    por_id = {l["message_id"]: l for l in linhas}
    assert (por_id["m2"]["origem"], por_id["m2"]["atendente_id"]) == ("automacao", None)
    assert (por_id["m3"]["origem"], por_id["m3"]["atendente_id"]) == ("agendada", "a-edi")
    assert (por_id["m4"]["origem"], por_id["m4"]["atendente_id"]) == ("atendente", "a-edi")
    assert por_id["m5"]["origem"] == "cliente"


def test_conversa_vazia():
    linhas, estado = montar_linhas("BB", "c4", [], IDS, None)
    assert linhas == [] and estado["ultima_msg_em"] is None and estado["ultima_msg_de"] is None
    assert estado["ultima_msg_cliente_em"] is None


@pytest.mark.parametrize("resposta, esperado", [
    ({"data": {"attendantId": "a1"}}, "a1"),
    ({"data": {"id": "a2", "name": "X"}}, "a2"),
    ({"data": {"attendant": {"id": "a3"}}}, "a3"),
    ({"data": [{"userId": "a4"}]}, "a4"),
    ({"data": None}, None),
    (None, None),
])
def test_extrair_atendente_atual(resposta, esperado):
    assert extrair_atendente_atual(resposta) == esperado


# ── Webhook ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def cliente_webhook(monkeypatch):
    from fastapi.testclient import TestClient

    from frontend.app import app
    from frontend.services.unnichat import banco

    with TestClient(app, follow_redirects=False) as c:
        # Depois do startup: o coletor não liga no teste, só o webhook é exercitado.
        monkeypatch.setenv("UNNICHAT_TOKEN_IVAN_NETO_PRINCIPAL", "tok")
        monkeypatch.setenv("UNNICHAT_WEBHOOK_SECRET", "segredo-teste")
        chamadas = []
        monkeypatch.setattr(banco, "enfileirar", lambda itens, origem: chamadas.append((itens, origem)) or 1)
        yield c, chamadas


def test_webhook_sem_segredo_recusa(cliente_webhook):
    c, chamadas = cliente_webhook
    assert c.post("/api/unnichat/webhook/ivan_neto_principal", json={"id": "x"}).status_code == 401
    assert c.post("/api/unnichat/webhook/ivan_neto_principal", json={"id": "x"},
                  headers={"X-Webhook-Secret": "errado"}).status_code == 401
    assert chamadas == []


def test_webhook_conta_sem_token_recusa(cliente_webhook):
    c, _ = cliente_webhook
    r = c.post("/api/unnichat/webhook/outra_conta", json={"id": "x"}, headers={"X-Webhook-Secret": "segredo-teste"})
    assert r.status_code == 400


def test_webhook_enfileira_contato(cliente_webhook):
    c, chamadas = cliente_webhook
    r = c.post("/api/unnichat/webhook/IVAN_NETO_PRINCIPAL",
               json={"contact": {"id": "c-123", "phoneNumber": "5511999990000", "name": "Fulano"}},
               headers={"X-Webhook-Secret": "segredo-teste"})
    assert r.status_code == 200 and r.json()["enfileirado"] is True
    assert chamadas == [([{"conexao": "ivan_neto_principal", "contact_id": "c-123",
                           "telefone": "5511999990000", "nome": "Fulano"}], "webhook")]


def test_status_do_coletor_so_admin():
    from frontend.auth import ROUTE_PERMISSIONS
    assert ROUTE_PERMISSIONS["/api/unnichat/status"] == ["admin"]
