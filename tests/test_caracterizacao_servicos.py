"""Testes de caracterização da camada de serviços (``frontend/services/``).

Mesma ideia de ``test_caracterizacao_readers.py``, um nível acima: congela o
que a atribuição de vendas, o overview de criativos e o contexto do debriefing
produzem hoje, para poder quebrá-los em pedaços menores sem mudar número.

São as funções mais delicadas do sistema — ``_sales_attribution`` e
``_creative_overview`` sozinhas somam ~690 das 859 linhas de
``attribution.py``, e carregam várias correções sutis de escopo de etapa. É
justamente por isso que elas precisam de rede antes de qualquer refatoração.

Diferença em relação aos readers: aqui as entradas são objetos (``Launch``,
``MetaSummary``, ``VendasSummary``), então o teste monta a entrada real via os
mesmos leitores que o app usa, e só depois chama o serviço.

Uso::

    ATUALIZAR_BASELINE=1 pytest tests/test_caracterizacao_servicos.py -m caracterizacao
    pytest tests/test_caracterizacao_servicos.py -m caracterizacao
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
os.environ["PRE_WARM_CACHE"] = "false"

from tests.caracterizacao_util import impressao_digital, normalizar  # noqa: E402

BASELINE_DIR = Path(os.environ.get("BASELINE_DIR") or (ROOT / "tests" / "baseline")) / "servicos"
ATUALIZAR = os.environ.get("ATUALIZAR_BASELINE", "").lower() in ("1", "true", "sim")

LANCAMENTOS = ["PBB-ABR-26", "PI-AGO-26"]

# O contexto do debriefing embute a data/hora da própria geração e o
# comparativo com o lançamento anterior, que se move com o dado. Comparado só
# pela forma, como os readers voláteis.
SO_FORMA = {"debriefing_ctx"}


@pytest.fixture(scope="session")
def entradas() -> dict:
    """Entrada real de cada lançamento: launch + meta + google + vendas.

    Montada uma vez por sessão — cada `read_*` destes custa segundos.
    """
    from frontend.core import get_launches
    from frontend.db_readers import read_google, read_meta, read_vendas

    launches = get_launches()
    por_codigo = {lan.code: lan for lan in launches}

    dados = {"__launches__": launches}
    for code in LANCAMENTOS:
        lan = por_codigo.get(code)
        if lan is None:
            continue
        dados[code] = {
            "launch": lan,
            "meta": read_meta(code),
            "google": read_google(code),
            "vendas": read_vendas(code),
        }
    return dados


def _caminho(codigo: str) -> Path:
    return BASELINE_DIR / f"{codigo}.json"


@pytest.fixture(scope="session")
def baselines() -> dict[str, dict]:
    dados: dict[str, dict] = {}
    for codigo in LANCAMENTOS:
        caminho = _caminho(codigo)
        dados[codigo] = (
            {} if (ATUALIZAR or not caminho.exists())
            else json.loads(caminho.read_text(encoding="utf-8"))
        )
    yield dados

    if ATUALIZAR:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        for codigo, conteudo in dados.items():
            _caminho(codigo).write_text(
                json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )


def _calcular(nome: str, ctx: dict, launches: list):
    """Executa um dos serviços sob teste com a entrada real do lançamento."""
    from frontend.services.attribution import _creative_overview, _sales_attribution

    launch, meta, google, vendas = ctx["launch"], ctx["meta"], ctx["google"], ctx["vendas"]

    if nome == "sales_attribution":
        return _sales_attribution(launch, vendas)

    if nome == "creative_overview":
        return _creative_overview(
            meta, google, vendas, _sales_attribution(launch, vendas), launch.code
        )

    if nome == "debriefing_ctx":
        from frontend.services.debriefing_build import build_debriefing_context

        return asyncio.run(build_debriefing_context(launch, launches, True))

    raise AssertionError(f"serviço desconhecido: {nome}")


def _forma(valor):
    """Estrutura sem os valores — ver ``_forma`` em test_caracterizacao_readers."""
    if isinstance(valor, dict):
        if "__sha__" in valor:
            return "<coleção>"
        return {k: _forma(v) for k, v in sorted(valor.items())}
    if isinstance(valor, bool):
        return "<bool>"
    if isinstance(valor, (int, float)):
        return "<número>"
    if isinstance(valor, str):
        return "<texto>"
    if valor is None:
        return "<nulo>"
    return f"<{type(valor).__name__}>"


@pytest.mark.caracterizacao
@pytest.mark.parametrize("codigo", LANCAMENTOS)
@pytest.mark.parametrize("servico", ["sales_attribution", "creative_overview", "debriefing_ctx"])
def test_saida_do_servico_nao_mudou(servico, codigo, entradas, baselines):
    ctx = entradas.get(codigo)
    if ctx is None:
        pytest.skip(f"lançamento {codigo} não existe no banco")

    try:
        saida = normalizar(_calcular(servico, ctx, entradas["__launches__"]))
    except Exception as e:  # noqa: BLE001 — a exceção também é comportamento
        saida = {"__excecao__": f"{type(e).__name__}: {e}"}

    obtido = impressao_digital(saida)

    if ATUALIZAR:
        baselines[codigo][servico] = obtido
        return

    if servico not in baselines[codigo]:
        pytest.skip(f"{servico} ainda não está no baseline de {codigo}")

    esperado = baselines[codigo][servico]
    if obtido["sha256"] == esperado["sha256"]:
        return

    despejo = BASELINE_DIR / "_falhas" / f"{codigo}.{servico}.json"
    despejo.parent.mkdir(parents=True, exist_ok=True)
    despejo.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    if servico in SO_FORMA:
        assert _forma(obtido["resumo"]) == _forma(esperado["resumo"]), (
            f"{servico} mudou de FORMA para {codigo}.\nSaída completa em {despejo}."
        )
        return

    assert obtido["resumo"] == esperado["resumo"], (
        f"{servico} mudou de resultado para {codigo}.\nSaída completa em {despejo}.\n"
        f"Se for intencional, regrave com ATUALIZAR_BASELINE=1."
    )
    pytest.fail(
        f"{servico} mudou para {codigo}: mesmo esqueleto, valores diferentes.\n"
        f"Saída completa em {despejo}."
    )
