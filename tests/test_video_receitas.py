"""Receitas das peças nativas do storyboard (texto/caixa/vetor no Figma; imagem só ilustração e fundo)."""
import json
from pathlib import Path

from scripts.video.receitas_figma import IMAGEM, receita
from scripts.video.storyboard import _ler

RAIZ = Path(__file__).resolve().parents[1]
CRIATIVO = json.loads((RAIZ / "scripts/video/modelo/src/data/criativo.resolvido.json").read_text(encoding="utf-8"))
CENAS = {c["id"]: c for c in CRIATIVO["cenas"]}
# peças de cada componente (as mesmas do render-pecas.mjs)
PECAS = {
    "Desenho": ["imagem", "etiquetas[0]"], "Manchete": ["folha", "kicker", "titulo", "corpo"],
    "Grafico": ["kicker", "numero", "grafico", "rotuloFim", "selo"],
    "Carimbo": ["folha", "kicker", "pergunta", "carimbo", "corpo", "mao"],
    "Rota": ["kicker", "titulo", "selo", "rotuloCume"],
    "PapelMesa": ["folha", "kicker", "titulo", "grafico", "mao", "adesivo"],
    "Cartao": ["cartao", "kicker", "titulo", "subtitulo", "carimbo"],
    "Checklist": ["kicker", "titulo", "itens[0]", "itens[3]"], "Contador": ["kicker", "numero", "medalhas"],
    "Cta": ["botao", "chamada"],
}


def _peca(pid, caixa=(100, 200, 600, 120)):
    x, y, w, h = caixa
    return {"id": pid, "x": x, "y": y, "w": w, "h": h, "origem": [x + w / 2, y + h / 2], "caixa": list(caixa)}


def _textos(no):
    if no["t"] == "texto":
        yield no
    for f in no.get("filhos", []):
        yield from _textos(f)


def test_so_ilustracao_e_imagem_o_resto_vira_nativo():
    for c in CRIATIVO["cenas"]:
        for pid in PECAS[c["componente"]]:
            r = receita(c, _peca(pid))
            if pid == "imagem":
                assert r is IMAGEM, (c["id"], pid)
            else:
                assert isinstance(r, dict) and r["t"] == "frame", (c["id"], pid)


def test_todo_texto_editavel_aponta_para_uma_prop_que_existe():
    for c in CRIATIVO["cenas"]:
        for pid in PECAS[c["componente"]]:
            r = receita(c, _peca(pid))
            if r is IMAGEM:
                continue
            for t in _textos(r):
                if t.get("caminho"):
                    _ler(c["props"], t["caminho"])          # KeyError = receita apontando errado


def test_balao_caixa_ink_com_letra_paper_e_cor_editavel():
    r = receita(CENAS["dona-de-casa"], _peca("etiquetas[0]"))
    assert (r["fill"], r["raio"], r["pad"]) == ("#1A1A1A", 7.0, [7.0, 15.0, 7.0, 15.0])
    t = r["filhos"][0]
    assert (t["caminho"], t["familia"], t["estilo"], t["tamanho"], t["cor"]) == (
        "etiquetas[0].texto", "Inter", "Extra Bold", 27.0, "#F4EFE4")
    assert r["cores"] == {"fill": "etiquetas[0].cor", "texto": "etiquetas[0].corTexto"}


def test_corpo_com_marca_texto_na_palavra_certa():
    r = receita(CENAS["cargo"], _peca("corpo"))
    t = next(_textos(r))
    ini, fim = t["destaque"]["inicio"], t["destaque"]["fim"]
    assert t["texto"][ini:fim] == "nível médio"


def test_numero_do_grafico_mostra_o_valor_final_formatado():
    r = receita(CENAS["salario"], _peca("numero"))
    textos = {t.get("caminho"): t["texto"] for t in _textos(r)}
    assert textos == {"prefixo": "R$", "valorFinal": "7.234"}


def test_grafico_vira_vetor_com_a_linha_dos_pontos():
    r = receita(CENAS["salario"], _peca("grafico"))
    vetores = [f for f in r["filhos"] if f["t"] == "vetor"]
    assert any(v["nome"] == "Linha" and v["path"].startswith("M 0 ") for v in vetores)
    assert {t["caminho"] for t in _textos(r)} == {"eixo[0]", "eixo[1]"}


def test_curva_sai_so_com_comandos_que_o_figma_aceita():
    # Figma (vectorPaths) não aceita vírgula nem S: a curva suave vira C com o ponto refletido
    r = receita(CENAS["metodo"], _peca("grafico"))
    for v in (f for f in r["filhos"] if f["t"] == "vetor"):
        assert "," not in v["path"] and not set("SsQqTtAaHhVv") & set(v["path"]), v["nome"]
    boa = next(f for f in r["filhos"] if f["nome"] == "Curva boa")["path"]
    # "M 0 340 C 160 320, 280 260, 420 190 S 660 60, 780 30" × 0,5 → o S vira C (560,120 refletido)
    assert boa == "M 0 170 C 80 160 140 130 210 95 C 280 60 330 30 390 15"


def test_peca_centralizada_cresce_para_os_dois_lados():
    assert receita(CENAS["cta"], _peca("botao"))["ancora"] == "centro"
    assert receita(CENAS["cargo"], _peca("titulo"))["ancora"] == "esq"


def test_folha_gira_como_no_video_e_recebe_as_filhas():
    r = receita(CENAS["cargo"], _peca("folha", (7, 413, 1067, 807)))
    assert r["rot"] == 1.0                    # Manchete: tilt -3 → -1° no CSS → +1° no Figma
    assert r["filhas"] is True and r["fill"] == "#F4EFE4"
