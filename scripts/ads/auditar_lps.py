"""Auditoria das landing pages que estão nos anúncios de um lançamento (Meta + Google), só leitura.

    python -m scripts.ads.auditar_lps BV-26              # só anúncios ativos
    python -m scripts.ads.auditar_lps BV-26 --todos      # inclui pausados
    python -m scripts.ads.auditar_lps BV-26 --sem-velocidade

Para cada URL distinta que um anúncio usa:
1. está na lista oficial do lançamento (padroes.LPS_OFICIAIS: url → tag esperada)?
2. abre a página no navegador (Playwright — o site bloqueia curl) e lê o formulário do AC (`_form_NNN`);
3. o formulário (GET /api/3/forms/{id}) aplica a tag do lançamento e não é de outro lançamento?
4. o container GTM do domínio e o pixel Meta do expert disparam? (o site só carrega os scripts depois da
   primeira interação — a auditoria rola a página antes de olhar a rede);
5. velocidade no celular pela PageSpeed Insights (token GTM_REFRESH_TOKEN, escopo openid).

Nasceu do erro da -v3a/ na BV-26 (form 422 da Black 2025). Não altera nada; sai com 1 se houver alerta.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests

from scripts.ads import padroes as P
from scripts.ads.google import Google
from scripts.ads.meta import Meta, expert_do_nome, links_do_criativo

CONTAS_META = [P.META_CONTAS["ca2_anunciante"], P.META_CONTAS["felipe_nova"]]
UA_CELULAR = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/129.0 Mobile Safari/537.36")


# ---------------------------------------------------------------------------- funções puras (testadas)
def normalizar_url(url: str) -> str:
    """Sem query/fragmento, host minúsculo, com barra no fim — a UTM e o {lpurl} não mudam a página."""
    p = urlsplit(url.strip())
    caminho = p.path if p.path.endswith("/") else p.path + "/"
    return f"{p.scheme.lower() or 'https'}://{p.netloc.lower()}{caminho}"


def codigos_lancamento(texto: str) -> set[str]:
    """'FORMULÁRIO BLACK 2025 v3 A - BV-25' → {'BV-25'}; '[PES-SET-26]' → {'PES-SET-26'}."""
    return set(re.findall(r"\b([A-Z]{2,3}(?:-[A-Z]{3})?-\d{2})\b", texto or ""))


def pixels_disparados(reqs: list[str]) -> set[str]:
    """IDs de pixel Meta com evento enviado: GET /tr/?id=… ou POST /tr/ com o id no corpo
    (urlencoded `id=…` ou multipart `name="id"` — o fbevents.js usa os dois)."""
    ids = set()
    for r in reqs:
        if "facebook.com/tr" in r:
            ids |= set(re.findall(r"(?:^|[?&\s])id=(\d+)", r))
            ids |= set(re.findall(r'name="id"\s+(\d+)', r))
    return ids


def problemas_lp(lp: dict, lancamento: str, experts: set[str]) -> list[str]:
    """Alertas de uma LP já lida. `lp`: url, status, final, forms [{id,nome,tags}], gtm, pixels, nota, lcp."""
    cfg, out = P.LPS_OFICIAIS.get(lancamento), []
    tag = (cfg or {}).get(lp["url"])
    if cfg and not tag:
        out.append("fora da lista oficial do lançamento")
    if lp.get("erro"):
        return out + [f"não abriu: {lp['erro']}"]
    if lp["status"] >= 400:
        out.append(f"HTTP {lp['status']}")
    if normalizar_url(lp["final"]) != lp["url"]:
        out.append(f"redireciona para {lp['final']}")
    if not lp["forms"]:
        out.append("nenhum formulário do AC na página")
    for f in lp["forms"]:
        outros = codigos_lancamento(f["nome"]) - {lancamento}
        if outros and lancamento not in codigos_lancamento(f["nome"]):
            out.append(f"form {f['id']} é de outro lançamento: {f['nome']}")
        if tag and not any(tag in t for t in f["tags"]):
            out.append(f"form {f['id']} não aplica a tag {tag} (aplica {f['tags'] or 'nenhuma'})")
        elif cfg and not tag and not any(e in t for e in set(cfg.values()) for t in f["tags"]):
            out.append(f"form {f['id']} não aplica nenhuma tag do lançamento (aplica {f['tags'] or 'nenhuma'})")
    esperado = P.GTM_POR_DOMINIO.get(urlsplit(lp["url"]).netloc)
    if esperado and esperado not in lp["gtm"]:
        out.append(f"GTM {esperado} não carregou (carregou {sorted(lp['gtm']) or 'nenhum'})")
    for e in sorted(experts):
        if P.META_EXPERTS[e]["pixel_id"] not in lp["pixels"]:
            out.append(f"pixel Meta do {e} ({P.META_EXPERTS[e]['pixel_id']}) não disparou")
    if lp.get("nota") is not None and lp["nota"] < P.LP_NOTA_MINIMA:
        out.append(f"PageSpeed celular {lp['nota']} (< {P.LP_NOTA_MINIMA})")
    if lp.get("lcp") is not None and lp["lcp"] > P.LP_LCP_MAXIMO_S:
        out.append(f"LCP {lp['lcp']:.1f} s (> {P.LP_LCP_MAXIMO_S:.0f} s)")
    return out


# ---------------------------------------------------------------------------- coleta
def urls_meta(lancamento: str, todos: bool) -> list[dict]:
    m, out = Meta(), []
    for conta in CONTAS_META:
        for c in m.campanhas(conta, lancamento):
            if not todos and c["effective_status"] != "ACTIVE":
                continue
            for ad in m.anuncios(c["id"], campos="id,name,effective_status,creative{object_story_spec,asset_feed_spec}"):
                if not todos and ad["effective_status"] != "ACTIVE":
                    continue
                links = links_do_criativo(ad.get("creative") or {})
                for link in links or [""]:
                    out.append({"plataforma": "Meta", "campanha_id": c["id"], "campanha": c["name"],
                                "anuncio": ad["name"], "url": normalizar_url(link) if link else "",
                                "expert": expert_do_nome(c["name"])})
    return out


def urls_google(lancamento: str, todos: bool) -> list[dict]:
    g, out = Google(), []
    filtro = "" if todos else ("AND campaign.status = 'ENABLED' AND ad_group.status = 'ENABLED' "
                               "AND ad_group_ad.status = 'ENABLED'")
    for conta in P.GOOGLE_CONTAS.values():
        for x in g.buscar(conta, f"""SELECT campaign.id, campaign.name, ad_group_ad.ad.id, ad_group_ad.ad.name,
                ad_group_ad.ad.final_urls FROM ad_group_ad
                WHERE campaign.name LIKE '%{lancamento}%' AND ad_group_ad.status != 'REMOVED' {filtro}"""):
            ad = x["adGroupAd"]["ad"]
            for link in ad.get("finalUrls") or [""]:
                out.append({"plataforma": "Google", "campanha_id": x["campaign"]["id"], "campanha": x["campaign"]["name"],
                            "anuncio": ad.get("name") or ad["id"], "url": normalizar_url(link) if link else "",
                            "expert": expert_do_nome(x["campaign"]["name"])})
    return out


def ler_forms_ac(ids: set[str]) -> dict[str, dict]:
    base, chave, out = os.environ["AC_API_URL"].rstrip("/"), os.environ["AC_API_KEY"], {}
    for i in ids:
        r = requests.get(f"{base}/api/3/forms/{i}", headers={"Api-Token": chave}, timeout=30)
        if r.status_code != 200:
            out[i] = {"id": i, "nome": f"(AC devolveu {r.status_code})", "tags": []}
            continue
        f = r.json().get("form", {})
        acoes = (f.get("actiondata") or {}).get("actions", [])
        out[i] = {"id": i, "nome": f.get("name", ""), "tags": [a["tag"] for a in acoes if a.get("type") == "add-a-tag"]}
    return out


def abrir_paginas(urls: list[str]) -> dict[str, dict]:
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        nav = p.chromium.launch()
        for url in urls:
            pg = nav.new_page(user_agent=UA_CELULAR, viewport={"width": 412, "height": 915})
            reqs: list[str] = []
            # o pixel às vezes manda o evento por POST em /tr/, com o id no corpo — guardar o corpo também
            pg.on("request", lambda r: reqs.append(r.url + (" " + (r.post_data or "")[:300] if "facebook.com/tr" in r.url else "")))
            try:
                resp = pg.goto(url, wait_until="networkidle", timeout=60000)
                pg.mouse.move(100, 200)          # o site adia GTM/pixel até a primeira interação
                pg.mouse.wheel(0, 600)
                pg.keyboard.press("Tab")
                pg.wait_for_timeout(6000)
                html, rede = pg.content(), " ".join(reqs)
                out[url] = {"url": url, "status": resp.status if resp else 0, "final": pg.url,
                            "form_ids": sorted(set(re.findall(r"_form_(\d+)", html))),
                            "gtm": set(re.findall(r"gtm\.js\?id=(GTM-[A-Z0-9]+)", rede)),
                            "pixels": pixels_disparados(reqs)}
            except Exception as e:  # noqa: BLE001 — uma LP fora do ar não derruba a auditoria
                out[url] = {"url": url, "erro": str(e).splitlines()[0][:120], "form_ids": [], "gtm": set(), "pixels": set()}
            pg.close()
        nav.close()
    return out


def _token_pagespeed() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "grant_type": "refresh_token", "refresh_token": os.environ["GTM_REFRESH_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"]})
    r.raise_for_status()
    return r.json()["access_token"]


def velocidade(url: str, token: str) -> dict:
    r = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", timeout=180,
                     headers={"Authorization": f"Bearer {token}"},
                     params={"url": url, "strategy": "mobile", "category": "performance"})
    if r.status_code != 200:
        return {"nota": None, "lcp": None, "erro_psi": r.json().get("error", {}).get("message", r.status_code)}
    lh = r.json()["lighthouseResult"]
    a = lh["audits"]
    return {"nota": round(lh["categories"]["performance"]["score"] * 100),
            "lcp": a["largest-contentful-paint"]["numericValue"] / 1000,
            "peso_kb": a["total-byte-weight"]["numericValue"] / 1024}


# ---------------------------------------------------------------------------- relatório
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lancamento")
    ap.add_argument("--todos", action="store_true", help="inclui anúncios/campanhas pausados")
    ap.add_argument("--sem-velocidade", action="store_true", help="pula a PageSpeed (mais rápido)")
    a = ap.parse_args()

    anuncios = urls_meta(a.lancamento, a.todos) + urls_google(a.lancamento, a.todos)
    sem_link = [x for x in anuncios if not x["url"]]
    por_url: dict[str, list[dict]] = defaultdict(list)
    for x in anuncios:
        if x["url"]:
            por_url[x["url"]].append(x)
    print(f"{len(anuncios)} anúncio(s), {len(por_url)} URL(s) distinta(s)\n")

    paginas = abrir_paginas(sorted(por_url))
    forms = ler_forms_ac({i for p in paginas.values() for i in p["form_ids"]})
    if not a.sem_velocidade:
        token = _token_pagespeed()
        with ThreadPoolExecutor(4) as ex:
            for url, v in zip(por_url, ex.map(lambda u: velocidade(u, token), por_url)):
                paginas[url].update(v)

    total = 0
    for url in sorted(por_url, key=lambda u: -len(por_url[u])):
        lp = paginas[url] | {"forms": [forms[i] for i in paginas[url]["form_ids"]]}
        experts = {x["expert"] for x in por_url[url] if x["expert"]}
        probs = problemas_lp(lp, a.lancamento, experts)
        total += bool(probs)
        print(f"[{'OK' if not probs else '!!'}] {url}")
        for f in lp["forms"]:
            print(f"      form {f['id']} · {f['nome']} · tags {f['tags']}")
        if lp.get("nota") is not None:
            print(f"      celular: nota {lp['nota']} · LCP {lp['lcp']:.1f} s · {lp['peso_kb']:.0f} KB")
        elif lp.get("erro_psi"):
            print(f"      PageSpeed falhou: {lp['erro_psi']}")
        for p in probs:
            print(f"      !! {p}")
        campanhas = defaultdict(int)
        for x in por_url[url]:
            campanhas[(x["plataforma"], x["campanha_id"], x["campanha"])] += 1
        print(f"      {len(por_url[url])} anúncio(s) em {len(campanhas)} campanha(s):")
        for (plat, cid, nome), n in sorted(campanhas.items()):
            print(f"        {plat} {cid} {nome} ({n})")
        print()

    if sem_link:
        print(f"{len(sem_link)} anúncio(s) sem link legível pela API (post existente / vídeo sem CTA):")
        for x in sem_link:
            print(f"  {x['plataforma']} {x['campanha_id']} {x['campanha']} · {x['anuncio']}")
    print(f"\n{total} LP(s) com alerta.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
