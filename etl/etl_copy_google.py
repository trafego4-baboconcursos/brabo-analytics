"""
ETL: copy escrito dos anúncios do Google Ads → Supabase (tabela: ad_copy_textos)

Puxa headlines, long headlines, descriptions, CTAs e final URL de cada `ADxxx`
do Google e grava na mesma tabela do Meta, com `platform='google'`.

    python etl/etl_copy_google.py --launch PES-SET-26
    python etl/etl_copy_google.py --launch PES-SET-26 --dry-run

Por que existe: no PES-SET-26, 18 `ADxxx` rodaram **só no Google** e somavam
R$ 81.622 (12% da verba) sem copy nenhum no banco — a única fatia grande que
sobrou depois de `etl_copy_meta.py` e `etl_transcrever_meta.py`.

Três tipos de anúncio aparecem, e os três guardam o texto em campos diferentes:
`DEMAND_GEN_VIDEO_RESPONSIVE_AD`, `VIDEO_RESPONSIVE_AD` e
`DEMAND_GEN_MULTI_ASSET_AD`.

O mesmo `ADxxx` se repete em dezenas de grupos/campanhas. Em vez de gravar a
primeira ocorrência, junta o conjunto **distinto** de textos por campo: é o pool
de copy daquele criativo, e variação entre campanhas é informação, não ruído.

Pré-requisitos .env: GOOGLE_ADS_* (mesmas credenciais de etl_google_ads.py)
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()
logger = get_logger("etl_copy_google")

RX_AD = re.compile(r"^(AD\d+)", re.I)

# Cada tipo guarda o texto num bloco proprio do payload. A ordem aqui e a de
# preferencia: o primeiro bloco presente no anuncio e o que vale.
BLOCOS = (
    "demandGenVideoResponsiveAd",
    "videoResponsiveAd",
    "demandGenMultiAssetAd",
)

# campo no payload -> campo em ad_copy_textos. Mantem o mesmo vocabulario do
# Meta ('title'/'description'/'cta'/'link') pra tabela cruzar as duas fontes.
CAMPOS = {
    "headlines": "title",
    "longHeadlines": "long_headline",
    "descriptions": "description",
    "callToActions": "cta",
}

FORMATO_POR_TIPO = {
    "DEMAND_GEN_VIDEO_RESPONSIVE_AD": "video",
    "VIDEO_RESPONSIVE_AD": "video",
    "DEMAND_GEN_MULTI_ASSET_AD": "imagem",
}

GAQL = """
SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.ad.type,
       ad_group_ad.ad.final_urls,
       ad_group_ad.ad.demand_gen_video_responsive_ad.headlines,
       ad_group_ad.ad.demand_gen_video_responsive_ad.long_headlines,
       ad_group_ad.ad.demand_gen_video_responsive_ad.descriptions,
       ad_group_ad.ad.demand_gen_video_responsive_ad.call_to_actions,
       ad_group_ad.ad.video_responsive_ad.headlines,
       ad_group_ad.ad.video_responsive_ad.long_headlines,
       ad_group_ad.ad.video_responsive_ad.descriptions,
       ad_group_ad.ad.video_responsive_ad.call_to_actions,
       ad_group_ad.ad.demand_gen_multi_asset_ad.headlines,
       ad_group_ad.ad.demand_gen_multi_asset_ad.descriptions,
       campaign.name
FROM   ad_group_ad
WHERE  campaign.name LIKE '%{launch}%'
"""


def _cabecalhos() -> dict:
    import etl_google_ads as ga  # noqa: PLC0415

    h = {
        "Authorization": f"Bearer {ga._get_access_token()}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type": "application/json",
    }
    login = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    if login:
        h["login-customer-id"] = login
    return h


def buscar_anuncios(launch: str) -> list[dict]:
    """Todos os ad_group_ad do lançamento, nas contas do .env."""
    import etl_google_ads as ga  # noqa: PLC0415

    headers = _cabecalhos()
    contas = [c.strip().replace("-", "")
              for c in os.environ["GOOGLE_ADS_CUSTOMER_ID"].split(",") if c.strip()]
    consulta = GAQL.format(launch=launch)
    linhas: list[dict] = []
    for conta in contas:
        url = (f"https://googleads.googleapis.com/{ga.API_VERSION}"
               f"/customers/{conta}/googleAds:search")
        token = None
        while True:
            payload = {"query": consulta}
            if token:
                payload["pageToken"] = token
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.status_code != 200:
                # Uma conta sem acesso nao pode derrubar as outras — a do Ivan
                # foi separada em 13/08/26 e nem todo token ve as tres.
                logger.warning("Conta %s: HTTP %s — %s", conta, r.status_code,
                               r.text[:160])
                break
            dados = r.json()
            linhas.extend(dados.get("results", []))
            token = dados.get("nextPageToken")
            if not token:
                break
    logger.info("%d anuncios do Google encontrados em %s", len(linhas), launch)
    return linhas


def extrair(linhas: list[dict], launch: str) -> list[dict]:
    """Conjunto distinto de textos por (ad_code, campo)."""
    # {ad_code: {campo: {texto, ...}}}, e o formato/ad_id do primeiro visto
    pool: dict[str, dict[str, set]] = {}
    formato: dict[str, str] = {}
    ad_id: dict[str, str] = {}

    for item in linhas:
        anuncio = (item.get("adGroupAd") or {}).get("ad") or {}
        nome = anuncio.get("name") or ""
        m = RX_AD.match(nome)
        if not m:
            continue
        codigo = m.group(1).upper()
        campos = pool.setdefault(codigo, {})
        formato.setdefault(codigo, FORMATO_POR_TIPO.get(anuncio.get("type"), "?"))
        ad_id.setdefault(codigo, str(anuncio.get("id") or ""))

        for url in anuncio.get("finalUrls") or []:
            campos.setdefault("link", set()).add(url.strip())

        for bloco in BLOCOS:
            dados = anuncio.get(bloco)
            if not dados:
                continue
            for chave, campo in CAMPOS.items():
                for asset in dados.get(chave) or []:
                    txt = " ".join(str(asset.get("text") or "").split())
                    if txt:
                        campos.setdefault(campo, set()).add(txt)
            break   # só o bloco do tipo do anúncio

    agora = datetime.now(timezone.utc)
    registros: list[dict] = []
    for codigo, campos in pool.items():
        for campo, textos in campos.items():
            # sorted() deixa a ordem estavel entre execucoes: sem isso, o set
            # embaralharia e o UPSERT reescreveria linhas a toa a cada rodada.
            for i, txt in enumerate(sorted(textos), start=1):
                registros.append({
                    "lancamento_codigo": launch, "ad_code": codigo,
                    "platform": "google", "ad_id": ad_id.get(codigo),
                    "formato": formato.get(codigo), "campo": campo,
                    "ordem": i, "texto": txt,
                    "n_palavras": len(txt.split()), "updated_at": agora,
                })
    return registros


def gravar(registros: list[dict]) -> None:
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
            conn.execute(sql, r)


def relatorio(launch: str, registros: list[dict]) -> None:
    """Quanto de verba só-Google este ETL acabou de cobrir."""
    codigos = {r["ad_code"] for r in registros}
    with get_engine().connect() as conn:
        gasto = dict(conn.execute(text(r"""
            SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')), sum(cost)
            FROM   google_ads_daily
            WHERE  lancamento_codigo = :c
              AND  upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) ~ '^AD[0-9]+$'
            GROUP  BY 1
        """), {"c": launch}).fetchall())
        sem_meta = {r[0] for r in conn.execute(text("""
            SELECT DISTINCT ad_code FROM ad_copy_textos
            WHERE lancamento_codigo = :c AND platform = 'meta'
        """), {"c": launch})}

    so_google = [a for a in codigos if a not in sem_meta]
    print(f"\n{'=' * 70}\nCOPY GOOGLE - {launch}\n{'=' * 70}")
    print(f"{len(registros)} textos em {len(codigos)} anuncios")
    print(f"  cobertos por gasto:      R$ {sum(float(gasto.get(a) or 0) for a in codigos):,.0f}")
    print(f"  destes, so no Google:    {len(so_google)} anuncios, "
          f"R$ {sum(float(gasto.get(a) or 0) for a in so_google):,.0f}")
    faltam = [a for a in gasto if a not in codigos and float(gasto[a] or 0) >= 100]
    if faltam:
        print(f"\n[!] Gastaram >= R$ 100 no Google e seguem sem copy ({len(faltam)}): "
              + ", ".join(sorted(faltam, key=lambda a: -float(gasto[a]))[:15]))


def main() -> int:
    ap = argparse.ArgumentParser(description="Puxa o copy escrito dos anuncios do Google Ads")
    ap.add_argument("--launch", required=True)
    ap.add_argument("--dry-run", action="store_true", help="so relata, nao grava")
    args = ap.parse_args()

    linhas = buscar_anuncios(args.launch)
    if not linhas:
        logger.error("Nenhum anuncio do Google encontrado em %s", args.launch)
        return 1
    registros = extrair(linhas, args.launch)
    if not registros:
        logger.error("Nenhum texto extraido — conferir se os nomes seguem ADxxx")
        return 2

    relatorio(args.launch, registros)
    if args.dry_run:
        logger.info("dry-run: nada gravado")
        return 0
    gravar(registros)
    logger.info("%s: %d textos do Google gravados", args.launch, len(registros))
    return 0


if __name__ == "__main__":
    sys.exit(main())
