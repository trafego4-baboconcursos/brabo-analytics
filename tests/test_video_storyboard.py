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


# --- ajustes por camada: posição/rotação/escala lidas do Figma (palco em meia escala) ---
from scripts.video.storyboard import aplicar_ajustes, diferencas_ajustes  # noqa: E402

# caixa da peça no canvas 1080×1920 (corte pelo alfa do render isolado)
MANIFESTO = {"dona": {"pecas": [{"id": "etiquetas[0]", "x": 100, "y": 200, "w": 300, "h": 80}]}}
PARADO = {"cx": 125.0, "cy": 120.0, "largura": 150.0, "rot": 0.0}   # mesma caixa no palco de 540


def _lido(**mudou):
    return {"dona": {"etiquetas[0]": {**PARADO, **mudou}}}


def test_peca_intocada_nao_gera_ajuste():
    assert diferencas_ajustes(CRIATIVO, MANIFESTO, _lido(cx=125.3, rot=0.2)) == []


def test_mover_no_palco_vira_deslocamento_em_px_do_video():
    difs = diferencas_ajustes(CRIATIVO, MANIFESTO, _lido(cx=135.0, cy=140.0))
    assert difs == [("dona", "etiquetas[0]", {}, {"dx": 20, "dy": 40})]


def test_girar_no_figma_inverte_o_sinal_e_dobrar_largura_e_escala_2():
    difs = diferencas_ajustes(CRIATIVO, MANIFESTO, _lido(rot=10.0, largura=300.0))
    assert difs == [("dona", "etiquetas[0]", {}, {"rot": -10.0, "escala": 2.0})]


def test_ajuste_novo_soma_ao_que_ja_existia():
    criativo = copy.deepcopy(CRIATIVO)
    criativo["cenas"][1]["ajustes"] = {"story": {"etiquetas[0]": {"dx": 8, "rot": -4.0, "escala": 1.5}}}
    difs = diferencas_ajustes(criativo, MANIFESTO, _lido(cx=135.0, rot=1.0, largura=300.0))
    assert difs == [("dona", "etiquetas[0]", {"dx": 8, "rot": -4.0, "escala": 1.5},
                     {"dx": 28, "rot": -5.0, "escala": 3.0})]


def test_aplicar_ajustes_grava_no_formato_sem_mexer_no_original():
    difs = [("dona", "etiquetas[0]", {}, {"dx": 20, "dy": 40})]
    novo = aplicar_ajustes(CRIATIVO, difs, formato="story")
    assert novo["cenas"][1]["ajustes"] == {"story": {"etiquetas[0]": {"dx": 20, "dy": 40}}}
    assert "ajustes" not in CRIATIVO["cenas"][1]


def test_camada_lida_que_nao_esta_no_manifesto_e_erro():
    with pytest.raises(KeyError, match=r"etiquetas\[9\]"):
        diferencas_ajustes(CRIATIVO, MANIFESTO, {"dona": {"etiquetas[9]": PARADO}})
