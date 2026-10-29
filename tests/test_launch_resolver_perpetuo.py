"""Classificação das campanhas do perpétuo (Mestre em Questões) pelo nome."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))

from launch_resolver import resolve_perpetuo_or_distribuicao_code  # noqa: E402


@pytest.mark.parametrize("nome, esperado", [
    ("[GA][INSS][compra][frio][p-max][02.07.26]", "PERPETUO-PMQ-INSS"),
    ("[MA][TJ][compra][frio][29.05.26]", "PERPETUO-PMQ-TJSP"),
    ("[GA][BB][compra][frio][p-max][02.07.2026]", "PERPETUO-PMQ-PBB"),
    # search de remarketing do perpétuo: [quente] também é perpétuo
    ("[GA][INSS][compra][quente][search][08.05.2026]", "PERPETUO-PMQ-INSS"),
    ("[GA][TJSP][compra][quente][search][02.07.2026]", "PERPETUO-PMQ-TJSP"),
    ("[GA][BB][compra][quente][search][02.07.2026]", "PERPETUO-PMQ-PBB"),
])
def test_compra_sem_codigo_e_perpetuo(nome, esperado):
    assert resolve_perpetuo_or_distribuicao_code(nome) == esperado


@pytest.mark.parametrize("nome", [
    "[MA][INSS][compra][quente][PI-NOV-26]",       # tem código de lançamento
    "[MA][INSS][captação][frio][02.07.26]",        # não é [compra]
    "[GA][compra][frio][search][02.07.26]",        # sem produto
])
def test_nao_e_perpetuo(nome):
    assert resolve_perpetuo_or_distribuicao_code(nome) is None


@pytest.mark.parametrize("nome, esperado", [
    # expert + perfil no mesmo nome: vence o expert, que vem primeiro
    ("[GA][video-view][distribuição][frio][felipe graton][brabo concursos][18.05.26]", "DISTRIBUICAO-FELIPE-GRATON"),
    ("[GA][video-view][distribuição][quente][ivan neto][brabo concursos][23.10.2026]", "DISTRIBUICAO-IVAN-NETO"),
    ("[MA][engajamento][distribuição][quente][felipe graton][25.08.26]", "DISTRIBUICAO-FELIPE-GRATON"),
    ("[ma][tráfego][distribuição][frio][mateus andrade][15.05.26]", "DISTRIBUICAO-MATEUS-ANDRADE"),
    ("[MA][engajamento][distribuição][frio][brabo concursos]", "DISTRIBUICAO-BRABO-CONCURSOS"),
    ("[MA][engajamento][distribuição][frio][brabo editora][15.07.2026]", None),
])
def test_distribuicao_por_expert(nome, esperado):
    assert resolve_perpetuo_or_distribuicao_code(nome) == esperado
