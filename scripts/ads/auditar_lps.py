"""Auditoria das landing pages de um lançamento (Meta + Google + lista oficial), só leitura nas plataformas.

    python -m scripts.ads.auditar_lps BV-26              # anúncios ativos + LPs oficiais; grava no banco
    python -m scripts.ads.auditar_lps BV-26 --todos      # inclui anúncios pausados
    python -m scripts.ads.auditar_lps BV-26 --sem-velocidade --nao-gravar
    python -m scripts.ads.auditar_lps ativos             # todo lançamento com gasto nos últimos 3 dias

Para cada LP (URL usada em anúncio ou cadastrada na lista oficial `lp_oficiais`, banco operacional):
1. está na lista oficial do lançamento? (url → tag esperada)
2. abre no navegador (Playwright — o site bloqueia curl) e lê o formulário do AC (`_form_NNN`), além das
   boas práticas de leitura: campos do formulário, formulário na 1ª dobra do celular, título/H1, viewport;
3. o formulário (GET /api/3/forms/{id}) aplica a tag do lançamento e não é de outro lançamento?
4. a página de obrigado do formulário abre e bate com um gatilho de Lead do GTM publicado? (API do GTM)
5. o container GTM do domínio e o pixel Meta do expert disparam? O rastreio carrega antes da 1ª
   interação? (as LPs da Black 2026 adiam até a pessoa rolar/tocar — a auditoria rola antes de olhar);
6. velocidade no celular pela PageSpeed Insights: nota, LCP, FCP, CLS, TBT, Speed Index, TTFB, peso,
   requisições, as maiores oportunidades e o CrUX (usuários reais do Chrome, por URL ou origem);
7. print da página (lp_screenshots, o mesmo do debriefing) para quem ainda não tem ou passou de 7 dias;
8. taxa real dos anúncios do Meta nessa LP nos últimos 3 dias: abriu/clicou e lead/página aberta.

Grava o resultado em `lp_auditoria` (base da página /landing-pages) e o mapa anúncio → LP do Google em
`ad_landing_pages` (o do Meta vem do ETL). Nasceu do erro da -v3a/ na BV-26: form 422 da Black 2025, tag
de 2025 e obrigado em /obg-black-vitalicia-25-v3a, fora do gatilho de Lead — nenhum cadastro contou como
Lead no Meta nem no Google. Sai com 1 se houver alerta.
"""
from __future__ import annotations

import argparse
import json
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
VIEWPORT_CELULAR = {"width": 412, "height": 915}

# Lido na página antes de qualquer interação (a posição do form muda depois de rolar).
_JS_PRATICAS = """() => {
  const f = document.querySelector('form[class*="_form_"]') || document.querySelector('form');
  const visivel = e => e.type !== 'hidden' && e.type !== 'submit' && e.type !== 'button' && e.offsetParent !== null;
  const campos = f ? [...f.querySelectorAll('input,select,textarea')].filter(visivel).length : 0;
  const r = f ? f.getBoundingClientRect() : null;
  const h1 = document.querySelector('h1');
  return {campos_form: campos, form_topo_px: r ? Math.round(r.top + window.scrollY) : null,
          altura_tela: window.innerHeight, titulo: document.title || null,
          h1: h1 ? h1.innerText.trim().slice(0, 140) : null,
          viewport_meta: !!document.querySelector('meta[name=viewport]')};
}"""


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


def problemas_lp(lp: dict, lancamento: str, experts: set[str], gatilhos_lead: list[str] | None = None,
                 oficiais: dict[str, str | None] | None = None) -> list[str]:
    """Alertas de uma LP já lida. `lp`: url, status, final, forms [{id,nome,tags,obrigado,obrigado_status}],
    gtm, pixels, nota, lcp, cls, tbt_ms e, se houver dado, `real` (cliques, lpv, leads, lead_por_lpv).
    `gatilhos_lead`: trechos de URL dos gatilhos de Lead do GTM publicado (None = não conferir).
    `oficiais`: url → tag esperada da lista oficial do lançamento (None = lançamento sem lista)."""
    out = []
    na_lista = oficiais is not None and lp["url"] in oficiais
    tag = oficiais.get(lp["url"]) if na_lista else None
    if oficiais is not None and not na_lista:
        out.append("fora da lista oficial do lançamento")
    if lp.get("erro"):
        return out + [f"não abriu: {lp['erro']}"]
    if lp["status"] >= 400:
        out.append(f"HTTP {lp['status']}")
    if normalizar_url(lp["final"]) != lp["url"]:
        out.append(f"redireciona para {lp['final']}")
    if not lp["forms"]:
        out.append("nenhum formulário do AC na página")
    tags_do_lancamento = {t for t in (oficiais or {}).values() if t}
    for f in lp["forms"]:
        outros = codigos_lancamento(f["nome"]) - {lancamento}
        if outros and lancamento not in codigos_lancamento(f["nome"]):
            out.append(f"form {f['id']} é de outro lançamento: {f['nome']}")
        if tag and not any(tag in t for t in f["tags"]):
            out.append(f"form {f['id']} não aplica a tag {tag} (aplica {f['tags'] or 'nenhuma'})")
        elif not na_lista and tags_do_lancamento and not any(e in t for e in tags_do_lancamento for t in f["tags"]):
            out.append(f"form {f['id']} não aplica nenhuma tag do lançamento (aplica {f['tags'] or 'nenhuma'})")
        obg = f.get("obrigado")
        if gatilhos_lead and obg and not any(g in obg for g in gatilhos_lead):
            out.append(f"form {f['id']} manda para {obg}, que não dispara Lead no GTM "
                       f"(gatilhos: {', '.join(gatilhos_lead)})")
        if obg and f.get("obrigado_status") and f["obrigado_status"] >= 400:
            out.append(f"página de obrigado do form {f['id']} responde HTTP {f['obrigado_status']}")
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
    if lp.get("cls") is not None and lp["cls"] > P.LP_CLS_MAXIMO:
        out.append(f"CLS {lp['cls']:.2f} (> {P.LP_CLS_MAXIMO}) — layout pulando")
    if lp.get("tbt_ms") is not None and lp["tbt_ms"] > P.LP_TBT_MAXIMO_MS:
        out.append(f"TBT {lp['tbt_ms']:.0f} ms (> {P.LP_TBT_MAXIMO_MS}) — página travada por script")
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


def resumo_pagespeed(j: dict) -> dict:
    """Recorte da resposta da PageSpeed: laboratório (Lighthouse, celular simulado em 4G lento), as 3
    maiores oportunidades e o CrUX (usuários reais do Chrome nos últimos 28 dias — da URL quando ela
    tem tráfego suficiente, senão da origem)."""
    lh = j["lighthouseResult"]
    a = lh["audits"]
    num = lambda k: (a.get(k) or {}).get("numericValue") or 0  # noqa: E731
    oport = sorted((x for x in a.values() if (x.get("details") or {}).get("type") == "opportunity"
                    and (x["details"].get("overallSavingsMs") or 0) > 100),
                   key=lambda x: -x["details"]["overallSavingsMs"])[:3]

    def crux(bloco: dict | None) -> dict:
        m = (bloco or {}).get("metrics") or {}
        out = {}
        for chave, nome in (("LARGEST_CONTENTFUL_PAINT_MS", "lcp_ms"), ("INTERACTION_TO_NEXT_PAINT", "inp_ms"),
                            ("CUMULATIVE_LAYOUT_SHIFT_SCORE", "cls"), ("FIRST_CONTENTFUL_PAINT_MS", "fcp_ms"),
                            ("EXPERIMENTAL_TIME_TO_FIRST_BYTE", "ttfb_ms")):
            if chave in m:
                p75 = m[chave]["percentile"]
                out[nome] = {"p75": p75 / 100 if nome == "cls" else p75, "categoria": m[chave].get("category")}
        return out

    exp_url = j.get("loadingExperience") or {}
    return {
        "nota": round(lh["categories"]["performance"]["score"] * 100),
        "lcp": num("largest-contentful-paint") / 1000, "fcp": num("first-contentful-paint") / 1000,
        "cls": num("cumulative-layout-shift"), "tbt_ms": num("total-blocking-time"),
        "si": num("speed-index") / 1000, "ttfb_ms": num("server-response-time"),
        "peso_kb": num("total-byte-weight") / 1024,
        "requisicoes": len(((a.get("network-requests") or {}).get("details") or {}).get("items", [])),
        "oportunidades": [{"titulo": x["title"], "economia_ms": round(x["details"]["overallSavingsMs"])} for x in oport],
        "crux_url": crux(exp_url) if not exp_url.get("origin_fallback") else {},
        "crux_origem": crux(j.get("originLoadingExperience")),
    }


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
                                "anuncio_id": ad["id"], "anuncio": ad["name"],
                                "url": normalizar_url(link) if link else "", "expert": expert_do_nome(c["name"])})
    return out


def urls_google(lancamento: str) -> list[dict]:
    """Todos os anúncios não removidos, com `ativo` — o mapa anúncio → LP do Google precisa dos pausados
    também (o histórico deles está em google_ads_daily); a auditoria filtra pelo `ativo`."""
    g, out = Google(), []
    for conta in P.GOOGLE_CONTAS.values():
        for x in g.buscar(conta, f"""SELECT campaign.id, campaign.name, campaign.status, ad_group.status,
                ad_group_ad.status, ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.ad.final_urls
                FROM ad_group_ad WHERE campaign.name LIKE '%{lancamento}%' AND ad_group_ad.status != 'REMOVED'"""):
            ad = x["adGroupAd"]["ad"]
            ativo = (x["campaign"]["status"] == "ENABLED" and x["adGroup"]["status"] == "ENABLED"
                     and x["adGroupAd"]["status"] == "ENABLED")
            for link in ad.get("finalUrls") or [""]:
                out.append({"plataforma": "Google", "campanha_id": x["campaign"]["id"], "campanha": x["campaign"]["name"],
                            "anuncio_id": ad["id"], "anuncio": ad.get("name") or ad["id"], "ativo": ativo,
                            "url": normalizar_url(link) if link else "", "expert": expert_do_nome(x["campaign"]["name"])})
    return out


def _engine(var: str):
    from src.db_engine import make_engine
    return make_engine(var)


def ler_oficiais(lancamento: str) -> dict[str, str | None] | None:
    """url → tag esperada, da tabela lp_oficiais (banco operacional). None = lançamento sem lista."""
    from sqlalchemy import text
    with _engine("SUPABASE_USERS_URL").connect() as c:
        linhas = c.execute(text("SELECT url, tag_esperada FROM lp_oficiais WHERE lancamento_codigo = :c"),
                           {"c": lancamento.upper()}).all()
    return {u: t for u, t in linhas} or None


def ler_forms_ac(ids: set[str]) -> dict[str, dict]:
    base, chave, out = os.environ["AC_API_URL"].rstrip("/"), os.environ["AC_API_KEY"], {}
    for i in ids:
        r = requests.get(f"{base}/api/3/forms/{i}", headers={"Api-Token": chave}, timeout=30)
        if r.status_code != 200:
            out[i] = {"id": i, "nome": f"(AC devolveu {r.status_code})", "tags": [], "obrigado": None}
            continue
        f = r.json().get("form", {})
        acoes = (f.get("actiondata") or {}).get("actions", [])
        out[i] = {"id": i, "nome": f.get("name", ""), "tags": [a["tag"] for a in acoes if a.get("type") == "add-a-tag"],
                  "obrigado": (f.get("submitdata") or {}).get("url") if f.get("submit") == "open-url" else None,
                  "envios": int(f.get("entries") or 0), "criado_em": f.get("cdate")}
    return out


def abrir_paginas(urls: list[str]) -> dict[str, dict]:
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        nav = p.chromium.launch()
        for url in urls:
            pg = nav.new_page(user_agent=UA_CELULAR, viewport=VIEWPORT_CELULAR)
            reqs: list[str] = []
            # o pixel às vezes manda o evento por POST em /tr/, com o id no corpo — guardar o corpo também
            pg.on("request", lambda r: reqs.append(r.url + (" " + (r.post_data or "")[:300] if "facebook.com/tr" in r.url else "")))
            try:
                resp = pg.goto(url, wait_until="networkidle", timeout=60000)
                praticas = pg.evaluate(_JS_PRATICAS)
                antes = " ".join(reqs)
                pg.mouse.move(100, 200)          # o site adia GTM/pixel até a primeira interação
                pg.mouse.wheel(0, 600)
                pg.keyboard.press("Tab")
                pg.wait_for_timeout(6000)
                html, rede = pg.content(), " ".join(reqs)
                out[url] = {"url": url, "status": resp.status if resp else 0, "final": pg.url,
                            "form_ids": sorted(set(re.findall(r"_form_(\d+)", html))),
                            "gtm": set(re.findall(r"gtm\.js\?id=(GTM-[A-Z0-9]+)", rede)),
                            "pixels": pixels_disparados(reqs),
                            "rastreio_antes_interacao": bool(re.search(r"gtm\.js\?id=|facebook\.com/tr", antes)),
                            "https": url.startswith("https://"),
                            "dominios_terceiros": len({urlsplit(u.split(" ")[0]).netloc for u in reqs}
                                                      - {urlsplit(url).netloc, ""}),
                            **praticas}
            except Exception as e:  # noqa: BLE001 — uma LP fora do ar não derruba a auditoria
                out[url] = {"url": url, "erro": str(e).splitlines()[0][:120], "form_ids": [], "gtm": set(), "pixels": set()}
            pg.close()
        nav.close()
    return out


def status_paginas(urls: set[str]) -> dict[str, int]:
    """HTTP de cada página de obrigado (no navegador: o Cloudflare barra requests direto)."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(user_agent=UA_CELULAR)
        for u in urls:
            try:
                r = pg.goto(u, wait_until="domcontentloaded", timeout=45000)
                out[u] = r.status if r else 0
            except Exception:  # noqa: BLE001
                out[u] = 0
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
    """URL → cliques/lpv/leads dos anúncios do Meta nos últimos `dias` (mesma leitura de /landing-pages).
    Janela curta de propósito: o link é editado no próprio anúncio, e o histórico inteiro deixaria o
    alerta da LP antiga aceso na LP nova por semanas."""
    from datetime import date, timedelta
    from frontend.db_readers.carregamento_lp import read_carregamento_lp
    d = read_carregamento_lp(lancamento, date.today() - timedelta(days=dias), date.today())
    return {r["url"]: r | {"desde": d["desde"]} for r in (d or {}).get("por_lp", [])}


def velocidade(url: str, token: str) -> dict:
    r = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", timeout=180,
                     headers={"Authorization": f"Bearer {token}"},
                     params={"url": url, "strategy": "mobile", "category": "performance", "locale": "pt"})
    if r.status_code != 200:
        return {"nota": None, "lcp": None, "erro_psi": r.json().get("error", {}).get("message", r.status_code)}
    return resumo_pagespeed(r.json())


# ---------------------------------------------------------------------------- gravação
def _jsonavel(v):
    if isinstance(v, set):
        return sorted(v)
    return str(v)


def gravar_auditoria(lancamento: str, resultados: list[dict]) -> None:
    from sqlalchemy import text
    with _engine("SUPABASE_DB_URL").begin() as c:
        for r in resultados:
            c.execute(text("""
                INSERT INTO lp_auditoria (lancamento_codigo, url, auditado_em, ok, alertas, dados)
                VALUES (:l, :u, NOW(), :ok, CAST(:a AS JSONB), CAST(:d AS JSONB))
                ON CONFLICT (lancamento_codigo, url) DO UPDATE
                   SET auditado_em = NOW(), ok = EXCLUDED.ok, alertas = EXCLUDED.alertas, dados = EXCLUDED.dados
            """), {"l": lancamento.upper(), "u": r["url"], "ok": not r["alertas"],
                   "a": json.dumps(r["alertas"], ensure_ascii=False),
                   "d": json.dumps(r["dados"], ensure_ascii=False, default=_jsonavel)})


def gravar_lp_google(lancamento: str, anuncios: list[dict]) -> int:
    """Mapa anúncio → LP do Google em ad_landing_pages (o do Meta é gravado pelo etl_meta_ads)."""
    from sqlalchemy import text
    linhas = {(x["anuncio_id"]): x["url"] for x in anuncios if x["url"]}
    if not linhas:
        return 0
    with _engine("SUPABASE_DB_URL").begin() as c:
        c.execute(text("""
            INSERT INTO ad_landing_pages (platform, ad_id, url, lancamento_codigo, updated_at)
            VALUES ('google', :ad_id, :url, :code, NOW())
            ON CONFLICT (platform, ad_id) DO UPDATE SET url = EXCLUDED.url, updated_at = NOW()
        """), [{"ad_id": str(a), "url": u, "code": lancamento.upper()} for a, u in linhas.items()])
    return len(linhas)


# ---------------------------------------------------------------------------- relatório
def lancamentos_ativos(dias: int = 3) -> list[str]:
    """Lançamentos com gasto no Meta ou no Google nos últimos `dias` (fora distribuição e perpétuo,
    que não têm lista de LP por lançamento)."""
    from sqlalchemy import text
    with _engine("SUPABASE_DB_URL").connect() as c:
        linhas = c.execute(text("""
            SELECT DISTINCT lancamento_codigo FROM (
                SELECT lancamento_codigo, spend AS gasto FROM meta_ads_daily WHERE date >= CURRENT_DATE - :d
                UNION ALL
                SELECT lancamento_codigo, cost FROM google_ads_daily WHERE date >= CURRENT_DATE - :d) x
            WHERE gasto > 0 AND lancamento_codigo IS NOT NULL
              AND lancamento_codigo NOT LIKE 'DISTRIBUICAO%' AND lancamento_codigo NOT LIKE 'PERPETUO%'
            ORDER BY 1"""), {"d": dias}).scalars().all()
    return list(linhas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lancamento", help="código do lançamento, ou 'ativos'")
    ap.add_argument("--todos", action="store_true", help="inclui anúncios/campanhas pausados")
    ap.add_argument("--sem-velocidade", action="store_true", help="pula a PageSpeed (mais rápido)")
    ap.add_argument("--nao-gravar", action="store_true", help="não grava em lp_auditoria / ad_landing_pages")
    a = ap.parse_args()
    if a.lancamento.lower() == "ativos":
        codigos = lancamentos_ativos()
        print(f"lançamentos com gasto nos últimos 3 dias: {', '.join(codigos) or 'nenhum'}\n")
        rc = 0
        for cod in codigos:
            print(f"==================== {cod}")
            rc |= auditar(cod, a)
        return rc
    return auditar(a.lancamento, a)


def auditar(lancamento: str, a: argparse.Namespace) -> int:
    lanc = lancamento.upper()

    google = urls_google(lanc)
    if not a.nao_gravar:
        print(f"mapa anúncio → LP do Google: {gravar_lp_google(lanc, google)} anúncio(s)")
    anuncios = urls_meta(lanc, a.todos) + [x for x in google if a.todos or x["ativo"]]
    oficiais = ler_oficiais(lanc)
    sem_link = [x for x in anuncios if not x["url"]]
    por_url: dict[str, list[dict]] = defaultdict(list)
    for x in anuncios:
        if x["url"]:
            por_url[x["url"]].append(x)
    for u in oficiais or {}:
        por_url.setdefault(u, [])     # LP oficial ainda sem anúncio também é auditada
    print(f"{len(anuncios)} anúncio(s), {len(por_url)} LP(s) "
          f"({len(oficiais or {})} na lista oficial{'' if oficiais else ' — lançamento sem lista oficial'})\n")

    paginas = abrir_paginas(sorted(por_url))
    forms = ler_forms_ac({i for p in paginas.values() for i in p["form_ids"]})
    status_obg = status_paginas({f["obrigado"] for f in forms.values() if f.get("obrigado")})
    for f in forms.values():
        f["obrigado_status"] = status_obg.get(f.get("obrigado"))
    token = _token_google_leitura()
    gatilhos: dict[str, list[str]] = {}
    for gtm_id in sorted(set(P.GTM_POR_DOMINIO.values())):
        try:
            gatilhos[gtm_id] = gatilhos_de_lead(gtm_publicado(gtm_id, token))
        except Exception as e:  # noqa: BLE001
            print(f"!! GTM {gtm_id} não lido ({e}) — página de obrigado não conferida")
    try:
        real = taxa_real_meta(lanc)
    except Exception as e:  # noqa: BLE001
        real = {}
        print(f"!! taxa real do Meta não lida ({e})")
    if not a.sem_velocidade:
        with ThreadPoolExecutor(4) as ex:
            for url, v in zip(por_url, ex.map(lambda u: velocidade(u, token), por_url)):
                paginas[url].update(v)

    total, resultados = 0, []
    for url in sorted(por_url, key=lambda u: -len(por_url[u])):
        lp = paginas[url] | {"forms": [forms[i] for i in paginas[url]["form_ids"]], "real": real.get(url)}
        experts = {x["expert"] for x in por_url[url] if x["expert"]}
        gtm_lp = P.GTM_POR_DOMINIO.get(urlsplit(url).netloc)
        probs = problemas_lp(lp, lanc, experts, gatilhos.get(gtm_lp), oficiais)
        total += bool(probs)
        resultados.append({"url": url, "alertas": probs, "dados": lp | {
            "gatilhos_lead": gatilhos.get(gtm_lp), "experts": sorted(experts),
            "anuncios_ativos": {"Meta": sum(x["plataforma"] == "Meta" for x in por_url[url]),
                                "Google": sum(x["plataforma"] == "Google" for x in por_url[url])}}})
        print(f"[{'OK' if not probs else '!!'}] {url}")
        for f in lp["forms"]:
            print(f"      form {f['id']} · {f['nome']} · tags {f['tags']} · obrigado {f.get('obrigado') or '-'}"
                  f" (HTTP {f.get('obrigado_status') or '-'})")
        if lp.get("nota") is not None:
            print(f"      celular: nota {lp['nota']} · LCP {lp['lcp']:.1f} s · CLS {lp['cls']:.2f} · TBT {lp['tbt_ms']:.0f} ms"
                  f" · {lp['peso_kb']:.0f} KB · {lp['requisicoes']} requisições")
        elif lp.get("erro_psi"):
            print(f"      PageSpeed falhou: {lp['erro_psi']}")
        if not lp.get("erro"):
            print(f"      leitura: {lp.get('campos_form')} campo(s) no form · form a {lp.get('form_topo_px')} px do topo"
                  f" (tela {lp.get('altura_tela')}) · rastreio antes da interação: "
                  f"{'sim' if lp.get('rastreio_antes_interacao') else 'NÃO'}")
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

    if not a.nao_gravar:
        gravar_auditoria(lanc, resultados)
        print(f"auditoria gravada em lp_auditoria ({len(resultados)} LP(s))")
        # Print da página para /landing-pages e o debriefing: só o que falta ou passou de 7 dias.
        try:
            from scripts.capturar_lps import capturar_urls
            capturar_urls([u for u in por_url if not paginas[u].get("erro")], lanc, dias=7)
        except Exception as e:  # noqa: BLE001 — print é enfeite; não derruba a auditoria
            print(f"!! print das LPs não capturado ({e})")
    if sem_link:
        print(f"{len(sem_link)} anúncio(s) sem link legível pela API (post existente / vídeo sem CTA):")
        for x in sem_link:
            print(f"  {x['plataforma']} {x['campanha_id']} {x['campanha']} · {x['anuncio']}")
    print(f"\n{total} LP(s) com alerta.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
