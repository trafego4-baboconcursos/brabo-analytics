"""
Encurtador de links (substitui o Bitly): /links (painel) e /links/{id} (estatísticas).

O redirecionamento público <domínio curto>/<nome> não passa por aqui: é o app
Brabo Links (ver frontend/services/links.py). Este router cria, edita e lê.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.exc import DBAPIError

from frontend.core import _base_ctx, _get_current_user, get_launches, logger, templates
from frontend.db_readers import links as db
from frontend.services.links import (
    BASE_CURTA, CATEGORIAS, HOST_CURTO, PAPEIS_EDICAO, PERIODOS,
    LinkInvalido, campos_do_formulario, destino_final, detecta_categoria, link_json,
    normaliza_destino, normaliza_slug, slugify, valida_slug,
)

router = APIRouter()


def _ctx(request: Request, page: str, title: str, **extra) -> dict:
    user = _get_current_user(request)
    return _base_ctx(
        request, page, title, None, get_launches(),
        CATEGORIAS=CATEGORIAS, BASE_CURTA=BASE_CURTA, HOST_CURTO=HOST_CURTO,
        pode_editar=user["role"] in PAPEIS_EDICAO, link_json=link_json,
        **extra,
    )


@router.get("/links", response_class=HTMLResponse)
async def links_page(request: Request):
    try:
        dados = await run_in_threadpool(db.painel)
        erro_banco = None
    except DBAPIError:
        # Sem o schema `encurtador` (o Brabo Links cria na primeira subida) ou banco fora.
        logger.exception("links: falha lendo o encurtador")
        dados, erro_banco = {"links": [], "hoje": 0, "ontem": 0, "sete": 0, "sete_antes": 0}, True
    campanhas, usadas = db.listas(dados["links"])
    ctx = await run_in_threadpool(
        _ctx, request, "links", "Links", d=dados, campanhas=campanhas, usadas=usadas, erro_banco=erro_banco,
    )
    return templates.TemplateResponse("links.html", ctx)


@router.get("/links/{link_id}", response_class=HTMLResponse)
async def link_page(request: Request, link_id: int, periodo: str = "30"):
    link = await run_in_threadpool(db.link, link_id)
    if not link:
        return RedirectResponse("/links", status_code=303)
    if periodo not in PERIODOS:
        periodo = "30"
    st = await run_in_threadpool(db.estatisticas, link_id, PERIODOS[periodo])
    campanhas, usadas = await run_in_threadpool(db.listas)
    ctx = await run_in_threadpool(
        _ctx, request, "links", link["titulo"], link=link, st=st, periodo=periodo,
        campanhas=campanhas, usadas=usadas, final=destino_final(link),
        criado_txt=link["criado_em"].astimezone(db.TZ).strftime("%d/%m/%Y %H:%M"),
    )
    return templates.TemplateResponse("link_detalhe.html", ctx)


@router.get("/links/{link_id}/cliques.csv")
async def link_csv(link_id: int):
    link = await run_in_threadpool(db.link, link_id)
    if not link:
        return Response("Link não encontrado.", status_code=404)

    def gerar():
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        buf.write("﻿")  # Excel abre com acento certo
        for linha in db.exportar_cliques(link_id):
            w.writerow(linha)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    nome = f"cliques-{link['slug']}-{datetime.now(db.TZ):%Y%m%d}.csv"
    return StreamingResponse(gerar(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/links/{link_id}/qr.{fmt}")
async def link_qr(link_id: int, fmt: str, baixar: int = 0):
    import segno  # noqa: PLC0415 — só esta rota usa

    if fmt not in ("svg", "png"):
        return Response(status_code=404)
    link = await run_in_threadpool(db.link, link_id)
    if not link:
        return Response(status_code=404)
    code = segno.make(f"{BASE_CURTA}/{link['slug']}", error="m")
    buf = io.BytesIO()
    if fmt == "svg":
        code.save(buf, kind="svg", scale=10, border=2, dark="#111111", light="#ffffff", xmldecl=False)
        mt = "image/svg+xml"
    else:
        code.save(buf, kind="png", scale=16, border=2, dark="#111111", light="#ffffff")
        mt = "image/png"
    headers = {"Cache-Control": "private, max-age=300"}
    if baixar:
        headers["Content-Disposition"] = f'attachment; filename="qr-{link["slug"]}.{fmt}"'
    return Response(buf.getvalue(), media_type=mt, headers=headers)


# ── API (JSON) ────────────────────────────────────────────────────────────────
# Sem token CSRF, como o resto do app: o cookie de sessão é SameSite=Lax (não vai
# em POST de outro site) e as rotas de escrita só aceitam corpo JSON, que um
# formulário de outro site não consegue mandar.

def _erro(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"erro": msg}, status_code=status)


async def _corpo(request: Request) -> dict | None:
    if not request.headers.get("content-type", "").startswith("application/json"):
        return None
    try:
        b = await request.json()
    except ValueError:
        return None
    return b if isinstance(b, dict) else None


@router.get("/api/links/sugestao")
async def api_sugestao(destino: str = "", titulo: str = "", slug: str = "", id: int = 0):
    """Categoria detectada + nome sugerido + se o nome está livre (enquanto a pessoa digita)."""
    destino = normaliza_destino(destino)
    base = slugify(titulo)
    if not base and destino:
        partes = [p for p in urlsplit(destino).path.split("/") if p]
        base = slugify(partes[-1].rsplit(".", 1)[0]) if partes else ""
    if base and (valida_slug(base) or await run_in_threadpool(db.slug_existe, base)):
        for i in range(2, 50):  # já usado ou reservado: tenta base-2, base-3…
            cand = f"{base[:56]}-{i}"
            if not valida_slug(cand) and not await run_in_threadpool(db.slug_existe, cand):
                base = cand
                break
    out = {"categoria": detecta_categoria(destino) if destino else "", "sugestao": base}
    s = normaliza_slug(slug)
    if s:
        erro = valida_slug(s)
        if not erro and await run_in_threadpool(db.slug_existe, s, id or None):
            erro = "Esse nome já está em uso."
        out["slug_erro"] = erro or ""
    return out


async def _salvar(request: Request, link_id: int | None):
    user = _get_current_user(request)
    if user["role"] not in PAPEIS_EDICAO:
        return _erro("Seu usuário só pode ver os links.", 403)
    body = await _corpo(request)
    if body is None:
        return _erro("Recarregue a página e tente de novo.")
    try:
        campos = campos_do_formulario(body)
        if await run_in_threadpool(db.slug_existe, campos["slug"], link_id):
            raise LinkInvalido(f"Já existe um link “{campos['slug']}”. Escolha outro nome.", 409)
        if link_id is None:
            r = await run_in_threadpool(db.criar, campos, user.get("email") or "")
        else:
            r = await run_in_threadpool(db.atualizar, link_id, campos)
    except LinkInvalido as e:
        return _erro(str(e), e.status)
    if r is None:
        return _erro("Link não encontrado.", 404)
    return link_json(r)


@router.post("/api/links")
async def api_criar(request: Request):
    return await _salvar(request, None)


@router.patch("/api/links/{link_id}")
async def api_editar(request: Request, link_id: int):
    return await _salvar(request, link_id)


@router.post("/api/links/{link_id}/ativo")
async def api_ativo(request: Request, link_id: int):
    """Arquivar (ativo=false) tira o link do ar sem apagar os cliques; reativar volta."""
    if _get_current_user(request)["role"] not in PAPEIS_EDICAO:
        return _erro("Seu usuário só pode ver os links.", 403)
    body = await _corpo(request)
    if body is None:
        return _erro("Recarregue a página e tente de novo.")
    r = await run_in_threadpool(db.atualizar, link_id, {"ativo": bool(body.get("ativo"))})
    if r is None:
        return _erro("Link não encontrado.", 404)
    return link_json(r)
