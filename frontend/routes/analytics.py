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
from frontend.services.fetch import _launch_cfg

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

    receita = (vendas.total_receita if vendas else 0.0)
    invest  = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0)
    roas    = receita / invest if invest > 0 else 0.0

    cfg = await run_in_threadpool(_launch_cfg, launch.code) if launch else {}
    goal_leads  = int(cfg.get("meta_leads") or 0)
    goal_invest = float(cfg.get("meta_investimento_captacao") or 0)
    leads_meta  = (meta.total_leads if meta else 0) + (int(round(google.total_conversoes)) if google else 0)
    prog_leads  = min(100.0, leads_meta / goal_leads * 100) if goal_leads > 0 else None
    valor_medio_lead = invest / leads_meta if leads_meta > 0 else 0.0
    prog_invest = min(100.0, invest / goal_invest * 100) if goal_invest > 0 else None

    ctx = _base_ctx(request, "captacao", "Captação", launch, launches,
        meta=meta, google=google, vendas=vendas,
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
    d = await _fetch_all_data(launch, needs_daily=True)
    meta, google = d["meta"], d["google"]
    daily_breakdown_preq = d.get("daily_breakdown_preq") or []
    meta_ads_preq = meta.preq_por_ad if meta else []
    youtube_ads_preq = google.preq_por_ad if google else []

    ctx = _base_ctx(request, "pre_qualificacao", "Pré-Qualificação", launch, launches,
        daily_breakdown_preq=daily_breakdown_preq,
        meta_ads_preq=meta_ads_preq,
        youtube_ads_preq=youtube_ads_preq,
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

    receita = (vendas.total_receita if vendas else 0.0)
    invest  = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0)
    roas    = receita / invest if invest > 0 else 0.0

    ctx = _base_ctx(request, "funil", "Funil Completo", launch, launches,
        meta=meta, google=google, vendas=vendas, leads=leads,
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
    receita = vendas.total_receita if vendas else 0.0
    invest  = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0)
    roas    = receita / invest if invest > 0 else 0.0
    if creative_overview and leads:
        creative_overview["resumo"]["total_leads"] = leads.total_leads
    ctx = _base_ctx(request, "insights", "Insights", launch, launches,
        meta=meta, google=google, vendas=vendas, leads=leads, sales_attr=sales_attr,
        insights_data=creative_overview, creative_overview_error=creative_overview_error,
        typeform_count=typeform_count,
        receita=receita, invest=invest, roas=roas,
        drive_thumbnails=drive_thumbnails,
        data_errors=d.get("_errors", []))
    return templates.TemplateResponse("insights.html", ctx)


@router.get("/calendario", response_class=HTMLResponse)
async def calendario_page(request: Request, launch_code: str | None = None):
    from bs4 import BeautifulSoup
    launches = await run_in_threadpool(get_launches)
    launch   = resolve_launch(launch_code, launches)

    cal_html_path = WORKSPACE_ROOT / "frontend" / "static" / "calendario" / "SISTEMA_CALENDARIO_2026.html"
    try:
        soup = BeautifulSoup(cal_html_path.read_text(encoding="utf-8"), "html.parser")
        cal_styles = "\n".join(
            str(s) for s in soup.find_all("style")
            if s.get("id") != "brabo-ds-style"
        )
        main = soup.find("main", id="bs-main")
        cal_body = main.decode_contents() if main else ""
    except Exception:
        logger.exception("Falha ao carregar arquivo de calendário")
        cal_styles = ""
        cal_body = "<p>Arquivo de calendário não encontrado.</p>"

    ctx = _base_ctx(request, "calendario", "Calendário", launch, launches,
                    cal_styles=cal_styles, cal_body=cal_body)
    return templates.TemplateResponse("calendario.html", ctx)


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

    receita = vendas.total_receita if vendas else 0.0
    invest = (meta.total_gasto if meta else 0.0) + (google.total_custo if google else 0.0)
    roas = receita / invest if invest > 0 else 0.0

    data_status = [
        {"label": "Meta Ads", "available": bool(launch and launch.has_meta), "detail": f"{meta.total_leads if meta else 0} leads" if meta else "CSV ausente"},
        {"label": "Google Ads", "available": bool(launch and launch.has_google), "detail": f"{google.total_conversoes:.0f} conversoes" if google else "CSV ausente"},
        {"label": "Vendas", "available": bool(launch and launch.has_vendas), "detail": f"{vendas.total_vendas if vendas else 0} vendas" if vendas else "CSV ausente"},
        {"label": "Active Campaign", "available": bool(launch and launch.has_ac), "detail": f"{leads.total_leads if leads else 0} leads AC" if leads else "CSV ausente"},
        {"label": "Typeform", "available": bool(launch and launch.has_typeform), "detail": "Pasta com CSV detectada" if launch and launch.has_typeform else "CSV ausente"},
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
        data_status=data_status,
        v1_reports=_v1_reports_for_launch(launch),
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("comparativo_v1_v2.html", ctx)


@router.get("/debriefing", response_class=HTMLResponse)
async def debriefing(request: Request, launch_code: str | None = None):
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
    creative_data = None
    creative_data_error = False
    if launch and (meta or google):
        try:
            creative_data = await run_in_threadpool(
                _creative_overview, meta, google, vendas, sales_attr,
                launch_code=launch.code if launch else "",
            )
        except Exception:
            logger.exception("Debriefing: falha ao montar creative overview")
            creative_data_error = True

    leads_antigos = None
    if launch and vendas:
        try:
            from frontend.db_readers.leads import read_leads_antigos_compradores  # noqa: PLC0415
            leads_antigos = await run_in_threadpool(read_leads_antigos_compradores, launch.code, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao classificar leads antigos × novos")

    perfil_por_anuncio = None
    pesquisa_engajamento = None
    if launch:
        try:
            from frontend.db_readers.typeform import read_perfil_por_anuncio, read_pesquisa_engajamento  # noqa: PLC0415
            perfil_por_anuncio = await run_in_threadpool(read_perfil_por_anuncio, launch.code)
            pesquisa_engajamento = await run_in_threadpool(read_pesquisa_engajamento, launch.code)
        except Exception:
            logger.exception("Debriefing: falha ao montar perfil do lead por anúncio")

    dia1 = prev_dia1 = None
    qualidade_regiao = None
    if launch:
        try:
            from frontend.db_readers.sales import read_dia1_sales, read_qualidade_regiao  # noqa: PLC0415
            dia1 = await run_in_threadpool(read_dia1_sales, launch.code)
            if previous:
                prev_dia1 = await run_in_threadpool(read_dia1_sales, previous.code)
            qualidade_regiao = await run_in_threadpool(read_qualidade_regiao, launch.code, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar vendas hora a hora do dia 1 / qualidade por regiao")

    caminho_comprador = None
    if launch and vendas:
        try:
            from frontend.db_readers.caminho_comprador import read_caminho_comprador  # noqa: PLC0415
            caminho_comprador = await run_in_threadpool(read_caminho_comprador, launch.code, vendas)
        except Exception:
            logger.exception("Debriefing: falha ao montar caminho do comprador")

    prev_meta = prev_google = prev_vendas = None
    prev_sales_attr = None
    if previous:
        try:
            prev_d = await run_in_threadpool(_fetch_prev_for_debriefing, previous)
            prev_meta   = prev_d.get("meta")
            prev_google = prev_d.get("google")
            prev_vendas = prev_d.get("vendas")
            if getattr(previous, "has_ac", False) and prev_vendas:
                prev_sales_attr = await run_in_threadpool(_sales_attribution, previous, prev_vendas)
        except Exception:
            logger.exception("Debriefing: falha ao buscar dados do lançamento anterior")

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
        dia1=dia1,
        prev_dia1=prev_dia1,
        qualidade_regiao=qualidade_regiao,
        caminho_comprador=caminho_comprador,
    )

    ctx = _base_ctx(request, "debriefing", "Debriefing", launch, launches,
                    dbf=dbf, drive_thumbnails=thumb,
                    data_errors=data_errors,
                    creative_data_error=creative_data_error)
    return templates.TemplateResponse("debriefing.html", ctx)


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

    from frontend.db_readers.caminho_comprador import read_caminho_comprador  # noqa: PLC0415
    data = await run_in_threadpool(read_caminho_comprador, launch.code)
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
