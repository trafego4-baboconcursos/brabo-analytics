"""
frontend/services/links.py — regras do encurtador de links (página /links).

O encurtador substitui o Bitly. Dividido em duas partes:
  * aqui no Analytics: criar, editar e ver estatísticas (páginas /links);
  * no app Brabo Links (repo trafego2-create/brabo-links, EasyPanel novo): só o
    redirecionamento público <domínio curto>/<nome> e o registro do clique.
Os dois usam as mesmas tabelas, no schema `encurtador` do banco comercial
(SUPABASE_USERS_URL). As consultas ficam em frontend/db_readers/links.py.

RESERVADOS e SLUG_RE precisam bater com app/store.py do Brabo Links: são os
caminhos do próprio app, que não podem virar link curto.
"""
from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Endereço público dos links curtos (o app Brabo Links), sem barra no fim. O padrão
# é o endereço provisório do EasyPanel novo; quando o domínio próprio sair,
# preencha BRABO_LINKS_URL no Environment.
BASE_CURTA = (os.getenv("BRABO_LINKS_URL", "").strip()
              or "https://automacoes-brabo-links.qacfzn.easypanel.host").rstrip("/")
HOST_CURTO = BASE_CURTA.split("://", 1)[-1]
# O que aparece antes do nome no campo "Nome do link". O endereço provisório do
# EasyPanel é comprido demais pra isso; com domínio próprio, mostra o domínio.
ROTULO_CURTO = os.getenv("BRABO_LINKS_ROTULO", "").strip() or (
    "brabo-links" if HOST_CURTO.endswith(".easypanel.host") else HOST_CURTO)

CATEGORIAS = {
    "youtube": ("YouTube", "ti-brand-youtube"),
    "vendas": ("Página de vendas", "ti-shopping-cart"),
    "checkout": ("Checkout", "ti-credit-card"),
    "ebook": ("E-book / Material", "ti-book"),
    "whatsapp": ("WhatsApp", "ti-brand-whatsapp"),
    "pagina": ("Outro", "ti-link"),
}
UTMS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
CAMPOS_LINK = ("id", "slug", "destino", "titulo", "categoria", "campanha", "ativo", *UTMS)

# Quem cria/edita. "leitura" só vê; "comercial" nem entra (fora de _ALL no middleware).
PAPEIS_EDICAO = ("admin", "analista", "trafego")

RESERVADOS = {
    "app", "api", "login", "logout", "static", "healthz", "admin", "favicon.ico",
    "robots.txt", "img", "qr", "links", "usuarios",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
PERIODOS = {"7": 7, "30": 30, "90": 90, "tudo": None}


class LinkInvalido(ValueError):
    """Erro de validação com a mensagem pronta pra mostrar na tela."""

    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60].strip("-")


def normaliza_slug(s: str) -> str:
    return (s or "").strip().strip("/").lower()


def valida_slug(slug: str) -> str | None:
    if not slug:
        return "Escolha um nome para o link."
    if slug in RESERVADOS:
        return f"“{slug}” é reservado pelo sistema. Escolha outro nome."
    if not SLUG_RE.match(slug):
        return "Use só letras minúsculas, números, - e _ (sem espaço nem acento)."
    return None


def normaliza_destino(url: str) -> str:
    url = (url or "").strip()
    if url and not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        url = "https://" + url
    return url


def valida_destino(url: str) -> str | None:
    if not url:
        return "Cole o link de destino."
    if not re.match(r"^https?://[^\s/$.?#][^\s/?#]*\.[a-z]{2,}(?::\d+)?([/?#]\S*)?$", url, re.I):
        return "Esse não parece um link válido. Confira se copiou o endereço inteiro (ex.: https://site.com/pagina)."
    if HOST_CURTO and url.split("://", 1)[1].lower().startswith(HOST_CURTO.lower() + "/"):
        return "O destino não pode ser outro link curto daqui (daria voltas infinitas)."
    return None


def detecta_categoria(url: str) -> str:
    u = (url or "").lower()
    if re.search(r"(youtube\.com|youtu\.be)", u):
        return "youtube"
    if re.search(r"(wa\.me|whatsapp\.com)", u):
        return "whatsapp"
    if re.search(r"(pay\.hotmart|checkout|/pay/|eduzz|kiwify\.com\.br/|tmb\.|pagamento)", u):
        return "checkout"
    if re.search(r"(\.pdf($|\?)|drive\.google|docs\.google|ebook|e-book|material|apostila)", u):
        return "ebook"
    if re.search(r"(braboconcursos|aprovasim|hotmart\.com|/vendas|/oferta|/inscricao|lp\.)", u):
        return "vendas"
    return "pagina"


def destino_final(link: dict) -> str:
    """Destino + UTMs fixas do link: o endereço em que a pessoa cai. O Brabo Links
    faz a mesma conta no redirecionamento (lá, UTM do clique vence a fixa)."""
    extra = [(k, link[k]) for k in UTMS if link.get(k)]
    if not extra:
        return link["destino"]
    p = urlsplit(link["destino"])
    chaves = {k for k, _ in extra}
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in chaves] + extra
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


def campos_do_formulario(body: dict) -> dict:
    """Valida o JSON do formulário (criar/editar) e devolve as colunas prontas.
    A checagem de nome repetido fica com quem chama (precisa do banco)."""
    destino = normaliza_destino(str(body.get("destino", "")))
    erro = valida_destino(destino)
    if erro:
        raise LinkInvalido(erro)
    slug = normaliza_slug(str(body.get("slug", "")))
    erro = valida_slug(slug)
    if erro:
        raise LinkInvalido(erro)
    categoria = str(body.get("categoria") or "") or detecta_categoria(destino)
    if categoria not in CATEGORIAS:
        categoria = "pagina"
    utms = {k: " ".join(str(body.get(k) or "").split())[:200] for k in UTMS}
    utms["utm_source"] = utms["utm_source"][:100]
    utms["utm_medium"] = utms["utm_medium"][:100]
    if utms["utm_source"] and not utms["utm_medium"]:
        raise LinkInvalido("Preencha também o utm_medium (no Active os dois andam juntos, ex.: ig / social).")
    return {
        "slug": slug, "destino": destino, "categoria": categoria,
        "titulo": str(body.get("titulo", "")).strip()[:200] or slug,
        "campanha": str(body.get("campanha", "")).strip().upper()[:60],
        **utms,
    }


def link_json(r: dict) -> dict:
    """O que a tela precisa de um link (data-link das linhas e resposta da API)."""
    return {
        **{k: r[k] for k in CAMPOS_LINK},
        "curto": f"{BASE_CURTA}/{r['slug']}", "final": destino_final(r),
    }
