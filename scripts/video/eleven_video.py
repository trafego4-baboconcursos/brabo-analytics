"""Ilustração parada → vídeo animado pela API de vídeo da ElevenLabs (Veo 3.1 Fast, 1º quadro).

A ilustração da cena (ex.: Desenho) vira o `start_frame`; o modelo anima com câmera parada
(as etiquetas do vídeo ficam por cima, no mesmo lugar). Sem áudio — o som é o do bruto.
Chave: ELEVENLABS_API_KEY no .env (nunca impressa). Custo de cada geração vai para
videos/_ia_uso.jsonl (créditos antes/depois).

Uso:
    python -m scripts.video.eleven_video <imagem> <saida.mp4> --segundos 5.48 --prompt "…"
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://api.elevenlabs.io/v1"
MODELO = "veo-3.1-fast-generate-001"
DURACOES_VEO = (4, 6, 8)
BASE_PROMPT = ("Anime esta ilustração mantendo exatamente o mesmo desenho, traço, cores e enquadramento; "
               "câmera parada, sem zoom e sem cortes; não adicione texto, pessoas nem objetos novos; "
               "nunca crie mãos, braços ou dedos a mais; mão que segura objeto fica parada. ")
# ↑ AD368 (11/11/26): pedir "vire a página do caderno" gerou uma terceira mão. Peça movimento de
#   rosto, respiração, vapor, luz — não ação de mão com objeto.
ENV = Path("C:/dev/workspace-mmm/.env")
LOG = Path("C:/dev/workspace-mmm/videos/_ia_uso.jsonl")


def duracao_veo(segundos: float) -> int:
    """Menor duração aceita pelo Veo (4/6/8 s) que cobre a cena."""
    for d in DURACOES_VEO:
        if d >= segundos - 1e-6:
            return d
    raise ValueError(f"cena de {segundos} s passa do máximo do Veo (8 s): divida em duas")


def montar_pedido(imagem: Path, movimento: str, segundos: float) -> dict:
    mime = "image/png" if imagem.suffix.lower() == ".png" else "image/jpeg"
    return {
        "model_id": MODELO,
        "prompt": BASE_PROMPT + movimento,
        "duration_secs": duracao_veo(segundos),
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "generate_audio": False,
        "start_frame": {"type": "inline_base64", "mime_type": mime,
                        "content_base64": base64.b64encode(Path(imagem).read_bytes()).decode()},
    }


def filtro_aparar(cropdetect: str, largura: int, altura: int) -> str | None:
    """Filtro ffmpeg que tira as faixas pretas que o Veo põe nas laterais (cropdetect) e volta ao
    tamanho original sem distorcer (amplia pela largura e recorta no centro). None = sem faixa."""
    w, h, x, y = (int(v) for v in cropdetect.removeprefix("crop=").split(":"))
    if (w, h) == (largura, altura):
        return None
    m = 2   # +2 px de cada lado que sobrou cortado: a borda da faixa vem meio escura (antialias)
    if w < largura:
        w, x = w - 2 * m, x + m
    if h < altura:
        h, y = h - 2 * m, y + m
    return f"crop={w}:{h}:{x}:{y},scale={largura}:-2,crop={largura}:{altura}"


def aparar_bordas(video: Path) -> bool:
    """Aplica filtro_aparar no próprio arquivo (ffmpeg no PATH). True se mexeu."""
    import re
    import subprocess
    sonda = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "cropdetect=limit=24:round=2:reset=0",
                            "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    achados = re.findall(r"crop=\d+:\d+:\d+:\d+", sonda.stderr)
    dims = re.search(r", (\d{3,5})x(\d{3,5})", sonda.stderr)
    if not achados or not dims:
        return False
    filtro = filtro_aparar(achados[-1], int(dims.group(1)), int(dims.group(2)))
    if filtro is None:
        return False
    tmp = video.with_suffix(".aparado.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", filtro, "-an", "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", str(tmp)], check=True)
    tmp.replace(video)
    return True


def _chave() -> str:
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        if linha.startswith("ELEVENLABS_API_KEY="):
            return linha.split("=", 1)[1].strip().strip('"')
    raise SystemExit("ELEVENLABS_API_KEY não está no .env")


def _req(metodo: str, url: str, chave: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(url, data=dados, method=metodo,
                               headers={"xi-api-key": chave, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ElevenLabs {e.code}: {e.read().decode(errors='replace')[:400]}")


def creditos(chave: str) -> int:
    d = _req("GET", f"{API}/user/subscription", chave)
    return d["character_limit"] - d["character_count"]


def gerar(imagem: Path, saida: Path, movimento: str, segundos: float) -> dict:
    chave = _chave()
    antes = creditos(chave)
    g = _req("POST", f"{API}/flows/video", chave, montar_pedido(imagem, movimento, segundos))
    gid = g["id"]
    while True:
        time.sleep(12)
        g = _req("GET", f"{API}/flows/video/{gid}", chave)
        if g["status"] in ("completed", "failed"):
            break
    if g["status"] == "failed":
        raise SystemExit(f"geração {gid} falhou: {g.get('failure_reason')} {g.get('error_message', '')}")
    saida.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(g["content_url"], timeout=300) as r:
        saida.write_bytes(r.read())
    aparar_bordas(saida)       # Veo entrega com 4 px pretos nas laterais
    gasto = antes - creditos(chave)
    registro = {"quando": datetime.now().isoformat(timespec="seconds"), "ferramenta": "elevenlabs/" + MODELO,
                "id": gid, "imagem": str(imagem), "saida": str(saida), "segundos": duracao_veo(segundos),
                "creditos": gasto}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ilustração → vídeo (ElevenLabs, Veo 3.1 Fast)")
    ap.add_argument("imagem", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--segundos", type=float, required=True, help="duração da cena (vira 4/6/8 s)")
    ap.add_argument("--prompt", required=True, help="o movimento desejado (o resto do prompt é fixo)")
    a = ap.parse_args(argv)
    print(json.dumps(gerar(a.imagem, a.saida, a.prompt, a.segundos), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
