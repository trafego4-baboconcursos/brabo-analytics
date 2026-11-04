"""etl/verba_diaria.py: o que baixa, o que aplica hoje e o que vira falha (sem chamar Meta/Google)."""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))

import verba_diaria as vd  # noqa: E402

HOJE = dt.date(2026, 11, 5)


def _plano(aplicar_em="2026-11-05"):
    return {"aplicar_em": aplicar_em, "campanhas": [
        {"plataforma": "meta", "id": "123", "nome": "a", "valor": 100.0}]}


def _pasta(tmp_path, planos):
    for nome, conteudo in planos.items():
        (tmp_path / nome).write_text(json.dumps(conteudo) if not isinstance(conteudo, str) else conteudo,
                                     encoding="utf-8")
    return tmp_path


def test_so_planos_de_hoje(tmp_path):
    pasta = _pasta(tmp_path, {"hoje.json": _plano(), "ontem.json": _plano("2026-11-04"), "lixo.json": "{nao e json"})
    aplicar, problemas = vd.planos_do_dia(pasta, HOJE)
    assert [p.name for p in aplicar] == ["hoje.json"]
    assert problemas == []


def test_plano_de_hoje_invalido_vira_problema(tmp_path):
    ruim = {"aplicar_em": "2026-11-05", "campanhas": [{"plataforma": "meta", "id": "x", "valor": 1}]}
    aplicar, problemas = vd.planos_do_dia(_pasta(tmp_path, {"ruim.json": ruim}), HOJE)
    assert aplicar == [] and "ruim.json" in problemas[0]


def _get_fake(itens, conteudo=b"{}"):
    def get(url):
        return json.dumps(itens).encode() if url == vd.URL_LISTA else conteudo
    return get


def test_baixa_so_json_do_proprio_repositorio(tmp_path):
    ok = vd.PREFIXO_RAW + "main/config/orcamentos/a.json"
    itens = [
        {"name": "a.json", "type": "file", "download_url": ok},
        {"name": "b.json", "type": "file", "download_url": "https://evil.example/b.json"},
        {"name": "c.txt", "type": "file", "download_url": vd.PREFIXO_RAW + "main/c.txt"},
        {"name": "../d.json", "type": "file", "download_url": vd.PREFIXO_RAW + "main/d.json"},
        {"name": "sub", "type": "dir", "download_url": None},
    ]
    assert [p.name for p in vd.baixar_planos(tmp_path, _get_fake(itens))] == ["a.json"]


def test_lista_vazia_e_erro(tmp_path):
    with pytest.raises(RuntimeError):
        vd.baixar_planos(tmp_path, _get_fake([]))


def _com_imagem(monkeypatch, pasta):
    monkeypatch.setattr(vd, "PASTA_IMAGEM", pasta)


def test_aplica_plano_do_dia_e_registra_falha(tmp_path, monkeypatch):
    _com_imagem(monkeypatch, _pasta(tmp_path, {"a.json": _plano(), "b.json": _plano()}))
    chamados = []

    def rodar(cmd, **kw):
        chamados.append(cmd[-1])
        return SimpleNamespace(returncode=1 if cmd[-1].endswith("b.json") else 0, stdout="ok", stderr="boom")

    res = vd.aplicar_verba_do_dia(hoje=HOJE, baixar=False, rodar=rodar)
    assert [Path(c).name for c in chamados] == ["a.json", "b.json"]
    assert len(res["falhas"]) == 1 and "b.json" in res["falhas"][0]


def test_download_falho_cai_para_a_imagem(tmp_path, monkeypatch):
    _com_imagem(monkeypatch, _pasta(tmp_path, {"a.json": _plano()}))

    def get(url):
        raise OSError("sem rede")

    res = vd.aplicar_verba_do_dia(hoje=HOJE, get=get,
                                  rodar=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    assert res["planos"] == ["a.json"] and res["fonte"].startswith("imagem") and not res["falhas"]


def test_timeout_de_um_plano_nao_derruba_os_outros(tmp_path, monkeypatch):
    _com_imagem(monkeypatch, _pasta(tmp_path, {"a.json": _plano(), "b.json": _plano()}))

    def rodar(cmd, **kw):
        if cmd[-1].endswith("a.json"):
            raise subprocess.TimeoutExpired(cmd, 1)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    res = vd.aplicar_verba_do_dia(hoje=HOJE, baixar=False, rodar=rodar)
    assert len(res["falhas"]) == 1 and "a.json" in res["falhas"][0]


def _plano_valor(valor, aplicar_em="2026-11-05"):
    return {"aplicar_em": aplicar_em, "campanhas": [{"plataforma": "meta", "id": "123", "nome": "a", "valor": valor}]}


def test_campanha_acima_do_teto_e_barrada(tmp_path, monkeypatch):
    _com_imagem(monkeypatch, _pasta(tmp_path, {"a.json": _plano_valor(75000.0), "b.json": _plano_valor(7500.0)}))
    chamados = []
    res = vd.aplicar_verba_do_dia(hoje=HOJE, baixar=False, rodar=lambda c, **k: chamados.append(c[-1]) or
                                  SimpleNamespace(returncode=0, stdout="", stderr=""))
    assert [Path(c).name for c in chamados] == ["b.json"]
    assert len(res["falhas"]) == 1 and "BARRADO" in res["falhas"][0] and "a.json" in res["falhas"][0]


def test_soma_do_dia_acima_do_teto_barra_tudo(tmp_path, monkeypatch):
    monkeypatch.setenv("VERBA_MAX_DIA", "10000")
    _com_imagem(monkeypatch, _pasta(tmp_path, {"a.json": _plano_valor(7000.0), "b.json": _plano_valor(7000.0)}))
    chamados = []
    res = vd.aplicar_verba_do_dia(hoje=HOJE, baixar=False, rodar=lambda c, **k: chamados.append(c) or None)
    assert chamados == [] and "BARRADOS todos" in res["falhas"][0]


def test_tetos_aceitam_os_planos_reais_de_hoje():
    """Os tetos padrão não podem barrar o que já roda: maior campanha ~7,8 mil, maior dia ~90 mil."""
    max_camp, max_dia = vd.tetos()
    assert max_camp >= 1.5 * 7800 and max_dia >= 1.5 * 90000
