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


def test_peca_filha_e_lida_relativa_a_caixa_da_mae():
    # kicker dentro da folha: no Figma a camada fica dentro do frame da folha
    manif = {"dona": {"pecas": [{"id": "folha", "x": 90, "y": 190, "w": 900, "h": 600},
                                {"id": "etiquetas[0]", "pai": "folha", "x": 100, "y": 200, "w": 300, "h": 80}]}}
    lido = {"dona": {"etiquetas[0]": {"cx": 80.0 + 10, "cy": 25.0, "largura": 150.0, "rot": 0.0}}}
    assert diferencas_ajustes(CRIATIVO, manif, lido) == [("dona", "etiquetas[0]", {}, {"dx": 20})]


# O pipeline de vídeo só roda local: o Pillow não está no requirements.txt do servidor/CI. Os testes que montam
# PNG pulam sem ele; o resto do arquivo segue rodando no CI.
import importlib.util  # noqa: E402

precisa_pil = pytest.mark.skipif(importlib.util.find_spec("PIL") is None, reason="Pillow só no ambiente local de vídeo")


def _png(caminho, caixa=None, tamanho=(1080, 1920)):
    from PIL import Image
    img = Image.new("RGBA", tamanho, (0, 0, 0, 0))
    if caixa:
        x, y, w, h = caixa
        img.paste((255, 0, 0, 255), (x, y, x + w, y + h))
    img.save(caminho)


@precisa_pil
def test_montar_pecas_corta_pelo_alfa_e_pula_peca_vazia(tmp_path):
    from scripts.video.storyboard import montar_pecas
    cena = tmp_path / "dona"
    cena.mkdir()
    _png(cena / "fundo.png", (0, 0, 1080, 1920))
    _png(cena / "etiquetas[0].png", (100, 200, 300, 80))
    _png(cena / "imagem.png")                                     # peça que não aparece nesse instante
    (cena / "lista.json").write_text('[{"id": "imagem"}, {"id": "etiquetas[0]"}]', encoding="utf-8")
    _png(cena / "legenda.png", (90, 1300, 900, 100))
    m = montar_pecas(tmp_path)
    assert m["dona"]["fundo"] == "dona/fundo.png"
    # legenda: camada de cima, recortada como as peças, mas não editável
    assert m["dona"]["legenda"] == {"arquivo": "dona/legenda.recorte.png", "x": 90, "y": 1300, "w": 900, "h": 100}
    assert m["dona"]["pecas"] == [{"id": "etiquetas[0]", "arquivo": "dona/etiquetas[0].recorte.png",
                                   "x": 100, "y": 200, "w": 300, "h": 80}]
    from PIL import Image
    assert Image.open(tmp_path / "dona" / "etiquetas[0].recorte.png").size == (300, 80)


# caixa da <Peca> mais larga que o visível (carimbo numa linha inteira da folha): no vídeo a
# peça escala/gira em volta do centro da CAIXA (origem); no Figma, do centro da IMAGEM.
MANIF_ORIGEM = {"dona": {"pecas": [{"id": "etiquetas[0]", "x": 100, "y": 200, "w": 300, "h": 80, "origem": [540, 240]}]}}


def test_escala_em_volta_da_imagem_compensa_a_origem_da_caixa():
    difs = diferencas_ajustes(CRIATIVO, MANIF_ORIGEM, _lido(largura=300.0))
    assert difs == [("dona", "etiquetas[0]", {}, {"dx": 290, "escala": 2.0})]


def test_rotacao_em_volta_da_imagem_compensa_a_origem_da_caixa():
    difs = diferencas_ajustes(CRIATIVO, MANIF_ORIGEM, _lido(rot=90.0))
    assert difs == [("dona", "etiquetas[0]", {}, {"dx": -290, "dy": -290, "rot": -90.0})]


@precisa_pil
def test_montar_pecas_le_a_origem_da_caixa(tmp_path):
    from scripts.video.storyboard import montar_pecas
    cena = tmp_path / "dona"
    cena.mkdir()
    _png(cena / "fundo.png", (0, 0, 1080, 1920))
    _png(cena / "etiquetas[0].png", (100, 200, 300, 80))
    _png(cena / "etiquetas[0].caixa.png", (60, 200, 960, 80))      # caixa da peça (render "caixa:")
    (cena / "lista.json").write_text('[{"id": "etiquetas[0]"}]', encoding="utf-8")
    p = montar_pecas(tmp_path)["dona"]["pecas"][0]
    assert p["origem"] == [540.0, 240.0]
    assert p["caixa"] == [60, 200, 960, 80]


def test_nome_das_camadas_em_portugues_e_volta_pelo_nome():
    from scripts.video.storyboard import nome_camada
    props = CRIATIVO["cenas"][1]["props"]
    assert nome_camada("etiquetas[0]", props) == "Balão 1 · trabalha"
    assert nome_camada("kicker", {}) == "Sobretítulo"
    assert nome_camada("rotuloFim.valor", {}) == "Valor final · texto"
    assert nome_camada("algo_novo", {}) == "algo_novo"            # sem tradução: fica o id
    # a volta aceita a camada pelo nome em português
    lido = {"dona": {"Balão 1 · trabalha": {**PARADO, "cx": 135.0}}}
    assert diferencas_ajustes(CRIATIVO, MANIFESTO, lido) == [("dona", "etiquetas[0]", {}, {"dx": 20})]


def test_texto_lido_pelo_nome_em_portugues():
    lidos = {"salario": {"Selo": "✓ Estabilidade por lei", "Valor final · linha de baixo": "CARREIRA"}}
    assert diferencas_textos(CRIATIVO, lidos) == [("salario", "selo", "✓ Estabilidade", "✓ Estabilidade por lei")]


# --- peças nativas (texto vivo / caixa / vetor): o balão como exemplo ---
from scripts.video.storyboard import aplicar_props, diferencas_nativas  # noqa: E402

# balão de 300 px de largura no vídeo, centro (250, 240); no Figma (palco ½): centro (125, 120)
MANIF_BALAO = {"dona": {"pecas": [{"id": "etiquetas[0]", "x": 100, "y": 200, "w": 300, "h": 80, "origem": [250, 240]}]}}
NATIVOS0 = {"dona": {"etiquetas[0]": {   # como o Figma criou a peça (devolvido pelo storyboard_video.js)
    "cx": 125.0, "cy": 120.0, "largura": 150.0, "altura": 40.0, "rot": 4.0, "fonte": 27.0, "pv": [250, 240],
    "ancora": "esq", "cores": {"fill": "etiquetas[0].cor", "texto": "etiquetas[0].corTexto"},
    "cor0": "#1A1A1A", "corTexto0": "#F4EFE4"}}}


def _balao(texto="trabalha", **mudou):
    base = {"cx": 125.0, "cy": 120.0, "largura": 150.0, "altura": 40.0, "rot": 4.0, "fonte": 27.0,
            "textos": {"✎ Balão 1 · texto": texto}, "cor": "#1A1A1A", "corTexto": "#F4EFE4"}
    return {"dona": {"etiquetas[0]": {**base, **mudou}}}


def test_balao_vira_peca_nativa_e_sai_da_caixa_de_textos():
    d = dados_storyboard(CRIATIVO, CAPTIONS, pecas=MANIF_BALAO)
    tela = d["telas"][1]
    nat = tela["camadas"]["pecas"][0]["nativo"]
    assert (nat["fill"], nat["pv"], nat["filhos"][0]["rotulo"]) == ("#1A1A1A", [250.0, 240.0], "✎ Balão 1 · texto")
    assert "etiquetas[0].texto" not in tela["textos"]          # edita no próprio balão


def test_balao_intocado_nao_gera_nada():
    assert diferencas_nativas(CRIATIVO, MANIF_BALAO, _balao(), NATIVOS0) == ([], [])


def test_texto_maior_cresce_para_a_direita_sem_mover_o_balao():
    # Figma: auto layout cresce a partir da esquerda → o centro anda metade do que cresceu
    aj, props = diferencas_nativas(CRIATIVO, MANIF_BALAO, _balao("trabalha fora", largura=200.0, cx=150.0), NATIVOS0)
    assert aj == []
    assert props == [("dona", "etiquetas[0].texto", "trabalha", "trabalha fora")]


def test_mover_girar_e_aumentar_a_letra_do_balao():
    aj, _ = diferencas_nativas(CRIATIVO, MANIF_BALAO,
                               _balao(cx=135.0, cy=130.0, rot=14.0, fonte=40.5, largura=225.0, altura=60.0), NATIVOS0)
    # o centro no Figma vai para onde o centro fica no vídeo (+10/+10 no palco = +20/+20); a letra
    # 1,5× cresce a caixa junto (escala em volta do centro), então não há "crescimento de texto"
    assert aj == [("dona", "etiquetas[0]", {}, {"dx": 20, "dy": 20, "rot": -10.0, "escala": 1.5})]


def test_texto_que_quebra_linha_cresce_para_baixo_sem_mover():
    aj, _ = diferencas_nativas(CRIATIVO, MANIF_BALAO, _balao("trabalha muito", altura=80.0, cy=140.0), NATIVOS0)
    assert aj == []


def test_balao_nativo_nao_entra_na_conta_das_imagens():
    # o mesmo lidos vai para as duas funções: o balão (tem "fonte") é só de diferencas_nativas
    assert diferencas_ajustes(CRIATIVO, MANIF_BALAO, _balao(cx=200.0)) == []


def test_trocar_a_cor_da_caixa():
    _, props = diferencas_nativas(CRIATIVO, MANIF_BALAO, _balao(cor="#E8643C"), NATIVOS0)
    assert props == [("dona", "etiquetas[0].cor", "#1A1A1A", "#E8643C")]
    novo = aplicar_props(CRIATIVO, props)
    assert novo["cenas"][1]["props"]["etiquetas"][0]["cor"] == "#E8643C"
    assert "cor" not in CRIATIVO["cenas"][1]["props"]["etiquetas"][0]


def test_cor_de_peca_sem_prop_de_cor_vira_ajuste():
    # selo do mapa: não tem prop de cor → a cor nova vai para o ajuste da peça (Peca → CSS var)
    manif = {"dona": {"pecas": [{"id": "etiquetas[0]", "x": 100, "y": 200, "w": 300, "h": 80, "origem": [250, 240]}]}}
    n0 = {"dona": {"etiquetas[0]": {**NATIVOS0["dona"]["etiquetas[0]"], "cores": None}}}
    aj, props = diferencas_nativas(CRIATIVO, manif, _balao(cor="#E8633D", corTexto="#E8633D"), n0)
    assert props == []
    assert aj == [("dona", "etiquetas[0]", {}, {"cor": "#E8633D", "corTexto": "#E8633D"})]


def test_numero_editado_volta_como_numero():
    crit = {"codigo": "X", "cenas": [{"id": "sal", "componente": "Grafico", "de": 0, "ate": 1,
                                      "props": {"valorFinal": 7234, "prefixo": "R$"}, "sfx": []}]}
    manif = {"sal": {"pecas": [{"id": "numero", "x": 0, "y": 0, "w": 100, "h": 50}]}}
    n0 = {"sal": {"numero": {"cx": 25.0, "cy": 12.5, "largura": 50.0, "altura": 25.0, "rot": 0.0, "fonte": 95.0,
                             "pv": [50, 25], "ancora": "esq"}}}
    lido = {"sal": {"numero": {"cx": 25.0, "cy": 12.5, "largura": 50.0, "altura": 25.0, "rot": 0.0, "fonte": 95.0,
                               "textos": {"✎ Valor": "7.500", "✎ Moeda": "R$"}}}}
    assert diferencas_nativas(crit, manif, lido, n0)[1] == [("sal", "valorFinal", 7234, 7500)]


@precisa_pil
def test_caixa_alfa_de_png_opaco_sem_canal_alfa_e_a_imagem_toda(tmp_path):
    # o render grava RGB quando a peça cobre o quadro inteiro (ex.: ilustração em tela cheia)
    from PIL import Image
    from scripts.video.storyboard import caixa_alfa
    Image.new("RGB", (1080, 1920), (200, 100, 50)).save(tmp_path / "imagem.png")
    assert caixa_alfa(tmp_path / "imagem.png") == (0, 0, 1080, 1920)


def test_dados_storyboard_levam_as_camadas_de_cada_tela():
    d = dados_storyboard(CRIATIVO, CAPTIONS, pecas=MANIFESTO)
    p = d["telas"][1]["camadas"]["pecas"][0]
    assert {k: p[k] for k in MANIFESTO["dona"]["pecas"][0]} == MANIFESTO["dona"]["pecas"][0]
    assert p["nome"] == "Balão 1 · trabalha" and p["nativo"]["t"] == "frame"
    assert d["telas"][1]["rotulos"] == {}           # o texto do balão é editado no próprio balão
    assert "camadas" not in d["telas"][0]          # cena sem render de camadas: tela só com o still


def test_camada_lida_que_nao_esta_no_manifesto_e_erro():
    with pytest.raises(KeyError, match=r"etiquetas\[9\]"):
        diferencas_ajustes(CRIATIVO, MANIFESTO, {"dona": {"etiquetas[9]": PARADO}})
