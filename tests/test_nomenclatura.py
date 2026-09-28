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


# ── Black: a tag [base forte] não pode ganhar de [captação] nem de [alunos] ────
# No BV-26 a Base Forte é uma TRILHA de captação (evento gratuito com LP e pixel
# próprios) e o nome traz as duas tags. Enquanto "base forte" vinha antes no mapa,
# a mesma campanha saía Aquecimento no Meta e Captação no Google (que escreve
# `[base-forte]`, com hífen, e escapava do match) — e um público de Aluno era
# reportado como Super Quente. Ver MUDANCAS_BV-26.

@pytest.mark.parametrize(("nome", "etapa", "temp"), [
    ("[MA][trio][mateus][captação][base forte][alunos][imagem][BV-26][28.09.26]", "Captação", "Aluno"),
    ("[MA][mateus][captação][base forte][super quente][imagem][BV-26][28.09.26]", "Captação", "Super Quente"),
    ("[MA][mateus][captação][alunos][imagem][BV-26][05.10.26]", "Captação", "Aluno"),
    ("[MA][mateus][envolvimento][aquecimento][alunos][principal][BV-26][24.09.26]", "Aquecimento", "Aluno"),
    # BV-25: "Base Forte" era campanha de TRÁFEGO, aquecimento de verdade.
    ("[TRÁFEGO] Base Forte Longo Mateus - BV-25 - 10.10.25", "Aquecimento", "Super Quente"),
    ("[M] [CADASTRO] Captação INSS Alunos Principal - BV-25 - 27.10.25", "Captação", "Aluno"),
])
def test_black_base_forte_nao_atropela_captacao_nem_publico(nome, etapa, temp):
    from frontend.db_readers.nomenclatura import categorizar_campanha_meta
    e, t, _bucket, _seg = categorizar_campanha_meta(nome, launch_code="BV-26" if "BV-26" in nome else "BV-25")
    assert (e, t) == (etapa, temp)


def test_black_meta_e_google_classificam_igual():
    """O hífen do Google (`[base-forte]`) não pode dar resultado diferente do Meta."""
    from frontend.db_readers.nomenclatura import categorizar_campanha_google, categorizar_campanha_meta
    e_m, t_m, _b, _s = categorizar_campanha_meta(
        "[MA][felipe][captação][base forte][alunos][BV-26][28.09.26]", launch_code="BV-26")
    e_g, t_g, _sg = categorizar_campanha_google(
        "[GA][felipe][captação][base-forte][alunos][BV-26][28.09.26]", launch_code="BV-26")
    assert (e_m, t_m) == (e_g, t_g) == ("Captação", "Aluno")


@pytest.mark.parametrize(("nome", "code", "esperado"), [
    ("[MA][trio][mateus][captação][base forte][alunos][BV-26][28.09.26]", "BV-26", "Base Forte"),
    ("[MA][felipe][captação][base-forte][alunos][BV-26][28.09.26]", "BV-26", "Base Forte"),
    ("[MA][mateus][captação][alunos][imagem][BV-26][05.10.26]", "BV-26", "Black Vitalícia"),
    ("[M] [CADASTRO] Captação INSS Alunos Principal - BV-25", "BV-25", "Black Vitalícia"),
    # Aquecimento não tem trilha — nem quando o nome diz "Base Forte" (BV-25).
    ("[TRÁFEGO] Base Forte Longo Mateus - BV-25 - 10.10.25", "BV-25", None),
    ("[MA][mateus][envolvimento][aquecimento][alunos][BV-26]", "BV-26", None),
    # Fora da Black não existe trilha, mesmo na Captação.
    ("[MA][cadastro][captação][frio][reels][PES-SET-26][31.08.26]", "PES-SET-26", None),
])
def test_trilha_black(nome, code, esperado):
    from frontend.db_readers.nomenclatura import categorizar_campanha_meta
    from src.nomenclatura import trilha_black
    etapa = categorizar_campanha_meta(nome, launch_code=code)[0]
    assert trilha_black(nome, code, etapa) == esperado
