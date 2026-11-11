"""Prepara um criativo animado novo a partir dos brutos (corte final + áudio).

Cria videos/<CODIGO>/ como cópia do modelo (scripts/video/modelo) e deixa pronto:
- public/<codigo>-<formato>.mp4: proxies a 30 fps (formato pelas dimensões do vídeo);
- src/data/captions.json: transcrição palavra a palavra (whisper medium + glossário
  + valores em R$ juntados), no formato Caption do Remotion;
- cortes.json: cortes de câmera de cada bruto;
- src/data/criativo.json: esqueleto com os formatos preenchidos (ganho dos efeitos
  pelo volume, sugestão de legenda queimada) e `cenas: []` para o roteiro.

Uso:
    python -m scripts.video.novo_criativo AD370 --lancamento PI-NOV-26 --brutos "videos/brutos/AD370"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
MODELO = Path(__file__).resolve().parent / "modelo"
GLOSSARIO_PADRAO = Path(__file__).resolve().parent / "glossario_transcricao.json"
EXTENSOES_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}


# ---------------------------------------------------------------- funções puras

def _nucleo(texto: str) -> str:
    """Palavra sem espaço nem pontuação nas pontas (para casar com o glossário)."""
    return re.sub(r"^\W+|\W+$", "", texto.strip())


def aplicar_glossario(palavras: list[dict], glossario: dict) -> list[dict]:
    """Troca sequências de palavras do whisper pelas corretas (mantém pontuação final e tempos)."""
    regras = sorted(glossario["regras"], key=lambda r: -len(r["de"]))  # a mais longa vence
    saida: list[dict] = []
    i = 0
    while i < len(palavras):
        for r in regras:
            n = len(r["de"])
            trecho = palavras[i:i + n]
            if len(trecho) == n and [_nucleo(w["text"]) for w in trecho] == r["de"]:
                ultimo = trecho[-1]["text"].strip()
                pontuacao = ultimo[len(_nucleo(ultimo)) + ultimo.find(_nucleo(ultimo)):]
                novos = list(r["para"])
                novos[-1] = novos[-1] + pontuacao
                ini, fim = trecho[0]["startMs"], trecho[-1]["endMs"]
                passo = (fim - ini) / len(novos)
                for k, texto in enumerate(novos):
                    a, b = int(ini + k * passo), int(ini + (k + 1) * passo)
                    saida.append({"text": texto if not saida else " " + texto, "startMs": a, "endMs": b,
                                  "timestampMs": (a + b) // 2, "confidence": None})
                i += n
                break
        else:
            w = dict(palavras[i])
            w["text"] = w["text"].strip() if not saida else " " + w["text"].strip()
            saida.append(w)
            i += 1
    return saida


def juntar_valores(palavras: list[dict]) -> list[dict]:
    """Cola o que o whisper quebra em valores: "R" "$" "7" ".234" ",00." → "R$ 7.234,00."."""
    saida: list[dict] = []
    for w in palavras:
        t = w["text"].strip()
        if saida:
            p = saida[-1]["text"].strip()
            cola = (t == "$" and p == "R") or bool(re.match(r"^[.,]\d", t)) or (bool(re.match(r"^\d", t)) and p.endswith("$"))
            if cola:
                sep = " " if p.endswith("$") else ""
                saida[-1]["text"] = saida[-1]["text"] + sep + t
                saida[-1]["endMs"] = w["endMs"]
                saida[-1]["timestampMs"] = (saida[-1]["startMs"] + w["endMs"]) // 2
                continue
        saida.append(dict(w))
    return saida


def ganho_por_rms(rms_formato: float, rms_story: float) -> float:
    """Quanto subir os efeitos num bruto mais alto que o do story (mantém o equilíbrio com a fala)."""
    return round(rms_formato / rms_story, 2) if rms_story > 0 else 1.0


def refinar_inicio_legenda(t_detectado: float, cortes: list[float], passo: float) -> float:
    """A legenda do bruto costuma entrar num corte: troca o instante da varredura pelo
    último corte entre o quadro anterior (sem legenda) e o detectado. Sem corte, fica igual."""
    no_intervalo = [c for c in cortes if t_detectado - passo < c <= t_detectado]
    return round(max(no_intervalo), 3) if no_intervalo else t_detectado


def formato_por_dimensao(largura: int, altura: int) -> str:
    return "story" if altura > largura else "h" if largura > altura else "feed"


def detectar_legenda_queimada(quadros: list[Path]) -> bool:
    """Sugestão: há texto claro com sombra escura deslocada na faixa de baixo (70%–95% da altura)?

    Conta pixels quase brancos cujo vizinho 3 px abaixo e à direita é quase preto. É
    só uma pista — o Claude confirma olhando os quadros antes de gravar no criativo.
    """
    votos = 0
    for q in quadros:
        img = Image.open(q).convert("L")
        w, h = img.size
        faixa = img.crop((0, int(h * 0.70), w, int(h * 0.95)))
        px = faixa.load()
        fw, fh = faixa.size
        amostra = fw * fh / 2
        com_sombra = sum(
            1 for y in range(0, fh - 3) for x in range(0, fw - 3, 2)
            if px[x, y] > 230 and px[x + 3, y + 3] < 50
        )
        # selo do bruto (caixa branca sólida, ex. "CONCURSO PÚBLICO" do AD358) tem muito
        # branco na faixa (8–11% medido); legenda queimada tem pouco (0,8–3,5%)
        claro = sum(1 for y in range(fh) for x in range(0, fw, 2) if px[x, y] > 230)
        if com_sombra / amostra > 0.0015 and claro / amostra < 0.06:
            votos += 1
    return votos >= (len(quadros) + 1) // 2


# ---------------------------------------------------------------- ffmpeg / whisper

def _ffmpeg_bin() -> Path | None:
    """ffmpeg do winget (o PATH do shell nem sempre enxerga a instalação recente)."""
    if shutil.which("ffmpeg"):
        return None
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    achados = sorted(base.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"))
    return achados[-1].parent if achados else None


def _exe(nome: str) -> str:
    pasta = _ffmpeg_bin()
    return str(pasta / f"{nome}.exe") if pasta else nome


def _sonda(video: Path) -> dict:
    out = subprocess.run([_exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    return {"largura": s["width"], "altura": s["height"], "duracao": float(j["format"]["duration"])}


def _volume_medio_db(video: Path) -> float:
    err = subprocess.run([_exe("ffmpeg"), "-i", str(video), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", err)
    if not m:
        raise RuntimeError(f"não consegui medir o volume de {video.name} (o vídeo tem áudio?)")
    return float(m.group(1))


def _cortes(video: Path) -> list[float]:
    err = subprocess.run([_exe("ffmpeg"), "-i", str(video), "-vf", "scale=270:-1,select='gt(scene,0.3)',showinfo",
                          "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [round(float(x), 3) for x in re.findall(r"pts_time:([\d.]+)", err)]


def _proxy(origem: Path, destino: Path) -> None:
    subprocess.run([_exe("ffmpeg"), "-v", "error", "-y", "-i", str(origem), "-r", "30", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(destino)], check=True)


def _quadros(video: Path, pasta: Path, tempos: list[float]) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    saida = []
    for i, t in enumerate(tempos):
        p = pasta / f"q{i:02d}.png"
        subprocess.run([_exe("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=540:-1", str(p)], check=True)
        saida.append(p)
    return saida


def _transcrever(video: Path) -> list[dict]:
    from faster_whisper import WhisperModel  # dependência pesada: só quando transcreve
    modelo = WhisperModel("medium", device="cpu", compute_type="int8")
    segs, _ = modelo.transcribe(str(video), language="pt", word_timestamps=True, vad_filter=True)
    palavras = []
    for s in segs:
        for w in s.words or []:
            a, b = int(w.start * 1000), int(w.end * 1000)
            palavras.append({"text": w.word if palavras else w.word.strip(), "startMs": a, "endMs": b,
                             "timestampMs": (a + b) // 2, "confidence": None})
    return palavras


# ---------------------------------------------------------------- CLI

def _copiar_modelo(destino: Path) -> None:
    def ignorar(d, nomes):
        fora = [n for n in nomes if n in {"node_modules", "out", ".remotion"}]
        if Path(d).name == "public":
            fora += [n for n in nomes if n != "sfx"]
        if Path(d).name == "data":
            fora += list(nomes)
        return fora
    shutil.copytree(MODELO, destino, ignore=ignorar)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prepara um criativo animado novo a partir dos brutos")
    ap.add_argument("codigo", help="ex.: AD370")
    ap.add_argument("--lancamento", required=True)
    ap.add_argument("--brutos", type=Path, required=True, help="pasta com os brutos (um por formato)")
    ap.add_argument("--destino", type=Path, default=None, help="padrão: videos/<CODIGO>")
    ap.add_argument("--pular-npm", action="store_true")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")

    destino = a.destino or RAIZ / "videos" / a.codigo
    if destino.exists():
        print(f"{destino} já existe; escolha outro --destino ou apague a pasta", file=sys.stderr)
        return 1
    brutos = sorted(p for p in a.brutos.iterdir() if p.suffix.lower() in EXTENSOES_VIDEO)
    if not brutos:
        print(f"nenhum vídeo em {a.brutos}", file=sys.stderr)
        return 1

    por_formato: dict[str, tuple[Path, dict]] = {}
    for b in brutos:
        info = _sonda(b)
        f = formato_por_dimensao(info["largura"], info["altura"])
        if f in por_formato:
            print(f"dois brutos {f}: {por_formato[f][0].name} e {b.name}; deixe um por formato", file=sys.stderr)
            return 1
        por_formato[f] = (b, info)
    print("formatos:", ", ".join(f"{f}={b.name}" for f, (b, _) in por_formato.items()))

    _copiar_modelo(destino)
    if not a.pular_npm:
        subprocess.run("npm ci --no-audit --no-fund", cwd=destino, shell=True, check=True)
    (destino / "src" / "data").mkdir(parents=True, exist_ok=True)

    codigo = a.codigo.lower()
    formatos, cortes = {}, {}
    db = {f: _volume_medio_db(b) for f, (b, _) in por_formato.items()}
    ref_db = db.get("story", next(iter(db.values())))
    for f, (b, info) in por_formato.items():
        proxy = destino / "public" / f"{codigo}-{f}.mp4"
        _proxy(b, proxy)
        cortes[f] = _cortes(proxy)
        dur = info["duracao"]
        qs = _quadros(proxy, destino / "out" / "quadros" / f, [dur * k / 6 for k in range(1, 6)])
        queimada = detectar_legenda_queimada(qs)
        formatos[f] = {"video": proxy.name, "legenda_queimada": queimada,
                       "ganho_sfx": ganho_por_rms(10 ** (db[f] / 20), 10 ** (ref_db / 20))}
        if queimada:
            # 1º segundo (de 0,5 em 0,5 até 20 s) em que a legenda do bruto aparece
            inicio = _quadros(proxy, destino / "out" / "quadros" / f"{f}-inicio", [k * 0.5 for k in range(0, 41)])
            visto = next((k * 0.5 for k, q in enumerate(inicio) if detectar_legenda_queimada([q])), 0.0)
            formatos[f]["queimada_desde_s"] = refinar_inicio_legenda(visto, cortes[f], passo=0.5)
        print(f"{f}: {len(cortes[f])} cortes, ganho {formatos[f]['ganho_sfx']}, legenda queimada (sugestão): {queimada}")

    origem_fala = por_formato.get("story", next(iter(por_formato.values())))[0]
    glossario = json.loads(GLOSSARIO_PADRAO.read_text(encoding="utf-8"))
    palavras = juntar_valores(aplicar_glossario(_transcrever(origem_fala), glossario))
    (destino / "src" / "data" / "captions.json").write_text(json.dumps(palavras, ensure_ascii=False, indent=0), encoding="utf-8")
    (destino / "cortes.json").write_text(json.dumps(cortes, indent=1), encoding="utf-8")
    duracao = round(min(info["duracao"] for _, info in por_formato.values()), 2)
    criativo = {"codigo": a.codigo, "lancamento": a.lancamento, "duracao_s": duracao, "selo_bruto_ate_s": None,
                "formatos": formatos, "cenas": []}
    (destino / "src" / "data" / "criativo.json").write_text(json.dumps(criativo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok: {len(palavras)} palavras, criativo em {destino}")
    print("próximos passos: conferir legenda_queimada olhando out/quadros/, escrever as cenas no criativo.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
