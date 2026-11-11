"""Preparação automática de criativo novo: funções puras (glossário, valores, ganho, legenda queimada)."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.video.novo_criativo import (
    GLOSSARIO_PADRAO,
    aplicar_glossario,
    detectar_legenda_queimada,
    formato_por_dimensao,
    ganho_por_rms,
    juntar_valores,
    refinar_inicio_legenda,
)


def pal(textos: list[str], passo: float = 0.2) -> list[dict]:
    """Palavras no formato Caption do Remotion (espaço na frente, menos a 1ª)."""
    return [{"text": (t if i == 0 else " " + t), "startMs": int(i * passo * 1000), "endMs": int((i + 1) * passo * 1000),
             "timestampMs": int((i + 0.5) * passo * 1000), "confidence": None} for i, t in enumerate(textos)]


GLOS = json.loads(GLOSSARIO_PADRAO.read_text(encoding="utf-8"))


def test_glossario_do_ad368():
    p = aplicar_glossario(pal(["Projeto", "e", "NSS."]), GLOS)
    assert [w["text"].strip() for w in p] == ["Projeto", "INSS."]
    assert p[1]["startMs"] == 200 and p[1]["endMs"] == 600       # do "e" até o fim de "NSS."


def test_glossario_palavra_unica_e_vizinha():
    p = aplicar_glossario(pal(["Matheus,", "toca", "eu", "sabe"]), GLOS)
    assert [w["text"].strip() for w in p] == ["Mateus,", "toca", "ou", "sabe"]
    assert p[0]["text"] == "Mateus,"                                 # 1ª palavra continua sem espaço


def test_glossario_nao_mexe_em_palavra_parecida():
    p = aplicar_glossario(pal(["eu", "acho"]), GLOS)                 # "eu" só vira "ou" antes de "sabe"
    assert [w["text"].strip() for w in p] == ["eu", "acho"]


def test_juntar_valores_reais():
    p = juntar_valores(pal(["Salário", "R", "$", "7", ".234", ",00."]))
    assert [w["text"].strip() for w in p] == ["Salário", "R$ 7.234,00."]
    assert p[1]["startMs"] == 200 and p[1]["endMs"] == 1200


def test_juntar_valores_nao_cola_numero_solto():
    p = juntar_valores(pal(["duas", "horas", "e", "6", "aprovações"]))
    assert len(p) == 5


def test_inicio_da_legenda_queimada_encaixa_no_corte():
    # varredura de 0,5 s achou a legenda em 7,5 s; o corte real do AD358 é em 7,17 s
    assert refinar_inicio_legenda(7.5, [7.17, 12.95, 16.95], passo=0.5) == 7.17
    assert refinar_inicio_legenda(7.5, [3.0, 12.95], passo=0.5) == 7.5   # sem corte no intervalo: fica a varredura


def test_ganho_do_horizontal_do_ad368():
    assert round(ganho_por_rms(6667.0, 3766.0), 2) == 1.77


def test_formato_por_dimensao():
    assert formato_por_dimensao(1080, 1920) == "story"
    assert formato_por_dimensao(1080, 1080) == "feed"
    assert formato_por_dimensao(1920, 1080) == "h"


def _quadro(tmp_path: Path, nome: str, com_legenda: bool) -> Path:
    img = Image.new("RGB", (1080, 1080), (90, 80, 70))
    d = ImageDraw.Draw(img)
    d.rectangle([300, 200, 700, 500], fill=(240, 240, 240))           # parede clara (sem sombra) no alto
    if com_legenda:
        fonte = ImageFont.load_default(size=52)
        for dx, dy, cor in ((3, 3, (0, 0, 0)), (0, 0, (255, 255, 255))):
            d.text((250 + dx, 900 + dy), "DEVERIA PRESTAR", font=fonte, fill=cor)
    p = tmp_path / nome
    img.save(p)
    return p


def _quadro_com_selo(tmp_path: Path, nome: str) -> Path:
    """Como a caixa "CONCURSO PÚBLICO" do AD358: bloco branco grande com texto escuro e sombra."""
    img = Image.new("RGB", (1080, 1080), (90, 80, 70))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([200, 800, 880, 990], radius=20, fill=(255, 255, 255))
    d.rectangle([203, 993, 883, 996], fill=(0, 0, 0))                # sombra do bloco
    fonte = ImageFont.load_default(size=70)
    d.text((240, 850), "CONCURSO PÚBLICO", font=fonte, fill=(10, 10, 10))
    p = tmp_path / nome
    img.save(p)
    return p


def test_selo_branco_do_bruto_nao_conta_como_legenda(tmp_path):
    # no AD358 a caixa "CONCURSO PÚBLICO" fazia o início da legenda queimada sair 0,0 s (real: 7,1 s)
    assert detectar_legenda_queimada([_quadro_com_selo(tmp_path, f"x{i}.png") for i in range(5)]) is False


def test_detecta_legenda_queimada_na_faixa_de_baixo(tmp_path):
    com = [_quadro(tmp_path, f"c{i}.png", True) for i in range(5)]
    sem = [_quadro(tmp_path, f"s{i}.png", False) for i in range(5)]
    assert detectar_legenda_queimada(com) is True
    assert detectar_legenda_queimada(sem) is False
