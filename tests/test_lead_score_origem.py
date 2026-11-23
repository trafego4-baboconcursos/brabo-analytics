"""Score por lead com origem (frontend/services/lead_score.py): derivação do UTM e cálculo vetorizado.
Sem banco: o modelo de teste é pequeno e montado aqui."""
import math

import numpy as np
import pandas as pd

from frontend.services import lead_score as ls


def test_derivar_origem_canal_temperatura_etapa():
    d = ls.derivar_origem(
        ["google", "fb-captacao-quente-principal-v10", "yt-captacao-quente-principal-v2", None, "tiktok"],
        ["[GA][cadastro][captação][quente][principal]", "[MA][pré-qualificação][frio][x]", "", None, "[MA][captação][super quente]"],
    )
    assert d["canal"].tolist() == ["google", "meta", "outro", "vazio", "outro"]
    assert d["temp"].tolist() == ["quente", "frio", "outro", "outro", "super quente"]
    assert d["etapa"].tolist() == ["capt", "pre", "outro", "outro", "capt"]


def _modelo(com_origem: bool) -> dict:
    # coef: respondeu, idade=a, idade=b, preocup0, preocup1, [carga], canal=meta, canal=google
    m = {"perguntas": ["idade"], "vocab": {"idade": ["a", "b"]}, "multi": {"preocup": ["medo", "sem tempo"]},
         "intercepto": -3.0, "coef": [0.5, 0.2, -0.1, -0.3, 0.4]}
    if com_origem:
        m["colunas_controle"] = 1
        m["origem"] = {"cols": [["canal", "meta"], ["canal", "google"]]}
        m["coef"] += [9.9, 0.1, 0.6]          # 9.9 = controle do tipo de linha: tem de ser ignorado
    return m


def _leads() -> pd.DataFrame:
    return pd.DataFrame({
        "respondeu": [1, 1, 0, 0], "idade": ["a", "b", "", ""],
        "preocup": ["medo, sem tempo", "", "", ""], "canal": ["meta", "google", "google", "meta"],
    })


def test_logit_vetorial_confere_com_conta_manual():
    d = _leads()
    p = ls._logit_vetorial(_modelo(False), d)
    z0 = -3.0 + 0.5 + 0.2 + (-0.3 + 0.4)            # respondeu, idade=a, medo + sem tempo
    z1 = -3.0 + 0.5 - 0.1                            # respondeu, idade=b
    z2 = -3.0                                        # não respondeu, sem nada
    assert np.allclose(p[:3], [1 / (1 + math.exp(-z)) for z in (z0, z1, z2)])


def test_logit_com_origem_ignora_o_controle_de_tipo_de_linha():
    d = _leads()
    p = ls._logit_vetorial(_modelo(True), d, com_origem=True)
    z2 = -3.0 + 0.6                                  # não respondeu, canal google (0,6) — o 9,9 não entra
    z3 = -3.0 + 0.1                                  # não respondeu, canal meta (0,1)
    assert np.allclose(p[2:], [1 / (1 + math.exp(-z)) for z in (z2, z3)])
    assert p[2] > p[3]                               # quem não respondeu passa a ter ordem pela origem
