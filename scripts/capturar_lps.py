"""
scripts/capturar_lps.py — Print das landing pages, guardado no banco.

Substitui o thum.io no "Landing Pages que Mais Converteram" do debriefing.
O serviço público não dava controle de nada: renderizava a versão responsiva
por padrão, decidia sozinho quando recapturar e ia à rede a cada carregamento
da página. Aqui o print é tirado uma vez, em viewport desktop, e fica no banco.

Por que um script e não parte do app: a captura precisa do Chromium (~400MB
via Playwright), e a imagem de produção é uma python:3.10-slim. Rodar isto
fora do container mantém o deploy leve — o app só lê bytes do banco. Se um dia
a captura tiver que ser automática lá dentro, aí sim entra o Chromium na
imagem.

Uso:
    python scripts/capturar_lps.py --lancamento PES-SET-26
    python scripts/capturar_lps.py --lancamento PES-SET-26 --forcar
    python scripts/capturar_lps.py --url https://lp.braboconcursos.com.br/xxx

Requer (só na máquina que captura, não em produção):
    pip install playwright && playwright install chromium
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from sqlalchemy import text  # noqa: E402

from frontend.db import _get_engine  # noqa: E402
from frontend.db_readers.ga4 import read_landing_pages_por_etapa  # noqa: E402
from logger import get_logger  # noqa: E402

logger = get_logger("capturar_lps")

# Renderiza como desktop (1280 de largura CSS) mas grava a imagem em escala
# reduzida: o deviceScaleFactor encolhe o arquivo SEM mudar o layout, que é o
# problema de simplesmente usar um viewport estreito (viraria layout mobile).
# 1280 * 0.5 = 640px de largura no arquivo, exibido a 300 — sobra resolução
# pra tela retina sem guardar uma imagem de vários MB.
VIEWPORT_LARGURA = 1280
VIEWPORT_ALTURA = 800
ESCALA = 0.5
QUALIDADE_JPEG = 72

# As LPs ficam atrás do Cloudflare, que barra o User-Agent padrão do Playwright
# ("HeadlessChrome"): a primeira captura gravou a tela "Um momento…" do desafio
# em vez da página (18/09/26). Com UA de navegador real o desafio não aparece —
# testado contra as quatro combinações (headless shell, headless+UA, Chrome
# real headless, Chrome real com janela) e só a do UA padrão é barrada.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

DDL = """
CREATE TABLE IF NOT EXISTS lp_screenshots (
    landing_page      TEXT PRIMARY KEY,
    url               TEXT NOT NULL,
    lancamento_codigo TEXT,
    content_type      TEXT NOT NULL DEFAULT 'image/jpeg',
    image_data        BYTEA NOT NULL,
    largura           INT,
    altura            INT,
    bytes             INT,
    capturado_em      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lp_screenshots_lancamento ON lp_screenshots (lancamento_codigo);
"""


def _base_url(produto: str | None) -> str:
    """Mesma regra do template do debriefing (lp_base_url)."""
    return ("https://lp.mateusandrade.com.br" if produto == "INSS"
            else "https://lp.braboconcursos.com.br")


def _landing_pages_do_lancamento(code: str) -> list[str]:
    por_etapa = read_landing_pages_por_etapa(code)
    paths: list[str] = []
    for linhas in por_etapa.values():
        for l in linhas:
            lp = l.get("landing_page") or ""
            if lp.startswith("/") and lp not in paths:
                paths.append(lp)
    return paths


def _ja_capturadas(conn) -> set[str]:
    return {r[0] for r in conn.execute(text("SELECT landing_page FROM lp_screenshots"))}


def capturar(paths_e_urls: list[tuple[str, str]], code: str | None, forcar: bool) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright não instalado. Rode: pip install playwright && playwright install chromium")
        return 1

    engine = _get_engine()
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in DDL.split(";"))):
            conn.execute(text(stmt))
        existentes = set() if forcar else _ja_capturadas(conn)

    pendentes = [(lp, url) for lp, url in paths_e_urls if lp not in existentes]
    if not pendentes:
        logger.info("Nada a capturar (%d já no banco; use --forcar pra refazer).", len(paths_e_urls))
        return 0

    logger.info("Capturando %d página(s)...", len(pendentes))
    erros = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": VIEWPORT_LARGURA, "height": VIEWPORT_ALTURA},
            device_scale_factor=ESCALA,
            user_agent=USER_AGENT,
            locale="pt-BR",
        )
        page = ctx.new_page()
        for lp, url in pendentes:
            try:
                # `networkidle` NÃO serve aqui: estas LPs têm pixel de
                # rastreamento, player de vídeo e polling, então a rede nunca
                # fica ociosa e o goto estourava os 60s em 100% das páginas
                # (primeira tentativa, 18/09/26). Espera o `load` e, se nem
                # ele vier, segue assim mesmo — o que importa pro print é o
                # DOM montado, não a rede parar.
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                try:
                    page.wait_for_load_state("load", timeout=15_000)
                except Exception:
                    pass
                page.wait_for_timeout(2_000)
                # Rola até o fim pra disparar lazy-load de imagem antes do print
                # da página inteira — sem isso o miolo sai em branco.
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(300)
                # Não grava desafio de bot no lugar da página: a primeira
                # versão salvou a tela do Cloudflare sem reclamar, e o defeito
                # só apareceu quando eu abri a imagem.
                titulo = (page.title() or "").lower()
                corpo = (page.inner_text("body")[:400] or "").lower()
                if ("um momento" in titulo or "just a moment" in titulo
                        or "security verification" in corpo or "verify you are human" in corpo):
                    raise RuntimeError(f"veio o desafio do Cloudflare, não a página (título: {page.title()!r})")

                dims = page.evaluate(
                    "() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight]"
                )
                # Recorta na largura do viewport em vez de aceitar a largura do
                # documento: uma LP com marquee/ticker estoura o scrollWidth
                # (a v5 do PBB-AGO-26 reportou 7.975px) e o full_page puro
                # devolvia um retângulo quase vazio, com o conteúdo espremido
                # em 13% da imagem. Altura também tem teto — página de 3.800px
                # já é o normal aqui, mas não vale guardar uma de 20.000.
                altura = min(int(dims[1]), 6000)
                img = page.screenshot(
                    full_page=True, type="jpeg", quality=QUALIDADE_JPEG,
                    clip={"x": 0, "y": 0, "width": VIEWPORT_LARGURA, "height": altura},
                )
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO lp_screenshots
                            (landing_page, url, lancamento_codigo, content_type, image_data, largura, altura, bytes, capturado_em)
                        VALUES (:lp, :url, :code, 'image/jpeg', :data, :w, :h, :b, NOW())
                        ON CONFLICT (landing_page) DO UPDATE SET
                            url = EXCLUDED.url,
                            lancamento_codigo = EXCLUDED.lancamento_codigo,
                            content_type = EXCLUDED.content_type,
                            image_data = EXCLUDED.image_data,
                            largura = EXCLUDED.largura,
                            altura = EXCLUDED.altura,
                            bytes = EXCLUDED.bytes,
                            capturado_em = NOW()
                    """), {"lp": lp, "url": url, "code": code, "data": img,
                           "w": int(dims[0]), "h": int(dims[1]), "b": len(img)})
                logger.info("OK %s (%.0f KB, página %dx%d css)", lp, len(img) / 1024, dims[0], dims[1])
            except Exception as e:
                erros += 1
                logger.error("FALHOU %s: %s", lp, e)
        browser.close()
    return 1 if erros and erros == len(pendentes) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Captura print das landing pages e grava no banco.")
    ap.add_argument("--lancamento", help="Código do lançamento (ex: PES-SET-26)")
    ap.add_argument("--url", help="Captura uma URL avulsa em vez do lançamento inteiro")
    ap.add_argument("--forcar", action="store_true", help="Recaptura mesmo o que já está no banco")
    args = ap.parse_args()

    if args.url:
        from urllib.parse import urlparse
        lp = urlparse(args.url).path or "/"
        return capturar([(lp, args.url)], None, True)

    if not args.lancamento:
        ap.error("informe --lancamento ou --url")

    code = args.lancamento.upper()
    from frontend.core import get_launches, resolve_launch
    launch = resolve_launch(code, get_launches())
    if not launch:
        logger.error("Lançamento %s não encontrado.", code)
        return 1

    base = _base_url(getattr(launch, "product", None))
    paths = _landing_pages_do_lancamento(code)
    if not paths:
        logger.error("Nenhuma landing page encontrada no GA4 para %s.", code)
        return 1
    return capturar([(lp, base + lp) for lp in paths], code, args.forcar)


if __name__ == "__main__":
    raise SystemExit(main())
