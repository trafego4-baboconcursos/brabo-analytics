from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    templates, logger, WORKSPACE_ROOT,
    get_launches, resolve_launch, find_previous_launch, _base_ctx,
    _fetch_all_data, _creative_overview, _v1_reports_for_launch,
    _get_cached, _set_cached,
    read_comparativo, get_drive_thumbnails,
    _fetch_prev_for_debriefing, _compute_debriefing_ctx,
    _sales_attribution,
)
from frontend.services.fetch import (
    _launch_cfg, _perfil_por_anuncio, _pesquisa_engajamento,
    _leads_antigos_compradores, _qualidade_regiao, _caminho_comprador,
    _landing_pages_por_etapa,
)
from frontend.services.calendario import build_calendario_ctx

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    cfg = await run_in_threadpool(_launch_cfg, launch.code) if launch else {}

    ctx = _base_ctx(request, "index", "Índice", launch, launches, cfg=cfg)
    return templates.TemplateResponse("index.html", ctx)


@router.get("/captacao", response_class=HTMLResponse)
async def captacao(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_daily=True)
    meta, google, vendas = d["meta"], d["google"], d["vendas"]
    daily_breakdown      = d["daily_breakdown"]
    daily_breakdown_preq = d.get("daily_breakdown_preq") or []
    wa_cost = d.get("wa_cost")
    wa_gasto = (wa_cost.get("total_cost_brl") or 0.0) if wa_cost else 0.0

    # ads_invest é só Meta+Google (captação de lead de verdade) — CPL/valor por
    # lead e a meta de investimento de captação NUNCA podem incluir WhatsApp,
    # que não gera lead nenhum. wa_gasto só entra no invest/ROAS (KPI de
    # investimento total da campanha, não de custo por lead).
    ads_invest = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0)
    receita = (vendas.total_receita if vendas else 0.0)
    invest  = ads_invest + wa_gasto
    roas    = receita / invest if invest > 0 else 0.0

    cfg = await run_in_threadpool(_launch_cfg, launch.code) if launch else {}
    goal_leads  = int(cfg.get("meta_leads") or 0)
    goal_invest = float(cfg.get("meta_investimento_captacao") or 0)
    leads_meta  = (meta.total_leads if meta else 0) + (int(round(google.total_conversoes)) if google else 0)
    prog_leads  = min(100.0, leads_meta / goal_leads * 100) if goal_leads > 0 else None
    valor_medio_lead = ads_invest / leads_meta if leads_meta > 0 else 0.0
    prog_invest = min(100.0, ads_invest / goal_invest * 100) if goal_invest > 0 else None

    ctx = _base_ctx(request, "captacao", "Captação", launch, launches,
        meta=meta, google=google, vendas=vendas, wa_gasto=wa_gasto,
        receita=receita, invest=invest, roas=roas,
        goal_leads=goal_leads, goal_invest=goal_invest,
        leads_meta=leads_meta, valor_medio_lead=valor_medio_lead,
        prog_leads=prog_leads, prog_invest=prog_invest,
        daily_breakdown=daily_breakdown,
        daily_breakdown_preq=daily_breakdown_preq,
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("dashboard.html", ctx)


@router.get("/pre-qualificacao", response_class=HTMLResponse)
async def pre_qualificacao(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_daily=True, needs_thumbnails=True)
    meta, google = d["meta"], d["google"]
    daily_breakdown_preq = d.get("daily_breakdown_preq") or []
    meta_ads_preq = meta.preq_por_ad if meta else []
    youtube_ads_preq = google.preq_por_ad if google else []

    ctx = _base_ctx(request, "pre_qualificacao", "Pré-Qualificação", launch, launches,
        daily_breakdown_preq=daily_breakdown_preq,
        meta_ads_preq=meta_ads_preq,
        youtube_ads_preq=youtube_ads_preq,
        drive_thumbnails=d.get("drive_thumbnails") or {},
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("pre_qualificacao.html", ctx)


@router.get("/funil", response_class=HTMLResponse)
async def funil_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_thumbnails=True, needs_sales_attr=True)
    meta, google, vendas, leads, sales_attr, typeform_count, drive_thumbnails = (
        d["meta"], d["google"], d["vendas"], d["leads"], d["sales_attr"], d["typeform_count"], d["drive_thumbnails"]
    )

    wa_cost = d.get("wa_cost")
    wa_gasto = (wa_cost.get("total_cost_brl") or 0.0) if wa_cost else 0.0

    receita = (vendas.total_receita if vendas else 0.0)
    invest  = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0) + wa_gasto
    roas    = receita / invest if invest > 0 else 0.0

    ctx = _base_ctx(request, "funil", "Funil Completo", launch, launches,
        meta=meta, google=google, vendas=vendas, leads=leads, wa_gasto=wa_gasto,
        sales_attr=sales_attr,
        typeform_count=typeform_count,
        receita=receita, invest=invest, roas=roas,
        drive_thumbnails=drive_thumbnails,
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("funil.html", ctx)


@router.get("/insights", response_class=HTMLResponse)
async def insights_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_thumbnails=True, needs_sales_attr=True)
    meta, google, vendas, leads, sales_attr, typeform_count, drive_thumbnails = (
        d["meta"], d["google"], d["vendas"], d["leads"], d["sales_attr"], d["typeform_count"], d["drive_thumbnails"]
    )
    creative_overview = None
    creative_overview_error = False
    try:
        creative_overview = await run_in_threadpool(
            _creative_overview, meta, google, vendas, sales_attr,
            launch_code=launch.code if launch else ""
        )
    except Exception:
        logger.exception("Insights: falha ao montar creative overview")
        creative_overview_error = True
    wa_cost = d.get("wa_cost")
    wa_gasto = (wa_cost.get("total_cost_brl") or 0.0) if wa_cost else 0.0
    receita = vendas.total_receita if vendas else 0.0
    invest  = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0) + wa_gasto
    roas    = receita / invest if invest > 0 else 0.0
    if creative_overview and leads:
        creative_overview["resumo"]["total_leads"] = leads.total_leads
    ctx = _base_ctx(request, "insights", "Insights", launch, launches,
        meta=meta, google=google, vendas=vendas, leads=leads, sales_attr=sales_attr, wa_gasto=wa_gasto,
        insights_data=creative_overview, creative_overview_error=creative_overview_error,
        typeform_count=typeform_count,
        receita=receita, invest=invest, roas=roas,
        drive_thumbnails=drive_thumbnails,
        data_errors=d.get("_errors", []))
    return templates.TemplateResponse("insights.html", ctx)


def _load_calendario_assets() -> tuple[str, str]:
    """Lê o CSS e o <script> do arquivo estático original (design system e
    lógica de hoje/status/sync entre tabelas) — reaproveitados como estão;
    só o conteúdo das tabelas passa a ser gerado dinamicamente a partir do
    launch_config de cada lançamento (ver build_calendario_ctx)."""
    from bs4 import BeautifulSoup
    cal_html_path = WORKSPACE_ROOT / "frontend" / "static" / "calendario" / "SISTEMA_CALENDARIO_2026.html"
    try:
        soup = BeautifulSoup(cal_html_path.read_text(encoding="utf-8"), "html.parser")
        cal_styles = "\n".join(
            str(s) for s in soup.find_all("style")
            if s.get("id") not in ("brabo-ds-style", "brabo-accent")
        )
        main = soup.find("main", id="bs-main")
        scripts = main.find_all("script") if main else []
        cal_script = str(scripts[-1]) if scripts else ""
        return cal_styles, cal_script
    except Exception:
        logger.exception("Falha ao carregar assets do calendário")
        return "", ""


@router.get("/calendario", response_class=HTMLResponse)
async def calendario_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch   = resolve_launch(launch_code, launches)
    cal_styles, cal_script = await run_in_threadpool(_load_calendario_assets)
    cal = await run_in_threadpool(build_calendario_ctx, launches, _launch_cfg)

    ctx = _base_ctx(request, "calendario", "Calendário", launch, launches,
                    cal_styles=cal_styles, cal_script=cal_script, cal=cal)
    return templates.TemplateResponse("calendario.html", ctx)


@router.get("/lancamentos", response_class=HTMLResponse)
async def lancamentos_page(request: Request, launch_code: str | None = None):
    from frontend.services.fetch import _meta, _google, _vendas  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch   = resolve_launch(launch_code, launches)

    def _summary(l):
        try:
            m = _meta(l) if l.has_meta else None
            g = _google(l) if l.has_google else None
            v = _vendas(l) if l.has_vendas else None
            leads  = (m.total_leads if m else 0) + (int(round(g.total_conversoes)) if g else 0)
            invest = (m.total_gasto if m else 0.0) + (g.total_custo if g else 0.0)
            receita = v.total_receita if v else 0.0
            return {
                "leads": leads, "invest": invest, "receita": receita,
                "roas": receita / invest if invest > 0 else 0.0,
            }
        except Exception:
            logger.exception("Lançamentos: falha ao resumir %s", l.code)
            return {"leads": 0, "invest": 0.0, "receita": 0.0, "roas": 0.0}

    ctx = _base_ctx(request, "lancamentos", "Lançamentos", launch, launches)
    summaries = await asyncio.gather(*[
        run_in_threadpool(_summary, l) for l in ctx["launches"]
    ])
    summary_by_code = {l.code: s for l, s in zip(ctx["launches"], summaries)}
    ctx["summary_by_code"] = summary_by_code

    return templates.TemplateResponse("lancamentos.html", ctx)


@router.get("/comparativo", response_class=HTMLResponse)
def comparativo_page(request: Request, launch_code: str | None = None):
    try:
        launches = get_launches()
        launch = resolve_launch(launch_code, launches)
        previous = find_previous_launch(launch, launches) if launch else None
        previous2 = find_previous_launch(previous, launches) if previous else None

        comp_data = None
        comp_error = None
        if launch and previous:
            try:
                cache_key = f"{previous.code}_{launch.code}_{previous2.code if previous2 else 'none'}"
                comp_data = _get_cached(cache_key, "comparativo")
                if comp_data is None:
                    comp_data = read_comparativo(launch, previous, previous2)
                    _set_cached(cache_key, "comparativo", comp_data)
            except Exception as exc:
                logger.exception("Erro ao montar dados comparativos")
                comp_error = "Não foi possível carregar os dados comparativos. Tente novamente."

        drive_thumbnails: dict = {}
        if launch:
            try:
                drive_thumbnails = get_drive_thumbnails(launch.code) or {}
            except Exception:
                logger.debug("Thumbnails indisponíveis para comparativo")

        ctx = _base_ctx(
            request, "comparativo", "Comparativo", launch, launches,
            comp=comp_data,
            comp_error=comp_error,
            previous_launch=previous,
            drive_thumbnails=drive_thumbnails,
        )
        return templates.TemplateResponse("comparativo.html", ctx)
    except Exception as exc:
        import html
        msg = html.escape(f"{type(exc).__name__}: {exc}")
        body = (
            "<html><body style='font-family:Arial,sans-serif;padding:24px'>"
            "<h2>Falha ao abrir /comparativo</h2>"
            "<p>O erro aconteceu durante a montagem ou renderização da página.</p>"
            f"<pre style='white-space:pre-wrap;background:#f6f8fa;padding:12px;border:1px solid #d0d7de;border-radius:8px'>{msg}</pre>"
            "</body></html>"
        )
        return HTMLResponse(body, status_code=500)


@router.get("/comparativo-v1-v2", response_class=HTMLResponse)
async def comparativo_v1_v2(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch)
    meta, google, vendas, leads = d["meta"], d["google"], d["vendas"], d["leads"]

    wa_cost = d.get("wa_cost")
    wa_gasto = (wa_cost.get("total_cost_brl") or 0.0) if wa_cost else 0.0
    receita = vendas.total_receita if vendas else 0.0
    invest = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0) + wa_gasto
    roas = receita / invest if invest > 0 else 0.0

    data_status = [
        {"label": "Meta Ads", "available": bool(launch and launch.has_meta), "detail": f"{meta.total_leads if meta else 0} leads" if meta else "CSV ausente"},
        {"label": "Google Ads", "available": bool(launch and launch.has_google), "detail": f"{google.total_conversoes:.0f} conversoes" if google else "CSV ausente"},
        {"label": "Vendas", "available": bool(launch and launch.has_vendas), "detail": f"{vendas.total_vendas if vendas else 0} vendas" if vendas else "CSV ausente"},
        {"label": "Active Campaign", "available": bool(launch and launch.has_ac), "detail": f"{leads.total_leads if leads else 0} leads AC" if leads else "CSV ausente"},
        {"label": "Pesquisas", "available": bool(launch and launch.has_typeform), "detail": "Pasta com CSV detectada" if launch and launch.has_typeform else "CSV ausente"},
    ]

    ctx = _base_ctx(
        request,
        "comparativo-v1-v2",
        "Comparativo V1/V2",
        launch,
        launches,
        meta=meta,
        google=google,
        vendas=vendas,
        leads=leads,
        receita=receita,
        invest=invest,
        roas=roas,
        wa_gasto=wa_gasto,
        data_status=data_status,
        v1_reports=_v1_reports_for_launch(launch),
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("comparativo_v1_v2.html", ctx)


@router.get("/debriefing", response_class=HTMLResponse)
async def debriefing(request: Request, launch_code: str | None = None, modo: str | None = None):
    """``modo=slides`` renderiza o mesmo conteúdo em modo apresentação
    (um slide 1920x1080 por seção, pronto pra "Salvar como PDF" no Chrome);
    é o que o botão "Gerar PDF" da aba abre."""
    slides = modo == "slides"
    # Carregamento progressivo: fora do modo slides, as seções mais pesadas
    # (Typeform perfil/engajamento, qualidade por estado, caminho do comprador)
    # não entram nesta requisição — o template renderiza um esqueleto e o
    # navegador busca cada uma em /debriefing/secao/<nome> depois que a página
    # já apareceu. O PDF/slides precisa de tudo de uma vez, então lá é inline.
    lazy = not slides
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    previous = find_previous_launch(launch, launches) if launch else None

    d = await _fetch_all_data(launch, needs_daily=True, needs_hotmart=True, needs_tmb=True, needs_sales_attr=True, needs_youtube=True, needs_thumbnails=True) if launch else {}
    meta          = d.get("meta")
    google        = d.get("google")
    vendas        = d.get("vendas")
    sales_attr    = d.get("sales_attr")
    daily         = d.get("daily_breakdown") or []
    hotmart       = d.get("hotmart")
    tmb           = d.get("tmb")
    youtube_aulas = d.get("youtube_aulas") or []
    thumb         = d.get("drive_thumbnails") or {}

    data_errors = list(d.get("_errors", []))

    # Os blocos abaixo (creative overview, leads antigos, perfil/pesquisa,
    # qualidade por região, caminho do comprador, dados do lançamento
    # anterior) são independentes entre si — só dependem do que já foi
    # buscado acima — então rodam em paralelo via asyncio.gather em vez de
    # sequencialmente, o que era o principal gargalo de carregamento da página.

    async def f_creative():
        if not (launch and (meta or google)):
            return None, False
        try:
            data = await run_in_threadpool(
                _creative_overview, meta, google, vendas, sales_attr,
                launch_code=launch.code if launch else "",
            )
            return data, False
        except Exception:
            logger.exception("Debriefing: falha ao montar creative overview")
            return None, True

    async def f_leads_antigos():
        if not (launch and vendas):
            return None
        try:
            return await run_in_threadpool(_leads_antigos_compradores, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao classificar leads antigos × novos")
            return None

    async def f_perfil_pesquisa():
        if not launch or lazy:
            return None, None
        try:
            return await asyncio.gather(
                run_in_threadpool(_perfil_por_anuncio, launch),
                run_in_threadpool(_pesquisa_engajamento, launch),
            )
        except Exception:
            logger.exception("Debriefing: falha ao montar perfil do lead por anúncio")
            return None, None

    async def f_qualidade_regiao():
        if not launch or lazy:
            return None
        try:
            return await run_in_threadpool(_qualidade_regiao, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar qualidade por regiao")
            return None

    async def f_caminho_comprador():
        if not (launch and vendas) or lazy:
            return None
        try:
            return await run_in_threadpool(_caminho_comprador, launch, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar caminho do comprador")
            return None

    async def f_landing_pages():
        if not launch:
            return None
        try:
            return await run_in_threadpool(_landing_pages_por_etapa, launch)
        except Exception:
            logger.exception("Debriefing: falha ao montar landing pages por etapa (GA4)")
            return None

    async def f_previous():
        if not previous:
            return None, None, None, None, None
        try:
            prev_d = await run_in_threadpool(_fetch_prev_for_debriefing, previous)
            p_meta    = prev_d.get("meta")
            p_google  = prev_d.get("google")
            p_vendas  = prev_d.get("vendas")
            p_wa_cost = prev_d.get("wa_cost")
            p_sales_attr = None
            if getattr(previous, "has_ac", False) and p_vendas:
                p_sales_attr = await run_in_threadpool(_sales_attribution, previous, p_vendas)
            return p_meta, p_google, p_vendas, p_wa_cost, p_sales_attr
        except Exception:
            logger.exception("Debriefing: falha ao buscar dados do lançamento anterior")
            return None, None, None, None, None

    (
        (creative_data, creative_data_error),
        leads_antigos,
        (perfil_por_anuncio, pesquisa_engajamento),
        qualidade_regiao,
        caminho_comprador,
        (prev_meta, prev_google, prev_vendas, prev_wa_cost, prev_sales_attr),
        landing_pages_por_etapa,
    ) = await asyncio.gather(
        f_creative(), f_leads_antigos(), f_perfil_pesquisa(),
        f_qualidade_regiao(), f_caminho_comprador(), f_previous(),
        f_landing_pages(),
    )

    dbf = _compute_debriefing_ctx(
        launch, previous,
        meta, google, vendas, sales_attr, daily, hotmart, creative_data,
        prev_meta, prev_google, prev_vendas,
        youtube_aulas=youtube_aulas,
        prev_sales_attr=prev_sales_attr,
        tmb=tmb,
        leads_antigos=leads_antigos,
        perfil_por_anuncio=perfil_por_anuncio,
        pesquisa_engajamento=pesquisa_engajamento,
        qualidade_regiao=qualidade_regiao,
        caminho_comprador=caminho_comprador,
        landing_pages_por_etapa=landing_pages_por_etapa,
        wa_cost=d.get("wa_cost"),
        prev_wa_cost=prev_wa_cost,
    )

    ctx = _base_ctx(request, "debriefing", "Debriefing", launch, launches,
                    dbf=dbf, drive_thumbnails=thumb,
                    data_errors=data_errors,
                    creative_data_error=creative_data_error,
                    slides=slides, lazy=lazy)
    return templates.TemplateResponse("debriefing.html", ctx)


_DEBRIEFING_SECOES_LAZY = ("pesquisa_engajamento", "qualidade_regiao", "perfil_por_anuncio", "caminho_comprador")


@router.get("/debriefing/secao/{secao}", response_class=HTMLResponse)
async def debriefing_secao(request: Request, secao: str, launch_code: str | None = None):
    """Fragmento HTML de uma seção pesada do debriefing, buscado pelo
    navegador depois que a página já carregou (ver `lazy` em debriefing()).
    Resposta vazia = sem dado pra esse lançamento (o JS remove a seção).
    Usa os mesmos leitores cacheados da página inteira, então na segunda
    visita dentro do TTL sai da memória."""
    if secao not in _DEBRIEFING_SECOES_LAZY:
        return Response("seção desconhecida", status_code=404, media_type="text/plain")
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    if not launch:
        return HTMLResponse("")

    dbf: dict = {}
    thumbs: dict = {}
    try:
        if secao == "pesquisa_engajamento":
            dbf[secao] = await run_in_threadpool(_pesquisa_engajamento, launch)
        elif secao == "qualidade_regiao":
            dbf[secao] = await run_in_threadpool(_qualidade_regiao, launch, None)
        elif secao == "caminho_comprador":
            cc = await run_in_threadpool(_caminho_comprador, launch, None)
            dbf[secao] = (cc or {}).get("resumo")
        elif secao == "perfil_por_anuncio":
            # A pesquisa só traz ad_code/leads/respostas; nome, investimento e
            # vendas vêm de Meta/Google/atribuição (todos cacheados, rápido).
            from frontend.services.debriefing import _enrich_perfil_por_anuncio  # noqa: PLC0415
            d, perfil = await asyncio.gather(
                _fetch_all_data(launch, needs_sales_attr=True, needs_thumbnails=True),
                run_in_threadpool(_perfil_por_anuncio, launch),
            )
            dbf[secao] = _enrich_perfil_por_anuncio(perfil, d.get("meta"), d.get("google"), d.get("sales_attr"))
            thumbs = d.get("drive_thumbnails") or {}
    except Exception:
        logger.exception("Debriefing: falha ao carregar seção %s", secao)
        return Response("falha ao carregar seção", status_code=500, media_type="text/plain")

    ctx = {"request": request, "dbf": dbf, "launch": launch, "drive_thumbnails": thumbs}
    return templates.TemplateResponse(f"debriefing/_secao_{secao}.html", ctx)


@router.get("/api/caminho-comprador.csv")
async def api_caminho_comprador_csv(launch_code: str | None = None):
    """Base unificada 'caminho do comprador' (uma linha por comprador) em CSV
    — pra rodar análise/IA em cima, conforme a pauta do debriefing."""
    import csv
    import io

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    if not launch:
        return Response("lancamento nao encontrado", status_code=404, media_type="text/plain")

    data = await run_in_threadpool(_caminho_comprador, launch, None)
    if not data or not data.get("rows"):
        return Response("sem dados", status_code=404, media_type="text/plain")

    buf = io.StringIO()
    cols = ["email", "nome", "estado", "ad_code", "plataforma", "data_cadastro",
            "grupo", "respondeu_pesquisa", "canal", "vendas", "receita"]
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for row in data["rows"]:
        writer.writerow(row)

    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="caminho_comprador_{launch.code}.csv"'},
    )
