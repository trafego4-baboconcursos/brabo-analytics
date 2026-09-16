"""Testes de caracterização dos readers (``frontend/db_readers/``).

Rede de segurança para refatoração: congela num baseline JSON o que cada
``read_*`` devolve hoje para um conjunto de lançamentos **fechados**, e falha se
algum número mudar. Não afirma que os valores estão certos — afirma que a
refatoração não os alterou.

Nem todo reader dá para congelar pelo valor: alguns leem tabelas que continuam
recebendo linhas mesmo depois do carrinho fechar (ver ``VOLATEIS``). Desses o
teste cobra só a forma da resposta. Os demais — a maioria, e justamente os de
mídia e venda — são comparados pelo digest do resultado inteiro.

O baseline guarda digest + esqueleto, nunca o conteúdo: são ~180 MB de dados,
com e-mail e telefone de comprador, que não podem entrar no repositório.

Os readers são descobertos por introspecção: qualquer ``read_*`` novo em
``frontend/db_readers/`` entra na cobertura sozinho, desde que sua assinatura
seja ``(launch..., **opcionais)``.

Uso::

    # gerar/atualizar o baseline (faça isso ANTES de refatorar, com tudo verde)
    ATUALIZAR_BASELINE=1 pytest tests/test_caracterizacao_readers.py -m caracterizacao

    # verificar que nada mudou (depois de refatorar)
    pytest tests/test_caracterizacao_readers.py -m caracterizacao

Precisa do banco real (``.env``); é excluído no CI com ``-m "not caracterizacao"``.
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import pkgutil
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# O warm-up assíncrono reescreveria o snapshot do debriefing no meio da
# comparação; nos testes ele não deve subir.
os.environ["PRE_WARM_CACHE"] = "false"

from tests.caracterizacao_util import impressao_digital, normalizar  # noqa: E402

# Permite apontar o baseline para fora da árvore: é assim que se compara o
# código de antes e o de depois de uma refatoração, gerando o baseline num
# worktree no commit anterior e verificando aqui (ver docs/sistema/ARQUITETURA.md).
BASELINE_DIR = Path(os.environ.get("BASELINE_DIR") or (ROOT / "tests" / "baseline"))
ATUALIZAR = os.environ.get("ATUALIZAR_BASELINE", "").lower() in ("1", "true", "sim")

# Lançamentos já encerrados: o ETL roda com janela retroativa de 3 dias, então
# esses números não se movem entre a gravação do baseline e a verificação.
LANCAMENTOS = ["PBB-ABR-26", "PI-AGO-26"]

# Readers deixados de fora e por quê.
IGNORADOS = {
    # Não recebem lançamento: operam sobre conta/vertical e mudam todo dia.
    "read_distribuicao",
    "read_instagram_detail",
    "read_perpetuo",
    # Lê a tabela de snapshot, que o warm-up reescreve sozinho.
    "read_snapshot",
}

# Readers cujo valor legitimamente muda com o tempo, mesmo para um lançamento
# já encerrado: leem tabelas que continuam recebendo linhas (sendflow/WhatsApp,
# formulários do sistema novo, sincronismo do Active Campaign) ou devolvem
# totais globais, não recortados pela janela do lançamento.
#
# Medido, não chutado: duas execuções a ~15 min de distância divergiram nestes
# e em nenhum outro. Chamados duas vezes seguidas, com o cache limpo entre elas,
# todos devolvem exatamente o mesmo resultado — ou seja, o código é
# determinístico; o que muda é o dado.
#
# Para eles o teste exige só que a FORMA da resposta continue a mesma (mesmos
# campos, sem exceção nova), que é o que uma refatoração pode quebrar.
VOLATEIS = {
    "leads.read_lancamentos_anteriores",
    "leads.read_leads",
    "leads.read_recorrencia_lancamento",
    "leads.read_utm_cobertura",
    "sales.read_qualidade_regiao",
    "sales.read_vendas_consolidado",
    "typeform.read_pesquisa_engajamento",
    "typeform.read_typeform",
    "typeform.read_typeform_count",
    "whatsapp_groups.read_compradores_por_dia_grupo",
    "whatsapp_groups.read_leads_x_whatsapp",
    "whatsapp_groups.read_vendas_grupos_whatsapp",
    "whatsapp_groups.read_whatsapp_groups",
    "whatsapp_messages.read_disparo_resumo",
    "whatsapp_messages.read_whatsapp_messages",
    "youtube_aulas.read_aulas_ao_vivo",
    "youtube_aulas.read_retencao_video",
}

# Nomes de parâmetro que recebem o código do lançamento.
PARAMS_CODIGO = {"launch_folder_or_code", "launch_code", "codigo"}
# Nomes de parâmetro que recebem o objeto Launch.
PARAMS_LAUNCH = {"launch"}


def _descobrir_readers() -> list[tuple[str, str, bool]]:
    """Lista ``(modulo, funcao, precisa_objeto_launch)`` de todo reader elegível."""
    import frontend.db_readers as pacote

    achados: list[tuple[str, str, bool]] = []
    for info in pkgutil.iter_modules(pacote.__path__):
        modulo = importlib.import_module(f"frontend.db_readers.{info.name}")
        for nome, fn in vars(modulo).items():
            if not nome.startswith("read_") or not inspect.isfunction(fn):
                continue
            # Só o que foi definido aqui — ignora re-exports de outro módulo.
            if fn.__module__ != modulo.__name__ or nome in IGNORADOS:
                continue

            params = list(inspect.signature(fn).parameters.values())
            if not params:
                continue
            primeiro = params[0]
            if primeiro.name in PARAMS_CODIGO:
                precisa_launch = False
            elif primeiro.name in PARAMS_LAUNCH:
                precisa_launch = True
            else:
                continue
            # Os demais parâmetros precisam ter default: chamamos só com o 1º.
            if any(p.default is inspect.Parameter.empty for p in params[1:]):
                continue
            achados.append((info.name, nome, precisa_launch))

    return sorted(achados)


READERS = _descobrir_readers()


@pytest.fixture(scope="session")
def launches_por_codigo() -> dict:
    from frontend.db_readers.launches import discover_launches

    return {lan.code: lan for lan in discover_launches()}


def _forma(resumo: Any) -> Any:
    """Só a estrutura de ``resumo``: nomes de campo e tipos, sem os valores.

    É o que se exige de um reader volátil — que continue devolvendo os mesmos
    campos, com os mesmos tipos, depois da refatoração.
    """
    if isinstance(resumo, dict):
        # __n__/__sha__ descrevem uma coleção: a contagem varia com o dado, o
        # que importa é que continue sendo uma coleção.
        if "__sha__" in resumo:
            return "<coleção>"
        return {k: _forma(v) for k, v in sorted(resumo.items())}
    if isinstance(resumo, bool):
        return "<bool>"
    if isinstance(resumo, (int, float)):
        return "<número>"
    if isinstance(resumo, str):
        return "<texto>"
    if resumo is None:
        return "<nulo>"
    return f"<{type(resumo).__name__}>"


def _caminho_baseline(codigo: str) -> Path:
    return BASELINE_DIR / f"{codigo}.json"


@pytest.fixture(scope="session")
def baselines() -> dict[str, dict]:
    """Baseline em memória; no modo de atualização começa vazio e é regravado."""
    dados: dict[str, dict] = {}
    for codigo in LANCAMENTOS:
        caminho = _caminho_baseline(codigo)
        if ATUALIZAR or not caminho.exists():
            dados[codigo] = {}
        else:
            dados[codigo] = json.loads(caminho.read_text(encoding="utf-8"))
    yield dados

    if ATUALIZAR:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        for codigo, conteudo in dados.items():
            _caminho_baseline(codigo).write_text(
                json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )


def test_descobriu_readers():
    """Guarda contra a introspecção quebrar e o teste virar um no-op silencioso."""
    assert len(READERS) >= 25, (
        f"só {len(READERS)} readers descobertos — a introspecção provavelmente quebrou"
    )


@pytest.mark.caracterizacao
@pytest.mark.parametrize("codigo", LANCAMENTOS)
@pytest.mark.parametrize(
    ("modulo", "funcao", "precisa_launch"),
    READERS,
    ids=[f"{m}.{f}" for m, f, _ in READERS],
)
def test_saida_do_reader_nao_mudou(
    codigo, modulo, funcao, precisa_launch, baselines, launches_por_codigo
):
    launch = launches_por_codigo.get(codigo)
    if launch is None:
        pytest.skip(f"lançamento {codigo} não existe no banco")

    fn = getattr(importlib.import_module(f"frontend.db_readers.{modulo}"), funcao)
    chave = f"{modulo}.{funcao}"

    try:
        saida = normalizar(fn(launch if precisa_launch else codigo))
    except Exception as e:  # noqa: BLE001 — a exceção também é comportamento
        saida = {"__excecao__": f"{type(e).__name__}: {e}"}

    obtido = impressao_digital(saida)

    if ATUALIZAR:
        baselines[codigo][chave] = obtido
        return

    if chave not in baselines[codigo]:
        pytest.skip(f"{chave} ainda não está no baseline de {codigo}")

    esperado = baselines[codigo][chave]
    if obtido["sha256"] == esperado["sha256"]:
        return

    if chave in VOLATEIS:
        # Valor pode ter mudado por dado novo; a forma, não.
        assert _forma(obtido["resumo"]) == _forma(esperado["resumo"]), (
            f"{chave} mudou de FORMA para {codigo} (campos diferentes).\n"
            f"Reader volátil: o valor pode mudar, a estrutura não."
        )
        return

    # Saída completa em disco para conseguir diferenciar o que mudou de fato —
    # o baseline versionado guarda só o digest e o esqueleto.
    despejo = BASELINE_DIR / "_falhas" / f"{codigo}.{chave}.json"
    despejo.parent.mkdir(parents=True, exist_ok=True)
    despejo.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )

    assert obtido["resumo"] == esperado["resumo"], (
        f"{chave} mudou de resultado para {codigo}.\n"
        f"Saída completa gravada em {despejo}.\n"
        f"Se a mudança for intencional, regrave o baseline com ATUALIZAR_BASELINE=1."
    )
    pytest.fail(
        f"{chave} mudou para {codigo}: mesmo esqueleto, valores diferentes "
        f"({esperado['bytes']} → {obtido['bytes']} bytes).\n"
        f"Saída completa gravada em {despejo}."
    )
