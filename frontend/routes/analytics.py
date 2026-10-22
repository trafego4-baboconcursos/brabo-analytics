from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.concurrency import run_in_threadpool

from src.anos import ANO_COOKIE, do_ano
from src.constants import climas_ordem, etapa_prequali
from frontend.cache import force_refresh_end, force_refresh_start
from frontend.core import (
    templates, logger,
    get_launches, resolve_launch, find_previous_launch, _base_ctx,
    _fetch_all_data, _creative_overview, _v1_reports_for_launch,
    get_drive_thumbnails,
    _fetch_prev_for_debriefing, _compute_debriefing_ctx,
    _sales_attribution, read_comparativo_historico, read_historico_grande,
)
from frontend.services.fetch import (
    _launch_cfg, _perfil_por_anuncio, _pesquisa_engajamento,
    _leads_antigos_compradores, _qualidade_regiao, _caminho_comprador,
    _landing_pages_por_etapa, _leads_x_whatsapp, _vendas_grupos_whatsapp,
    _disparo_resumo, _conversao_pagina_captura, _utm_cobertura, _sorteio,
    _cadastrados_lancamentos_anteriores, comparativo_cached,
)
from frontend.db_readers.eventos import read_eventos, eventos_por_dia, CORES_TIPO
from frontend.services.calendario import build_calendario_ctx
from frontend.services.debriefing_build import build_debriefing_context
from frontend.services.orcamento import (
    get_etapa, previsto_por_etapa, previsto_por_subetapa, REMARKETING_SUBETAPAS,
    buckets_previsto_x_realizado, curva_diaria, com_realizado_diario,
    publico_por_dia, previsto_publico_por_dia, investimento_diario_etapa, etapa_cfg,
    com_percentuais, kpis_captacao_periodo_comparavel, combinar_previsto_realizado,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    cfg = await run_in_threadpool(_launch_cfg, launch.code) if launch else {}

    ctx = _base_ctx(request, "index", "Índice", launch, launches, cfg=cfg)
    return templates.TemplateResponse("index.html", ctx)


@router.get("/captacao", response_class=HTMLResponse)
async def captacao(request: Request, launch_code: str | None = None, trilha: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    # Black: ?trilha=base-forte|vitalicia abre a Captação de uma trilha só. Fora
    # da Black o parâmetro é ignorado.
    from src.constants import e_black  # noqa: PLC0415
    from src.nomenclatura import TRILHA_BASE_FORTE, TRILHA_VITALICIA  # noqa: PLC0415

    trilha_nome = None
    if launch and e_black(launch.code):
        trilha_nome = {"base-forte": TRILHA_BASE_FORTE, "vitalicia": TRILHA_VITALICIA}.get((trilha or "").lower())
    d = await _fetch_all_data(launch, needs_daily=True, needs_thumbnails=True)
    meta, google, vendas = d["meta"], d["google"], d["vendas"]
    daily_breakdown      = d["daily_breakdown"]
    daily_breakdown_preq = d.get("daily_breakdown_preq") or []
    wa_cost = d.get("wa_cost")
    wa_gasto = (wa_cost.get("total_cost_brl") or 0.0) if wa_cost else 0.0

    # Esta página é só Captação — investimento/leads têm que vir escopados
    # pela etapa (por_etapa["Captação"]), não pelo total do lançamento
    # inteiro (que também soma Pré-Qualificação/Remarketing/etc).
    meta_capt = (getattr(meta, "por_etapa", {}) or {}).get("Captação") or {}
    google_capt = (getattr(google, "por_etapa", {}) or {}).get("Captação") or {}
    meta_capt_gasto = float(meta_capt.get("gasto") or meta_capt.get("custo") or 0)
    google_capt_gasto = float(google_capt.get("custo") or 0)
    meta_capt_leads = int(meta_capt.get("leads") or 0)
    google_capt_conv = float(google_capt.get("conversoes") or 0)

    # ads_invest é só Meta+Google (captação de lead de verdade) — CPL/valor por
    # lead e a meta de investimento de captação NUNCA podem incluir WhatsApp,
    # que não gera lead nenhum. wa_gasto só entra no invest/ROAS (KPI de
    # investimento total da campanha, não de custo por lead).
    ads_invest = meta_capt_gasto + google_capt_gasto
    receita = (vendas.total_receita if vendas else 0.0)
    invest  = ads_invest + wa_gasto
    roas    = receita / invest if invest > 0 else 0.0

    # Trilha: investimento e leads saem só dela. Meta e verba do lançamento valem
    # para o conjunto, então não aparecem como progresso de uma trilha.
    leads_active_trilha = None
    if trilha_nome:
        mt = (getattr(meta, "por_trilha_captacao", {}) or {}).get(trilha_nome) or {}
        gt = (getattr(google, "por_trilha_captacao", {}) or {}).get(trilha_nome) or {}
        meta_capt_gasto = float(mt.get("gasto") or 0)
        google_capt_gasto = float(gt.get("custo") or 0)
        meta_capt_leads = int(mt.get("leads") or 0)
        google_capt_conv = float(gt.get("conversoes") or 0)
        wa_gasto = 0.0
        ads_invest = meta_capt_gasto + google_capt_gasto
        invest = ads_invest
        receita, roas = 0.0, 0.0
        try:
            from frontend.db_readers.leads import read_leads_por_trilha  # noqa: PLC0415
            leads_active_trilha = await run_in_threadpool(read_leads_por_trilha, launch.code, trilha_nome)
        except Exception:
            logger.exception("Captação: falha ao contar leads da trilha")

    cfg = await run_in_threadpool(_launch_cfg, launch.code) if launch else {}
    goal_leads  = int(cfg.get("meta_leads") or 0)
    goal_invest = float(cfg.get("meta_investimento_captacao") or 0)
    leads_meta  = meta_capt_leads + int(round(google_capt_conv))
    prog_leads  = min(100.0, leads_meta / goal_leads * 100) if goal_leads > 0 and not trilha_nome else None
    valor_medio_lead = ads_invest / leads_meta if leads_meta > 0 else 0.0
    prog_invest = min(100.0, ads_invest / goal_invest * 100) if goal_invest > 0 and not trilha_nome else None

    conversao_pagina_captura = None
    if launch:
        try:
            conversao_pagina_captura = await run_in_threadpool(_conversao_pagina_captura, launch)
        except Exception:
            logger.exception("Captação: falha ao montar conversão da página de captura (GA4)")

    # KPIs Principais x lançamento anterior, no mesmo período relativo
    # (mesma quantidade de dias decorridos desde o início da Captação).
    prev_kpis = None
    if launch:
        previous = find_previous_launch(launch, launches)
        if previous:
            try:
                prev_cfg = await run_in_threadpool(_launch_cfg, previous.code)
                prev_kpis = await run_in_threadpool(
                    kpis_captacao_periodo_comparavel, launch, previous, cfg, prev_cfg,
                )
            except Exception:
                logger.exception("Captação: falha ao montar comparativo com lançamento anterior")

    # % de Leads por Campanha — Facebook/YouTube por temperatura (só
    # Captação; a segmentação por temperatura não existe em Pré-Qualificação
    # neste sistema) + TikTok (sempre 0, sem fonte de dado ainda).
    # Na Black o vocabulário de público é outro (Aluno/Super Quente/Novo);
    # fixar Quente/Frio/Específico mostrava três linhas zeradas.
    _clima_labels = climas_ordem(launch.code if launch else None)
    meta_temp_capt = (getattr(meta, "por_temperatura_captacao", {}) or {})
    google_temp = (getattr(google, "por_temperatura", {}) or {})
    if trilha_nome:
        meta_temp_capt = (getattr(meta, "por_temperatura_por_trilha", {}) or {}).get(trilha_nome) or {}
        google_temp = (getattr(google, "por_temperatura_por_trilha", {}) or {}).get(trilha_nome) or {}
    leads_por_campanha_raw = []
    for c in _clima_labels:
        m = meta_temp_capt.get(c) or {}
        leads_por_campanha_raw.append({
            "campanha": f"Facebook {c}",
            "leads": int(m.get("leads") or 0),
            "gasto": float(m.get("gasto") or m.get("custo") or 0),
        })
    for c in _clima_labels:
        g = google_temp.get(c) or {}
        leads_por_campanha_raw.append({
            "campanha": f"YouTube {c}",
            "leads": int(round(g.get("conversoes") or 0)),
            "gasto": float(g.get("custo") or 0),
        })
    leads_por_campanha_raw.append({"campanha": "Tiktok", "leads": 0, "gasto": 0.0})
    total_leads_camp = sum(r["leads"] for r in leads_por_campanha_raw) or 1
    total_gasto_camp = sum(r["gasto"] for r in leads_por_campanha_raw) or 1
    leads_por_campanha = []
    for r in leads_por_campanha_raw:
        leads_por_campanha.append({
            **r,
            "cpl": r["gasto"] / r["leads"] if r["leads"] > 0 else 0.0,
            "pct_investimento": r["gasto"] / total_gasto_camp * 100,
            "pct_leads": r["leads"] / total_leads_camp * 100,
        })

    # Taxa de Comparecimento WPP — reaproveita o mesmo cruzamento usado em
    # "Leads X Grupos de WhatsApp" no debriefing (leads da AC × pessoas
    # ativas nos grupos, deduplicado normal+VIP).
    leads_x_whatsapp = None
    utm_cobertura = None
    if launch:
        try:
            leads_x_whatsapp = await run_in_threadpool(_leads_x_whatsapp, launch)
        except Exception:
            logger.exception("Captação: falha ao montar leads x WhatsApp")
        try:
            utm_cobertura = await run_in_threadpool(_utm_cobertura, launch)
        except Exception:
            logger.exception("Captação: falha ao montar cobertura de UTM")

    # Divisão de Verba por Público em Cada Dia (Previsto x Realizado) —
    # pauta debriefing 08/09/26, mesmo cruzamento já usado em /verba.
    dia_publico_previsto = com_percentuais(previsto_publico_por_dia(cfg, "Captação"))
    dia_publico_realizado = com_percentuais(
        await run_in_threadpool(publico_por_dia, launch.code, cfg, "Captação") if launch else {}
    )
    verba_diaria_combinada = combinar_previsto_realizado(dia_publico_previsto, dia_publico_realizado)

    if trilha_nome == TRILHA_BASE_FORTE:
        page_key, page_title = "captacao_base_forte", "Captação Base Forte"
    elif trilha_nome:
        page_key, page_title = "captacao", "Captação BV"
    else:
        page_key, page_title = "captacao", "Captação"
    ctx = _base_ctx(request, page_key, page_title, launch, launches,
        trilha_nome=trilha_nome, leads_active_trilha=leads_active_trilha,
        meta=meta, google=google, vendas=vendas, wa_gasto=wa_gasto,
        meta_capt_gasto=meta_capt_gasto, google_capt_gasto=google_capt_gasto,
        meta_capt_leads=meta_capt_leads, google_capt_conv=google_capt_conv,
        receita=receita, invest=invest, roas=roas,
        goal_leads=goal_leads, goal_invest=goal_invest,
        leads_meta=leads_meta, valor_medio_lead=valor_medio_lead,
        prog_leads=prog_leads, prog_invest=prog_invest,
        daily_breakdown=daily_breakdown,
        daily_breakdown_preq=daily_breakdown_preq,
        conversao_paginas=(conversao_pagina_captura or {}).get("Captação") or [],
        leads_por_campanha=leads_por_campanha,
        total_leads_camp=total_leads_camp, total_gasto_camp=total_gasto_camp,
        leads_x_whatsapp=leads_x_whatsapp,
        utm_cobertura=utm_cobertura,
        prev_kpis=prev_kpis,
        drive_thumbnails=d.get("drive_thumbnails") or {},
        verba_diaria_combinada=verba_diaria_combinada,
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

    # Resumo de investimento/leads — escopado pela etapa (por_etapa["Pré-
    # Qualificação"]), igual ao fix da página de Captação (não pode somar o
    # total do lançamento inteiro).
    # Na Black a etapa que ocupa este lugar do funil é o Aquecimento — mesmo
    # papel, nome diferente. Com a string fixa, a página vinha zerada no BV.
    _etapa_pq = etapa_prequali(launch.code if launch else None)
    meta_preq = (getattr(meta, "por_etapa", {}) or {}).get(_etapa_pq) or {}
    google_preq = (getattr(google, "por_etapa", {}) or {}).get(_etapa_pq) or {}
    meta_preq_gasto = float(meta_preq.get("gasto") or meta_preq.get("custo") or 0)
    google_preq_gasto = float(google_preq.get("custo") or 0)
    meta_preq_leads = int(meta_preq.get("leads") or 0)
    google_preq_conv = float(google_preq.get("conversoes") or 0)
    invest_preq = meta_preq_gasto + google_preq_gasto
    leads_preq = meta_preq_leads + int(round(google_preq_conv))
    cpl_preq = invest_preq / leads_preq if leads_preq > 0 else 0.0

    # ThruViews (Meta) / Views (Google TrueView) — mesma etapa, sem TikTok
    # ainda (sem fonte de dado integrada).
    meta_preq_thruviews = int(meta_preq.get("thruplays") or 0)
    google_preq_views = int(google_preq.get("visualizacoes") or 0)
    thruviews_preq = meta_preq_thruviews + google_preq_views

    conversao_pagina_captura = None
    if launch:
        try:
            conversao_pagina_captura = await run_in_threadpool(_conversao_pagina_captura, launch)
        except Exception:
            logger.exception("Pré-Qualificação: falha ao montar conversão da página de captura (GA4)")

    # % de Leads por Campanha — Facebook/YouTube por temperatura, escopado
    # pela Pré-Qualificação (por_temperatura_prequali existe em ambas as
    # plataformas) + TikTok (sempre 0, sem fonte de dado ainda).
    _clima_labels = climas_ordem(launch.code if launch else None)
    meta_temp_preq = (getattr(meta, "por_temperatura_prequali", {}) or {})
    google_temp_preq = (getattr(google, "por_temperatura_prequali", {}) or {})
    leads_por_campanha_preq_raw = []
    for c in _clima_labels:
        m = meta_temp_preq.get(c) or {}
        leads_por_campanha_preq_raw.append({
            "campanha": f"Facebook {c}",
            "leads": int(m.get("leads") or 0),
            "gasto": float(m.get("gasto") or m.get("custo") or 0),
        })
    for c in _clima_labels:
        g = google_temp_preq.get(c) or {}
        leads_por_campanha_preq_raw.append({
            "campanha": f"YouTube {c}",
            "leads": int(round(g.get("conversoes") or 0)),
            "gasto": float(g.get("custo") or 0),
        })
    leads_por_campanha_preq_raw.append({"campanha": "Tiktok", "leads": 0, "gasto": 0.0})
    total_leads_camp_preq = sum(r["leads"] for r in leads_por_campanha_preq_raw) or 1
    total_gasto_camp_preq = sum(r["gasto"] for r in leads_por_campanha_preq_raw) or 1
    leads_por_campanha_preq = []
    for r in leads_por_campanha_preq_raw:
        leads_por_campanha_preq.append({
            **r,
            "cpl": r["gasto"] / r["leads"] if r["leads"] > 0 else 0.0,
            "pct_investimento": r["gasto"] / total_gasto_camp_preq * 100,
            "pct_leads": r["leads"] / total_leads_camp_preq * 100,
        })

    ctx = _base_ctx(request, "pre_qualificacao", _etapa_pq, launch, launches,
        meta=meta, google=google,
        # Rótulo da etapa: "Aquecimento" na Black. O template usa em todo título.
        etapa_pq=_etapa_pq,
        daily_breakdown_preq=daily_breakdown_preq,
        meta_ads_preq=meta_ads_preq,
        youtube_ads_preq=youtube_ads_preq,
        drive_thumbnails=d.get("drive_thumbnails") or {},
        conversao_paginas=(conversao_pagina_captura or {}).get(_etapa_pq) or [],
        data_errors=d.get("_errors", []),
        invest_preq=invest_preq, leads_preq=leads_preq, cpl_preq=cpl_preq,
        meta_preq_gasto=meta_preq_gasto, google_preq_gasto=google_preq_gasto,
        meta_preq_leads=meta_preq_leads, google_preq_conv=google_preq_conv,
        thruviews_preq=thruviews_preq, meta_preq_thruviews=meta_preq_thruviews,
        google_preq_views=google_preq_views,
        leads_por_campanha=leads_por_campanha_preq,
        total_leads_camp=total_leads_camp_preq, total_gasto_camp=total_gasto_camp_preq,
    )
    return templates.TemplateResponse("pre_qualificacao.html", ctx)


@router.get("/verba", response_class=HTMLResponse)
async def verba_page(request: Request, launch_code: str | None = None):
    """Verba do Lançamento — espelha a planilha "Verba Diária" do usuário
    (pauta 06/09/26). Construída em blocos: bloco 1 é Previsto x Realizado
    por etapa (Pré-Qualificação, Captação, cada sub-etapa de remarketing e
    WhatsApp)."""
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_daily=True)
    meta, google = d["meta"], d["google"]
    wa_cost = d.get("wa_cost")
    wa_gasto = (wa_cost.get("total_cost_brl") or 0.0) if wa_cost else 0.0
    daily_capt = d.get("daily_breakdown") or []
    daily_preq = d.get("daily_breakdown_preq") or []

    cfg = await run_in_threadpool(_launch_cfg, launch.code) if launch else {}
    previsto_map = previsto_por_etapa(cfg)
    previsto_sub = previsto_por_subetapa(cfg)
    # WhatsApp pode ter sido cadastrado como uma "etapa" própria no wizard
    # (nome livre, ex: "WhatsApp") — usa o previsto de lá se existir.
    previsto_whatsapp = next(
        (float(et.get("total") or 0) for et in (cfg.get("etapas") or []) if et.get("nome") == "WhatsApp"),
        0.0,
    )

    linhas = []
    for nome in ["Pré-Qualificação", "Captação"]:
        e = get_etapa(meta, google, nome)
        linhas.append({"nome": nome, "previsto": previsto_map.get(nome, 0.0), "realizado": e["invest"]})
    for nome in REMARKETING_SUBETAPAS:
        e = get_etapa(meta, google, nome)
        linhas.append({"nome": nome, "previsto": previsto_sub.get(nome, 0.0), "realizado": e["invest"]})
    linhas.append({"nome": "WhatsApp", "previsto": previsto_whatsapp, "realizado": wa_gasto})

    total_previsto = sum(l["previsto"] for l in linhas)
    total_realizado = sum(l["realizado"] for l in linhas)
    for l in linhas:
        l["pct_previsto"] = (l["previsto"] / total_previsto * 100) if total_previsto > 0 else 0.0
        l["pct_realizado"] = (l["realizado"] / total_realizado * 100) if total_realizado > 0 else 0.0

    # % de Remarketing (5 sub-etapas + WhatsApp) sobre o previsto total —
    # mesma conta da linha "Remarketing" solta no fim do bloco na planilha.
    previsto_remarketing = sum(previsto_sub.values()) + previsto_whatsapp
    pct_remarketing_previsto = (previsto_remarketing / total_previsto * 100) if total_previsto > 0 else 0.0

    # Bloco 2/4: Investimento em Captação / Pré-Qualificação por Público
    # (bucket previsto % x realizado real por temperatura Meta/Google).
    bloco_capt_publico = buckets_previsto_x_realizado(meta, google, cfg, "Captação")
    bloco_preq_publico = buckets_previsto_x_realizado(meta, google, cfg, "Pré-Qualificação")

    # Curva diária de verba investida (previsto x realizado) — Captação e
    # Pré-Qualificação.
    curva_capt = com_realizado_diario(curva_diaria(cfg, "Captação"), daily_capt)
    curva_preq = com_realizado_diario(curva_diaria(cfg, "Pré-Qualificação"), daily_preq)

    # Divisão de verba por público em cada dia (só Captação — é o único
    # bloco que a planilha de referência detalha nesse nível).
    dia_publico_realizado = com_percentuais(
        await run_in_threadpool(publico_por_dia, launch.code, cfg, "Captação") if launch else {}
    )
    dia_publico_previsto = com_percentuais(previsto_publico_por_dia(cfg, "Captação"))
    verba_diaria_combinada = combinar_previsto_realizado(dia_publico_previsto, dia_publico_realizado)

    # Blocos por sub-etapa de remarketing: Previsto x Realizado total, split
    # Facebook/Google (buckets) e curva diária própria.
    subetapas_blocos = []
    for nome in REMARKETING_SUBETAPAS:
        et = etapa_cfg(cfg, nome)
        if not et:
            continue
        bloco_pub = buckets_previsto_x_realizado(meta, google, cfg, nome)
        daily_rows = await run_in_threadpool(
            investimento_diario_etapa, launch.code, nome, et.get("start_date"), et.get("end_date"),
        ) if launch else []
        curva = com_realizado_diario(curva_diaria(cfg, nome), daily_rows)
        subetapas_blocos.append({"nome": nome, "bucket": bloco_pub, "curva": curva})

    # Anotações do diário: o que foi FEITO em cada dia, ao lado do que aconteceu
    # na curva. Vem de eventos_trafego (ver scripts/eventos.py).
    eventos = await run_in_threadpool(read_eventos, launch.code) if launch else []
    eventos_dia = eventos_por_dia(eventos)

    ctx = _base_ctx(request, "verba", "Verba do Lançamento", launch, launches,
        eventos=eventos, eventos_dia=eventos_dia, cores_tipo=CORES_TIPO,
        verba_linhas=linhas, verba_total_previsto=total_previsto, verba_total_realizado=total_realizado,
        verba_pct_remarketing_previsto=pct_remarketing_previsto,
        bloco_capt_publico=bloco_capt_publico, bloco_preq_publico=bloco_preq_publico,
        curva_capt=curva_capt, curva_preq=curva_preq,
        verba_diaria_combinada=verba_diaria_combinada,
        subetapas_blocos=subetapas_blocos,
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("verba.html", ctx)


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


@router.get("/aulas-ao-vivo", response_class=HTMLResponse)
async def aulas_ao_vivo_page(request: Request, launch_code: str | None = None):
    """Análise da transmissão das aulas, minuto a minuto.

    Não usa `_fetch_all_data`: a página depende só de `youtube_live_curva` e
    `youtube_aulas_stats`, e carregar Meta/Google/vendas junto custaria
    dezenas de segundos sem entrar em nada do que é mostrado aqui.
    """
    from frontend.db_readers.youtube_aulas import read_aulas_ao_vivo, read_retencao_video  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    dados = await run_in_threadpool(read_aulas_ao_vivo, launch.code) if launch else {"aulas": [], "totais": {}}
    ret = await run_in_threadpool(read_retencao_video, launch.code) if launch else {"aulas": [], "segmentos": []}
    ctx = _base_ctx(request, "aulas_ao_vivo", "Aulas Ao Vivo", launch, launches,
                    aulas=dados["aulas"], totais=dados["totais"], ret=ret, data_errors=[])
    return templates.TemplateResponse("aulas_ao_vivo.html", ctx)


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


@router.get("/calendario", response_class=HTMLResponse)
async def calendario_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch   = resolve_launch(launch_code, launches)
    ctx = _base_ctx(request, "calendario", "Calendário", launch, launches)
    cal = await run_in_threadpool(build_calendario_ctx, do_ano(ctx["launches"], ctx["ano_sel"]), _launch_cfg)
    ctx["cal"] = cal
    return templates.TemplateResponse("calendario.html", ctx)


@router.get("/ano")
async def trocar_ano(ano: int, next: str = "/calendario"):
    """Grava o ano global (cookie) e volta para a página de origem. `next` só aceita caminho local."""
    destino = next if next.startswith("/") and not next.startswith("//") else "/calendario"
    resp = RedirectResponse(url=destino, status_code=303)
    if 2000 <= ano <= 2100:
        resp.set_cookie(ANO_COOKIE, str(ano), max_age=60 * 60 * 24 * 400, samesite="lax", httponly=True)
    return resp


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
                "vendas": int(v.total_vendas) if v else 0,
                "roas": receita / invest if invest > 0 else 0.0,
            }
        except Exception:
            logger.exception("Lançamentos: falha ao resumir %s", l.code)
            return {"leads": 0, "invest": 0.0, "receita": 0.0, "vendas": 0, "roas": 0.0}

    ctx = _base_ctx(request, "lancamentos", "Lançamentos", launch, launches)
    from datetime import date as _date  # noqa: PLC0415

    # Esta página é do ANO: lista e soma só os lançamentos cujo código termina no ano escolhido
    # (PI-JAN-26 é de 2026 mesmo começando em nov/2025; BV-25 é de 2025 e fica de fora de 2026).
    ano_sel = ctx["ano_sel"]   # ano global (seletor do Calendário), resolvido em _base_ctx
    lancs_ano = do_ano(ctx["launches"], ano_sel)

    summaries = await asyncio.gather(*[
        run_in_threadpool(_summary, l) for l in lancs_ano
    ])
    summary_by_code = {l.code: s for l, s in zip(lancs_ano, summaries)}
    ctx["summary_by_code"] = summary_by_code

    from src.constants import PALETA_PRODUTO  # noqa: PLC0415
    ctx["paleta_produto"] = PALETA_PRODUTO
    ctx["hoje"] = _date.today()
    # Janela do carrinho de cada lançamento (cartões: situação e "carrinho abre em dd/mm")
    ctx["carrinhos"] = await run_in_threadpool(_carrinhos_do_ano, [l.code for l in lancs_ano])

    # Seções abaixo dos lançamentos: perpétuo (um cartão por vertical) e distribuição (um por perfil)
    from frontend.cache import _get_or_compute as _cache  # noqa: PLC0415
    from frontend.db_readers.distribuicao import read_distribuicao_cards  # noqa: PLC0415
    from frontend.db_readers.perpetuo import read_perpetuo_cards  # noqa: PLC0415

    _ano_cartoes = ano_sel
    ctx["ano_cartoes"] = _ano_cartoes
    try:
        ctx["perpetuo_cards"], ctx["distribuicao_cards"] = await asyncio.gather(
            run_in_threadpool(_cache, "EMPRESA", f"perpetuo_cards::{_ano_cartoes}", lambda: read_perpetuo_cards(_ano_cartoes), 600),
            run_in_threadpool(_cache, "EMPRESA", f"distribuicao_cards::{_ano_cartoes}", lambda: read_distribuicao_cards(_ano_cartoes), 600),
        )
    except Exception:
        logger.exception("Lançamentos: falha ao montar os cartões de perpétuo e distribuição")
        ctx["perpetuo_cards"], ctx["distribuicao_cards"] = [], []
    ctx["perpetuo_tot"], ctx["distribuicao_tot"] = _totais_secoes(ctx["perpetuo_cards"], ctx["distribuicao_cards"])
    ctx["resumo_ano"] = _resumo_do_ano(lancs_ano, summary_by_code, ano_sel)
    # faturamento do ano por produto (prefixo do código), para o "% dos lançamentos do ano" da faixa de cada produto
    ctx["prod_ano_rec"] = {}
    if ctx["resumo_ano"]:
        _suf = f"-{str(ctx['resumo_ano']['ano'])[-2:]}"
        for _l in lancs_ano:
            if str(_l.code).upper().endswith(_suf):
                _pref = str(_l.code).split("-")[0].upper()
                ctx["prod_ano_rec"][_pref] = ctx["prod_ano_rec"].get(_pref, 0.0) + float((summary_by_code.get(_l.code) or {}).get("receita") or 0)
    if ctx["resumo_ano"]:
        ano = ctx["resumo_ano"]["ano"]
        codes = [l.code for l in lancs_ano]
        invest_mensal = await run_in_threadpool(_invest_mensal_do_ano, codes)
        ctx["resumo_ano"]["mensal"] = _faturamento_mensal(lancs_ano, summary_by_code, ano, ctx["carrinhos"], invest_mensal)

        # Empresa inteira: perpétuo, setor de vendas (fora do carrinho) e investimento fora de lançamento.
        # A meta anual passa a medir o faturamento TOTAL da empresa, não só o dos lançamentos.
        from frontend.cache import _get_or_compute  # noqa: PLC0415
        from frontend.db_readers.empresa import read_empresa_ano  # noqa: PLC0415
        from frontend.db_readers.perpetuo import read_perpetuo_ano  # noqa: PLC0415

        try:
            empresa_raw, perp = await asyncio.gather(
                run_in_threadpool(_get_or_compute, "EMPRESA", f"empresa_ano::{ano}", lambda: read_empresa_ano(ano), 600),
                run_in_threadpool(_get_or_compute, "EMPRESA", f"perpetuo_ano::{ano}", lambda: read_perpetuo_ano(ano), 600),
            )
            emp = _empresa_do_ano(ctx["resumo_ano"], empresa_raw, perp)
            ctx["resumo_ano"]["empresa"] = emp
            # gasto de distribuição sem perfil definido (campanha sem código): fecha o quadro com os cartões
            soma_perfis = sum(c.get("invest") or 0 for c in ctx.get("distribuicao_cards") or [])
            ctx["distribuicao_sem_perfil"] = max(emp["linhas"][3]["invest"] - soma_perfis, 0.0)
            ctx["resumo_ano"]["meta"] = _meta_do_ano(
                ano, ctx["resumo_ano"]["total"], ctx["resumo_ano"]["ranking"],
                ctx["resumo_ano"]["n_lancamentos"], atingido=emp["receita"])
        except Exception:
            logger.exception("Lançamentos: falha ao montar o faturamento total da empresa")

    return templates.TemplateResponse("lancamentos.html", ctx)


def _resumo_do_ano(launches, summary_by_code, ano: int | None = None) -> dict | None:
    """Soma dos lançamentos do ano (só informativo): faturamento, investimento e o que deriva.

    O ano vem do sufixo do código (PBB-ABR-26 → 2026). Só entram lançamentos — campanhas
    de distribuição e perpétuo não têm código de lançamento. Receita = líquida contratada
    (Hotmart + TMB); investimento = Meta + Google, os mesmos números dos cartões abaixo.
    """
    from datetime import date  # noqa: PLC0415

    ano = ano or date.today().year
    sufixo = f"-{str(ano)[-2:]}"
    do_ano = [l for l in launches if str(l.code).upper().endswith(sufixo)]
    if not do_ano:
        return None

    def _soma(itens):
        s = {"leads": 0, "invest": 0.0, "receita": 0.0, "vendas": 0}
        for l in itens:
            x = summary_by_code.get(l.code) or {}
            for k in s:
                s[k] += x.get(k) or 0
        s["roas"] = s["receita"] / s["invest"] if s["invest"] > 0 else 0.0
        s["resultado"] = s["receita"] - s["invest"]
        s["ticket"] = s["receita"] / s["vendas"] if s["vendas"] > 0 else 0.0
        s["cac"] = s["invest"] / s["vendas"] if s["vendas"] > 0 else 0.0
        s["cpl"] = s["invest"] / s["leads"] if s["leads"] > 0 else 0.0
        return s

    total = _soma(do_ano)
    por_produto: dict[str, dict] = {}
    for l in do_ano:
        nome = getattr(l, "product_name", None) or getattr(l, "product", None) or "Outros"
        por_produto.setdefault(nome, []).append(l)
    produtos = []
    for nome, itens in por_produto.items():
        s = _soma(itens)
        s["nome"] = nome
        s["lancamentos"] = len(itens)
        s["pct_receita"] = s["receita"] / total["receita"] * 100 if total["receita"] > 0 else 0.0
        produtos.append(s)
    produtos.sort(key=lambda x: x["receita"], reverse=True)

    ranking = []
    for l in do_ano:
        x = summary_by_code.get(l.code) or {}
        if (x.get("receita") or 0) > 0:  # lançamento ainda sem venda não entra no ranking
            ranking.append({"code": l.code, "accent": getattr(l, "accent", None),
                            "receita": x.get("receita") or 0.0, "invest": x.get("invest") or 0.0,
                            "roas": x.get("roas") or 0.0, "vendas": x.get("vendas") or 0})
    ranking.sort(key=lambda x: x["receita"], reverse=True)
    maximo = ranking[0]["receita"] if ranking else 0.0
    for r in ranking:
        r["pct_barra"] = r["receita"] / maximo * 100 if maximo > 0 else 0.0
        r["rot"] = _rotulo_curto(r["receita"])
        r["pct_ano"] = r["receita"] / total["receita"] * 100 if total["receita"] > 0 else 0.0

    return {"ano": ano, "n_lancamentos": len(do_ano), "total": total,
            "produtos": produtos, "ranking": ranking, "meta": _meta_do_ano(ano, total, ranking, len(do_ano))}


_MESES_PT = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def _rotulo_curto(v: float) -> str:
    """R$ em formato curto para o rótulo das barras: 2,5 mi / 850 mil / 90."""
    v = float(v or 0)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}".replace(".", ",") + " mi"
    if v >= 1_000:
        return f"{v / 1_000:.0f} mil"
    return f"{v:.0f}" if v else ""


def _fracao_por_mes(ini, fim, ano: int) -> dict[int, float]:
    """Fração dos dias de [ini, fim] que cai em cada mês de `ano`. Dia fora do ano conta
    no mês mais próximo (janeiro ou dezembro), para o total do ano nunca se perder."""
    from datetime import timedelta  # noqa: PLC0415

    dias = (fim - ini).days + 1
    if dias <= 0:
        return {}
    cont: dict[int, int] = {}
    for i in range(dias):
        d = ini + timedelta(days=i)
        m = d.month if d.year == ano else (1 if d.year < ano else 12)
        cont[m] = cont.get(m, 0) + 1
    return {m: n / dias for m, n in cont.items()}


def _faturamento_mensal(do_ano, summary_by_code: dict, ano: int, carrinhos: dict, invest_mensal: dict) -> dict:
    """Faturamento e matrículas por mês (APROXIMADO) + investimento real do mês.

    Faturamento e matrículas de cada lançamento são distribuídos pelos dias do carrinho
    (o que atravessa a virada de mês é dividido); sem janela de carrinho, vai para o mês
    de término do lançamento. É por mês da VENDA (contratado), não de caixa. O investimento
    é o gasto real de Meta + Google em cada mês; o que foi gasto antes de janeiro (campanha
    de pré-lançamento do PI-JAN-26 em 2025) entra em `invest_antes`.
    """
    meses = [{"mes": i + 1, "nome": _MESES_PT[i], "receita": 0.0, "vendas": 0.0, "invest": 0.0} for i in range(12)]
    for l in do_ano:
        x = summary_by_code.get(l.code) or {}
        receita, vendas = float(x.get("receita") or 0), float(x.get("vendas") or 0)
        if receita <= 0 and vendas <= 0:
            continue
        janela = carrinhos.get(l.code)
        if janela and janela[0] and janela[1]:
            fracoes = _fracao_por_mes(janela[0], janela[1], ano)
        else:
            fim = getattr(l, "data_fim", None) or getattr(l, "data_inicio", None)
            fracoes = {max(1, min(12, fim.month)) if fim and fim.year == ano else (1 if fim and fim.year < ano else 12): 1.0} if fim else {}
        for m, f in fracoes.items():
            meses[m - 1]["receita"] += receita * f
            meses[m - 1]["vendas"] += vendas * f

    invest_antes = 0.0
    for (a, m), v in (invest_mensal or {}).items():
        if a < ano:
            invest_antes += float(v)
        elif a == ano:
            meses[m - 1]["invest"] += float(v)
    teto = max([m["receita"] for m in meses] + [m["invest"] for m in meses] + [0.0])
    for m in meses:
        m["vendas"] = int(round(m["vendas"]))
        m["receita_rot"], m["invest_rot"] = _rotulo_curto(m["receita"]), _rotulo_curto(m["invest"])
        m["h_receita"] = m["receita"] / teto * 100 if teto > 0 else 0.0
        m["h_invest"] = m["invest"] / teto * 100 if teto > 0 else 0.0
    return {"meses": meses, "invest_antes": invest_antes,
            "melhor_mes": max(meses, key=lambda m: m["receita"])["nome"] if teto > 0 else None}


def _carrinhos_do_ano(codes: list[str]) -> dict:
    from frontend.services.fetch import _launch_cfg  # noqa: PLC0415
    from frontend.utils import _safe_date  # noqa: PLC0415

    saida = {}
    for code in codes:
        try:
            cfg = _launch_cfg(code) or {}
            saida[code] = (_safe_date(cfg.get("carrinho_start_date")), _safe_date(cfg.get("carrinho_end_date")))
        except Exception:
            logger.exception("Lançamentos: falha ao ler o carrinho de %s", code)
    return saida


def _invest_mensal_do_ano(codes: list[str]) -> dict:
    """{(ano, mês): R$} do gasto real de Meta + Google dos lançamentos."""
    from sqlalchemy import text as _text  # noqa: PLC0415

    from frontend.db import _get_engine  # noqa: PLC0415

    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(_text("""
                SELECT EXTRACT(YEAR FROM d)::int, EXTRACT(MONTH FROM d)::int, SUM(v)
                FROM (SELECT date AS d, spend AS v FROM meta_ads_daily WHERE lancamento_codigo = ANY(:c)
                      UNION ALL
                      SELECT date, cost FROM google_ads_daily WHERE lancamento_codigo = ANY(:c)) t
                GROUP BY 1, 2
            """), {"c": codes}).fetchall()
        return {(int(a), int(m)): float(v or 0) for a, m, v in rows}
    except Exception:
        logger.exception("Lançamentos: falha ao somar o investimento por mês")
        return {}


def _totais_secoes(perpetuo: list[dict], distribuicao: list[dict]) -> tuple[dict, dict]:
    """Totais das faixas de resumo do perpétuo e da distribuição."""
    p = {k: sum(c.get(k) or 0 for c in perpetuo) for k in ("receita", "vendas", "invest", "receita_30d")}
    p["roas"] = p["receita"] / p["invest"] if p["invest"] > 0 else 0.0
    d = {k: sum(c.get(k) or 0 for c in distribuicao) for k in ("invest", "invest_30d", "seguidores", "novos_30d")}
    d["custo_por_seguidor"] = d["invest_30d"] / d["novos_30d"] if d["novos_30d"] > 0 else 0.0
    return p, d


def _empresa_do_ano(resumo: dict, empresa: dict, perpetuo: dict) -> dict:
    """Faturamento e investimento da empresa inteira no ano, repartidos por origem.

    `resumo["total"]` são os lançamentos (venda dentro do carrinho). Perpétuo vem do leitor
    próprio. O **setor de vendas** é o que sobra do total vendido (Hotmart + TMB) depois de
    tirar lançamentos e perpétuo: mentorias e outros produtos vendidos fora da janela do
    carrinho. A distribuição não tem venda ligada — entra só com o investimento.
    """
    t = resumo["total"]
    vendido_r = empresa["hotmart"]["receita"] + empresa["tmb"]["receita"]
    vendido_v = empresa["hotmart"]["vendas"] + empresa["tmb"]["vendas"]
    perp_r, perp_v = perpetuo["total"]["receita"], perpetuo["total"]["vendas"]
    setor_r = max(vendido_r - t["receita"] - perp_r, 0.0)
    setor_v = max(vendido_v - t["vendas"] - perp_v, 0)
    total_r = t["receita"] + perp_r + setor_r
    total_v = t["vendas"] + perp_v + setor_v

    inv = empresa["invest"]
    inv_dist = inv["distribuicao"] + inv["sem_codigo"]
    inv_total = t["invest"] + inv["perpetuo"] + inv_dist

    def _linha(chave, nome, icone, descricao, receita, vendas, invest):
        return {"chave": chave, "nome": nome, "icone": icone, "descricao": descricao,
                "receita": receita, "vendas": vendas, "invest": invest,
                "pct": receita / total_r * 100 if total_r > 0 else 0.0}

    linhas = [
        _linha("lancamentos", "Lançamentos", "ti-rocket",
               f"Vendas dentro do carrinho dos {resumo['n_lancamentos']} lançamentos do ano",
               t["receita"], t["vendas"], t["invest"]),
        _linha("vendas", "Setor de vendas", "ti-headset",
               "Vendas fora do carrinho: mentorias, apostilas e cursos vendidos fora da janela de um lançamento",
               setor_r, setor_v, 0.0),
        _linha("perpetuo", "Perpétuo", "ti-infinity",
               "Mestre em Questões (TJ-SP, INSS, BB) e Planner",
               perp_r, perp_v, inv["perpetuo"]),
        _linha("distribuicao", "Distribuição", "ti-share",
               "Só anúncio: as campanhas de distribuição não têm venda ligada; o que trazem aparece nos lançamentos ou no setor de vendas",
               0.0, 0, inv_dist),
    ]
    return {
        "linhas": linhas, "receita": total_r, "vendas": total_v, "invest": inv_total,
        "resultado": total_r - inv_total, "roas": total_r / inv_total if inv_total > 0 else 0.0,
        "completo": bool(empresa.get("completo", True)),
        "vendido_hotmart": empresa["hotmart"]["receita"], "vendido_tmb": empresa["tmb"]["receita"],
    }


def _meta_do_ano(ano: int, total: dict, ranking: list, n_lancamentos: int, atingido: float | None = None) -> dict | None:
    """Progresso da meta anual de faturamento (só informativo).

    `ritmo`: quanto do ano já passou, para comparar com o % da meta atingido.
    `restantes`: lançamentos do ano que ainda não venderam nada; `necessario_por_restante`
    é quanto cada um teria de faturar, em média, para fechar a meta.
    """
    from datetime import date  # noqa: PLC0415

    from src.constants import metas_faturamento_anual  # noqa: PLC0415

    degraus = metas_faturamento_anual(ano)
    if not degraus:
        return None
    meta = degraus[0][1]
    teto = max(v for _, v in degraus)   # a barra vai até a meta desafio
    hoje = date.today()
    dias_ano = (date(ano, 12, 31) - date(ano, 1, 1)).days + 1
    decorridos = min(max((hoje - date(ano, 1, 1)).days + 1, 0), dias_ano) if hoje.year == ano else (dias_ano if hoje.year > ano else 0)
    # `total` são os lançamentos (base da média por lançamento); `atingido` é o que conta para a meta
    # — o total da empresa quando disponível, senão só os lançamentos.
    atingido = total["receita"] if atingido is None else atingido
    falta = max(meta - atingido, 0.0)
    restantes = max(n_lancamentos - len(ranking), 0)
    com_venda = len(ranking)
    niveis = [
        {"nome": nome, "valor": v, "pct": atingido / v * 100, "falta": max(v - atingido, 0.0),
         "batida": atingido >= v, "pos": v / teto * 100}
        for nome, v in degraus
    ]
    return {
        "niveis": niveis,
        "pct_fill": min(atingido / teto * 100, 100.0),
        "pos_ritmo": meta * (decorridos / dias_ano) / teto * 100,   # onde a meta base deveria estar hoje
        "valor": meta, "atingido": atingido, "falta": falta,
        "pct": atingido / meta * 100, "pct_barra": min(atingido / meta * 100, 100.0),
        "pct_ano": decorridos / dias_ano * 100,
        "media_lancamento": total["receita"] / com_venda if com_venda else 0.0,
        "restantes": restantes,
        "necessario_por_restante": falta / restantes if restantes else 0.0,
        "batida": atingido >= meta,
    }


@router.get("/comparativo", response_class=HTMLResponse)
def comparativo_page(request: Request, launch_code: str | None = None):
    try:
        launches = get_launches()
        launch = resolve_launch(launch_code, launches)
        previous = find_previous_launch(launch, launches) if launch else None
        previous2 = find_previous_launch(previous, launches) if previous else None

        # `?ao_vivo=1` recalcula na hora, ignorando o cache da página e o dos
        # leitores por baixo (force_refresh, o mesmo do re-aquecimento pós-ETL
        # — sem ele read_vendas/read_meta devolveriam o valor velho e a página
        # continuaria antiga). Existe por causa do dia da abertura: os
        # checkpoints do "Dia 1" viram de hora em hora e o TTL de 1h segurava o
        # número novo na tela. Recalcula tudo de forma síncrona, então é lento
        # de propósito — é botão de conferência, não o caminho normal.
        ao_vivo = request.query_params.get("ao_vivo") == "1"

        comp_data = None
        comp_error = None
        if launch and previous:
            try:
                token = force_refresh_start() if ao_vivo else None
                try:
                    comp_data = comparativo_cached(launch, previous, previous2, ignorar_cache=ao_vivo)
                finally:
                    if token is not None:
                        force_refresh_end(token)
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
            ao_vivo=ao_vivo,
        )
        return templates.TemplateResponse("comparativo.html", ctx)
    except Exception as exc:
        import html
        # Logar antes de responder: a página mostra só tipo e mensagem, e
        # "'NoneType' object is not subscriptable" sem traceback não diz em que
        # linha foi. Sem isso o diagnóstico começa reproduzindo na mão.
        logger.exception("Falha ao montar/renderizar /comparativo (launch=%s)", launch_code)
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


_SNAPSHOT_CARRINHO_MIN = 10
_ULTIMO_REAQUECIMENTO: dict[str, float] = {}


def _carrinho_aberto(code: str) -> bool:
    from datetime import date  # noqa: PLC0415
    from frontend.utils import _safe_date  # noqa: PLC0415

    cfg = _launch_cfg(code) or {}
    ini, fim = _safe_date(cfg.get("carrinho_start_date")), _safe_date(cfg.get("carrinho_end_date"))
    return bool(ini and fim and ini <= date.today() <= fim)


def _reaquecer_com_carrinho_aberto(code: str) -> None:
    """Re-aquece o lançamento (caches + snapshot do debriefing), no máximo a cada
    `_SNAPSHOT_CARRINHO_MIN` minutos por lançamento, sem esperar a página."""
    import time as _time  # noqa: PLC0415
    from frontend.services.prewarm import schedule_warm  # noqa: PLC0415

    agora = _time.monotonic()
    if agora - _ULTIMO_REAQUECIMENTO.get(code, -1e9) < _SNAPSHOT_CARRINHO_MIN * 60:
        return
    _ULTIMO_REAQUECIMENTO[code] = agora
    schedule_warm([code], invalidate=True, origem="carrinho-aberto")


@router.get("/debriefing", response_class=HTMLResponse)
async def debriefing(request: Request, launch_code: str | None = None, modo: str | None = None):
    """``modo=slides`` renderiza o mesmo conteúdo em modo apresentação
    (um slide 1920x1080 por seção, pronto pra "Salvar como PDF" no Chrome);
    é o que o botão "Gerar PDF" da aba abre."""
    slides = modo == "slides"
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)

    # 1) Caminho rápido: snapshot pré-calculado pelo aquecimento (boot + após
    #    cada rodada do ETL), gravado em debriefing_snapshot. Uma consulta e
    #    tudo inline — nada de esqueleto nem cálculo. `?ao_vivo=1` ignora o
    #    snapshot (depuração / conferir dado recém-carregado).
    snapshot_at = None
    built = None
    if launch and request.query_params.get("ao_vivo") != "1":
        from frontend.db_readers.debriefing_snapshot import read_snapshot  # noqa: PLC0415
        snap = await run_in_threadpool(read_snapshot, launch.code)
        if snap and isinstance(snap.get("payload"), dict) and snap["payload"].get("dbf"):
            built = snap["payload"]
            snapshot_at = snap["computed_at"]

    # 2) Sem snapshot: cálculo ao vivo. Fora do modo slides, as seções mais
    #    pesadas viram esqueleto e o navegador busca cada uma em
    #    /debriefing/secao/<nome> depois que a página já apareceu (lazy).
    lazy = False
    if built is None:
        lazy = not slides
        built = await build_debriefing_context(launch, launches, lazy=lazy)
        # Sem snapshot (lançamento antigo, fora do aquecimento) ou ?ao_vivo=1:
        # grava um em segundo plano com os caches que esta visita acabou de
        # aquecer — a próxima abertura já vem do snapshot.
        if launch:
            from frontend.services.prewarm import schedule_snapshot_only  # noqa: PLC0415
            schedule_snapshot_only(launch, launches)

    snapshot_label = ""
    snapshot_fresh = True
    if snapshot_at:
        try:
            from datetime import datetime, timezone  # noqa: PLC0415
            from zoneinfo import ZoneInfo  # noqa: PLC0415
            snapshot_label = snapshot_at.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m %H:%M")
            age_minutes = (datetime.now(timezone.utc) - snapshot_at.astimezone(timezone.utc)).total_seconds() / 60
            # Aquecimento roda a cada PRE_WARM_INTERVAL_MIN (padrão 30min) +
            # depois de todo ETL — 60min de folga cobre isso sem virar "vermelho"
            # à toa por uma rodada atrasada.
            snapshot_fresh = age_minutes <= 60
            # Carrinho aberto: a venda não passa pelo ETL (entra direto no banco
            # operacional), então nada dispara o aquecimento quando ela chega e o
            # snapshot ficaria até 1h mostrando o carrinho de antes (15/10/26: foi
            # gerado minutos antes de abrir e mostrou R$ 0 com 270 vendas). Com o
            # carrinho aberto e o snapshot com mais de 10 min, serve o que tem
            # e re-aquece em segundo plano; a próxima abertura já vem atualizada.
            if age_minutes > _SNAPSHOT_CARRINHO_MIN and await run_in_threadpool(_carrinho_aberto, launch.code):
                _reaquecer_com_carrinho_aberto(launch.code)
        except Exception:
            snapshot_label = str(snapshot_at)[:16]

    ctx = _base_ctx(request, "debriefing", "Debriefing", launch, launches,
                    dbf=built["dbf"], drive_thumbnails=built.get("drive_thumbnails") or {},
                    data_errors=built.get("data_errors") or [],
                    creative_data_error=bool(built.get("creative_data_error")),
                    slides=slides, lazy=lazy, snapshot_label=snapshot_label,
                    snapshot_fresh=snapshot_fresh)
    return templates.TemplateResponse("debriefing.html", ctx)


_DEBRIEFING_SECOES_LAZY = ("pesquisa_engajamento", "qualidade_regiao", "perfil_por_anuncio", "caminho_comprador", "leads_x_whatsapp", "vendas_grupos_whatsapp", "disparo_resumo", "funil_pesquisa", "comparativo_historico", "historico_grande", "sorteio", "cadastrados_lancamentos_anteriores")


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
            # Também passa `previous`: o card de engajamento agora tem o
            # form performance do Typeform (starts/submissions/completion
            # rate/tempo) com badge vs lançamento anterior.
            previous = find_previous_launch(launch, launches)
            dbf[secao] = await run_in_threadpool(_pesquisa_engajamento, launch, previous)
        elif secao == "funil_pesquisa":
            # Mesmo dado de pesquisa_engajamento (cache compartilhado, cache
            # hit garantido se aquela seção já carregou) — só o template
            # muda, focado no funil que a pauta pediu.
            previous = find_previous_launch(launch, launches)
            dbf["pesquisa_engajamento"] = await run_in_threadpool(_pesquisa_engajamento, launch, previous)
        elif secao == "leads_x_whatsapp":
            previous = find_previous_launch(launch, launches)
            dbf[secao] = await run_in_threadpool(_leads_x_whatsapp, launch, previous)
        elif secao == "vendas_grupos_whatsapp":
            previous = find_previous_launch(launch, launches)
            dbf[secao] = await run_in_threadpool(_vendas_grupos_whatsapp, launch, previous)
        elif secao == "disparo_resumo":
            dbf[secao] = await run_in_threadpool(_disparo_resumo, launch)
        elif secao == "sorteio":
            previous = find_previous_launch(launch, launches)
            dbf[secao] = await run_in_threadpool(_sorteio, launch, previous)
        elif secao == "comparativo_historico":
            dbf[secao] = await run_in_threadpool(read_comparativo_historico, launch, launches)
        elif secao == "historico_grande":
            dbf[secao] = await run_in_threadpool(read_historico_grande, launch, launches)
        elif secao == "qualidade_regiao":
            dbf[secao] = await run_in_threadpool(_qualidade_regiao, launch, None)
        elif secao == "caminho_comprador":
            cc = await run_in_threadpool(_caminho_comprador, launch, None)
            dbf[secao] = (cc or {}).get("resumo")
        elif secao == "cadastrados_lancamentos_anteriores":
            dbf[secao] = await run_in_threadpool(_cadastrados_lancamentos_anteriores, launch, None)
        elif secao == "perfil_por_anuncio":
            # A pesquisa só traz ad_code/leads/respostas; nome, investimento e
            # vendas vêm de Meta/Google/atribuição (todos cacheados, rápido).
            # ROAS comparativo (criativo "antigo"/validado) precisa também dos
            # mesmos dados do lançamento anterior.
            from frontend.services.debriefing import _enrich_perfil_por_anuncio  # noqa: PLC0415

            async def _prev_data():
                previous = find_previous_launch(launch, launches)
                if not previous:
                    return None, None, None
                prev_d = await run_in_threadpool(_fetch_prev_for_debriefing, previous)
                p_meta = prev_d.get("meta")
                p_google = prev_d.get("google")
                p_vendas = prev_d.get("vendas")
                p_sales_attr = None
                if getattr(previous, "has_ac", False) and p_vendas:
                    p_sales_attr = await run_in_threadpool(_sales_attribution, previous, p_vendas)
                return p_meta, p_google, p_sales_attr

            d, perfil, (prev_meta, prev_google, prev_sales_attr) = await asyncio.gather(
                _fetch_all_data(launch, needs_sales_attr=True, needs_thumbnails=True),
                run_in_threadpool(_perfil_por_anuncio, launch),
                _prev_data(),
            )
            dbf[secao] = _enrich_perfil_por_anuncio(
                perfil, d.get("meta"), d.get("google"), d.get("sales_attr"),
                prev_meta=prev_meta, prev_google=prev_google, prev_sales_attr=prev_sales_attr,
            )
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
