"""Design system de vídeo: tokens.json é a fonte única de cores/fontes/espaços do modelo Remotion."""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MODELO = RAIZ / "scripts" / "video" / "modelo"


def _tokens() -> dict:
    return json.loads((MODELO / "src" / "tokens.json").read_text(encoding="utf-8"))


def _luminancia(hex_cor: str) -> float:
    canais = [int(hex_cor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_cores_do_ad368():
    tok = _tokens()
    assert tok["cor"]["coral"] == "#E8643C" and tok["cor"]["lime"] == "#D4FF50"
    assert tok["cor"]["night"] == "#111111" and tok["cor"]["paper"] == "#F4EFE4"


def test_chaves_do_contrato():
    tok = _tokens()
    assert set(tok["cor"]) >= {"night", "card", "line", "text", "muted", "coral", "green", "paper",
                               "ink", "marker", "highlighter", "lime", "mat"}
    assert set(tok["fonte"]) == {"ui", "serif", "hand", "mono", "caption", "stamp"}
    assert set(tok["raio"]) == {"pilula", "cartao", "etiqueta"}


def test_espacos_no_grid_de_8():
    assert all(v % 8 == 0 or v == 4 for v in _tokens()["espaco"])


def test_legenda_lime_legivel_sobre_night():
    tok = _tokens()
    assert contraste(tok["cor"]["lime"], tok["cor"]["night"]) >= 4.5  # WCAG AA


def test_theme_nao_tem_cor_solta():
    ts = (MODELO / "src" / "theme.ts").read_text(encoding="utf-8")
    assert not re.search(r'"#[0-9A-Fa-f]{6}"', ts)
