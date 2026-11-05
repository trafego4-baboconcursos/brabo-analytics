"""etl/acoes_agendadas.py: janela de execução, validação e execução única (sem chamar o Meta)."""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))

import acoes_agendadas as aa  # noqa: E402

BR = aa.BRASILIA


def _pedido(executar_em="2026-11-05T22:00", **acao):
    a = {"plataforma": "meta", "id": "120248677678120014", "nome": "AD304", "status": "PAUSED", **acao}
    return {"executar_em": executar_em, "acoes": [a]}


def _pasta(tmp_path, pedidos):
    for nome, conteudo in pedidos.items():
        (tmp_path / nome).write_text(json.dumps(conteudo) if not isinstance(conteudo, str) else conteudo,
                                     encoding="utf-8")
    return tmp_path


class MetaFalso:
    def __init__(self, recusa=()):
        self.status, self.recusa, self.posts = {}, set(recusa), []

    def post(self, id_, **dados):
        self.posts.append(id_)
        if id_ not in self.recusa:
            self.status[id_] = dados["status"]

    def get(self, id_, fields):
        return {"status": self.status.get(id_, "ACTIVE")}


def test_janela(tmp_path):
    pasta = _pasta(tmp_path, {"p.json": _pedido()})
    antes = dt.datetime(2026, 11, 5, 21, 59, tzinfo=BR)
    na_hora = dt.datetime(2026, 11, 5, 22, 0, tzinfo=BR)
    tarde = dt.datetime(2026, 11, 5, 22, aa.JANELA_MIN, tzinfo=BR)
    assert aa.pedidos_na_janela(pasta, antes) == ([], [])
    assert len(aa.pedidos_na_janela(pasta, na_hora)[0]) == 1
    assert aa.pedidos_na_janela(pasta, tarde) == ([], [])


def test_pedido_invalido_na_janela_vira_problema(tmp_path):
    pasta = _pasta(tmp_path, {"g.json": _pedido(plataforma="google"), "s.json": _pedido(status="DELETED"),
                              "i.json": _pedido(id="abc"), "lixo.json": "{nao e json"})
    rodar, problemas = aa.pedidos_na_janela(pasta, dt.datetime(2026, 11, 5, 22, 5, tzinfo=BR))
    assert rodar == [] and len(problemas) == 3


def test_executa_uma_vez_e_confere(tmp_path, monkeypatch):
    monkeypatch.setattr(aa, "_executados", set())
    _pasta(tmp_path, {"p.json": _pedido()})
    monkeypatch.setattr(aa, "PASTA_IMAGEM", tmp_path)
    meta = MetaFalso()
    agora = dt.datetime(2026, 11, 5, 22, 3, tzinfo=BR)
    r1 = aa.rodar_acoes(agora, baixar=False, meta=meta)
    r2 = aa.rodar_acoes(agora + dt.timedelta(minutes=5), baixar=False, meta=meta)
    assert r1["executados"] == ["p.json: 1/1 ok"] and r1["falhas"] == []
    assert r2["executados"] == [] and meta.posts == ["120248677678120014"]


def test_status_que_nao_pegou_vira_falha(tmp_path, monkeypatch):
    monkeypatch.setattr(aa, "_executados", set())
    _pasta(tmp_path, {"p.json": _pedido()})
    monkeypatch.setattr(aa, "PASTA_IMAGEM", tmp_path)
    r = aa.rodar_acoes(dt.datetime(2026, 11, 5, 22, 0, tzinfo=BR), baixar=False,
                       meta=MetaFalso(recusa={"120248677678120014"}))
    assert r["executados"] == ["p.json: 0/1 ok"] and "status lido ACTIVE" in r["falhas"][0]


def test_pedido_do_repositorio_e_valido():
    for f in (aa.PASTA_IMAGEM).glob("*.json"):
        aa.ler_pedido(f)
