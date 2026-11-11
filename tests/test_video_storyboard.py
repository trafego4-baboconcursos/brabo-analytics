"""Storyboard no Figma: dados de cada tela (ida) e textos editados de volta para o criativo (volta)."""
import copy

import pytest

from scripts.video.storyboard import aplicar_textos, dados_storyboard, diferencas_textos


def _cap(texto, ini, fim):
    return {"text": texto, "startMs": int(ini * 1000), "endMs": int(fim * 1000), "timestampMs": 0, "confidence": None}


CAPTIONS = [_cap("Esse", 31.0, 31.2), _cap(" é", 31.2, 31.4), _cap(" o", 33.3, 33.4), _cap(" salário", 33.4, 34.0),
            _cap(" inicial", 34.0, 34.4), _cap(" depois", 50.0, 50.4)]

CRIATIVO = {
    "codigo": "AD368",
    "cenas": [{
        "id": "salario", "componente": "Grafico", "de": 33.2, "ate": 42.8,
        "props": {"kicker": "SALÁRIO INICIAL", "prefixo": "R$", "valorFinal": 7234, "pontos": [1, 2],
                  "eixo": ["INÍCIO", "FINAL"], "rotuloFim": {"valor": "≈ R$ 11 mil", "sub": "CARREIRA"},
                  "selo": "✓ Estabilidade", "em": {"conta": [34.1, 35.5]}},
        "sfx": [[33.2, "whoosh", 0.35], [35.5, "ding", 0.22]],
    }, {
        "id": "dona", "componente": "Desenho", "de": 3.4, "ate": 9.0,
        "props": {"img": "dona.jpg", "etiquetas": [{"texto": "trabalha", "em": 4.4, "x": 90, "y": 190, "rot": -4}]},
        "sfx": [],
    }],
}


def test_dados_trazem_fala_tempos_e_efeitos():
    d = dados_storyboard(CRIATIVO, CAPTIONS)
    tela = d["telas"][0]
    assert tela["id"] == "salario" and tela["de"] == 33.2 and tela["ate"] == 42.8
    assert tela["fala"] == "o salário inicial"                      # só as palavras dentro de [de, ate]
    assert tela["efeitos"] == ["33.2 s whoosh", "35.5 s ding"]


def test_textos_editaveis_por_caminho_sem_arquivos_nem_numeros():
    textos = dados_storyboard(CRIATIVO, CAPTIONS)["telas"][0]["textos"]
    assert textos == {
        "kicker": "SALÁRIO INICIAL", "prefixo": "R$", "eixo[0]": "INÍCIO", "eixo[1]": "FINAL",
        "rotuloFim.valor": "≈ R$ 11 mil", "rotuloFim.sub": "CARREIRA", "selo": "✓ Estabilidade",
    }
    assert dados_storyboard(CRIATIVO, CAPTIONS)["telas"][1]["textos"] == {"etiquetas[0].texto": "trabalha"}


def test_diferencas_listam_so_o_que_mudou():
    lidos = {"salario": {"selo": "✓ Estabilidade por lei", "kicker": "SALÁRIO INICIAL"}}
    assert diferencas_textos(CRIATIVO, lidos) == [("salario", "selo", "✓ Estabilidade", "✓ Estabilidade por lei")]


def test_aplicar_textos_muda_so_o_caminho_editado():
    novo = aplicar_textos(CRIATIVO, {"dona": {"etiquetas[0].texto": "trabalha fora"}})
    assert novo["cenas"][1]["props"]["etiquetas"][0] == {"texto": "trabalha fora", "em": 4.4, "x": 90, "y": 190, "rot": -4}
    assert CRIATIVO["cenas"][1]["props"]["etiquetas"][0]["texto"] == "trabalha"   # original intacto


def test_texto_lido_de_caminho_que_nao_existe_e_erro():
    with pytest.raises(KeyError, match="dona.*titulo"):
        diferencas_textos(CRIATIVO, {"dona": {"titulo": "x"}})
