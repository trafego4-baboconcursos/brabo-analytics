"""Congelamento do nome de campanha e classificação na escrita.

O bug que estes testes prendem: o upsert dos ETLs é `DELETE` da faixa +
`append`, então um backfill sobre período antigo regravava as linhas com o nome
**atual** da campanha. Campanha reaproveitada e renomeada num lançamento novo
levava o código do lançamento novo para o histórico do antigo — foi assim que
R$ 74 mil de Captação do PES-MAI-26 passaram a aparecer como `[PES-SET-26]`.

Não precisa de banco: `congelar_nomes` e `classificar` são funções puras sobre
DataFrame, e o mapa de nomes históricos é o que `nomes_congelados` leria.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

from campanha_historico import classificar, congelar_nomes  # noqa: E402

NOME_EPOCA = "[GA][cadastro][captação][quente][potencial][PES-MAI-26][27.04.26]"
NOME_ATUAL = "[GA][cadastro][captação][quente][potencial][old][PES-SET-26][04.09.26]"


def _df(linhas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(linhas)


def test_congela_nome_de_linha_que_ja_existia():
    df = _df([
        {"campaign_id": "23790852845", "date": "2026-05-01", "campaign_name": NOME_ATUAL},
        {"campaign_id": "23790852845", "date": "2026-05-02", "campaign_name": NOME_ATUAL},
    ])
    mapa = {
        ("23790852845", "2026-05-01"): NOME_EPOCA,
        ("23790852845", "2026-05-02"): NOME_EPOCA,
    }
    saida, trocados = congelar_nomes(df, mapa)
    assert trocados == 2
    assert list(saida["campaign_name"]) == [NOME_EPOCA, NOME_EPOCA]


def test_linha_nova_mantem_o_nome_atual():
    """Dia que ainda não estava gravado recebe o nome que a API devolveu agora."""
    df = _df([
        {"campaign_id": "23790852845", "date": "2026-05-01", "campaign_name": NOME_ATUAL},
        {"campaign_id": "23790852845", "date": "2026-09-07", "campaign_name": NOME_ATUAL},
    ])
    mapa = {("23790852845", "2026-05-01"): NOME_EPOCA}
    saida, trocados = congelar_nomes(df, mapa)
    assert trocados == 1
    assert list(saida["campaign_name"]) == [NOME_EPOCA, NOME_ATUAL]


def test_sem_campaign_id_nao_congela():
    """Modo CSV não tem id; sem chave estável, não dá pra afirmar que é a mesma campanha."""
    df = _df([{"campaign_id": None, "date": "2026-05-01", "campaign_name": NOME_ATUAL}])
    saida, trocados = congelar_nomes(df, {("23790852845", "2026-05-01"): NOME_EPOCA})
    assert trocados == 0
    assert list(saida["campaign_name"]) == [NOME_ATUAL]


def test_mapa_vazio_e_noop():
    df = _df([{"campaign_id": "1", "date": "2026-05-01", "campaign_name": NOME_ATUAL}])
    saida, trocados = congelar_nomes(df, {})
    assert trocados == 0
    assert saida.equals(df)


@pytest.mark.parametrize(
    "nome, esperado",
    [
        (NOME_EPOCA, ("Captação", "Quente", "Potencial", "Quente Potencial")),
        ("[MA][tráfego][lembrete][PES-MAI-26][04.05.26]", ("Lembrete", "Outros", "Outros", "Outros")),
    ],
)
def test_classificar_meta(nome, esperado):
    df = _df([{"campaign_name": nome, "lancamento_codigo": "PES-MAI-26"}])
    saida = classificar(df, "meta")
    assert tuple(saida.loc[0, ["etapa", "temperatura", "bucket", "segmento"]]) == esperado


def test_classificar_google_usa_o_nome_congelado():
    """A classificação sai do nome já congelado — é esse o ponto de gravar na escrita."""
    df = _df([{"campaign_name": NOME_EPOCA, "lancamento_codigo": "PES-MAI-26"}])
    saida = classificar(df, "google")
    assert saida.loc[0, "etapa"] == "Captação"
    assert saida.loc[0, "temperatura"] == "Quente"
    assert "bucket" not in saida.columns  # só o Meta tem bucket


def test_classificar_df_vazio_cria_as_colunas():
    """Upsert de df vazio não pode quebrar o `to_sql` por coluna faltando."""
    df = pd.DataFrame(columns=["campaign_name", "lancamento_codigo"])
    saida = classificar(df, "meta")
    assert {"etapa", "temperatura", "bucket", "segmento"} <= set(saida.columns)


def test_replay_vence_aula_tambem_na_escrita():
    """`[replay aula 2]` é Replay, não Aulas no Ar — regressão que já mordeu em 16/09/26."""
    df = _df([
        {"campaign_name": "[GA][rmk][replay aula 2][PES-MAI-26][11.05.26]", "lancamento_codigo": "PES-MAI-26"},
        {"campaign_name": "[GA][rmk][aula 3][PES-MAI-26][11.05.26]", "lancamento_codigo": "PES-MAI-26"},
    ])
    saida = classificar(df, "google")
    assert list(saida["etapa"]) == ["Replay", "Aulas no Ar"]
