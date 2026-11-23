from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.concurrency import run_in_threadpool

from frontend.core import (
    templates, get_launches, resolve_launch, _base_ctx, _fetch_all_data,
    AcCampaignSummary,
)

router = APIRouter()


@router.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch)
    vendas, leads = d["vendas"], d["leads"]
    ctx = _base_ctx(request, "leads", "Leads & Confronto", launch, launches,
        leads=leads, vendas=vendas,
        data_errors=d.get("_errors", []))
    return templates.TemplateResponse("leads.html", ctx)


def _score_leads_df(code: str):
    """DataFrame do score por lead do lançamento (cache de 30 min em `lead_score.obter_leads`)."""
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415
    from frontend.services import lead_score as ls  # noqa: PLC0415

    v = read_vendas(code)
    compradores = (v.emails_hotmart | v.emails_tmb) if v else set()
    return ls.obter_leads(code, compradores)


@router.get("/leads/score/resumo", response_class=HTMLResponse)
async def leads_score_resumo(request: Request, launch_code: str | None = None):
    """Trecho da /leads (carregado por fetch): escada de compra do score por decil e por faixa, com o veredito
    «estamos no caminho certo?». Vazio quando o lançamento não tem leads com UTM ou o modelo não está disponível."""
    from frontend.services import lead_score as ls  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    if not launch:
        return HTMLResponse("")
    df = await run_in_threadpool(_score_leads_df, launch.code)
    if df is None or df.empty:
        return HTMLResponse("")
    return templates.TemplateResponse("leads/_score_resumo.html", {"request": request, "r": ls.resumo_painel(df)})


@router.get("/leads/score.csv")
async def leads_score_csv(request: Request, launch_code: str | None = None,
                          decil_min: int | None = None, comprou: str | None = None):
    """Score por lead do lançamento em CSV (Excel: ';' e BOM): uma linha por lead, do maior para o menor score.
    Traz dois scores lado a lado — só pela pesquisa (o do debriefing) e com origem (canal/temperatura/etapa, vale
    também para quem não respondeu). `decil_min` (1–10) mantém só os leads dos decis de cima; `comprou=nao|sim`
    filtra por compra. Contém e-mail, então fica na mesma faixa de acesso da /leads."""
    from fastapi.responses import Response  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    if not launch:
        return Response("Lançamento não encontrado.", status_code=404, media_type="text/plain; charset=utf-8")

    df = await run_in_threadpool(_score_leads_df, launch.code)
    if df is None or df.empty:
        return Response("Este lançamento não tem leads com UTM ou o modelo de score não está disponível.",
                        status_code=404, media_type="text/plain; charset=utf-8")
    if decil_min:
        df = df[df["decil_origem"] >= max(1, min(10, decil_min))]
    if comprou in ("sim", "nao"):
        df = df[df["comprou"] == (comprou == "sim")]
    saida = df[["email", "respondeu", "faixa_pesquisa", "nota_pesquisa", "canal", "temp", "etapa",
                "nota_origem", "decil_origem", "comprou"]].copy()
    saida["respondeu"] = saida["respondeu"].map({1: "sim", 0: "não"})
    saida["comprou"] = saida["comprou"].map({True: "sim", False: "não"})
    saida.columns = ["E-mail", "Respondeu a pesquisa", "Faixa (só pesquisa)", "Nota (só pesquisa, 1-100)", "Canal",
                     "Temperatura", "Etapa", "Nota (com origem, 1-100)", "Decil (com origem, 10 = melhor)", "Comprou"]
    nome = f"score-leads_{launch.code}_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        "﻿" + saida.to_csv(sep=";", index=False),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/pesquisas", response_class=HTMLResponse)
async def pesquisas_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_tf=True)
    tf_data = d["tf"]
    ctx = _base_ctx(request, "pesquisas", "Pesquisas", launch, launches, tf=tf_data,
                    data_errors=d.get("_errors", []))
    return templates.TemplateResponse("pesquisas.html", ctx)


@router.get("/typeform", response_class=HTMLResponse)
async def typeform_page_legacy(request: Request, launch_code: str | None = None):
    """Link antigo — a página foi renomeada pra "Pesquisas" (cobre Typeform + sistema interno)."""
    qs = f"?launch_code={launch_code}" if launch_code else ""
    return RedirectResponse(url=f"/pesquisas{qs}", status_code=307)


@router.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request, launch_code: str | None = None):
    from frontend.db_readers.whatsapp_groups import read_whatsapp_groups, historico_diario  # noqa: PLC0415
    from frontend.db_readers.whatsapp_messages import read_whatsapp_messages  # noqa: PLC0415
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    wa = await run_in_threadpool(read_whatsapp_groups, launch.code if launch else "") if launch else None
    wa_hist = await run_in_threadpool(historico_diario, launch.code if launch else "") if launch else None
    wa_msgs = await run_in_threadpool(read_whatsapp_messages, launch) if launch else None
    launch_cfg = await run_in_threadpool(read_launch_config, launch.code) if launch else {}
    from src.constants import rotulos_blocos_whatsapp  # noqa: PLC0415
    # Aluno × não aluno dos membros — só Black; None fora dela ou sem régua.
    from frontend.db_readers.whatsapp_alunos import read_whatsapp_alunos  # noqa: PLC0415
    wa_alunos_blocos = []          # [(rótulo, resultado)], Vitalícia primeiro: é o que está captando
    if launch:
        from frontend.db_readers.whatsapp_alunos import BLOCOS  # noqa: PLC0415
        for _bloco, _rotulo in BLOCOS.items():
            _res = await run_in_threadpool(read_whatsapp_alunos, launch.code, _bloco)
            if _res and _res.get("total"):
                wa_alunos_blocos.append((_rotulo, _res))
    ctx = _base_ctx(request, "whatsapp", "Grupos de WhatsApp", launch, launches,
                    wa=wa, wa_hist=wa_hist, wa_msgs=wa_msgs, launch_cfg=launch_cfg,
                    wa_alunos_blocos=wa_alunos_blocos,
                    rotulos_blocos=rotulos_blocos_whatsapp(launch.code if launch else None),
                    data_errors=[])
    return templates.TemplateResponse("whatsapp.html", ctx)


@router.get("/crm-campanhas", response_class=HTMLResponse)
async def crm_campanhas_page(request: Request, launch_code: str | None = None):
    launches = await run_in_threadpool(get_launches)
    launch = resolve_launch(launch_code, launches)
    d = await _fetch_all_data(launch, needs_ac_camps=True)
    ac_summary = d["ac_summary"] or AcCampaignSummary()

    ctx = _base_ctx(
        request, "crm_campanhas", "E-mails (CRM) - Campanhas",
        launch, launches,
        ac_summary=ac_summary,
        data_errors=d.get("_errors", []),
    )
    return templates.TemplateResponse("ac_campanhas.html", ctx)
