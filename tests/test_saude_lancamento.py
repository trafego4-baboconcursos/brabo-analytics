"""Trava de classificação por ROAS da Saúde do Lançamento.

A nota numérica é uma soma de pesos e já era testada de fato só pelo olho; o que
este arquivo cobra é a regra acordada com a Júlia e o Michel em 16/09/26: o ROAS
limita o RÓTULO independentemente da nota, e duas guardas vêm antes da trava
(carrinho aberto e lançamento sem venda), senão ela mente nos dois extremos.

Roda sem banco — `_saude_classificacao` é função pura.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from frontend.services.debriefing import _saude_classificacao


def _faixa(nota: int, roas: float, **kw) -> str:
    kw.setdefault("em_andamento", False)
    kw.setdefault("sem_dados", False)
    return _saude_classificacao(nota, roas, **kw)["label"]


@pytest.mark.parametrize(
    ("nota", "roas", "esperado"),
    [
        # ROAS >= 3x: a nota manda, sem teto.
        (93, 3.42, "Excelente"),   # PES-MAI-26
        (86, 3.26, "Excelente"),   # PBB-JUN-26
        (85, 3.12, "Excelente"),   # PI-ABR-26
        (64, 3.10, "Regular"),
        (40, 3.10, "Atenção"),
        # 2–2,99x: teto em Bom. PI-AGO-26 é o caso que motivou a regra —
        # nota 80 chamava de Excelente um lançamento de 2,78x.
        (80, 2.78, "Bom"),         # PI-AGO-26
        (65, 2.20, "Bom"),         # PBB-AGO-26 (já estava em Bom)
        (55, 2.50, "Regular"),     # teto não promove quem está abaixo dele
        # 1–1,99x: teto em Atenção, por mais alta que a nota esteja.
        (95, 1.99, "Atenção"),
        (70, 1.00, "Atenção"),
        # < 1x: a receita líquida não paga a mídia — Péssimo na marra.
        (95, 0.99, "Péssimo"),
        (4, 0.02, "Péssimo"),
        (0, 0.00, "Péssimo"),
    ],
)
def test_trava_por_roas(nota, roas, esperado):
    assert _faixa(nota, roas) == esperado


def test_travado_por_roas_so_marca_quando_a_nota_alcancaria_mais():
    # nota 80 alcançaria Excelente, o ROAS de 2,78x segura em Bom
    assert _saude_classificacao(80, 2.78, em_andamento=False, sem_dados=False)["travado_por_roas"] is True
    # nota 55 já era Regular; o teto de Bom não segurou nada
    assert _saude_classificacao(55, 2.50, em_andamento=False, sem_dados=False)["travado_por_roas"] is False


def test_carrinho_aberto_nao_recebe_rotulo_final():
    """PES-SET-26 em 16/09: carrinho aberto até 28/09, ROAS 0,02x, nota 4.

    Sem esta guarda o lançamento em andamento apareceria "Péssimo" todos os
    dias até fechar, porque as vendas só entram no fim."""
    assert _faixa(4, 0.02, em_andamento=True) == "Em andamento"
    assert _faixa(93, 3.42, em_andamento=True) == "Em andamento"


def test_sem_venda_nao_classifica():
    """BV-25 (legado, sem venda atribuída) e PI-NOV-26 (ainda não começou)."""
    assert _faixa(0, 0.0, sem_dados=True) == "Sem dados"
    # sem_dados vence até a guarda de carrinho aberto
    assert _faixa(0, 0.0, sem_dados=True, em_andamento=True) == "Sem dados"


def test_cor_do_numero_e_do_rotulo_vem_da_mesma_faixa():
    """Antes o template tinha corte próprio pra cor (60) e outro pro rótulo
    (65): nota 60–64 saía amarela escrito "Regular". Agora é uma fonte só."""
    for nota in (60, 62, 64):
        f = _saude_classificacao(nota, 3.5, em_andamento=False, sem_dados=False)
        assert f["label"] == "Regular" and f["cor"] == "#fb923c"
