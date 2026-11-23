"""Gera os retratos da tela de loading (frases de pensadores).

Cada autor de BS_QUOTES (frontend/static/js/carregamento.js) tem um retrato no
estilo de um estudo a sanguínea do Leonardo da Vinci, gerado por IA via
ElevenLabs Flows (POST /v1/flows/image, modelo gemini-3-pro-image). O PNG bruto
(1024px) vai para --bruto; o recorte final (208px, webp ~10 KB, rosto
centralizado para o círculo de 104px) vai para frontend/static/img/pensadores/.

    python scripts/gerar_retratos_pensadores.py                 # só os que faltam
    python scripts/gerar_retratos_pensadores.py --so einstein   # refaz um
    python scripts/gerar_retratos_pensadores.py --so-recorte    # recorta de novo os brutos

A cor do tema não vem daqui: é um overlay em CSS (.bs-loading-foto::after).
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
import time
import urllib.request

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "frontend" / "static" / "img" / "pensadores"
BRUTO_PADRAO = RAIZ / "outputs" / "_retratos_pensadores_bruto"
BASE = "https://api.elevenlabs.io/v1"
MODELO = "gemini-3-pro-image"

ESTILO = (
    "Portrait study drawn in the style of a Leonardo da Vinci red chalk (sanguine) drawing "
    "on aged, warm-toned parchment paper. Head and shoulders, three-quarter view, the face centered "
    "in the middle of the square frame with generous margin around the head so it survives a circular crop. "
    "Fine cross-hatching, delicate sepia ink contour lines, soft smudged shading, faint foxing stains "
    "and texture on the paper. Monochrome sanguine and sepia only. "
    "The head is large, filling about 60% of the image height. "
    "No text, no letters, no signature, no border, no frame, no inner rectangle or framed vignette: "
    "the drawing sits directly on the full sheet."
)

# slug -> descrição visual (em inglês, vai direto no prompt)
PESSOAS: dict[str, str] = {
    # ── filósofos e pensadores clássicos ──
    "seneca": "Seneca the Younger, Roman Stoic philosopher, older man, balding with short beard, as in his classical busts",
    "aristoteles": "Aristotle, Greek philosopher, short curly hair and neat beard, as in his classical marble bust",
    "marco-aurelio": "Marcus Aurelius, the Roman emperor and Stoic philosopher, curly hair and full curly beard, as in his classical marble busts",
    "epicteto": "Epictetus, Greek Stoic philosopher and former slave, elderly man with long beard, simple cloak",
    "socrates": "Socrates, Greek philosopher, snub nose, bald head and full beard, as in his classical busts",
    "platao": "Plato, Greek philosopher, broad forehead and long full beard, as in his classical bust",
    "confucio": "Confucius, Chinese philosopher, elderly man with long beard and traditional scholar's robe and cap",
    "lao-tse": "Laozi, ancient Chinese sage, very old man with long white beard and flowing robes",
    "sun-tzu": "Sun Tzu, ancient Chinese general and strategist, middle-aged with thin moustache and topknot, armor collar",
    "leonardo-da-vinci": "Leonardo da Vinci, old man with long flowing hair and very long beard, as in his famous red chalk self-portrait",
    "einstein": "Albert Einstein, the physicist, in his 60s, unruly white hair and bushy moustache, as in his famous photographs",
    "descartes": "Rene Descartes, French philosopher, shoulder-length dark hair and thin moustache, as in the Frans Hals portrait",
    "kant": "Immanuel Kant, German philosopher, elderly, powdered hair tied back, 18th century collar",
    "nietzsche": "Friedrich Nietzsche, German philosopher, enormous walrus moustache, intense gaze, 19th century suit",
    "drucker": "Peter Drucker, management thinker, elderly man with glasses and receding hair, suit and tie",
    "rousseau": "Jean-Jacques Rousseau, Genevan philosopher, 18th century fur cap and coat, as in the Allan Ramsay portrait",
    "protagoras": "Protagoras, ancient Greek sophist, middle-aged with curly beard, Greek himation",
    "cora-coralina": "Cora Coralina, Brazilian poet, very elderly woman with white hair pinned back and kind wrinkled face",
    "fernando-pessoa": "Fernando Pessoa, Portuguese poet, round glasses, thin moustache and fedora hat",
    "joseph-addison": "Joseph Addison, English essayist, early 18th century long curled wig",
    "francis-bacon": "Francis Bacon, English philosopher, Elizabethan ruff collar, pointed beard and tall hat",
    "santayana": "George Santayana, philosopher, older man, bald with neat white moustache, early 20th century suit",
    "mandela": "Nelson Mandela, in his 70s, short grey hair, warm smile, patterned shirt",
    "paulo-freire": "Paulo Freire, Brazilian educator, older man with long white beard and glasses",
    "epicuro": "Epicurus, Greek philosopher, long curly beard, as in his classical marble bust",
    "pascal": "Blaise Pascal, French mathematician and philosopher, long 17th century hair, white collar",
    "montaigne": "Michel de Montaigne, French essayist, 16th century ruff collar, short beard and bald crown",
    "kierkegaard": "Soren Kierkegaard, Danish philosopher, young man with tall swept-up hair, high collar and cravat",
    "spinoza": "Baruch Spinoza, Dutch philosopher, long dark curly hair and thin moustache, 17th century collar",
    "heraclito": "Heraclitus, ancient Greek philosopher, brooding older man with long beard",
    "schopenhauer": "Arthur Schopenhauer, German philosopher, elderly, white tufts of hair at the sides, stern expression",
    "voltaire": "Voltaire, French writer, thin face, sly smile, 18th century powdered wig",
    "cicero": "Cicero, Roman statesman and orator, clean-shaven older man, as in his classical bust",
    "bertrand-russell": "Bertrand Russell, British philosopher, elderly, thick white hair, pipe in hand",
    "wittgenstein": "Ludwig Wittgenstein, Austrian philosopher, short wavy hair, intense eyes, open-collar shirt",
    # ── grandes pensadores ──
    "guimaraes-rosa": "Joao Guimaraes Rosa, Brazilian writer, round glasses and bow tie",
    "clarice-lispector": "Clarice Lispector, Brazilian writer, high cheekbones, almond eyes, dark hair, 1960s",
    "churchill": "Winston Churchill, British prime minister, bald, jowly, bow tie, stern expression",
    "gandhi": "Mahatma Gandhi, bald, round wire glasses, gentle smile, simple white shawl",
    "goethe": "Johann Wolfgang von Goethe, German writer, high forehead, 18th century cravat",
    "benjamin-franklin": "Benjamin Franklin, elderly, long thinning hair, small round spectacles, 18th century coat",
    "martin-luther-king": "Martin Luther King Jr., short hair and moustache, suit and tie, earnest expression",
    "drummond": "Carlos Drummond de Andrade, Brazilian poet, thin face, round glasses, receding hair",
    "suassuna": "Ariano Suassuna, Brazilian writer, elderly, white hair, glasses, warm smile",
    "helen-keller": "Helen Keller, American author, early 20th century, hair pinned up, high lace collar",
    "shakespeare": "William Shakespeare, high forehead, moustache and small beard, Elizabethan collar",
    "viktor-frankl": "Viktor Frankl, Austrian psychiatrist, older man with glasses and swept-back hair",
    "steve-jobs": "Steve Jobs, in his 50s, round rimless glasses, short beard, black turtleneck",
    "darcy-ribeiro": "Darcy Ribeiro, Brazilian anthropologist, older man with white hair and glasses, smiling",
    # ── bíblicos (sem retrato histórico: figura idealizada, arte renascentista) ──
    "salomao": "King Solomon of the Bible, a wise middle-aged king with a long beard and a simple crown, in ancient Near Eastern robes",
    "paulo": "Apostle Paul, as traditionally depicted in Renaissance art, balding with a long dark beard, simple robe",
    "davi": "King David of the Bible, young king with curly hair and short beard, simple crown",
    "moises": "Moses, as depicted in Michelangelo-era art, strong elderly lawgiver with a head cloth draped over his hair, thick wavy beard, holding the stone tablets against his chest",
    "josue": "Joshua of the Bible, a strong middle-aged warrior leader with short beard, ancient leather armor collar",
    "isaias": "Prophet Isaiah, as depicted in Renaissance art, elderly prophet with long beard and head cloth",
    "jeremias": "Prophet Jeremiah, as depicted in Renaissance art, pensive elderly prophet with long beard",
    "jesus": "Jesus of Nazareth, as traditionally depicted in Renaissance art, shoulder-length hair and beard, serene expression, simple robe",
    "tiago": "Apostle James, as depicted in Renaissance art, middle-aged with long hair and beard, simple robe",
    "pedro": "Apostle Peter, as depicted in Renaissance art, older man with short curly grey hair and short beard",
    # ── cientistas ──
    "marie-curie": "Marie Curie, the physicist and chemist, around 40 years old, hair pinned up, simple dark high-collared dress, as in her well-known photographs",
    "feynman": "Richard Feynman, physicist, in his 50s, wavy swept-back hair, playful smile",
    "carl-sagan": "Carl Sagan, astronomer, in his 40s, dark hair, turtleneck under a corduroy jacket",
    "hawking": "Stephen Hawking, physicist, as a young man in his 20s before his illness, glasses and tousled hair",
    "turing": "Alan Turing, mathematician, young man with dark side-parted hair, 1930s suit",
    "newton": "Isaac Newton, long flowing hair (wig), 17th century cravat, as in the Godfrey Kneller portrait",
    "niels-bohr": "Niels Bohr, physicist, heavy brows, receding hair, 1920s suit",
    "pasteur": "Louis Pasteur, chemist, short beard, 19th century suit",
    "darwin": "Charles Darwin, elderly, very long white beard and bald crown",
    "edison": "Thomas Edison, inventor, middle-aged, swept white hair, bow tie",
    "rosalind-franklin": "Rosalind Franklin, scientist, early 30s, short dark hair, 1950s",
    "oswaldo-cruz": "Oswaldo Cruz, Brazilian physician and scientist, large curled moustache, early 20th century suit",
    "linus-pauling": "Linus Pauling, chemist, elderly with white hair, beret, warm smile",
    "faraday": "Michael Faraday, scientist, middle-aged, curly hair, 19th century cravat",
    "jane-goodall": "Jane Goodall, primatologist, older woman with grey hair in a ponytail, gentle smile",
    "fleming": "Alexander Fleming, bacteriologist, older man with bow tie and swept-back grey hair",
    "arquimedes": "Archimedes, ancient Greek mathematician, older man with curly beard, Greek tunic",
    "lavoisier": "Antoine Lavoisier, chemist, 18th century powdered wig, as in the Jacques-Louis David portrait",
}


def _chave() -> str:
    env = (RAIZ / ".env").read_text(encoding="utf-8").splitlines()
    for linha in env:
        if linha.startswith("ELEVENLABS_API_KEY="):
            return linha.split("=", 1)[1].strip().strip('"')
    sys.exit("ELEVENLABS_API_KEY ausente no .env")


def _api(chave: str, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo,
                                 headers={"xi-api-key": chave, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def recortar(png: pathlib.Path, destino: pathlib.Path) -> int:
    """Quadrado central de 76% (a partir de 7% do topo) → 208px webp."""
    im = Image.open(png).convert("RGB")
    w, h = im.size
    lado = int(w * 0.76)
    x0, y0 = (w - lado) // 2, int(h * 0.07)
    im = im.crop((x0, y0, x0 + lado, y0 + lado)).resize((208, 208), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=78)
    destino.write_bytes(buf.getvalue())
    return len(buf.getvalue())


def gerar(slugs: list[str], bruto: pathlib.Path, lote: int = 6) -> list[str]:
    chave = _chave()
    falhas: list[str] = []
    for i in range(0, len(slugs), lote):
        pend: dict[str, str] = {}
        for slug in slugs[i:i + lote]:
            corpo = {"model_id": MODELO, "prompt": f"{PESSOAS[slug]}. {ESTILO}",
                     "aspect_ratio": "1:1", "resolution": "1K"}
            try:
                pend[slug] = _api(chave, "POST", "/flows/image", corpo)["id"]
            except Exception as e:  # noqa: BLE001 — relata e segue para o próximo
                print(f"FALHOU ao enviar {slug}: {e}", flush=True)
                falhas.append(slug)
        t0 = time.time()
        while pend and time.time() - t0 < 600:
            time.sleep(5)
            for slug, gid in list(pend.items()):
                g = _api(chave, "GET", f"/flows/image/{gid}")
                if g["status"] == "completed":
                    png = bruto / f"{slug}.png"
                    urllib.request.urlretrieve(g["content_url"], png)
                    n = recortar(png, DESTINO / f"{slug}.webp")
                    print(f"ok {slug} ({n} bytes)", flush=True)
                    del pend[slug]
                elif g["status"] == "failed":
                    print(f"FALHOU {slug}: {g.get('failure_reason')}", flush=True)
                    falhas.append(slug)
                    del pend[slug]
        for slug in pend:
            print(f"SEM RESPOSTA {slug}", flush=True)
            falhas.append(slug)
    return falhas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so", nargs="*", help="slugs específicos (refaz mesmo se já existir)")
    ap.add_argument("--so-recorte", action="store_true", help="só recorta de novo os PNG brutos")
    ap.add_argument("--bruto", type=pathlib.Path, default=BRUTO_PADRAO)
    ap.add_argument("--dry-run", action="store_true", help="lista o que seria gerado")
    a = ap.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    a.bruto.mkdir(parents=True, exist_ok=True)

    if a.so_recorte:
        for png in sorted(a.bruto.glob("*.png")):
            print(png.stem, recortar(png, DESTINO / f"{png.stem}.webp"))
        return

    if a.so:
        desconhecidos = [s for s in a.so if s not in PESSOAS]
        if desconhecidos:
            sys.exit(f"slug sem descrição em PESSOAS: {desconhecidos}")
        slugs = a.so
    else:
        slugs = [s for s in PESSOAS if not (DESTINO / f"{s}.webp").exists()]
    print(f"{len(slugs)} retrato(s) a gerar: {', '.join(slugs)}", flush=True)
    if a.dry_run or not slugs:
        return
    falhas = gerar(slugs, a.bruto)
    if falhas:
        print(f"\n{len(falhas)} falha(s): {' '.join(falhas)}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
