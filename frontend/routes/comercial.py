from __future__ import annotations
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.concurrency import run_in_threadpool

from frontend.auth import _get_current_user, resposta_403
from frontend.core import templates, get_launches, _base_ctx
from frontend.db_readers import (
    PERIODOS, RECARREGAR_HORAS, SITUACOES, read_atendimento, read_conversas_abertas, espera_texto,
)

router = APIRouter()


@router.get("/atendimento", response_class=HTMLResponse)
async def atendimento_page(request: Request, dias: int = 7, conexao: str | None = None,
                           inicio: str | None = None, fim: str | None = None):
    """Mensagens, templates e conversas abertas por atendente do Unnichat.

    Não é página de lançamento: o atendimento comercial é contínuo. O filtro é
    por conta (número de WhatsApp do Unnichat, cadastro unnichat_conexoes), não
    por produto: o que importa é em qual conta o atendimento aconteceu.
    """
    launches = await run_in_threadpool(get_launches)
    atendimento = await run_in_threadpool(read_atendimento, dias, conexao, None, inicio, fim)
    ctx = _base_ctx(
        request, "atendimento", "Atendimento", None, launches,
        atendimento=atendimento, dias=atendimento.dias, personalizado=atendimento.personalizado, periodos=PERIODOS, recarregar_horas=RECARREGAR_HORAS,
        conexao=atendimento.conexao, conexoes=atendimento.conexoes, situacoes=SITUACOES,
        coleta_ligada=_coletor().ESTADO["ligado"],
    )
    return templates.TemplateResponse("atendimento.html", ctx)


@router.get("/atendimento/conversas.csv")
async def atendimento_conversas_csv(conexao: str | None = None, atendente: str | None = None,
                                    situacao: str | None = None):
    """Relatório completo das conversas abertas em CSV (Excel-friendly: ';' e
    BOM). A página mostra no máximo 200; aqui vêm todas, com os mesmos filtros
    (conta, atendente, situação) da tabela."""
    import csv
    import io
    from datetime import datetime

    conversas = await run_in_threadpool(read_conversas_abertas, conexao, atendente or None, situacao or None)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Contato", "Telefone", "Atendente", "Conexão", "Última mensagem de",
                "Última mensagem em", "Esperando há", "Esperando (min)", "Situação"])
    for c in conversas:
        w.writerow([
            c["contato"], c["telefone"] or "", c["atendente"], c["conexao"],
            {"cliente": "Cliente", "atendente": "Atendente"}.get(c["ultima_msg_de"], ""),
            c["ultima_msg_em"].strftime("%d/%m/%Y %H:%M") if c["ultima_msg_em"] else "",
            espera_texto(c["espera_min"]),
            c["espera_min"] if c["espera_min"] is not None else "",
            SITUACOES[c["situacao"]],
        ])
    nome = "conversas-abertas_" + datetime.now().strftime("%Y-%m-%d_%H%M") + ".csv"
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


# ── Botão "Atualizar agora" ───────────────────────────────────────────────────
# Relê na hora as conversas com mensagem nas últimas ATUALIZAR_HORAS, sem esperar
# a recoleta automática (30 min) nem a recarga da página (2 h). Liberado pra
# quem abre a página, inclusive "leitura": não edita dado nenhum, só pede ao
# coletor pra reler o que já está no Unnichat.
ATUALIZAR_HORAS = 24


def _coletor():
    from frontend.services.unnichat import coletor  # noqa: PLC0415
    return coletor


def _contas(conexao: str | None) -> list[str]:
    contas = sorted(_coletor().tokens())
    return [conexao] if conexao in contas else contas


@router.post("/atendimento/atualizar")
async def atendimento_atualizar(conexao: str | None = None):
    from frontend.services.unnichat import banco  # noqa: PLC0415

    if not _coletor().ESTADO["ligado"]:
        return JSONResponse({"ok": False, "erro": "A coleta do Unnichat está desligada no servidor."}, status_code=503)
    na_fila = await run_in_threadpool(banco.pedir_atualizacao, _contas(conexao), ATUALIZAR_HORAS)
    return {"ok": True, "na_fila": na_fila}


@router.get("/atendimento/atualizar/status")
async def atendimento_atualizar_status(conexao: str | None = None):
    from frontend.services.unnichat import banco  # noqa: PLC0415

    return {"na_fila": await run_in_threadpool(banco.atualizacao_pendente, _contas(conexao))}


# ── Área Comercial: Visão geral, Comissões, Ranking (Task 5) ───────────────────
# ROUTE_PERMISSIONS deixa passar o grupo _CMRC_AREA; a trava de verdade é o nível em
# comercial_acessos (acesso_comercial). O recorte por vendedor é feito em
# services/comercial/telas.py, antes de qualquer agregação — nunca no template.
# "Em validação": o sistema calcula como se valesse, mas o pagamento segue a planilha
# até o gestor aprovar (decisão do usuário, 06/11/26).

def _telas():
    from frontend.services.comercial import telas  # noqa: PLC0415
    return telas


async def _acesso(request: Request):
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    return await run_in_threadpool(ac.acesso_comercial, _get_current_user(request))


def _hoje():
    from frontend.services.comercial.snapshot import agora_sp  # noqa: PLC0415
    return agora_sp().date()


class _Recusa(Exception):
    def __init__(self, resposta):
        self.resposta = resposta


def resposta_400(msg: str, titulo: str = "Período indisponível", voltar: str = "/comercial",
                 rotulo_voltar: str = "← Voltar para o mês atual") -> HTMLResponse:
    """Pedido fora do permitido: mesma cara do 403, com o motivo e um caminho de volta."""
    from html import escape  # noqa: PLC0415
    return HTMLResponse(
        content=f"""<html><body style="font-family:Inter,sans-serif;display:flex;align-items:center;
            justify-content:center;height:100vh;background:#eef0f8">
            <div style="text-align:center"><h1 style="font-size:48px;color:#2f5ee3">{escape(titulo)}</h1>
            <p style="color:#6b7280">{escape(msg)}</p>
            <a href="{escape(voltar)}" style="color:#2f5ee3">{escape(rotulo_voltar)}</a></div></body></html>""",
        status_code=400,
    )


async def _carregar(mes, inicio, fim, acesso):
    t = _telas()
    hoje = _hoje()
    try:
        periodo = t.resolver_periodo(mes, inicio, fim, hoje, gestor=t.e_gestor(acesso))
    except t.PeriodoInvalido as exc:
        raise _Recusa(resposta_400(str(exc))) from None
    res = await run_in_threadpool(t.carregar, periodo)
    return t, periodo, res, hoje


async def _pagina(request: Request, page: str, title: str, template: str, view: dict, hoje):
    launches = await run_in_threadpool(get_launches)
    ctx = _base_ctx(request, page, title, None, launches, v=view,
                    meses=_telas().meses_recentes(hoje),
                    situacao_rotulo=_telas().SITUACAO_ROTULO, motivo_rotulo=_telas().MOTIVO_ROTULO)
    return templates.TemplateResponse(template, ctx)


@router.get("/comercial", response_class=HTMLResponse)
async def comercial_visao(request: Request, mes: str | None = None,
                          inicio: str | None = None, fim: str | None = None):
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    try:
        t, periodo, res, hoje = await _carregar(mes, inicio, fim, acesso)
    except _Recusa as r:
        return r.resposta
    return await _pagina(request, "comercial_visao", "Comercial · Visão geral", "comercial_visao.html",
                         t.view_visao(res, periodo, acesso), hoje)


@router.get("/comercial/comissoes", response_class=HTMLResponse)
async def comercial_comissoes(request: Request, mes: str | None = None, inicio: str | None = None,
                              fim: str | None = None, vendedor: str | None = None):
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    try:
        t, periodo, res, hoje = await _carregar(mes, inicio, fim, acesso)
    except _Recusa as r:
        return r.resposta
    return await _pagina(request, "comercial_comissoes", "Comercial · Comissões", "comercial_comissoes.html",
                         t.view_comissoes(res, periodo, acesso, (vendedor or "").strip().upper() or None), hoje)


@router.get("/comercial/comissoes.xlsx")
async def comercial_comissoes_xlsx(request: Request, mes: str | None = None, inicio: str | None = None,
                                   fim: str | None = None, vendedor: str | None = None):
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    try:
        t, periodo, res, _ = await _carregar(mes, inicio, fim, acesso)
    except _Recusa as r:
        return r.resposta
    view = t.view_comissoes(res, periodo, acesso, (vendedor or "").strip().upper() or None)
    corpo = await run_in_threadpool(t.planilha_xlsx, view)
    sufixo = f"{periodo.mes:%Y-%m}" if not periodo.livre else f"{periodo.inicio}_{periodo.fim}"
    if view["vendedor"]:
        sufixo += "_" + view["vendedor"]
    elif not view["gestor"]:
        sufixo += "_" + (acesso.vendedor_codigo or "")
    return Response(
        corpo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="comissoes_{sufixo}.xlsx"'},
    )


@router.get("/comercial/ranking", response_class=HTMLResponse)
async def comercial_ranking(request: Request, mes: str | None = None, inicio: str | None = None,
                            fim: str | None = None, ordem: str = "vendido"):
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    try:
        t, periodo, res, hoje = await _carregar(mes, inicio, fim, acesso)
    except _Recusa as r:
        return r.resposta
    return await _pagina(request, "comercial_ranking", "Comercial · Ranking", "comercial_ranking.html",
                         t.view_ranking(res, periodo, acesso, ordem), hoje)


@router.post("/comercial/recalcular")
async def comercial_recalcular(request: Request, mes: str | None = None, voltar: str = Form("")):
    """Marca o snapshot do mês como desatualizado; a próxima leitura recalcula (~20 s)."""
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None or not ac.pode(acesso.nivel, "ver_time"):
        return resposta_403()
    try:
        periodo = _telas().resolver_periodo(mes, None, None, _hoje(), gestor=True)
    except _telas().PeriodoInvalido as exc:
        return resposta_400(str(exc))
    await run_in_threadpool(snap.marcar_desatualizado, periodo.mes)
    # só volta para dentro da área (nada de redirecionar para outro site)
    seguro = voltar.startswith("/comercial") and "//" not in voltar and "\\" not in voltar
    destino = voltar if seguro else f"/comercial?{periodo.query}"
    return RedirectResponse(destino, status_code=303)


# ── Área Comercial: Inconsistências (Task 6) ──────────────────────────────────
# Primeira tela que GRAVA por clique. Cada POST: nível checado aqui (ROUTE_PERMISSIONS só
# deixa o grupo entrar), entrada validada no serviço (400), escrita exata + histórico na
# mesma transação (db_readers/comercial.py), snapshot do mês da venda marcado desatualizado
# quando a escrita muda o cálculo, 303 de volta com um CÓDIGO de mensagem (nunca texto livre
# na URL).
_URL_INC = "/comercial/inconsistencias"


def _inc():
    from frontend.services.comercial import inconsistencias  # noqa: PLC0415
    return inconsistencias


def _com():
    from frontend.db_readers import comercial  # noqa: PLC0415
    return comercial


def _voltar_inc(mes, **qs) -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415
    params = ({"mes": f"{mes:%Y-%m}"} if mes else {}) | {k: v for k, v in qs.items() if v}
    return RedirectResponse(_URL_INC + ("?" + urlencode(params) if params else ""), status_code=303)


async def _acao(request: Request, permissao: str, mes: str | None, executar):
    """Esqueleto das ações. `executar(acesso, email, mes)` -> (código ok, transação, invalida?)."""
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None or not ac.pode(acesso.nivel, permissao):
        return resposta_403()
    email = (_get_current_user(request).get("email") or "").strip().lower()
    if not email:
        return resposta_403()  # toda escrita precisa de autor no histórico
    inc, com = _inc(), _com()
    mes_d = inc.mes_valido(mes, _hoje())
    try:
        ok, transacao, invalida = await run_in_threadpool(executar, acesso, email, mes_d)
    except inc.EntradaInvalida as exc:
        return resposta_400(str(exc), "Pedido inválido", _URL_INC + (f"?mes={mes_d:%Y-%m}" if mes_d else ""),
                            "← Voltar para Inconsistências")
    except com.EscritaRecusada as exc:
        return _voltar_inc(mes_d, erro=exc.codigo)
    if invalida:
        # mês da venda se ela está no snapshot do mês da tela; senão todos (mês desconhecido)
        achou = inc.localizar(await run_in_threadpool(inc.linhas_guardadas, mes_d), transacao)
        try:
            await run_in_threadpool(snap.marcar_desatualizado, mes_d if achou else None)
        except Exception:  # noqa: BLE001 — a escrita já foi; avisa para recalcular à mão
            import logging  # noqa: PLC0415
            logging.getLogger("comercial.inconsistencias").exception("marcar_desatualizado")
            return _voltar_inc(mes_d, ok=ok, erro="nao_invalidou")
    return _voltar_inc(mes_d, ok=ok)


@router.get("/comercial/inconsistencias", response_class=HTMLResponse)
async def comercial_inconsistencias(request: Request, mes: str | None = None, q: str | None = None,
                                    ok: str | None = None, erro: str | None = None):
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    t, inc, com = _telas(), _inc(), _com()
    hoje = _hoje()
    try:
        periodo = t.resolver_periodo(mes, None, None, hoje)  # só mês: as ações voltam para um mês
    except t.PeriodoInvalido as exc:
        return resposta_400(str(exc))
    res = await run_in_threadpool(t.carregar, periodo)
    gestor = ac.pode(acesso.nivel, "aprovar")
    fila = await run_in_threadpool(lambda: com.ler_fila(vendedor_codigo=acesso.vendedor_codigo, gestor=gestor))
    conflitos = {}
    if gestor:
        pedidos = [l.transacao for l in res.linhas if l.papel == "venda" and l.motivo == "conflito_codigo"]
        conflitos = await run_in_threadpool(com.ler_codigos_conflito, pedidos)
    view = inc.view_inconsistencias(res, periodo, acesso, fila, conflitos, q)
    view["msg_ok"] = inc.MENSAGENS_OK.get(ok or "")
    view["msg_erro"] = inc.MENSAGENS_ERRO.get(erro or "")
    return await _pagina(request, "comercial_inconsistencias", "Comercial · Inconsistências",
                         "comercial_inconsistencias.html", view, hoje)


@router.post("/comercial/reivindicar")
async def comercial_reivindicar(request: Request, transacao: str = Form(""), vendedor_codigo: str = Form(""),
                                mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        codigo = inc.codigo_do_pedido(acesso, vendedor_codigo)
        inc.conferir_reivindicacao(inc.localizar(inc.linhas_guardadas(mes_d), t), codigo)
        com.reivindicar(t, inc.plataforma_de(t), codigo, email)
        return "reivindicada", t, False  # pendente não muda o cálculo: não invalida o mês
    return await _acao(request, "reivindicar", mes, executar)


@router.post("/comercial/atribuicoes/aprovar")
async def comercial_aprovar(request: Request, transacao: str = Form(""), mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        com.decidir_atribuicao(t, inc.plataforma_de(t), True, email)
        return "aprovada", t, True
    return await _acao(request, "aprovar", mes, executar)


@router.post("/comercial/atribuicoes/recusar")
async def comercial_recusar(request: Request, transacao: str = Form(""), motivo: str = Form(""),
                            mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        m = inc.texto_obrigatorio(motivo, "Motivo da recusa")
        com.decidir_atribuicao(t, inc.plataforma_de(t), False, email, m)
        return "recusada", t, False  # pendente -> recusada: a venda segue sem vendedor
    return await _acao(request, "aprovar", mes, executar)


@router.post("/comercial/atribuir")
async def comercial_atribuir(request: Request, transacao: str = Form(""), vendedor_codigo: str = Form(""),
                             motivo: str = Form(""), mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        codigo = inc.limpar_codigo(vendedor_codigo)
        m = (motivo or "").strip()[:inc.MAX_TEXTO] or None
        com.atribuir_gestor(t, inc.plataforma_de(t), codigo, email, m)
        return "atribuida", t, True
    return await _acao(request, "aprovar", mes, executar)


@router.post("/comercial/reembolso")
async def comercial_reembolso(request: Request, transacao: str = Form(""), decisao: str = Form(""),
                              justificativa: str = Form(""), mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        if decisao not in ("mantem", "tira"):
            raise inc.EntradaInvalida("Escolha Mantém ou Tira.")
        j = inc.texto_obrigatorio(justificativa, "Justificativa")
        com.decidir_reembolso(t, inc.plataforma_de(t), decisao, j, email)
        return "reembolso", t, True
    return await _acao(request, "aprovar", mes, executar)


@router.post("/comercial/ajuste")
async def comercial_ajuste(request: Request, transacao: str = Form(""), pct: str = Form(""),
                           valor_base: str = Form(""), justificativa: str = Form(""), mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        p, b = inc.ler_ajuste(pct, valor_base)
        j = inc.texto_obrigatorio(justificativa, "Justificativa")
        com.gravar_ajuste(t, inc.plataforma_de(t), p, b, j, email)
        return "ajuste", t, True
    return await _acao(request, "aprovar", mes, executar)
