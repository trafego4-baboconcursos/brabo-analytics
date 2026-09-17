"""
ETL: copy escrito dos anúncios do Meta → Supabase (tabela: ad_copy_textos)

Puxa da Marketing API o texto que está **escrito** no anúncio — texto
principal, título, descrição, CTA e os cards do carrossel — e grava uma linha
por campo. Complementa `etl_legendas.py`, que cuida do que é **falado**.

    python etl/etl_copy_meta.py --launch PES-SET-26
    python etl/etl_copy_meta.py --launch PES-SET-26 --dry-run

Por que existe (achado de 17/09/26, PES-SET-26): dos R$ 679k do lançamento,
R$ 106k rodaram em carrossel/imagem. Esses anúncios nunca teriam transcrição de
fala — não há fala. O copy deles é este texto, e sem ele metade da verba ficava
invisível para qualquer análise de criativo. Os 3 carrosséis sozinhos são
R$ 87,6k, e o maior deles (AD367, R$ 41,4k) é o maior gasto do lançamento.

Também grava `formato` (video | carrossel | imagem) lido do payload, não do nome
do anúncio: `AD367 - Concurso para Mulher` é carrossel e nenhuma heurística de
nome acertaria isso.

Pré-requisitos .env: META_ACCESS_TOKEN
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()
logger = get_logger("etl_copy_meta")


def classificar_formato(creative: dict) -> str:
    """Formato real do criativo, lido do payload.

    Pelo nome do anúncio não dá: "AD367 - Concurso para Mulher" é um carrossel
    de 8 cards e era o maior gasto do PES-SET-26."""
    if not creative:
        return "?"
    story = creative.get("object_story_spec") or {}
    if story.get("video_data"):
        return "video"
    link = story.get("link_data") or {}
    if link.get("child_attachments"):
        return "carrossel"
    if link.get("image_hash") or link.get("picture"):
        return "imagem"
    feed = creative.get("asset_feed_spec") or {}
    if feed.get("videos"):
        return "video"
    if feed.get("images"):
        return "imagem"
    return "?"


def _limpar(valor) -> str:
    return " ".join(str(valor or "").split())


def extrair_copy(creative: dict) -> list[dict]:
    """Campos de texto do criativo → [{campo, ordem, texto}].

    `ordem` 0 é o nível do anúncio; 1..N são os cards do carrossel. A chave
    (campo, ordem) é o que permite guardar 8 títulos diferentes de um carrossel
    sem inventar coluna `title_8`."""
    if not creative:
        return []
    saida: list[dict] = []

    def add(campo: str, valor, ordem: int = 0) -> None:
        txt = _limpar(valor)
        if txt:
            saida.append({"campo": campo, "ordem": ordem, "texto": txt})

    story = creative.get("object_story_spec") or {}
    for chave in ("link_data", "video_data", "photo_data"):
        dados = story.get(chave) or {}
        if not dados:
            continue
        add("message", dados.get("message") or dados.get("caption"))
        add("title", dados.get("title") or dados.get("name"))
        add("description", dados.get("description") or dados.get("link_description"))
        add("cta", (dados.get("call_to_action") or {}).get("type"))
        add("link", dados.get("link") or (dados.get("call_to_action") or {})
            .get("value", {}).get("link"))
        for i, card in enumerate(dados.get("child_attachments") or [], start=1):
            add("title", card.get("name"), i)
            add("description", card.get("description"), i)
            add("message", card.get("message"), i)
            add("cta", (card.get("call_to_action") or {}).get("type"), i)
            add("link", card.get("link"), i)

    # Advantage+/dynamic creative: os textos ficam em asset_feed_spec, como
    # listas de variacoes. Cada variacao entra com sua propria ordem.
    feed = creative.get("asset_feed_spec") or {}
    for chave, campo in (("bodies", "message"), ("titles", "title"),
                         ("descriptions", "description")):
        for i, item in enumerate(feed.get(chave) or [], start=1):
            add(campo, item.get("text"), i)
    for i, cta in enumerate(feed.get("call_to_action_types") or [], start=1):
        add("cta", cta, i)

    vistos, unicos = set(), []
    for item in saida:
        chave = (item["campo"], item["ordem"])
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(item)
    return unicos


def gravar(registros: list[dict]) -> None:
    agora = datetime.now(timezone.utc)
    sql = text("""
        INSERT INTO ad_copy_textos (lancamento_codigo, ad_code, platform, ad_id,
                                    formato, campo, ordem, texto, n_palavras, updated_at)
        VALUES (:lancamento_codigo, :ad_code, :platform, :ad_id,
                :formato, :campo, :ordem, :texto, :n_palavras, :updated_at)
        ON CONFLICT (lancamento_codigo, ad_code, platform, campo, ordem) DO UPDATE SET
            ad_id = EXCLUDED.ad_id, formato = EXCLUDED.formato,
            texto = EXCLUDED.texto, n_palavras = EXCLUDED.n_palavras,
            updated_at = EXCLUDED.updated_at
    """)
    with get_engine().begin() as conn:
        for r in registros:
            conn.execute(sql, {**r, "updated_at": agora})


def relatorio(lancamento: str, registros: list[dict], gasto: dict[str, float]) -> None:
    por_formato: dict[str, set] = {}
    for r in registros:
        por_formato.setdefault(r["formato"], set()).add(r["ad_code"])

    print(f"\n{'=' * 70}\nCOPY ESCRITO - {lancamento}\n{'=' * 70}")
    n_ads = len({r["ad_code"] for r in registros})
    print(f"{len(registros)} campos de texto em {n_ads} anuncios\n")
    print(f"{'formato':12}{'anuncios':>10}{'gasto':>16}")
    for fmt, ads in sorted(por_formato.items(),
                           key=lambda x: -sum(gasto.get(a, 0) for a in x[1])):
        g = sum(gasto.get(a, 0) for a in ads)
        print(f"{fmt:12}{len(ads):>10}{'R$ ' + format(g, ',.0f'):>16}")

    estaticos = {a for f, ads in por_formato.items() if f in ("carrossel", "imagem")
                 for a in ads}
    if estaticos:
        g = sum(gasto.get(a, 0) for a in estaticos)
        print(f"\nEstatico coberto agora (nao teria transcricao de fala): "
              f"{len(estaticos)} anuncios, R$ {g:,.0f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Puxa o copy escrito dos anuncios do Meta")
    ap.add_argument("--launch", required=True, help="codigo do lancamento, ex: PES-SET-26")
    ap.add_argument("--dry-run", action="store_true", help="so relata, nao grava")
    args = ap.parse_args()

    import etl_meta_ads as meta_ads  # noqa: PLC0415 — evita custo de import no --help

    with get_engine().connect() as conn:
        ads = conn.execute(text(r"""
            SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) AS ad_code,
                   max(ad_id) AS ad_id, sum(spend) AS gasto
            FROM   meta_ads_daily
            WHERE  lancamento_codigo = :l
              AND  upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) ~ '^AD[0-9]+$'
            GROUP  BY 1
            HAVING sum(spend) > 0
            ORDER  BY 3 DESC
        """), {"l": args.launch}).fetchall()

    if not ads:
        logger.error("Nenhum anuncio do Meta com gasto em %s", args.launch)
        return 1

    gasto = {r[0]: float(r[2] or 0) for r in ads}
    logger.info("Consultando criativo de %d anuncios do Meta em %s", len(ads), args.launch)
    detalhes = meta_ads.fetch_creative_details([str(r[1]) for r in ads])

    registros: list[dict] = []
    sem_criativo = []
    for ad_code, ad_id, _ in ads:
        creative = (detalhes.get(str(ad_id)) or {}).get("creative") or {}
        campos = extrair_copy(creative)
        if not campos:
            sem_criativo.append(ad_code)
            continue
        formato = classificar_formato(creative)
        for campo in campos:
            registros.append({
                "lancamento_codigo": args.launch, "ad_code": ad_code,
                "platform": "meta", "ad_id": str(ad_id), "formato": formato,
                "n_palavras": len(campo["texto"].split()), **campo,
            })

    relatorio(args.launch, registros, gasto)
    if sem_criativo:
        print(f"\n[!] Sem nenhum campo de texto na API ({len(sem_criativo)}): "
              + ", ".join(sem_criativo[:15]))

    if args.dry_run:
        logger.info("dry-run: nada gravado")
        return 0

    gravar(registros)
    logger.info("%s: %d campos de copy gravados", args.launch, len(registros))
    return 0


if __name__ == "__main__":
    sys.exit(main())
