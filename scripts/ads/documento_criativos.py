"""Documento de criativos de um lançamento: campanha → anúncios, com o link de cada vídeo do YouTube (Google) e o formato
e a LP de cada anúncio (Facebook/Meta). Base para criar à mão, no Google Ads, o público "Viu Captação" (a API não cria
público de quem viu vídeo do YouTube) — o documento já traz a lista de vídeos de cada público, um por tipo de campanha.

    python -m scripts.ads.documento_criativos PI-NOV-26
    python -m scripts.ads.documento_criativos PI-NOV-26 --saida -   # imprime em vez de gravar

Grava `docs/performance/lancamentos/<LANC>/CRIATIVOS_<LANC>.md`, lido direto das plataformas (só leitura; inclui
pausados, exclui removidos). Rodar de novo a cada anúncio novo: o arquivo é sobrescrito, não se edita à mão.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

from scripts.ads import padroes as P
from scripts.ads.publicos import lancamento_do_nome

RAIZ = Path(__file__).resolve().parents[2]
PAPEIS = ("horizontal", "feed", "story")


# ---------------------------------------------------------------------------- funções puras (testadas)
def codigo_ad(nome: str) -> str:
    m = re.match(r"(AD\d+)", nome or "")
    return m.group(1) if m else (nome or "?")


def papel_do_video(nome_asset: str, posicao: int) -> str:
    """'AD043 - … (feed)' → feed. Sem marca no nome, usa a ordem em que o anúncio lista os vídeos."""
    m = re.search(r"\((horizontal|feed|story)\)\s*$", nome_asset or "", re.I)
    if m:
        return m.group(1).lower()
    return PAPEIS[posicao] if posicao < len(PAPEIS) else f"vídeo {posicao + 1}"


def tipo_da_campanha(nome: str) -> str:
    """Bloco do público Viu Captação: 'principal', 'potencial', 'imagem'… = o colchete depois do clima."""
    partes = re.findall(r"\[([^\]]+)\]", nome or "")
    for i, p in enumerate(partes):
        if p.lower() in ("quente", "frio", "específico", "especifico") and i + 1 < len(partes):
            return partes[i + 1].lower()
    return "outros"


def nome_publico_viu(tipo: str, lancamento: str) -> str:
    """Padrão dos lançamentos anteriores: 'Viu Captação - Principal - [PI-AGO-26] - 540D'."""
    return f"Viu Captação - {tipo.capitalize()} - [{lancamento}] - 540D"


def documento_md(lancamento: str, google: list[dict], meta: list[dict], gerado_em: dt.datetime) -> str:
    """google: [{nome, id, status, ads: {AD: {nome, videos: {papel: youtube_id}, imagem: bool}}}];
    meta: [{nome, id, status, ads: {nome: {formato, lp, n}}}]."""
    out = [
        "---",
        f'titulo: "Criativos por campanha — {lancamento}"',
        "area: lancamento",
        "status: vigente",
        f"atualizado: {gerado_em:%Y-%m-%d}",
        "responde:",
        f'  - "links dos videos do youtube de cada anuncio do {lancamento}"',
        f'  - "quais anuncios estao em cada campanha do {lancamento}"',
        f'  - "como criar o publico viu captacao no google ads do {lancamento}"',
        "relacionados:",
        f'  - "[[MUDANCAS_{lancamento}]]"',
        f'  - "[[PUBLICOS_{lancamento}]]"',
        '  - "[[MANUAL_OPERACAO_ADS]]"',
        '  - "[[INDICE_PERFORMANCE]]"',
        "---",
        "",
        f"# Criativos por campanha — {lancamento}",
        "",
        f"> Gerado em {gerado_em:%d/%m/%y %Hh%M} por `python -m scripts.ads.documento_criativos {lancamento}`, direto das",
        "> plataformas (ativos e pausados; removidos ficam de fora). **Não editar à mão:** rodar de novo a cada anúncio novo.",
        "",
    ]
    # --- públicos Viu Captação (Google): vídeos por tipo de campanha, sem repetir
    por_tipo: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for c in google:
        if "capta" not in c["nome"].lower():
            continue
        for ad, d in c["ads"].items():
            if d["videos"]:
                por_tipo[tipo_da_campanha(c["nome"])].setdefault(ad, {}).update(d["videos"])
    out += ["## Google (YouTube) — públicos \"Viu Captação\" (criar na interface)", "",
            "A API não cria público de quem viu vídeo do YouTube. No Google Ads: **Ferramentas → Gerenciador de públicos → "
            "Seus segmentos de dados → + → Usuários do YouTube** → tipo **\"Visualizou determinados vídeos\"** → colar os IDs "
            "abaixo (um por linha); duração de associação **540 dias**. Um público por tipo de campanha (padrão do PI-AGO-26 e do "
            "PES-NOV-26). Anúncio de imagem não entra.", ""]
    if not por_tipo:
        out += ["Nenhum anúncio de vídeo de captação.", ""]
    for tipo, ads in sorted(por_tipo.items()):
        ids = [v for ad in sorted(ads) for p in PAPEIS for v in [ads[ad].get(p)] if v]
        out += [f"### {nome_publico_viu(tipo, lancamento)}", "",
                f"{len(ads)} anúncio(s), {len(ids)} vídeo(s): {', '.join(sorted(ads))}", "",
                "```", *ids, "```", ""]
    # --- Google por campanha
    out += ["## Google (YouTube) — anúncios por campanha", ""]
    for c in google:
        out += [f"### {c['nome']}", "", f"ID `{c['id']}` · {c['status']} · {len(c['ads'])} anúncio(s)", ""]
        vid = {a: d for a, d in c["ads"].items() if d["videos"]}
        img = sorted(a for a, d in c["ads"].items() if not d["videos"])
        if vid:
            out += ["| Anúncio | Horizontal | Feed | Story |", "|---|---|---|---|"]
            for ad in sorted(vid):
                v = vid[ad]["videos"]
                cel = lambda p: f"[{v[p]}](https://youtu.be/{v[p]})" if v.get(p) else "—"
                out.append(f"| {vid[ad]['nome'].replace('|', chr(92) + '|')} | {cel('horizontal')} | {cel('feed')} | {cel('story')} |")
            out.append("")
        if img:
            out += [f"Imagem: {', '.join(c['ads'][a]['nome'] for a in img)}", ""]
    # --- Meta por campanha
    out += ["## Facebook (Meta) — anúncios por campanha", "",
            "Público de vídeo do Meta (\"Viu Captação 25%/50%\") se cria por API com os vídeos de página — ver MANUAL §4.1.6.", ""]
    for c in meta:
        out += [f"### {c['nome']}", "", f"ID `{c['id']}` · {c['status']} · {len(c['ads'])} anúncio(s) distintos", "",
                "| Anúncio | Formato | LP | Conjuntos |", "|---|---|---|---|"]
        for nome, d in sorted(c["ads"].items()):
            out.append(f"| {nome.replace('|', chr(92) + '|')} | {d['formato']} | {d['lp']} | {d['n']} |")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------- leitura das plataformas
def secao_google(g, lancamento: str) -> list[dict]:
    out = []
    for conta in P.GOOGLE_CONTAS.values():
        camps = [c for c in g.campanhas(conta, lancamento) if lancamento_do_nome(c["name"]) == lancamento.upper()]
        if not camps:
            continue
        ids = ",".join(str(c["id"]) for c in camps)
        linhas = g.buscar(conta, f"""SELECT campaign.id, ad_group_ad.ad.name, ad_group_ad.ad.type,
            ad_group_ad.ad.demand_gen_video_responsive_ad.videos, ad_group_ad.ad.video_responsive_ad.videos,
            ad_group_ad.ad.video_ad.video.asset FROM ad_group_ad
            WHERE campaign.id IN ({ids}) AND ad_group_ad.status != 'REMOVED'""")
        assets = {r["asset"]["resourceName"]: (r["asset"].get("name", ""), r["asset"].get("youtubeVideoAsset", {}).get("youtubeVideoId"))
                  for r in g.buscar(conta, "SELECT asset.resource_name, asset.name, asset.youtube_video_asset.youtube_video_id "
                                           "FROM asset WHERE asset.type = 'YOUTUBE_VIDEO'")}
        por_camp: dict[str, dict] = defaultdict(dict)
        for r in linhas:
            ad = r["adGroupAd"]["ad"]
            lista = ((ad.get("demandGenVideoResponsiveAd") or {}).get("videos") or (ad.get("videoResponsiveAd") or {}).get("videos")
                     or ([{"asset": ad["videoAd"]["video"]["asset"]}] if (ad.get("videoAd") or {}).get("video", {}).get("asset") else []))
            videos = {}
            for i, v in enumerate(lista):
                nome_a, yt = assets.get(v["asset"], ("", None))
                if yt:
                    videos[papel_do_video(nome_a, i)] = yt
            cod = codigo_ad(ad.get("name", ""))
            atual = por_camp[r["campaign"]["id"]].setdefault(cod, {"nome": ad.get("name", cod), "videos": {}})
            atual["videos"].update(videos)
        for c in sorted(camps, key=lambda c: c["name"]):
            out.append({"nome": c["name"], "id": c["id"], "status": f"{c['status']} · {c.get('advertisingChannelType', '')}",
                        "ads": por_camp.get(str(c["id"]), {})})
    return out


def secao_meta(m, lancamento: str) -> list[dict]:
    from scripts.ads.conferir import CONTAS_META
    out = []
    for conta in CONTAS_META:
        for c in sorted(m.campanhas(conta, lancamento), key=lambda c: c["name"]):
            if lancamento_do_nome(c["name"]) != lancamento.upper():
                continue
            ads, criativos = {}, {}
            for a in m.listar(f"{c['id']}/ads", fields="name,creative{id}", limit=500):
                cid = a.get("creative", {}).get("id")
                if cid not in criativos:
                    cr = m.get(cid, fields="object_story_spec,asset_feed_spec") if cid else {}
                    o, f = cr.get("object_story_spec") or {}, cr.get("asset_feed_spec") or {}
                    ld = o.get("link_data") or {}
                    formato = ("carrossel" if ld.get("child_attachments") else "vídeo feed+story" if f.get("videos")
                               else "imagem feed+story" if f.get("images") else "vídeo" if o.get("video_data") else "imagem" if ld else "post")
                    links = [l.get("website_url") for l in f.get("link_urls", [])] + [ld.get("link"),
                             (o.get("video_data") or {}).get("call_to_action", {}).get("value", {}).get("link")]
                    lp = next((l for l in links if l), "—")
                    criativos[cid] = (formato, re.sub(r"^https?://", "", lp))
                d = ads.setdefault(a["name"], {"formato": criativos[cid][0], "lp": criativos[cid][1], "n": 0})
                d["n"] += 1
            out.append({"nome": c["name"], "id": c["id"], "status": c["effective_status"], "ads": ads})
    return out


# ---------------------------------------------------------------------------- linha de comando
def main() -> int:
    from scripts.ads.google import Google
    from scripts.ads.meta import Meta

    ap = argparse.ArgumentParser()
    ap.add_argument("lancamento")
    ap.add_argument("--saida", help="caminho do .md ('-' imprime); padrão docs/performance/lancamentos/<LANC>/")
    a = ap.parse_args()
    lanc = a.lancamento.upper()
    md = documento_md(lanc, secao_google(Google(), lanc), secao_meta(Meta(), lanc), dt.datetime.now())
    if a.saida == "-":
        print(md)
        return 0
    destino = Path(a.saida) if a.saida else RAIZ / "docs" / "performance" / "lancamentos" / lanc / f"CRIATIVOS_{lanc}.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    print(f"{destino} gravado")
    indice = RAIZ / "docs" / "performance" / "INDICE_PERFORMANCE.md"
    if indice.exists() and f"[[CRIATIVOS_{lanc}]]" not in indice.read_text(encoding="utf-8"):
        print(f"Falta linkar [[CRIATIVOS_{lanc}]] na linha do lançamento em INDICE_PERFORMANCE.md (senão o check_docs reprova).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
