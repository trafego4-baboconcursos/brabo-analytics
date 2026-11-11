"""criativo.json: validação, âncoras na fala e resolução para a composição genérica."""
import copy
import json
import re
from pathlib import Path

import pytest

from scripts.video.criativo_schema import CriativoInvalido, carregar_criativo, resolver_criativo

RAIZ = Path(__file__).resolve().parents[1]
MODELO = RAIZ / "scripts" / "video" / "modelo"


def _cap(texto: str, ini: float, fim: float) -> dict:
    return {"text": texto, "startMs": int(ini * 1000), "endMs": int(fim * 1000),
            "timestampMs": int((ini + fim) * 500), "confidence": None}


# trechos reais do AD368 (tempos da transcrição)
TRANSCRICAO = [
    _cap(" estabilidade", 41.0, 41.7),
    _cap(" aprovada", 70.1, 70.5),          # 1ª ocorrência, fora da cena de teste
    _cap(" chances", 73.12, 73.42),
    _cap(" de", 73.42, 73.64),
    _cap(" ser", 73.64, 73.78),
    _cap(" aprovada.", 73.78, 74.28),
    _cap(" aprovada", 80.0, 80.4),          # depois da cena
]
TRANSCRICAO_SEM_APROVADA = [c for c in TRANSCRICAO if "aprovada" not in c["text"]] + [_cap(" aprovado", 73.78, 74.2)]

FORMATOS = {
    "story": {"video": "bruto-story.mp4", "legenda_queimada": False, "ganho_sfx": 1.0},
    "feed": {"video": "bruto-feed.mp4", "legenda_queimada": True, "queimada_desde_s": 7.1, "ganho_sfx": 1.0},
}


def _cena(id_="mapa", componente="Rota", de=70.0, ate=75.0, **extra) -> dict:
    c = {"id": id_, "componente": componente, "de": de, "ate": ate, "props": {}, "sfx": []}
    c.update(extra)
    return c


def _criativo(*cenas, formatos=None, duracao=146.4) -> dict:
    return {"codigo": "AD368", "lancamento": "PI-NOV-26", "duracao_s": duracao,
            "formatos": copy.deepcopy(formatos if formatos is not None else FORMATOS), "cenas": list(cenas)}


def _salvar(tmp_path: Path, dados: dict) -> Path:
    p = tmp_path / "criativo.json"
    p.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return p


def test_componente_inexistente(tmp_path):
    with pytest.raises(CriativoInvalido, match="componente 'Grafiko'"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(componente="Grafiko"))), TRANSCRICAO)


def test_cenas_sobrepostas_sem_emenda(tmp_path):
    dados = _criativo(_cena("a", de=10, ate=20), _cena("b", de=19, ate=25))
    with pytest.raises(CriativoInvalido, match="'a'.*'b'"):
        carregar_criativo(_salvar(tmp_path, dados), TRANSCRICAO)


def test_cenas_coladas_sao_emenda_valida(tmp_path):
    dados = _criativo(_cena("a", de=10, ate=20), _cena("b", de=20, ate=25))
    assert len(carregar_criativo(_salvar(tmp_path, dados), TRANSCRICAO)["cenas"]) == 2


def test_cena_alem_da_duracao(tmp_path):
    with pytest.raises(CriativoInvalido, match="146.4"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(de=140, ate=150))), TRANSCRICAO)


def test_ancora_resolvida_na_ordem_da_fala(tmp_path):
    # "aprovada" aparece 3x; a âncora pega a 1ª ocorrência DENTRO de [de, ate]
    dados = _criativo(_cena(de=72.0, ate=75.0, ancora_palavras={"bandeira": "aprovada"}))
    c = carregar_criativo(_salvar(tmp_path, dados), TRANSCRICAO)
    assert c["cenas"][0]["ancoras_s"]["bandeira"] == 73.78


def test_ancora_inexistente_sugere_parecida(tmp_path):
    dados = _criativo(_cena(de=72.0, ate=75.0, ancora_palavras={"bandeira": "aprovada"}))
    with pytest.raises(CriativoInvalido, match="'aprovada'.*'aprovado'"):
        carregar_criativo(_salvar(tmp_path, dados), TRANSCRICAO_SEM_APROVADA)


def test_legenda_queimada_exige_flag_por_formato(tmp_path):
    formatos = copy.deepcopy(FORMATOS)
    del formatos["feed"]["legenda_queimada"]
    with pytest.raises(CriativoInvalido, match="feed.*legenda_queimada"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(), formatos=formatos)), TRANSCRICAO)


def test_legenda_queimada_exige_inicio_da_legenda_do_bruto(tmp_path):
    formatos = copy.deepcopy(FORMATOS)
    del formatos["feed"]["queimada_desde_s"]
    with pytest.raises(CriativoInvalido, match="feed.*queimada_desde_s"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(), formatos=formatos)), TRANSCRICAO)


def test_props_com_arroba_viram_segundos(tmp_path):
    cena = _cena(de=72.0, ate=75.0, ancora_palavras={"bandeira": "aprovada"},
                 props={"em": {"bandeira": "@bandeira", "saiTitulo": "@bandeira-0.5", "trilha": [72.5, "@bandeira"]}})
    r = resolver_criativo(carregar_criativo(_salvar(tmp_path, _criativo(cena)), TRANSCRICAO))
    em = r["cenas"][0]["props"]["em"]
    assert em == {"bandeira": 73.78, "saiTitulo": 73.28, "trilha": [72.5, 73.78]}


def test_sfx_aceita_ancora(tmp_path):
    cena = _cena(de=72.0, ate=75.0, ancora_palavras={"bandeira": "aprovada"},
                 sfx=[[72.0, "whoosh", 0.35], ["@bandeira", "ding", 0.3]])
    r = resolver_criativo(carregar_criativo(_salvar(tmp_path, _criativo(cena)), TRANSCRICAO))
    assert r["cenas"][0]["sfx"] == [[72.0, "whoosh", 0.35], [73.78, "ding", 0.3]]


def test_arroba_sem_ancora_declarada(tmp_path):
    cena = _cena(props={"em": {"bandeira": "@cume"}})
    with pytest.raises(CriativoInvalido, match="@cume"):
        resolver_criativo(carregar_criativo(_salvar(tmp_path, _criativo(cena)), TRANSCRICAO))


def test_rota_titulo_sai_antes_da_bandeira(tmp_path):
    cena = _cena(props={"em": {"bandeira": 73.0, "saiTitulo": 73.5}})
    with pytest.raises(CriativoInvalido, match="saiTitulo"):
        resolver_criativo(carregar_criativo(_salvar(tmp_path, _criativo(cena)), TRANSCRICAO))


def test_resolvido_traz_cobertos_e_cta(tmp_path):
    dados = _criativo(_cena("mapa", de=62.9, ate=75.8), _cena("cta", componente="Cta", de=133.0, ate=146.4))
    r = resolver_criativo(carregar_criativo(_salvar(tmp_path, dados), TRANSCRICAO))
    assert r["cobertos"] == [[62.9, 75.8]]          # o CTA não cobre o vídeo
    assert r["cta"] == [133.0, 146.4]


def test_cli_funciona_no_console_cp1252_do_windows(tmp_path, monkeypatch):
    import io
    import sys
    from scripts.video.criativo_schema import main
    crit = _salvar(tmp_path, _criativo(_cena(componente="Grafiko")))   # erro → mensagem com acento
    trans = tmp_path / "t.json"
    trans.write_text(json.dumps(TRANSCRICAO), encoding="utf-8")
    for nome in ("stdout", "stderr"):
        monkeypatch.setattr(sys, nome, io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    assert main([str(crit), "--transcricao", str(trans), "--saida", str(tmp_path / "r.json")]) == 1
    ok = _salvar(tmp_path, _criativo(_cena()))
    assert main([str(ok), "--transcricao", str(trans), "--saida", str(tmp_path / "r.json")]) == 0


def test_nomes_json_igual_a_biblioteca():
    nomes = json.loads((MODELO / "src" / "cenas" / "nomes.json").read_text(encoding="utf-8"))
    index = (MODELO / "src" / "cenas" / "index.ts").read_text(encoding="utf-8")
    m = re.search(r"export const CENAS[^=]*=\s*\{(.*?)\};", index, re.S)
    assert m, "não achei `export const CENAS = {…}` em src/cenas/index.ts"
    assert nomes == re.findall(r"(\w+),", m.group(1))


# --- ajustes por peça (storyboard editável por camadas) ---

def test_ajuste_valido_passa_para_o_resolvido(tmp_path):
    aj = {"story": {"etiquetas[0]": {"dx": 20, "dy": -40, "rot": 5.5, "escala": 1.2}}}
    dados = carregar_criativo(_salvar(tmp_path, _criativo(_cena(ajustes=aj))), TRANSCRICAO)
    assert resolver_criativo(dados)["cenas"][0]["ajustes"] == aj


def test_ajuste_em_formato_que_nao_existe(tmp_path):
    aj = {"h": {"titulo": {"dx": 10}}}
    with pytest.raises(CriativoInvalido, match="'mapa'.*formato 'h'"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(ajustes=aj))), TRANSCRICAO)


def test_ajuste_com_campo_nao_numerico_ou_desconhecido(tmp_path):
    for ruim in ({"dx": "10"}, {"zoom": 2}, {"escala": 0}, {"dx": True}):
        aj = {"story": {"titulo": ruim}}
        with pytest.raises(CriativoInvalido, match="'mapa'.*'titulo'"):
            carregar_criativo(_salvar(tmp_path, _criativo(_cena(ajustes=aj))), TRANSCRICAO)


def test_ajuste_de_cor_aceita_hex(tmp_path):
    aj = {"story": {"selo": {"cor": "#E8633D", "corTexto": "#F2EFE9CC"}}}
    dados = carregar_criativo(_salvar(tmp_path, _criativo(_cena(ajustes=aj))), TRANSCRICAO)
    assert dados["cenas"][0]["ajustes"] == aj
    with pytest.raises(CriativoInvalido, match="'selo'"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(ajustes={"story": {"selo": {"cor": "coral"}}}))), TRANSCRICAO)


def test_ajuste_com_peca_sem_nome(tmp_path):
    with pytest.raises(CriativoInvalido, match="peça sem nome"):
        carregar_criativo(_salvar(tmp_path, _criativo(_cena(ajustes={"story": {"": {"dx": 1}}}))), TRANSCRICAO)
