"""Auditoria das landing pages que estão nos anúncios de um lançamento (Meta + Google), só leitura.

    python -m scripts.ads.auditar_lps BV-26              # só anúncios ativos
    python -m scripts.ads.auditar_lps BV-26 --todos      # inclui pausados
    python -m scripts.ads.auditar_lps BV-26 --sem-velocidade

Para cada URL distinta que um anúncio usa:
1. está na lista oficial do lançamento (padroes.LPS_OFICIAIS: url → tag esperada)?
2. abre a página no navegador (Playwright — o site bloqueia curl) e lê o formulário do AC (`_form_NNN`);
3. o formulário (GET /api/3/forms/{id}) aplica a tag do lançamento e não é de outro lançamento?
4. a página de obrigado do formulário bate com um gatilho de Lead do GTM publicado? (API do GTM)
5. o container GTM do domínio e o pixel Meta do expert disparam? (o site só carrega os scripts depois da
   primeira interação — a auditoria rola a página antes de olhar a rede);
6. velocidade no celular pela PageSpeed Insights (token GTM_REFRESH_TOKEN, escopo openid);
7. taxa real dos anúncios do Meta nessa LP nos últimos 3 dias: abriu/clicou e lead/página aberta
   (meta_ads_daily + ad_landing_pages, a mesma conta da seção "Carregamento da página" de /meta).

Nasceu do erro da -v3a/ na BV-26: form 422 da Black 2025, que aplicava a tag de 2025 e mandava para
/obg-black-vitalicia-25-v3a — fora do gatilho de Lead do GTM, então nenhum cadastro contou como Lead no
Meta nem no Google. Não altera nada; sai com 1 se houver alerta.
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
from scripts.ads.meta import Meta, expert_do_nome
from src.landing_pages import links_do_criativo, normalizar_url

CONTAS_META = [P.META_CONTAS["ca2_anunciante"], P.META_CONTAS["felipe_nova"]]
UA_CELULAR = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/129.0 Mobile Safari/537.36")


# ---------------------------------------------------------------------------- funções puras (testadas)
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


def problemas_lp(lp: dict, lancamento: str, experts: set[str], gatilhos_lead: list[str] | None = None) -> list[str]:
    """Alertas de uma LP já lida. `lp`: url, status, final, forms [{id,nome,tags,obrigado}], gtm, pixels,
    nota, lcp e, se houver dado, `real` (cliques, lpv, leads, lead_por_lpv). `gatilhos_lead`: trechos de
    URL dos gatilhos de Lead do GTM publicado (None = não conferir)."""
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
        obg = f.get("obrigado")
        if gatilhos_lead and obg and not any(g in obg for g in gatilhos_lead):
            out.append(f"form {f['id']} manda para {obg}, que não dispara Lead no GTM "
                       f"(gatilhos: {', '.join(gatilhos_lead)})")
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
    real = lp.get("real")
    if real and real["lpv"] >= P.LP_MIN_PAGINAS_PARA_TAXA and real["lead_por_lpv"] < P.LP_LEAD_POR_PAGINA_MIN:
        out.append(f"só {real['lead_por_lpv']:.1f}% de lead por página aberta no Meta ({real['leads']} leads em "
                   f"{real['lpv']} páginas) — o Lead está sendo contado?")
    return out


def gatilhos_de_lead(versao_gtm: dict) -> list[str]:
    """Trechos de URL ("contains") dos gatilhos que disparam as tags de Lead/conversão de uma versão
    publicada do GTM. Ex.: ['/obg-black-vitalicia-26', '/obg-base-forte-v']."""
    gatilhos = {t["triggerId"]: t for t in versao_gtm.get("trigger", [])}
    trechos = set()
    for tag in versao_gtm.get("tag", []):
        if tag.get("paused") or not re.search(r"lead|convers", tag.get("name", ""), re.I):
            continue
        for tid in tag.get("firingTriggerId", []):
            for f in (gatilhos.get(tid) or {}).get("filter", []):
                valores = [p.get("value", "") for p in f.get("parameter", [])]
                if f.get("type") == "contains" and len(valores) == 2 and "{{Page URL}}" in valores[0] + valores[1]:
                    trechos.add(valores[1] if "{{" in valores[0] else valores[0])
    return sorted(trechos)


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
        out[i] = {"id": i, "nome": f.get("name", ""), "tags": [a["tag"] for a in acoes if a.get("type") == "add-a-tag"],
                  "obrigado": (f.get("submitdata") or {}).get("url") if f.get("submit") == "open-url" else None}
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


def _token_google_leitura() -> str:
    """Token de leitura do GTM + PageSpeed (escopos tagmanager.readonly e openid)."""
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "grant_type": "refresh_token", "refresh_token": os.environ["GTM_REFRESH_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"]})
    r.raise_for_status()
    return r.json()["access_token"]


def gtm_publicado(public_id: str, token: str) -> dict:
    """Versão publicada (live) de um container, pelo ID público (GTM-XXXX)."""
    h, base = {"Authorization": f"Bearer {token}"}, "https://tagmanager.googleapis.com/tagmanager/v2/"
    for conta in requests.get(base + "accounts", headers=h, timeout=30).json().get("account", []):
        for c in requests.get(base + conta["path"] + "/containers", headers=h, timeout=30).json().get("container", []):
            if c["publicId"] == public_id:
                r = requests.get(base + c["path"] + "/versions:live", headers=h, timeout=30)
                r.raise_for_status()
                return r.json()
    raise RuntimeError(f"container {public_id} não visível com o GTM_REFRESH_TOKEN")


def taxa_real_meta(lancamento: str, dias: int = 3) -> dict[str, dict]:
    """URL → cliques/lpv/leads dos anúncios do Meta nos últimos `dias` (mesma leitura de /meta). Janela
    curta de propósito: o link é editado no próprio anúncio, e o histórico inteiro deixaria o alerta da
    LP antiga aceso na LP nova por semanas."""
    from datetime import date, timedelta
    from frontend.db_readers.carregamento_lp import read_carregamento_lp
    d = read_carregamento_lp(lancamento, date.today() - timedelta(days=dias), date.today())
    return {r["url"]: r | {"desde": d["desde"]} for r in (d or {}).get("por_lp", [])}


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
    token = _token_google_leitura()
    gatilhos: dict[str, list[str]] = {}
    for gtm_id in sorted(set(P.GTM_POR_DOMINIO.values())):
        try:
            gatilhos[gtm_id] = gatilhos_de_lead(gtm_publicado(gtm_id, token))
        except Exception as e:  # noqa: BLE001
            print(f"!! GTM {gtm_id} não lido ({e}) — página de obrigado não conferida")
    try:
        real = taxa_real_meta(a.lancamento)
    except Exception as e:  # noqa: BLE001
        real = {}
        print(f"!! taxa real do Meta não lida ({e})")
    if not a.sem_velocidade:
        with ThreadPoolExecutor(4) as ex:
            for url, v in zip(por_url, ex.map(lambda u: velocidade(u, token), por_url)):
                paginas[url].update(v)

    total = 0
    for url in sorted(por_url, key=lambda u: -len(por_url[u])):
        lp = paginas[url] | {"forms": [forms[i] for i in paginas[url]["form_ids"]], "real": real.get(url)}
        experts = {x["expert"] for x in por_url[url] if x["expert"]}
        gtm_lp = P.GTM_POR_DOMINIO.get(urlsplit(url).netloc)
        probs = problemas_lp(lp, a.lancamento, experts, gatilhos.get(gtm_lp))
        total += bool(probs)
        print(f"[{'OK' if not probs else '!!'}] {url}")
        for f in lp["forms"]:
            print(f"      form {f['id']} · {f['nome']} · tags {f['tags']} · obrigado {f.get('obrigado') or '-'}")
        if lp.get("nota") is not None:
            print(f"      celular: nota {lp['nota']} · LCP {lp['lcp']:.1f} s · {lp['peso_kb']:.0f} KB")
        elif lp.get("erro_psi"):
            print(f"      PageSpeed falhou: {lp['erro_psi']}")
        if lp["real"]:
            r = lp["real"]
            print(f"      Meta desde {r['desde'][8:10]}/{r['desde'][5:7]} (3 dias): {r['cliques']} cliques → {r['lpv']} páginas abertas "
                  f"({r['taxa']:.0f}%) → {r['leads']} leads ({r['lead_por_lpv']:.1f}% por página)")
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
