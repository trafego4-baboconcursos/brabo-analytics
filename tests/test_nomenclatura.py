"""Equivalência da classificação de campanhas por nome.

``frontend/db_readers/nomenclatura.py`` foi extraído de ``ads_meta`` e
``ads_google``, que mantinham cópias separadas dos mapas de bucket/modificador e
uma cópia quase igual do laço de classificação. A fixture foi gerada rodando a
implementação **antiga** sobre todos os 837 nomes de campanha distintos que
existem hoje no banco (Meta e Google), então este teste falha se a extração
mudar a classificação de qualquer campanha real.

Não precisa de banco: a fixture é um arquivo JSON versionado.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from frontend.db_readers.nomenclatura import (
    BUCKET_MAP,
    MODIFIER_MAP,
    categorizar_campanha_google,
    categorizar_campanha_meta,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "nomenclatura_campanhas.json").read_text(
        encoding="utf-8"
    )
)


def test_fixture_tem_massa_suficiente():
    """Evita que a fixture esvazie e o teste vire um no-op silencioso."""
    assert len(FIXTURE["meta"]) >= 900
    assert len(FIXTURE["google"]) >= 350


@pytest.mark.parametrize(
    "caso", FIXTURE["meta"], ids=[f"{c['nome'][:60]}|legacy={c['legacy']}" for c in FIXTURE["meta"]]
)
def test_meta_classifica_igual_a_implementacao_antiga(caso):
    obtido = list(categorizar_campanha_meta(caso["nome"], legacy=caso["legacy"]))
    assert obtido == caso["esperado"], (
        f"classificação mudou para {caso['nome']!r} (legacy={caso['legacy']})"
    )


@pytest.mark.parametrize(
    "caso", FIXTURE["google"], ids=[c["nome"][:60] for c in FIXTURE["google"]]
)
def test_google_classifica_igual_a_implementacao_antiga(caso):
    obtido = list(categorizar_campanha_google(caso["nome"]))
    assert obtido == caso["esperado"], f"classificação mudou para {caso['nome']!r}"


def test_bucket_e_modifier_sao_compartilhados():
    """O motivo de os mapas terem sido unificados: eram byte a byte iguais nos
    dois readers. Se alguém precisar diferenciá-los de novo, este teste cai e
    força a decisão a ser explícita."""
    assert BUCKET_MAP["p-max"] == "P-Max"
    assert MODIFIER_MAP["melhores-ads"] == "melhores ads"


@pytest.mark.parametrize(
    ("nome", "etapa_esperada"),
    [
        # "replay" tem que ganhar de "aula": a ordem dos mapas é significativa.
        ("[MA][REPLAY][AULA 2][QUENTE] PES-SET-26", "Replay"),
        ("[MA][AULA 2][QUENTE] PES-SET-26", "Aulas no Ar"),
    ],
)
def test_ordem_do_mapa_de_etapa_importa_no_meta(nome, etapa_esperada):
    assert categorizar_campanha_meta(nome)[0] == etapa_esperada
