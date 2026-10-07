"""Histórico de UTM por (contato, lançamento) — a regra que impede a erosão.

Contexto (07/10/26): a `leads` tem UMA linha por contato. Quando quem já está na
base se cadastra num lançamento novo, o ETL sobrescreve a linha e o lançamento
antigo perde a pessoa. O histórico (`etl/historico_utm.py`) guarda uma linha por
(contato, lançamento) com a regra decidida pelo Michel:
  - mesmo lançamento → a ÚLTIMA UTM vence;
  - lançamento diferente → linha nova, a antiga não é tocada.
Na Black, Base Forte e Black Vitalícia (mesmo código BV-26) ficam separadas.

Estes testes cobrem a transformação registro → linha, sem banco. A parte de
banco (ON CONFLICT) é conferida no item do MUDANCAS com dado real.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_ETL = Path(__file__).resolve().parent.parent / "etl"
# Mesma ordem do ETL: etl/ na frente, senão o pacote src/db sombreia o etl/db.py.
sys.path.insert(0, str(_ETL.parent / "src"))
sys.path.insert(0, str(_ETL))

import historico_utm as h  # noqa: E402
from etl_active_campaign import extract_launch_code  # noqa: E402

AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def _reg(cid, campanha, **extra):
    return {"id": cid, "email": f"{cid}@test.com", "utm_campaign": campanha,
            "utm_source": "facebook", "utm_medium": "cpc",
            "utm_content": extra.get("content", "AD219"), "utm_term": "", **extra}


def _linhas(registros):
    return h.linhas_historico(registros, extract_launch_code, agora=AGORA)


def test_lancamento_diferente_vira_linha_nova():
    """O caso que motivou tudo: cliente antigo da base entra na Black."""
    linhas = _linhas([
        _reg("1", "[MA][captação][quente][PI-AGO-26][20.07.26]"),
        _reg("1", "[MA][captação][base forte][alunos][BV-26][28.09.26]"),
    ])
    assert {(x["lancamento_codigo"], x["trilha"]) for x in linhas} == {
        ("PI-AGO-26", ""), ("BV-26", "Base Forte")}


def test_mesmo_lancamento_fica_a_ultima_utm():
    linhas = _linhas([
        _reg("1", "[MA][captação][quente][PI-AGO-26]", content="AD100"),
        _reg("1", "[GA][captação][frio][PI-AGO-26]", content="AD400"),
    ])
    assert len(linhas) == 1
    assert linhas[0]["utm_content"] == "AD400"
    assert linhas[0]["utm_campaign"].startswith("[GA]")


def test_trilhas_da_black_ficam_separadas():
    linhas = _linhas([
        _reg("1", "[MA][captação][base forte][alunos][BV-26]"),
        _reg("1", "[MA][captação][vitalícia][super quente][BV-26]"),
    ])
    assert sorted(x["trilha"] for x in linhas) == ["Base Forte", "Black Vitalícia"]


def test_fora_da_black_trilha_e_vazia():
    linhas = _linhas([_reg("1", "[MA][captação][base forte][PES-SET-26]")])
    assert linhas[0]["trilha"] == ""


def test_utm_sem_codigo_de_lancamento_nao_entra():
    """`{{campaign.name}}` e orgânico não nomeiam lançamento: não dá pra afirmar."""
    assert _linhas([_reg("1", "{{campaign.name}}"), _reg("2", ""),
                    _reg("3", "organico-instagram")]) == []


def test_codigo_vem_da_utm_nao_do_campo_lancamento():
    """O modo CSV preenche `lancamento_codigo` pela pasta quando a UTM não diz.
    O histórico ignora esse campo e só confia na própria utm_campaign."""
    reg = _reg("1", "organico", lancamento_codigo="PI-AGO-26")
    assert _linhas([reg]) == []


def test_ids_de_clique_vazios_viram_none():
    """None no ID de clique deixa o COALESCE do upsert preservar o anterior."""
    linha = _linhas([_reg("1", "[MA][PI-AGO-26]", gclid="", vk_ad_id="123")])[0]
    assert linha["gclid"] is None
    assert linha["vk_ad_id"] == "123"


def test_valores_nan_do_pandas_viram_vazio():
    linha = _linhas([_reg("1", "[MA][PI-AGO-26]", utm_term=float("nan"))])[0]
    assert linha["utm_term"] == ""
