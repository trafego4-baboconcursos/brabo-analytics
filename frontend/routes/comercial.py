from __future__ import annotations
from decimal import Decimal
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.concurrency import run_in_threadpool

from frontend.auth import _get_current_user, resposta_403
from frontend.core import templates, get_launches, _base_ctx
from frontend.db_readers import (
    PERIODOS, RECARREGAR_HORAS, SITUACOES, read_atendimento, read_conversas_abertas, espera_texto,
)

router = APIRouter()


async def _bloqueia_atendimento(request: Request):
    """403 se quem pede não é gestor (acesso.ve_atendimento); None se pode. Banco do nível
    fora do ar: o papel "comercial" fica fechado, o marketing segue (não tem nível)."""
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    user = _get_current_user(request) or {}
    role = user.get("role")
    if role == "admin":
        return None
    try:
        nivel = await run_in_threadpool(ac.nivel_comercial, user)
    except Exception:  # noqa: BLE001
        if role == "comercial":
            return resposta_403()
        nivel = None
    return None if ac.ve_atendimento(role, nivel) else resposta_403()


@router.get("/atendimento", response_class=HTMLResponse)
async def atendimento_page(request: Request, dias: int = 7, conexao: str | None = None,
                           inicio: str | None = None, fim: str | None = None):
    """Mensagens, templates e conversas abertas por atendente do Unnichat.

    Não é página de lançamento: o atendimento comercial é contínuo. O filtro é
    por conta (número de WhatsApp do Unnichat, cadastro unnichat_conexoes), não
    por produto: o que importa é em qual conta o atendimento aconteceu.
    """
    if (bloqueio := await _bloqueia_atendimento(request)) is not None:
        return bloqueio
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
async def atendimento_conversas_csv(request: Request, conexao: str | None = None, atendente: str | None = None,
                                    situacao: str | None = None):
    """Relatório completo das conversas abertas em CSV (Excel-friendly: ';' e
    BOM). A página mostra no máximo 200; aqui vêm todas, com os mesmos filtros
    (conta, atendente, situação) da tabela."""
    import csv
    import io
    from datetime import datetime

    if (bloqueio := await _bloqueia_atendimento(request)) is not None:
        return bloqueio

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
async def atendimento_atualizar(request: Request, conexao: str | None = None):
    from frontend.services.unnichat import banco  # noqa: PLC0415

    if (bloqueio := await _bloqueia_atendimento(request)) is not None:
        return bloqueio
    if not _coletor().ESTADO["ligado"]:
        return JSONResponse({"ok": False, "erro": "A coleta do Unnichat está desligada no servidor."}, status_code=503)
    na_fila = await run_in_threadpool(banco.pedir_atualizacao, _contas(conexao), ATUALIZAR_HORAS)
    return {"ok": True, "na_fila": na_fila}


@router.get("/atendimento/atualizar/status")
async def atendimento_atualizar_status(request: Request, conexao: str | None = None):
    from frontend.services.unnichat import banco  # noqa: PLC0415

    if (bloqueio := await _bloqueia_atendimento(request)) is not None:
        return bloqueio
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
    periodo = view.get("periodo")
    if periodo is not None and periodo.livre:  # período livre recalcula até mês fechado
        try:
            fechados = await run_in_threadpool(_com().meses_fechados)
        except Exception:  # noqa: BLE001 — só um aviso; a tela segue sem ele
            fechados = {}
        view["livre_fechados"] = sorted(f"{m:%m/%Y}" for m in fechados
                                        if m <= periodo.fim and m >= periodo.inicio.replace(day=1))
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
    bonus, metas = await run_in_threadpool(t.ler_extras, periodo, acesso)
    return await _pagina(request, "comercial_visao", "Comercial · Visão geral", "comercial_visao.html",
                         t.view_visao(res, periodo, acesso, bonus, metas), hoje)


async def _view_comissoes(t, res, periodo, acesso, vendedor):
    bonus, _metas = await run_in_threadpool(t.ler_extras, periodo, acesso)
    ativos = (await run_in_threadpool(t.ler_vendedores_ativos)
              if t.e_gestor(acesso) and bonus is not None and not res.fechado else [])
    ultimo = True
    if res.fechado:  # Ruling 19b: só o último mês fechado reabre
        fechados = await run_in_threadpool(_com().meses_fechados)
        ultimo = not any(m > periodo.mes for m in fechados)
    return t.view_comissoes(res, periodo, acesso, (vendedor or "").strip().upper() or None, bonus, ativos,
                            hoje=_hoje(), ultimo_fechado=ultimo)


@router.get("/comercial/comissoes", response_class=HTMLResponse)
async def comercial_comissoes(request: Request, mes: str | None = None, inicio: str | None = None,
                              fim: str | None = None, vendedor: str | None = None,
                              ok: str | None = None, erro: str | None = None, qtd: str | None = None):
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    try:
        t, periodo, res, hoje = await _carregar(mes, inicio, fim, acesso)
    except _Recusa as r:
        return r.resposta
    view = await _view_comissoes(t, res, periodo, acesso, vendedor)
    rt = _rt()
    view["msg_ok"] = rt.MENSAGENS_OK.get(ok or "") if view["gestor"] else None
    view["msg_erro"] = rt.MENSAGENS_ERRO.get(erro or "") if view["gestor"] else None
    if view["msg_erro"] and erro == "tem_a_verificar" and (qtd or "").isdigit() and len(qtd) <= 5:
        view["msg_erro"] = (f"Há {int(qtd)} venda(s) com reembolso a verificar neste mês: decida em "
                            "Inconsistências antes de fechar.")
    view["link_inconsistencias"] = erro == "tem_a_verificar"
    return await _pagina(request, "comercial_comissoes", "Comercial · Comissões", "comercial_comissoes.html",
                         view, hoje)


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
    view = await _view_comissoes(t, res, periodo, acesso, vendedor)
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
    _bonus, metas = await run_in_threadpool(t.ler_extras, periodo, acesso)
    return await _pagina(request, "comercial_ranking", "Comercial · Ranking", "comercial_ranking.html",
                         t.view_ranking(res, periodo, acesso, ordem, metas), hoje)


@router.get("/comercial/desempenho", response_class=HTMLResponse)
async def comercial_desempenho(request: Request, mes: str | None = None, inicio: str | None = None,
                               fim: str | None = None, comparar: str | None = None,
                               cinicio: str | None = None, cfim: str | None = None):
    from frontend.db_readers import comercial as com  # noqa: PLC0415
    from frontend.services.comercial import desempenho as d  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None:
        return resposta_403()
    try:
        t, periodo, res, hoje = await _carregar(mes, inicio, fim, acesso)
    except _Recusa as r:
        return r.resposta
    try:
        comparacao = d.resolver_comparacao(periodo, comparar, cinicio, cfim, hoje, gestor=t.e_gestor(acesso))
    except t.PeriodoInvalido as exc:
        return resposta_400(str(exc), "Comparação indisponível", "/comercial/desempenho",
                            "← Voltar ao Desempenho")
    comp = await run_in_threadpool(d.carregar_linhas, comparacao.periodo) if comparacao else None
    acumulado, desde, faltantes = await run_in_threadpool(d.carregar_acumulado, periodo)
    _bonus, metas = await run_in_threadpool(t.ler_extras, periodo, acesso)
    meta_time = None  # soma de TODAS as metas do mês (sem recorte): é número geral do time
    if not periodo.livre:
        todas = await run_in_threadpool(com.ler_metas_mes, periodo.mes, None)
        meta_time = sum((m["valor"] for m in todas.values()), Decimal("0")) if todas else None
    view = d.view_desempenho(res.linhas, comp, comparacao, acumulado, periodo, acesso, metas,
                             meta_time=meta_time, hoje=hoje, acumulado_incompleto=bool(faltantes))
    view.update(gerado_em=res.gerado_em, fechado=res.fechado, fechado_em=res.fechado_em,
                fechado_por=res.fechado_por, acumulado_desde=desde,
                comparar_mes=(f"{comparacao.periodo.mes:%Y-%m}" if comparacao and not comparacao.periodo.livre
                              else ""),
                comparar_livre=bool(comparacao and comparacao.periodo.livre))
    return await _pagina(request, "comercial_desempenho", "Comercial · Desempenho",
                         "comercial_desempenho.html", view, hoje)


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
    """Esqueleto das ações. `executar(acesso, email, mes)` -> (código ok, transação, invalida).
    `invalida`: False = nada; True = o mês da venda (se achada no mês da tela) ou todos;
    ("meses", lista | None) = esses meses (None = todos) — ex.: o estorno vive nos meses
    depois do mês fechado da venda (Ruling 19a)."""
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
        if isinstance(invalida, tuple):
            meses = [None] if invalida[1] is None else list(invalida[1])
        else:
            # mês da venda se ela está no snapshot do mês da tela; senão todos (mês desconhecido)
            achou = inc.localizar(await run_in_threadpool(inc.linhas_guardadas, mes_d), transacao)
            meses = [mes_d if achou else None]
        try:
            for m in meses:
                await run_in_threadpool(snap.marcar_desatualizado, m)
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
    gestor = ac.pode(acesso.nivel, "ver_time")
    fila = await run_in_threadpool(lambda: com.ler_fila(vendedor_codigo=acesso.vendedor_codigo, gestor=gestor))
    conflitos = {}
    if gestor:
        pedidos = [l.transacao for l in res.linhas if l.papel == "venda" and l.motivo == "conflito_codigo"]
        conflitos = await run_in_threadpool(com.ler_codigos_conflito, pedidos)
    achadas, erro_busca, tel = [], None, ""
    if not gestor and (q or "").strip():
        try:
            tel = inc.limpar_telefone(q)
        except inc.EntradaInvalida as exc:
            erro_busca = str(exc)
        else:
            achadas = await run_in_threadpool(_buscar_telefone, tel, res, hoje)
    view = inc.view_inconsistencias(res, periodo, acesso, fila, conflitos, q, achadas)
    view["telefone_busca"] = tel
    view["telefone_rotulo"] = inc.formatar_telefone(tel)
    view["msg_ok"] = inc.MENSAGENS_OK.get(ok or "")
    view["msg_erro"] = erro_busca or inc.MENSAGENS_ERRO.get(erro or "")
    return await _pagina(request, "comercial_inconsistencias", "Comercial · Inconsistências",
                         "comercial_inconsistencias.html", view, hoje)


def _buscar_telefone(tel: str, res, hoje):
    """Vendas sem código do telefone no mês atual e no anterior (abertos). O mês atual vem do
    que a tela já carregou; o anterior, do snapshot guardado (sem recalcular no request)."""
    inc, com = _inc(), _com()
    meses = inc.meses_da_busca(hoje, com.meses_fechados())
    meses_linhas = []
    for m in meses:
        ls = res.linhas if res.mes == m else inc.linhas_guardadas(m)
        if ls:
            meses_linhas.append((m, ls))
    return inc.buscar_por_telefone(tel, meses_linhas, com.transacoes_do_telefone)


@router.post("/comercial/reivindicar")
async def comercial_reivindicar(request: Request, transacao: str = Form(""), vendedor_codigo: str = Form(""),
                                mes: str = Form(""), conexao: str = Form(""), telefone: str = Form(""),
                                justificativa: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        cx = inc.limpar_conexao(conexao)
        tel = inc.limpar_telefone(telefone)
        just = inc.texto_obrigatorio(justificativa, "Justificativa")
        codigo = inc.codigo_do_pedido(acesso, vendedor_codigo)
        mes_venda = inc.mes_obrigatorio(mes, _hoje())  # Ruling 14: sem mês válido -> 400
        inc.exigir_venda_de_mes_aberto(t)  # Ruling 17
        linha = inc.linha_da_venda(mes_venda, t)
        conflito = None
        if linha is not None and linha.motivo == "conflito_codigo":
            conflito = com.ler_codigos_conflito([t]).get(t)
        inc.conferir_reivindicacao(linha, codigo, conflito)
        com.reivindicar(t, inc.plataforma_de(t), codigo, email, conexao=cx, telefone=tel,
                        justificativa=just)
        return "reivindicada", t, False  # pendente não muda o cálculo: não invalida o mês
    return await _acao(request, "reivindicar", mes, executar)


@router.post("/comercial/atribuicoes/aprovar")
async def comercial_aprovar(request: Request, transacao: str = Form(""), mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        inc.exigir_venda_de_mes_aberto(t)  # Ruling 17: aprovar = atribuir
        com.decidir_atribuicao(t, inc.plataforma_de(t), True, email)
        return "aprovada", t, True
    return await _acao(request, "aprovar", mes, executar)


@router.post("/comercial/atribuicoes/recusar")
async def comercial_recusar(request: Request, transacao: str = Form(""), motivo: str = Form(""),
                            mes: str = Form("")):
    def executar(acesso, email, mes_d):
        inc, com = _inc(), _com()
        t = inc.limpar_transacao(transacao)
        m = (motivo or "").strip()[:inc.MAX_TEXTO] or None  # 👎 basta; o motivo é opcional
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
        inc.exigir_venda_de_mes_aberto(t)  # Ruling 17
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
        # Ruling 19a: venda de mês fechado aceita a decisão; o "tira" vira estorno no primeiro
        # mês aberto depois -> invalida os meses seguintes ao fechado
        fechado = inc.exigir_venda_de_mes_aberto(t, reembolso=True)
        com.decidir_reembolso(t, inc.plataforma_de(t), decisao, j, email)
        if fechado is not None:
            from frontend.services.comercial import fechamento as fech  # noqa: PLC0415
            return "reembolso", t, ("meses", fech.meses_seguintes(fechado, _hoje()))
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
        inc.exigir_venda_de_mes_aberto(t)  # Ruling 17
        com.gravar_ajuste(t, inc.plataforma_de(t), p, b, j, email)
        return "ajuste", t, True
    return await _acao(request, "aprovar", mes, executar)


# ── Área Comercial: Regras e vendedores + bônus (Task 7a) ─────────────────────
# Só gestor. Cada POST: nível checado aqui, entrada validada no serviço (400), escrita exata +
# histórico na mesma transação, 303 de volta com código de mensagem. O que muda o cálculo marca
# o snapshot dos meses afetados como desatualizado DEPOIS do commit; meta e bônus não mudam
# linha nenhuma (são lidos na hora da tela) e não invalidam nada.
_URL_REGRAS = "/comercial/regras"


def _rt():
    from frontend.services.comercial import regras_tela  # noqa: PLC0415
    return regras_tela


def _destino(base: str, ancora: str = "", **qs) -> str:
    from urllib.parse import urlencode  # noqa: PLC0415
    params = {k: v for k, v in qs.items() if v}
    return base + ("?" + urlencode(params) if params else "") + (f"#{ancora}" if ancora else "")


async def _acao_cadastro(request: Request, permissao: str, executar, *, base: str = _URL_REGRAS,
                         ancora: str = "", qs: dict | None = None):
    """`executar(acesso, email)` -> (código ok, meses a invalidar). Meses: False = nada,
    None = todos, lista = esses."""
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None or not ac.pode(acesso.nivel, permissao):
        return resposta_403()
    email = (_get_current_user(request).get("email") or "").strip().lower()
    if not email:
        return resposta_403()  # toda escrita precisa de autor no histórico
    rt, com = _rt(), _com()
    qs = qs or {}
    try:
        ok, invalidar = await run_in_threadpool(executar, acesso, email)
    except rt.EntradaInvalida as exc:
        return resposta_400(str(exc), "Pedido inválido", _destino(base, ancora, **qs), "← Voltar")
    except com.EscritaRecusada as exc:
        return RedirectResponse(_destino(base, ancora, **qs, erro=exc.codigo), status_code=303)
    if invalidar is not False:
        try:
            for m in ([None] if invalidar is None else invalidar):
                await run_in_threadpool(snap.marcar_desatualizado, m)
        except Exception:  # noqa: BLE001 — a escrita já foi; avisa para recalcular à mão
            import logging  # noqa: PLC0415
            logging.getLogger("comercial.regras").exception("marcar_desatualizado")
            return RedirectResponse(_destino(base, ancora, **qs, ok=ok, erro="nao_invalidou"), status_code=303)
    return RedirectResponse(_destino(base, ancora, **qs, ok=ok), status_code=303)


@router.get("/comercial/regras", response_class=HTMLResponse)
async def comercial_regras(request: Request, mes_meta: str | None = None, q_base: str | None = None,
                           q_oferta: str | None = None, ok: str | None = None, erro: str | None = None):
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None or not ac.pode(acesso.nivel, "editar_regras"):
        return resposta_403()
    rt, com = _rt(), _com()
    hoje = _hoje()
    try:
        m = rt.mes(mes_meta, hoje, ate_proximo=True, escrita=False)
    except rt.EntradaInvalida as exc:
        return resposta_400(str(exc), "Pedido inválido", _URL_REGRAS, "← Voltar para Regras")
    dados = await run_in_threadpool(com.ler_tela_regras, m)
    view = rt.view_regras(dados, hoje, m, q_base, q_oferta)
    view["msg_ok"] = rt.MENSAGENS_OK.get(ok or "")
    view["msg_erro"] = rt.MENSAGENS_ERRO.get(erro or "")
    view["meu_email"] = (_get_current_user(request).get("email") or "").strip().lower()
    launches = await run_in_threadpool(get_launches)
    ctx = _base_ctx(request, "comercial_regras", "Comercial · Regras e vendedores", None, launches, v=view)
    return templates.TemplateResponse("comercial_regras.html", ctx)


@router.post("/comercial/regras/vendedores")
async def comercial_regras_vendedores(request: Request, acao: str = Form(""), codigo: str = Form(""),
                                      nome: str = Form("")):
    def executar(acesso, email):
        rt, com = _rt(), _com()
        c = rt.limpar_codigo(codigo)
        if acao == "criar":
            com.criar_vendedor(c, rt.texto(nome, "Nome"), email)
            return "vendedor_criado", None  # código já visto nas vendas troca "Vendedor N" pelo nome
        if acao == "renomear":
            com.renomear_vendedor(c, rt.texto(nome, "Nome"), email)
            return "vendedor_renomeado", None  # o nome vai gravado nas linhas do snapshot
        if acao in ("ativar", "desativar"):
            com.definir_vendedor_ativo(c, acao == "ativar", email)
            return "vendedor_ativo", False  # "ativo" não entra no cálculo
        raise rt.EntradaInvalida("Ação inválida.")
    return await _acao_cadastro(request, "editar_regras", executar, ancora="vendedores")


@router.post("/comercial/regras/acessos")
async def comercial_regras_acessos(request: Request, acao: str = Form(""), email: str = Form(""),
                                   nivel: str = Form(""), vendedor_codigo: str = Form("")):
    def executar(acesso, autor):
        from frontend.services.comercial import acesso as ac  # noqa: PLC0415
        rt, com = _rt(), _com()
        alvo = rt.email(email)
        if acao == "remover":
            rt.conferir_acesso_proprio(alvo, autor, None)
            com.remover_acesso(alvo, autor)
            ac.limpar_cache()
            return "acesso_removido", False
        if acao == "gravar":
            n = rt.escolha(nivel, rt.NIVEIS, "Nível")
            rt.conferir_acesso_proprio(alvo, autor, n)
            cod = rt.limpar_codigo(vendedor_codigo) if n == "vendedor" else None
            com.gravar_acesso(alvo, n, cod, autor)
            ac.limpar_cache()
            return "acesso_gravado", False
        raise rt.EntradaInvalida("Ação inválida.")
    return await _acao_cadastro(request, "editar_regras", executar, ancora="acessos")


@router.post("/comercial/regras/percentuais")
async def comercial_regras_percentuais(request: Request, acao: str = Form(""), id: str = Form(""),
                                       pct: str = Form(""), vigente_de: str = Form(""),
                                       plataforma: str = Form(""), modalidade: str = Form(""),
                                       tipo: str = Form(""), vendedor_codigo: str = Form(""),
                                       categorias: list[str] = Form([]), forca_tipo: str = Form("")):
    def executar(acesso, email):
        rt, com = _rt(), _com()
        hoje = _hoje()
        de = rt.data_inicio(vigente_de, hoje, rt.proximo_mes(hoje) if acao == "encerrar" else None)
        if acao == "versao":
            com.nova_versao_regra(_id(id), rt.pct(pct), de, email)
            return "regra_versionada", rt.meses_desde(de, hoje)
        if acao == "encerrar":
            com.encerrar_regra(_id(id), de, email)
            return "regra_encerrada", rt.meses_desde(de, hoje)
        if acao == "nova":
            t = rt.escolha(tipo, rt.TIPOS, "Tipo")
            com.nova_regra(rt.escolha(plataforma, rt.PLATAFORMAS, "Plataforma"),
                           rt.escolha(modalidade, rt.MODALIDADES, "Modalidade"), t, rt.pct(pct),
                           rt.codigo_opcional(vendedor_codigo),
                           rt.categorias(categorias, _categorias_conhecidas()) if categorias else None,
                           rt.forca_tipo(forca_tipo, t), de, email)
            return "regra_criada", rt.meses_desde(de, hoje)
        raise rt.EntradaInvalida("Ação inválida.")
    return await _acao_cadastro(request, "editar_regras", executar, ancora="percentuais")


def _id(txt: str) -> int:
    t = (txt or "").strip()
    if not t.isdigit() or len(t) > 9:
        raise _rt().EntradaInvalida("Registro inválido.")
    return int(t)


def _categorias_conhecidas() -> set[str]:
    from frontend.services.comercial.tabelas import BASE_TMB_POR_CATEGORIA  # noqa: PLC0415
    return set(_com().ler_categorias()) | set(BASE_TMB_POR_CATEGORIA)


@router.post("/comercial/regras/participacoes")
async def comercial_regras_participacoes(request: Request, acao: str = Form(""), id: str = Form(""),
                                         pct_ativa: str = Form(""), pct_reativa: str = Form(""),
                                         vigente_de: str = Form(""), beneficiario: str = Form(""),
                                         beneficiario_codigo: str = Form("")):
    def executar(acesso, email):
        rt, com = _rt(), _com()
        hoje = _hoje()
        de = rt.data_inicio(vigente_de, hoje, rt.proximo_mes(hoje) if acao == "encerrar" else None)
        if acao == "versao":
            com.nova_versao_participacao(_id(id), rt.pct(pct_ativa, "% sobre Ativa"),
                                         rt.pct(pct_reativa, "% sobre Reativa"), de, email)
            return "part_versionada", rt.meses_desde(de, hoje)
        if acao == "encerrar":
            com.encerrar_participacao(_id(id), de, email)
            return "part_encerrada", rt.meses_desde(de, hoje)
        if acao == "nova":
            com.nova_participacao(rt.texto(beneficiario, "Beneficiário"), rt.codigo_opcional(beneficiario_codigo),
                                  rt.pct(pct_ativa, "% sobre Ativa"), rt.pct(pct_reativa, "% sobre Reativa"),
                                  de, email)
            return "part_criada", rt.meses_desde(de, hoje)
        raise rt.EntradaInvalida("Ação inválida.")
    return await _acao_cadastro(request, "editar_participacoes", executar, ancora="participacoes")


@router.post("/comercial/regras/bases")
async def comercial_regras_bases(request: Request, acao: str = Form(""), id: str = Form(""),
                                 valor_base: str = Form(""), categoria: str = Form(""),
                                 vigente_de: str = Form(""), plataforma: str = Form(""),
                                 valor_cobrado: str = Form(""), q_base: str = Form("")):
    def executar(acesso, email):
        rt, com = _rt(), _com()
        hoje = _hoje()
        de = rt.data_inicio(vigente_de, hoje)
        cat = rt.texto(categoria, "Categoria")
        if acao == "versao":
            com.nova_versao_base(_id(id), rt.reais(valor_base, "Valor-base"), cat, de, email)
            return "base_versionada", rt.meses_desde(de, hoje)
        if acao == "nova":
            com.nova_base(rt.escolha(plataforma, rt.PLATAFORMAS, "Plataforma"),
                          rt.reais(valor_cobrado, "Valor cobrado"), rt.reais(valor_base, "Valor-base"),
                          cat, de, email)
            return "base_criada", rt.meses_desde(de, hoje)
        raise rt.EntradaInvalida("Ação inválida.")
    return await _acao_cadastro(request, "editar_regras", executar, ancora="valores-base",
                                qs={"q_base": (q_base or "").strip()[:64]})


@router.post("/comercial/regras/ofertas")
async def comercial_regras_ofertas(request: Request, codigo_do_preco: str = Form(""), nome: str = Form(""),
                                   q_oferta: str = Form("")):
    def executar(acesso, email):
        rt, com = _rt(), _com()
        com.gravar_oferta(rt.preco(codigo_do_preco), rt.texto(nome, "Nome da oferta", 200), email)
        return "oferta_gravada", None  # o nome traz o código AT: vendas de qualquer mês
    return await _acao_cadastro(request, "editar_regras", executar, ancora="ofertas",
                                qs={"q_oferta": (q_oferta or "").strip()[:64]})


@router.post("/comercial/regras/janelas")
async def comercial_regras_janelas(request: Request, acao: str = Form(""), lancamento: str = Form(""),
                                   inicio: str = Form(""), fim: str = Form("")):
    def executar(acesso, email):
        rt, com = _rt(), _com()
        lanc = rt.lancamento(lancamento, com.ler_lancamentos())
        automatica = com.janela_automatica(lanc)
        manual = com.ler_janelas_manuais().get(lanc)
        if acao == "gravar":
            ini, fi = rt.janela(inicio, fim)
            # Ruling 17: nenhum mês tocado pela janela que sai nem pela que entra pode estar fechado
            rt.recusar_se_fechado(*rt.meses_da_janela(manual or automatica, (ini, fi)))
            # a janela substituída é a manual anterior; na 1ª manual, a automática do launch_config
            antes = com.gravar_janela(lanc, ini, fi, email)
            return "janela_gravada", rt.meses_da_janela(antes or automatica, (ini, fi))
        if acao == "remover":
            rt.recusar_se_fechado(*rt.meses_da_janela(manual, automatica))
            antes = com.remover_janela(lanc, email)
            return "janela_removida", None  # a janela automática pode cair em outro mês
        raise rt.EntradaInvalida("Ação inválida.")
    return await _acao_cadastro(request, "editar_regras", executar, ancora="janelas")


@router.post("/comercial/regras/metas")
async def comercial_regras_metas(request: Request, vendedor_codigo: str = Form(""), mes: str = Form(""),
                                 valor: str = Form("")):
    m_txt = (mes or "").strip()[:7]

    def executar(acesso, email):
        rt, com = _rt(), _com()
        m = rt.mes(mes, _hoje(), ate_proximo=True)
        com.gravar_meta(rt.limpar_codigo(vendedor_codigo), m, rt.reais(valor, "Meta", zero=True), email)
        return "meta_gravada", False  # meta é lida na hora da tela
    return await _acao_cadastro(request, "editar_regras", executar, ancora="metas", qs={"mes_meta": m_txt})


@router.post("/comercial/bonus")
async def comercial_bonus(request: Request, vendedor_codigo: str = Form(""), mes: str = Form(""),
                          valor: str = Form(""), justificativa: str = Form(""), vendedor: str = Form("")):
    import re  # noqa: PLC0415
    m_txt = (mes or "").strip()[:7]
    filtro = (vendedor or "").strip().upper()
    filtro = filtro if re.fullmatch(r"AT\d{1,4}", filtro) else ""  # volta para o mesmo filtro da tela

    def executar(acesso, email):
        rt, com = _rt(), _com()
        m = rt.mes(mes, _hoje())
        com.gravar_bonus(rt.limpar_codigo(vendedor_codigo), m, rt.reais(valor, "Bônus", zero=True),
                         rt.texto_opcional(justificativa, "Justificativa"), email)
        return "bonus_gravado", False  # bônus é lido na hora da tela
    return await _acao_cadastro(request, "lancar_bonus", executar, base="/comercial/comissoes",
                                qs={"mes": m_txt, "vendedor": filtro})


# ── Área Comercial: fechar / reabrir o mês (Task 7b, Ruling 17) ──────────────────
# Só master/coordenador (pode "fechar_mes"). Fechar recalcula o mês do zero (~20 s, em
# threadpool) e congela linhas + bônus + totais; reabrir exige motivo. Depois do commit, os meses
# seguintes são marcados desatualizados (o estorno deles depende do estado deste mês).
def _url_comissoes(mes_txt: str, **qs) -> str:
    return _destino("/comercial/comissoes", "", mes=mes_txt, **qs)


async def _acao_fechamento(request: Request, mes: str, executar):
    """`executar(email, mes_date, hoje)` -> (código ok, meses a invalidar: None = todos)."""
    from frontend.services.comercial import acesso as ac  # noqa: PLC0415
    from frontend.services.comercial import fechamento as fech  # noqa: PLC0415
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    acesso = await _acesso(request)
    if acesso is None or not ac.pode(acesso.nivel, "fechar_mes"):
        return resposta_403()
    email = (_get_current_user(request).get("email") or "").strip().lower()
    if not email:
        return resposta_403()
    t, rt, com = _telas(), _rt(), _com()
    hoje = _hoje()
    try:
        periodo = t.resolver_periodo(mes, None, None, hoje)
        if not (mes or "").strip():
            raise t.PeriodoInvalido("Informe o mês.")
    except t.PeriodoInvalido as exc:
        return resposta_400(str(exc), "Pedido inválido", "/comercial/comissoes", "← Voltar para Comissões")
    m_txt = f"{periodo.mes:%Y-%m}"
    try:
        ok, invalidar = await run_in_threadpool(executar, email, periodo.mes, hoje)
    except rt.EntradaInvalida as exc:
        return resposta_400(str(exc), "Pedido inválido", _url_comissoes(m_txt), "← Voltar para Comissões")
    except fech.AVerificar as exc:
        return RedirectResponse(_url_comissoes(m_txt, erro="tem_a_verificar", qtd=str(exc.qtd)), status_code=303)
    except com.EscritaRecusada as exc:
        return RedirectResponse(_url_comissoes(m_txt, erro=exc.codigo), status_code=303)
    try:
        for m in ([None] if invalidar is None else invalidar):
            await run_in_threadpool(snap.marcar_desatualizado, m)
    except Exception:  # noqa: BLE001 — a escrita já foi; avisa para recalcular à mão
        import logging  # noqa: PLC0415
        logging.getLogger("comercial.fechamento").exception("marcar_desatualizado")
        return RedirectResponse(_url_comissoes(m_txt, ok=ok, erro="nao_invalidou"), status_code=303)
    return RedirectResponse(_url_comissoes(m_txt, ok=ok), status_code=303)


@router.post("/comercial/fechar-mes")
async def comercial_fechar_mes(request: Request, mes: str = Form("")):
    def executar(email, m, hoje):
        from frontend.services.comercial import fechamento as fech  # noqa: PLC0415
        from frontend.services.comercial.snapshot import agora_sp  # noqa: PLC0415
        agora = agora_sp()
        fech.fechar(m, email, agora if agora.date() == hoje else _meio_dia(hoje))
        return "mes_fechado_ok", fech.meses_seguintes(m, hoje)
    return await _acao_fechamento(request, mes, executar)


@router.post("/comercial/reabrir-mes")
async def comercial_reabrir_mes(request: Request, mes: str = Form(""), motivo: str = Form("")):
    def executar(email, m, hoje):
        from frontend.services.comercial import fechamento as fech  # noqa: PLC0415
        rt, com = _rt(), _com()
        com.reabrir_mes(m, rt.texto(motivo, "Motivo da reabertura", rt.MAX_TEXTO), email)
        seguintes = fech.meses_seguintes(m, hoje)
        return "mes_reaberto", None if seguintes is None else [m, *seguintes]
    return await _acao_fechamento(request, mes, executar)


def _meio_dia(d):
    """`hoje` (date) simulado nos testes -> meio-dia daquele dia (hora real fora disso)."""
    from datetime import datetime  # noqa: PLC0415
    return datetime(d.year, d.month, d.day, 12)
