"""Partes puras do scripts/ajustar_verba_lista.py (o que decide SE e O QUE aplicar)."""
import datetime as dt
import json

import pytest

from scripts.ajustar_verba_lista import BRASILIA, deve_aplicar, hoje_brasilia, ler_plano


def _plano(tmp_path, **mudar):
    p = {"aplicar_em": "2026-10-09", "campanhas": [
        {"plataforma": "meta", "id": "123", "nome": "a", "valor": 100.0},
        {"plataforma": "google", "conta": "6482320788", "id": "456", "nome": "b", "valor": 50.5}]}
    p.update(mudar)
    f = tmp_path / "plano.json"
    f.write_text(json.dumps(p), encoding="utf-8")
    return f


def test_plano_valido(tmp_path):
    assert len(ler_plano(_plano(tmp_path))["campanhas"]) == 2


@pytest.mark.parametrize("mudanca", [
    {"aplicar_em": ""},
    {"campanhas": []},
    {"campanhas": [{"plataforma": "tiktok", "id": "1", "nome": "x", "valor": 1}]},
    {"campanhas": [{"plataforma": "meta", "id": "abc", "nome": "x", "valor": 1}]},
    {"campanhas": [{"plataforma": "google", "id": "1", "nome": "x", "valor": 1}]},          # Google sem conta
    {"campanhas": [{"plataforma": "meta", "id": "1", "nome": "x", "valor": 0}]},
    {"campanhas": [{"plataforma": "meta", "id": "1", "nome": "x", "valor": 5}] * 2},         # repetida
])
def test_plano_invalido(tmp_path, mudanca):
    with pytest.raises(ValueError):
        ler_plano(_plano(tmp_path, **mudanca))


def test_so_aplica_na_data_do_plano(tmp_path):
    plano = ler_plano(_plano(tmp_path))
    assert deve_aplicar(plano, dt.date(2026, 10, 9))
    assert not deve_aplicar(plano, dt.date(2026, 10, 10))
    assert not deve_aplicar(plano, dt.date(2027, 10, 9))   # o cron anual não repete a verba no ano seguinte
    assert deve_aplicar(plano, dt.date(2027, 10, 9), forcar=True)


def test_data_usa_fuso_de_brasilia():
    # 03:05 UTC de 09/10 = 00:05 de 09/10 em Brasília; 02:59 UTC ainda é 08/10 lá.
    assert hoje_brasilia(dt.datetime(2026, 10, 9, 3, 5, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 9)
    assert hoje_brasilia(dt.datetime(2026, 10, 9, 2, 59, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 8)
    assert BRASILIA.utcoffset(None) == dt.timedelta(hours=-3)


def test_plano_real_do_bv26_e_valido():
    plano = ler_plano("config/orcamentos/BV-26-captacao-v2.json")
    assert len(plano["campanhas"]) == 14
    assert round(sum(c["valor"] for c in plano["campanhas"]), 2) == 6230.74
