"""
frontend/services/debriefing.py — Builders de contexto para debriefing.html.
"""
from __future__ import annotations

from typing import Any

from frontend.services.attribution import _merge_google_tipo_sales
from frontend.services.fetch import _launch_cfg

_CLIMA_ORDER = ["Quente", "Frio", "Específico"]
_REMARKETING_SUBETAPAS = ["Lembrete", "Depoimento", "Aulas no Ar", "Replay", "Matrículas Abertas"]
# Duas perguntas diferentes, e confundi-las já custou um número errado:
# `_REMARKETING_SUBETAPAS` é quais chaves de `por_etapa` do Meta/Google compõem o
# *gasto* de Remarketing — o WhatsApp não está lá porque não é campanha de mídia,
# entra separado via `wa_gasto`. Já o *orçamento* vem do wizard, onde o WhatsApp é
# uma etapa como as outras. Somar o gasto do WhatsApp no realizado sem somar a
# verba dele no previsto fazia o Remarketing aparecer estourado (PI-AGO-26, 16/09:
# previsto R$35.076 contra realizado R$69.211, ▲97,3%, quando havia R$115.024
# cadastrados pro WhatsApp — de estouro virou sobra).
_REMARKETING_ETAPAS_ORCAMENTO = _REMARKETING_SUBETAPAS + ["WhatsApp"]

# Faixas da Saúde do Lançamento, da PIOR pra melhor — o índice é o que a trava
# por ROAS limita. "Péssimo" não tem corte de nota: só se chega nele pela trava
# (ROAS < 1x), porque aí a receita líquida não paga nem a mídia.
_SAUDE_FAIXAS = (
    ("Péssimo",   "🔴", "#ef4444"),
    ("Atenção",   "🔴", "#f87171"),
    ("Regular",   "🟠", "#fb923c"),
    ("Bom",       "🟡", "#facc15"),
    ("Excelente", "🟢", "#4ade80"),
)
# nota >= corte  ->  faixa que a nota alcança
_SAUDE_CORTES = ((80, 4), (65, 3), (50, 2), (0, 1))
# ROAS >= corte  ->  faixa MÁXIMA que o rótulo pode assumir (pauta Júlia/Michel,
# 16/09/26): >=3x livre, 2–2,99x no máximo Bom, 1–1,99x no máximo Atenção,
# <1x Péssimo na marra. A cor do número sai da mesma tupla do rótulo — antes o
# template tinha corte próprio (60) e discordava do rótulo (65) na faixa 60-64.
_SAUDE_TETO_ROAS = ((3.0, 4), (2.0, 3), (1.0, 1), (0.0, 0))


def _saude_classificacao(nota: int, roas: float, *, em_andamento: bool, sem_dados: bool) -> dict:
    """Rótulo da Saúde do Lançamento: nota dá a faixa, ROAS dá o teto.

    A nota numérica não muda — o que a trava muda é como ela se chama. Sem
    trava, uma nota alta sustentada por rastreabilidade e eficiência de anúncio
    chamava de "Excelente" um lançamento que devolveu menos de 3x (PI-AGO-26:
    80/100 com ROAS 2,78x).

    As duas guardas vêm antes da trava porque senão ela mente nos extremos:
    carrinho aberto mede um lançamento pela metade (o PES-SET-26 apareceria
    "Péssimo" todo dia até fechar), e sem venda nenhuma não há o que classificar.
    """
    if sem_dados:
        return {"label": "Sem dados", "emoji": "⚪", "cor": "#94a3b8", "travado_por_roas": False}
    if em_andamento:
        return {"label": "Em andamento", "emoji": "⏳", "cor": "#60a5fa", "travado_por_roas": False}
    i_nota = next(i for corte, i in _SAUDE_CORTES if nota >= corte)
    i_teto = next(i for corte, i in _SAUDE_TETO_ROAS if roas >= corte)
    label, emoji, cor = _SAUDE_FAIXAS[min(i_nota, i_teto)]
    return {"label": label, "emoji": emoji, "cor": cor, "travado_por_roas": i_teto < i_nota}


def _build_clima_breakdown(obj: Any, attr: str, leads_key: str = "leads") -> list:
    d = getattr(obj, attr, {}) or {} if obj else {}
    rows = []
    for c in _CLIMA_ORDER:
        v = d.get(c) or {}
        gasto = float(v.get("gasto") or v.get("custo") or 0)
        leads = v.get(leads_key)
        if leads is None:
            leads = v.get("conversoes") or 0
        thruplays = int(v.get("thruplays") or 0)
        views_50 = int(v.get("views_50") or 0)
        # Base do "% viu 50%": no Meta, thruplays é contagem real (ThruPlay),
        # mesma base do numerador. No Google, video_views_50 é impressões ×
        # taxa de quartil da API — dividir por "views" (TrueView, uma base
        # menor e de conceito diferente) passava de 100%; a base correta é
        # impressões (mesmo universo usado pra calcular o numerador).
        impressoes = int(v.get("impressoes") or 0)
        base_50 = impressoes if impressoes > 0 else thruplays
        rows.append({
            "clima": c, "gasto": gasto, "leads": float(leads or 0),
            "thruplays": thruplays, "views_50": views_50,
            "custo_thruplay": (gasto / thruplays) if thruplays > 0 else 0.0,
            "pct_50": (views_50 / base_50 * 100) if base_50 > 0 else 0.0,
        })
    total = sum(r["gasto"] for r in rows) or 1
    for r in rows:
        r["pct"] = r["gasto"] / total * 100 if r["gasto"] > 0 else 0.0
    return rows


def _attach_clima_sales(rows: list, sales_dict: dict | None) -> list:
    sales_dict = sales_dict or {}
    for r in rows:
        s = sales_dict.get(r["clima"]) or {}
        r["vendas"] = int(s.get("vendas") or 0)
        r["faturamento"] = float(s.get("faturamento") or 0)
    return rows


def _attach_clima_variation(curr_rows: list, prev_rows: list) -> list:
    prev_map = {r["clima"]: r for r in prev_rows}
    for r in curr_rows:
        p = prev_map.get(r["clima"]) or {}
        prev_gasto = float(p.get("gasto") or 0)
        r["prev_gasto"] = prev_gasto
        r["var_pct"] = ((r["gasto"] - prev_gasto) / prev_gasto * 100) if prev_gasto > 0 else None
    return curr_rows


def _clima_raw(obj: Any, attr: str, clima: str, leads_key: str = "leads") -> tuple:
    d = (getattr(obj, attr, {}) or {}) if obj else {}
    v = d.get(clima) or {}
    gasto = float(v.get("gasto") or v.get("custo") or 0)
    leads = v.get(leads_key)
    if leads is None:
        leads = v.get("conversoes") or 0
    return gasto, float(leads or 0)


def _sales_raw(sales_dict: dict | None, clima: str) -> tuple:
    s = (sales_dict or {}).get(clima) or {}
    return int(s.get("vendas") or 0), float(s.get("faturamento") or 0)


def _build_leads_detail_table(
    meta: Any, google: Any,
    prev_meta: Any, prev_google: Any,
    sales_attr: Any, prev_sales_attr: Any,
    meta_attr: str = "por_temperatura_captacao",
    google_attr: str = "por_temperatura",
    meta_sales_key: str = "meta_temperatura_sales_por_etapa",
    google_sales_key: str = "google_temperatura_sales_por_etapa",
) -> list:
    """Público × Leads/Investimento/CPL/Conversão/Vendas/ROAS. Usado tanto
    pra "Leads por Público — Captação" (padrão) quanto pra "Performance da
    Qualificação" (attrs *_prequali + sales_key *_temperatura_sales_por_etapa,
    que já vem escopado por etapa — ver _sales_attribution)."""
    def _sales_dict(attr_sales: Any, key: str, etapa: str | None) -> dict:
        d = (attr_sales or {}).get(key) or {}
        return d.get(etapa, {}) if etapa else d

    etapa = "Pré-Qualificação" if "prequali" in meta_attr else "Captação"
    specs = [
        ("FB Quente",     meta,   meta_attr,   "Quente",     "leads",      _sales_dict(sales_attr, meta_sales_key, etapa)),
        ("FB Frio",       meta,   meta_attr,   "Frio",       "leads",      _sales_dict(sales_attr, meta_sales_key, etapa)),
        ("FB Específico", meta,   meta_attr,   "Específico", "leads",      _sales_dict(sales_attr, meta_sales_key, etapa)),
        ("YT Quente",     google, google_attr, "Quente",     "conversoes", _sales_dict(sales_attr, google_sales_key, etapa)),
        ("YT Frio",       google, google_attr, "Frio",       "conversoes", _sales_dict(sales_attr, google_sales_key, etapa)),
        ("YT Específico", google, google_attr, "Específico", "conversoes", _sales_dict(sales_attr, google_sales_key, etapa)),
    ]
    prev_specs = [
        ("FB Quente",     prev_meta,   meta_attr,   "Quente",     "leads",      _sales_dict(prev_sales_attr, meta_sales_key, etapa)),
        ("FB Frio",       prev_meta,   meta_attr,   "Frio",       "leads",      _sales_dict(prev_sales_attr, meta_sales_key, etapa)),
        ("FB Específico", prev_meta,   meta_attr,   "Específico", "leads",      _sales_dict(prev_sales_attr, meta_sales_key, etapa)),
        ("YT Quente",     prev_google, google_attr, "Quente",     "conversoes", _sales_dict(prev_sales_attr, google_sales_key, etapa)),
        ("YT Frio",       prev_google, google_attr, "Frio",       "conversoes", _sales_dict(prev_sales_attr, google_sales_key, etapa)),
        ("YT Específico", prev_google, google_attr, "Específico", "conversoes", _sales_dict(prev_sales_attr, google_sales_key, etapa)),
    ]

    def _calc(specs_list):
        raws = []
        for label, obj, attr, clima, leads_key, sales_dict in specs_list:
            gasto, leads = _clima_raw(obj, attr, clima, leads_key)
            vendas, faturamento = _sales_raw(sales_dict, clima)
            raws.append({"label": label, "gasto": gasto, "leads": leads, "vendas": vendas, "faturamento": faturamento})
        total = sum(r["gasto"] for r in raws) or 1
        for r in raws:
            r["cpl"] = r["gasto"] / r["leads"] if r["leads"] > 0 else 0.0
            r["conversao"] = (r["vendas"] / r["leads"] * 100) if r["leads"] > 0 else 0.0
            r["custo_venda"] = r["gasto"] / r["vendas"] if r["vendas"] > 0 else 0.0
            r["roas"] = r["faturamento"] / r["gasto"] if r["gasto"] > 0 else 0.0
            r["pct"] = r["gasto"] / total * 100 if total > 0 else 0.0
        return raws

    curr_rows = _calc(specs)
    prev_rows = _calc(prev_specs)
    prev_map = {r["label"]: r for r in prev_rows}

    def _pct_change(curr, prev):
        return ((curr - prev) / prev * 100) if prev else None

    for r in curr_rows:
        p = prev_map.get(r["label"]) or {}
        has_prev = bool(p.get("gasto") or p.get("leads"))
        r["has_prev"] = has_prev
        if has_prev:
            r["leads_var"]       = _pct_change(r["leads"], p["leads"])
            r["gasto_var"]       = _pct_change(r["gasto"], p["gasto"])
            r["cpl_var"]         = _pct_change(r["cpl"], p["cpl"])
            r["conversao_var"]   = r["conversao"] - p["conversao"]
            r["vendas_var"]      = _pct_change(r["vendas"], p["vendas"])
            r["custo_venda_var"] = _pct_change(r["custo_venda"], p["custo_venda"])
            r["roas_var"]        = _pct_change(r["roas"], p["roas"])
            r["vendas_prev"]     = p["vendas"]
        else:
            r["leads_var"] = r["gasto_var"] = r["cpl_var"] = r["conversao_var"] = None
            r["vendas_var"] = r["custo_venda_var"] = r["roas_var"] = None
            r["vendas_prev"] = None

    return curr_rows


def _build_rmkt_adsets(meta: Any, google: Any = None, whatsapp: float = 0.0, cfg: dict | None = None) -> list:
    """Lembrete/Depoimento/Aulas no Ar/Replay/Matrículas Abertas — soma Meta +
    Google (mesmas sub-etapas que get_etapa() usa pro total "Remarketing" do
    quadro de cima; sem o Google aqui os dois números não batiam — achado
    16/09/26, PI-AGO-26: topo R$69.211 vs detalhado R$66.208, diferença
    exatamente o gasto do Google nessas sub-etapas, R$3.003,80)."""
    _order = ["Lembrete", "Depoimento", "Aulas no Ar", "Replay", "Matrículas Abertas"]
    m_por = getattr(meta, "por_etapa", {}) or {}
    g_por = (getattr(google, "por_etapa", {}) or {}) if google else {}
    previsto_por_subetapa = {
        et.get("nome"): float(et.get("total") or 0)
        for et in ((cfg or {}).get("etapas") or [])
    }
    rows = []
    for e in _order:
        m_d = m_por.get(e) or {}
        g_d = g_por.get(e) or {}
        gasto = float(m_d.get("gasto") or m_d.get("custo") or 0) + float(g_d.get("custo") or 0)
        leads = int(m_d.get("leads") or 0) + int(float(g_d.get("conversoes") or 0))
        rows.append({
            "adset": e, "gasto": gasto, "leads": leads, "pct": 0.0,
            "previsto": previsto_por_subetapa.get(e, 0.0),
        })
    # O previsto do WhatsApp sai do wizard como o das outras sub-etapas — estava
    # cravado em 0.0, então a linha mostrava "—" mesmo com verba cadastrada.
    # A linha aparece também quando há verba e nenhum gasto ainda: orçamento
    # provisionado e não usado é informação, não ausência de dado.
    wa_previsto = previsto_por_subetapa.get("WhatsApp", 0.0)
    if whatsapp > 0 or wa_previsto > 0:
        rows.append({"adset": "WhatsApp", "gasto": whatsapp, "leads": 0, "pct": 0.0, "previsto": wa_previsto})
    total = sum(r["gasto"] for r in rows) or 1
    for r in rows:
        r["pct"] = r["gasto"] / total * 100 if r["gasto"] > 0 else 0.0
    return rows


def _build_top_ads_captacao(
    meta: Any, google: Any, sales_attr: Any = None, n: int = 5,
    meta_ads_attr: str = "captacao_por_ad", google_ads_attr: str = "anuncios_por_ad",
    etapa: str = "Captação",
) -> dict:
    """Top N anúncios por quantidade de vendas (atribuição UTM por ad_code),
    em 3 recortes: combinado (Meta + Google somados pelo mesmo código ADxxx),
    só Meta, só Google. Padrão é Captação; meta_ads_attr/google_ads_attr=
    "preq_por_ad" + etapa="Pré-Qualificação" reaproveita pra "Top 5 —
    Pré-Qualificação (Meta + Google)".

    Usa por_criativo_por_etapa (não por_criativo) no combinado — o mesmo
    ADxxx pode ter gasto irrisório numa etapa e pesado em outra (ex.: AD127
    no PI-AGO-26: R$0,52 na Pré-Qualificação, R$28mil na Captação); sem
    escopar por etapa, a venda inteira do ad cai em cima do gasto errado e
    o ROAS explode (achado debriefing 14/09/26). Nas listas só-Meta/só-Google
    usa por_criativo_canal_por_etapa — o mesmo ADxxx também pode ter gasto
    pesado numa plataforma e irrisório na outra (ex.: AD174: R$103mil no
    Google vs R$675 no Meta); sem escopar por canal, a tabela "(Meta)"
    herdava as vendas do Google inteiras."""
    por_criativo = (sales_attr or {}).get("por_criativo_por_etapa", {}).get(etapa, {}) or {}
    por_criativo_canal = (sales_attr or {}).get("por_criativo_canal_por_etapa", {}) or {}
    meta_ads = getattr(meta, meta_ads_attr, None) or []
    google_ads = getattr(google, google_ads_attr, None) or []

    def _row(code: str, nome: str, gasto: float, leads: int, vendas_dict: dict) -> dict:
        venda = vendas_dict.get(code, {})
        vendas = int(venda.get("vendas") or 0)
        receita = float(venda.get("faturamento") or 0)
        return {
            "ad_code": code, "nome": nome, "gasto": gasto, "leads": leads,
            "vendas": vendas, "receita": receita,
            "roas": receita / gasto if gasto > 0 else 0.0,
        }

    def _top(ads: list, channel: str) -> list:
        # Agrupa por ad_code ANTES de rankear — o mesmo ADxxx pode ter mais
        # de uma linha na origem (ex.: anúncio duplicado no Meta Ads Manager
        # e o "— Cópia" esquecido no nome); sem agrupar, cada linha herdava
        # as MESMAS vendas/receita inteiras do código (vendas são por
        # ad_code, não por linha), inflando o ROAS de cada fragmento
        # (achado 14/09/26, PI-AGO-26 — AD174 e "AD174 — Cópia" mostravam
        # 809x e 10.543x separados).
        vendas_dict = por_criativo_canal.get(channel, {}).get(etapa, {}) or {}
        acc: dict[str, dict] = {}
        for a in ads:
            code = str(a.get("ad_code") or "").upper()
            if not code:
                continue
            c = acc.setdefault(code, {"nome": a.get("nome"), "gasto": 0.0, "leads": 0})
            c["gasto"] += float(a.get("gasto") or 0)
            c["leads"] += int(a.get("leads") or 0)
            if len(str(a.get("nome") or "")) > len(str(c["nome"] or "")):
                c["nome"] = a.get("nome")
        rows = [_row(code, c["nome"], c["gasto"], c["leads"], vendas_dict) for code, c in acc.items()]
        return sorted(rows, key=lambda x: x["vendas"], reverse=True)[:n]

    combinado_acc: dict[str, dict] = {}
    for a in meta_ads + google_ads:
        code = str(a.get("ad_code") or "").upper()
        if not code:
            continue
        c = combinado_acc.setdefault(code, {"nome": a.get("nome"), "gasto": 0.0, "leads": 0})
        c["gasto"] += float(a.get("gasto") or 0)
        c["leads"] += int(a.get("leads") or 0)
    combinado_rows = sorted(
        (_row(code, c["nome"], c["gasto"], c["leads"], por_criativo) for code, c in combinado_acc.items()),
        key=lambda x: x["vendas"], reverse=True,
    )[:n]

    return {
        "combinado": combinado_rows,
        "meta": _top(meta_ads, "Meta Ads"),
        "google": _top(google_ads, "Google Ads"),
    }


def _enrich_perfil_por_anuncio(
    perfil: dict | None, meta: Any, google: Any, sales_attr: Any = None,
    prev_meta: Any = None, prev_google: Any = None, prev_sales_attr: Any = None,
) -> dict | None:
    """Completa cada linha de perfil_por_anuncio (que só tem ad_code/leads/
    respostas/dist, vindos da pesquisa) com nome, investimento, vendas e ROAS —
    somando Meta + Google quando o mesmo ADxxx roda nas duas plataformas.
    Também marca se o criativo é "antigo" (já rodou no lançamento anterior,
    ou seja, validado) ou "novo" (sem histórico pra comparar) e, quando
    antigo, traz o ROAS do lançamento passado pro mesmo ad_code."""
    if not perfil or not perfil.get("ads"):
        return perfil
    por_criativo = (sales_attr or {}).get("por_criativo", {}) or {}
    prev_por_criativo = (prev_sales_attr or {}).get("por_criativo", {}) or {}
    todos_ads = [
        *(getattr(meta, "preq_por_ad", None) or []),
        *(getattr(meta, "captacao_por_ad", None) or []),
        *(getattr(google, "preq_por_ad", None) or []),
        *(getattr(google, "anuncios_por_ad", None) or []),
    ]
    info: dict[str, dict] = {}
    for a in todos_ads:
        code = str(a.get("ad_code") or "").upper()
        if not code:
            continue
        d = info.setdefault(code, {"nome": a.get("nome"), "gasto": 0.0, "antigo": False})
        d["gasto"] += float(a.get("gasto") or 0)
        if a.get("antigo"):
            d["antigo"] = True

    prev_todos_ads = [
        *(getattr(prev_meta, "preq_por_ad", None) or []),
        *(getattr(prev_meta, "captacao_por_ad", None) or []),
        *(getattr(prev_google, "preq_por_ad", None) or []),
        *(getattr(prev_google, "anuncios_por_ad", None) or []),
    ]
    prev_gasto_por_ad: dict[str, float] = {}
    for a in prev_todos_ads:
        code = str(a.get("ad_code") or "").upper()
        if not code:
            continue
        prev_gasto_por_ad[code] = prev_gasto_por_ad.get(code, 0.0) + float(a.get("gasto") or 0)

    for row in perfil["ads"]:
        code = str(row.get("ad_code") or "").upper()
        d = info.get(code, {})
        row["nome"] = d.get("nome") or code
        row["gasto"] = d.get("gasto") or 0.0
        venda = por_criativo.get(code) or {}
        row["vendas"] = int(venda.get("vendas") or 0)
        row["receita"] = float(venda.get("faturamento") or 0)
        row["roas"] = (row["receita"] / row["gasto"]) if row["gasto"] > 0 else 0.0
        row["antigo"] = bool(d.get("antigo"))
        row["prev_roas"] = None
        if row["antigo"]:
            prev_gasto = prev_gasto_por_ad.get(code) or 0.0
            prev_receita = float((prev_por_criativo.get(code) or {}).get("faturamento") or 0)
            if prev_gasto > 0:
                row["prev_roas"] = prev_receita / prev_gasto
    return perfil


def _build_antigo_novo(meta: Any, google: Any, sales_attr: Any = None) -> dict:
    """Investimento/leads/vendas em anúncios antigos (ADxxx já usado em
    lançamento anterior do mesmo produto) × novos, por etapa. Combina Meta +
    Google; vendas/receita cruzadas por ad_code via atribuição UTM (mesma
    fonte da seção 'Vendas por Público').

    Duas correções (achado debriefing 14/09/26, PI-AGO-26 — chegava a somar
    mais receita que o faturamento total do lançamento):
    1. Usa por_criativo_por_etapa (não por_criativo): o mesmo ADxxx pode ter
       gasto pesado numa etapa e irrisório noutra — sem escopar, a venda
       inteira cai em cima da etapa errada.
    2. Soma vendas/receita UMA VEZ por ad_code (não por linha): o mesmo ADxxx
       aparece em várias linhas quando roda em mais de um conjunto de
       anúncios ou nas duas plataformas — somar por linha multiplicava a
       mesma venda."""
    por_criativo_por_etapa = (sales_attr or {}).get("por_criativo_por_etapa", {}) or {}
    listas = {
        "Pré-Qualificação": [
            *(getattr(meta, "preq_por_ad", None) or []),
            *(getattr(google, "preq_por_ad", None) or []),
        ],
        "Captação": [
            *(getattr(meta, "captacao_por_ad", None) or []),
            *(getattr(google, "anuncios_por_ad", None) or []),
        ],
    }
    out: dict[str, dict] = {}
    for etapa, ads in listas.items():
        if not ads:
            continue
        por_criativo = por_criativo_por_etapa.get(etapa, {}) or {}
        grupos = {
            "antigo": {"gasto": 0.0, "leads": 0, "n": 0, "vendas": 0, "receita": 0.0, "thruview": 0, "views_50": 0, "base_50": 0},
            "novo": {"gasto": 0.0, "leads": 0, "n": 0, "vendas": 0, "receita": 0.0, "thruview": 0, "views_50": 0, "base_50": 0},
        }
        codes_somados = {"antigo": set(), "novo": set()}
        for a in ads:
            key = "antigo" if a.get("antigo") else "novo"
            grupos[key]["gasto"] += float(a.get("gasto") or 0)
            grupos[key]["leads"] += int(a.get("leads") or 0)
            grupos[key]["n"] += 1
            # ThruView (custo/view): contador real no Meta (thruplays); no
            # Google é o video_views (TrueView) — mesmo conceito, campos com
            # nomes diferentes por plataforma.
            eh_meta = "thruplays" in a
            grupos[key]["thruview"] += int(a.get("thruplays") or a.get("video_views") or 0)
            grupos[key]["views_50"] += int(a.get("views_50") or 0)
            # Base do "% viu 50%": no Meta é a mesma ThruPlay (numerador e
            # base já no mesmo contador real); no Google, video_views_50 é
            # impressões × taxa de quartil da API — a base correta é
            # impressões, não video_views (TrueView, universo menor e de
            # conceito diferente, que fazia passar de 100%).
            grupos[key]["base_50"] += int(a.get("thruplays") or 0) if eh_meta else int(a.get("impressoes") or 0)
            code = str(a.get("ad_code") or "").upper()
            if code and code not in codes_somados[key]:
                codes_somados[key].add(code)
                venda = por_criativo.get(code, {})
                grupos[key]["vendas"] += int(venda.get("vendas") or 0)
                grupos[key]["receita"] += float(venda.get("faturamento") or 0)
        total_gasto = grupos["antigo"]["gasto"] + grupos["novo"]["gasto"] or 1
        for g in grupos.values():
            g["cpl"] = g["gasto"] / g["leads"] if g["leads"] > 0 else 0.0
            g["pct"] = g["gasto"] / total_gasto * 100
            g["roas"] = g["receita"] / g["gasto"] if g["gasto"] > 0 else 0.0
            g["custo_thruview"] = g["gasto"] / g["thruview"] if g["thruview"] > 0 else 0.0
            g["pct_50"] = g["views_50"] / g["base_50"] * 100 if g["base_50"] > 0 else 0.0
        out[etapa] = grupos
    return out


def _compute_debriefing_ctx(
    launch: Any,
    previous: Any,
    meta: Any,
    google: Any,
    vendas: Any,
    sales_attr: Any,
    daily: Any,
    hotmart: Any,
    creative_data: Any,
    prev_meta: Any,
    prev_google: Any,
    prev_vendas: Any,
    youtube_aulas: Any = None,
    prev_sales_attr: Any = None,
    tmb: Any = None,
    leads_antigos: Any = None,
    perfil_por_anuncio: Any = None,
    pesquisa_engajamento: Any = None,
    qualidade_regiao: Any = None,
    caminho_comprador: Any = None,
    cadastrados_lancamentos_anteriores: Any = None,
    landing_pages_por_etapa: Any = None,
    leads_x_whatsapp: Any = None,
    vendas_grupos_whatsapp: Any = None,
    disparo_resumo: Any = None,
    ebook_compradores: Any = None,
    hotmart_recompra: Any = None,
    prev_hotmart: Any = None,
    wa_cost: Any = None,
    prev_wa_cost: Any = None,
    hotmart_semana_seguinte: Any = None,
    prev_hotmart_semana_seguinte: Any = None,
    compradores_por_dia_grupo: Any = None,
    prev_compradores_por_dia_grupo: Any = None,
    prev_daily_captacao: Any = None,
    forma_pagamento_entrada: Any = None,
    comparativo_historico: Any = None,
    historico_grande: Any = None,
    whatsapp_groups_resumo: Any = None,
    prev_whatsapp_groups_resumo: Any = None,
    dia1_sales: Any = None,
    prev_dia1_sales: Any = None,
    sorteio: Any = None,
) -> dict:
    def _f(x): return float(x or 0)
    def _i(x): return int(x or 0)

    # Leads e CPL consideram só a etapa de Captação — leads de campanhas de
    # lembrete/remarketing/pré-quali distorcem o CPL real da captação. O
    # investimento total (invest) segue sendo o lançamento inteiro.
    def _captacao(summary) -> dict:
        return (getattr(summary, "por_etapa", None) or {}).get("Captação") or {}

    wa_gasto = _f((wa_cost or {}).get("total_cost_brl"))
    prev_wa_gasto = _f((prev_wa_cost or {}).get("total_cost_brl"))

    # Pessoas nos Grupos WhatsApp (Normal × VIP, pico histórico) e Vendas na
    # 1ª Hora — Resumo Executivo (pauta 15/09/26, ref. slide "Mentoria" do
    # DEBRIEFING 2.0). "Total de Grupos" foi removido da exibição (pedido do
    # usuário, 15/09/26) — a tabela bruta do Supabase ficava incompleta em
    # alguns lançamentos (ex.: PI-ABR-26, onde uma campanha inteira do
    # SendFlow nunca chegou no banco) e não dava pra confiar nesse número
    # sem correção manual por lançamento.
    def _pessoas_grupos_de(resumo):
        n = (resumo or {}).get("normal") or {}
        v = (resumo or {}).get("vip") or {}
        return _i(n.get("total_limpo")), _i(v.get("total_limpo"))

    def _venda_1h_de(dia1):
        for cp in ((dia1 or {}).get("checkpoints") or []):
            if cp.get("hora") == "9h" and not cp.get("pendente"):
                return _i(cp.get("total"))
        return None

    pessoas_grupos_normais, pessoas_grupos_vip = _pessoas_grupos_de(whatsapp_groups_resumo)
    prev_pessoas_grupos_normais, prev_pessoas_grupos_vip = _pessoas_grupos_de(prev_whatsapp_groups_resumo)
    vendas_primeira_hora = _venda_1h_de(dia1_sales)
    prev_vendas_primeira_hora = _venda_1h_de(prev_dia1_sales)

    invest = _f(getattr(meta, "total_gasto", 0)) + _f(getattr(google, "total_custo", 0)) + wa_gasto
    receita = _f(getattr(vendas, "total_receita_liquida", 0)) or _f(getattr(vendas, "total_receita", 0))
    receita_bruta = _f(getattr(vendas, "total_receita_bruta", 0)) or _f(getattr(vendas, "total_receita", 0))
    roas = receita / invest if invest > 0 else 0.0
    roas_bruto = receita_bruta / invest if invest > 0 else 0.0
    total_vendas = _i(getattr(vendas, "total_vendas", 0))
    ticket = _f(getattr(vendas, "total_ticket_medio", 0))

    meta_capt   = _captacao(meta)
    meta_leads  = _i(meta_capt.get("leads"))
    meta_spend  = _f(meta_capt.get("custo"))
    meta_cpl    = meta_spend  / meta_leads  if meta_leads  > 0 else 0.0

    google_capt  = _captacao(google)
    google_leads = int(_f(google_capt.get("conversoes")))
    google_spend = _f(google_capt.get("custo"))
    google_cpl   = google_spend / google_leads if google_leads > 0 else 0.0

    # TikTok — sem integração ainda
    tiktok_leads = 0
    tiktok_spend = 0.0
    tiktok_cpl   = 0.0

    total_leads = meta_leads + google_leads + tiktok_leads
    total_spend_all = meta_spend + google_spend + tiktok_spend
    cpl = total_spend_all / total_leads if total_leads > 0 else 0.0

    prev_invest = _f(getattr(prev_meta, "total_gasto", 0)) + _f(getattr(prev_google, "total_custo", 0)) + prev_wa_gasto
    prev_receita = _f(getattr(prev_vendas, "total_receita_liquida", 0)) or _f(getattr(prev_vendas, "total_receita", 0))
    prev_receita_bruta = _f(getattr(prev_vendas, "total_receita_bruta", 0)) or _f(getattr(prev_vendas, "total_receita", 0))
    prev_roas = prev_receita / prev_invest if prev_invest > 0 else 0.0
    prev_roas_bruto = prev_receita_bruta / prev_invest if prev_invest > 0 else 0.0
    prev_total_vendas = _i(getattr(prev_vendas, "total_vendas", 0))
    prev_ticket = _f(getattr(prev_vendas, "total_ticket_medio", 0))
    prev_meta_capt    = _captacao(prev_meta)
    prev_meta_leads   = _i(prev_meta_capt.get("leads"))
    prev_meta_spend   = _f(prev_meta_capt.get("custo"))
    prev_meta_cpl     = prev_meta_spend  / prev_meta_leads  if prev_meta_leads  > 0 else 0.0
    prev_google_capt  = _captacao(prev_google)
    prev_google_leads = int(_f(prev_google_capt.get("conversoes")))
    prev_google_spend = _f(prev_google_capt.get("custo"))
    prev_google_cpl   = prev_google_spend / prev_google_leads if prev_google_leads > 0 else 0.0
    prev_total_leads  = prev_meta_leads + prev_google_leads
    prev_cpl = (prev_meta_spend + prev_google_spend) / prev_total_leads if prev_total_leads > 0 else 0.0

    fontes_leads = [
        {"fonte": "Meta",   "icon": "ti-brand-meta",   "color": "#1877F2",
         "spend": meta_spend,   "leads": meta_leads,   "cpl": meta_cpl,
         "prev_leads": prev_meta_leads,   "prev_cpl": prev_meta_cpl,   "has_data": meta_leads > 0},
        {"fonte": "Google", "icon": "ti-brand-google", "color": "#EA4335",
         "spend": google_spend, "leads": google_leads, "cpl": google_cpl,
         "prev_leads": prev_google_leads, "prev_cpl": prev_google_cpl, "has_data": google_leads > 0},
        {"fonte": "TikTok", "icon": "ti-brand-tiktok", "color": "#000000",
         "spend": tiktok_spend, "leads": tiktok_leads, "cpl": tiktok_cpl,
         "prev_leads": 0, "prev_cpl": 0.0, "has_data": False},
    ]

    def get_etapa(m, g, name, whatsapp=0.0):
        # "Remarketing" não existe como chave própria em por_etapa — Meta/Google
        # classificam essas campanhas nas sub-etapas (Lembrete, Depoimento, etc.),
        # então somamos todas elas para compor o total de Remarketing. O WhatsApp
        # também é 100% remarketing (só dispara pra quem já é lead), então entra
        # no mesmo bucket.
        names = _REMARKETING_SUBETAPAS if name == "Remarketing" else [name]
        m_por = (getattr(m, "por_etapa", {}) or {}) if m else {}
        g_por = (getattr(g, "por_etapa", {}) or {}) if g else {}
        m_c = m_l = g_c = g_l = 0
        for n in names:
            m_d = m_por.get(n) or {}
            g_d = g_por.get(n) or {}
            m_c += _f(m_d.get("custo") or m_d.get("gasto"))
            g_c += _f(g_d.get("custo"))
            m_l += _i(m_d.get("leads"))
            g_l += _i(g_d.get("conversoes"))
        total = m_c + g_c + whatsapp
        return {"nome": name, "invest": total, "meta": m_c, "google": g_c, "tiktok": 0.0, "whatsapp": whatsapp, "leads": m_l + g_l}

    def _previsto_por_etapa(cfg: dict) -> dict:
        """Verba planejada por etapa (cadastrada no wizard) — Pré-Qualificação e
        Captação têm campo próprio; Remarketing soma o 'total' de cada
        sub-etapa provisionada na aba Evento, **incluindo o WhatsApp**, que é o
        que `get_etapa` já soma do lado do realizado."""
        cfg = cfg or {}
        remarketing_previsto = sum(
            _f(et.get("total")) for et in (cfg.get("etapas") or [])
            if et.get("nome") in _REMARKETING_ETAPAS_ORCAMENTO
        )
        return {
            "Pré-Qualificação": _f(cfg.get("meta_investimento_pre_quali")),
            "Captação": _f(cfg.get("meta_investimento_captacao")),
            "Remarketing": remarketing_previsto,
        }

    cfg = _launch_cfg(launch.code) if launch else {}
    previsto_map = _previsto_por_etapa(cfg)

    base = invest or 1.0
    etapas = []
    for name in ["Pré-Qualificação", "Captação", "Remarketing"]:
        e = get_etapa(meta, google, name, whatsapp=wa_gasto if name == "Remarketing" else 0.0)
        e["pct"] = e["invest"] / base * 100
        e["previsto"] = previsto_map.get(name, 0.0)
        etapas.append(e)

    prev_etapas: list = []
    if prev_meta or prev_google:
        prev_cfg = _launch_cfg(previous.code) if previous else {}
        prev_previsto_map = _previsto_por_etapa(prev_cfg)
        prev_base = prev_invest or 1.0
        for name in ["Pré-Qualificação", "Captação", "Remarketing"]:
            e = get_etapa(prev_meta, prev_google, name, whatsapp=prev_wa_gasto if name == "Remarketing" else 0.0)
            e["pct"] = e["invest"] / prev_base * 100
            e["previsto"] = prev_previsto_map.get(name, 0.0)
            prev_etapas.append(e)

    top_geral  = ((creative_data or {}).get("rows")        or [])[:5]
    top_meta   = ((creative_data or {}).get("meta_rows")   or [])[:5]
    top_google = ((creative_data or {}).get("google_rows") or [])[:5]

    # Mescla timelines Hotmart + TMB por data
    _hm_tl = getattr(hotmart, "timeline", []) or []
    _tmb_tl = getattr(tmb, "timeline", []) or []
    _merged: dict = {}
    for t in _hm_tl:
        d = t.get("data", "")
        _merged[d] = {"data": d, "data_str": t.get("data_str", d), "vendas": _i(t.get("vendas")), "faturamento": float(t.get("faturamento") or 0)}
    for t in _tmb_tl:
        d = t.get("data", "")
        if d in _merged:
            _merged[d]["vendas"] += _i(t.get("vendas"))
            _merged[d]["faturamento"] += float(t.get("faturamento") or 0)
        else:
            _merged[d] = {"data": d, "data_str": t.get("data_str", d), "vendas": _i(t.get("vendas")), "faturamento": float(t.get("faturamento") or 0)}
    timeline_raw = sorted(_merged.values(), key=lambda x: x["data"])
    cfg: dict = {}
    prev_cfg: dict = {}
    c_start = c_end = ""
    if launch:
        cfg = _launch_cfg(launch.code)
        c_start = cfg.get("carrinho_start_date") or ""
        c_end   = cfg.get("carrinho_end_date")   or ""

        def _fmt_periodo(s, e):
            try:
                from datetime import date
                ds = date.fromisoformat(str(s))
                de = date.fromisoformat(str(e))
                if ds.year == de.year:
                    return f"{ds.strftime('%d/%m')} a {de.strftime('%d/%m/%Y')}"
                return f"{ds.strftime('%d/%m/%Y')} a {de.strftime('%d/%m/%Y')}"
            except Exception:
                return f"{s} a {e}"

        periodo_atual = _fmt_periodo(c_start, c_end) if c_start and c_end else ""
        if previous:
            prev_cfg = _launch_cfg(previous.code)
            ps = prev_cfg.get("carrinho_start_date") or ""
            pe = prev_cfg.get("carrinho_end_date") or ""
            periodo_prev = _fmt_periodo(ps, pe) if ps and pe else ""
        else:
            periodo_prev = ""
        if c_start and c_end:
            timeline = [t for t in timeline_raw if c_start <= t.get("data", "") <= c_end]
        else:
            timeline = timeline_raw
    else:
        timeline = timeline_raw
        periodo_atual = ""
        periodo_prev  = ""

    max_vendas_dia = max((_i(t.get("vendas")) for t in timeline), default=1) or 1

    # Vendas por Período (pauta debriefing legado) — divide as vendas em 3
    # janelas não sobrepostas: Antecipadas (entre a abertura da página do
    # carrinho e a abertura oficial/aula que anuncia), Carrinho Aberto
    # (oficial) e Semana Seguinte (7 dias corridos após o fechamento).
    # Lançamento atual usa timeline_raw (Hotmart+TMB); o anterior usa só
    # Hotmart, porque não temos a timeline diária do TMB de lançamentos
    # passados (só o total agregado).
    def _sum_janela(rows, start, end):
        if not (start and end):
            return {"vendas": 0, "faturamento": 0.0}
        v = sum(_i(t.get("vendas")) for t in rows if start <= t.get("data", "") <= end)
        f = sum(float(t.get("faturamento") or 0) for t in rows if start <= t.get("data", "") <= end)
        return {"vendas": v, "faturamento": f}

    def _fmt_intervalo(s, e):
        """dd/mm ou dd/mm/aaaa a dd/mm/aaaa (data curta pra célula de tabela) —
        pauta 15/09/26, usuário pediu as datas de cada período na tabela
        "Vendas por Período", que só mostrava o rótulo antes."""
        from datetime import date as _date
        try:
            ds = _date.fromisoformat(str(s))
            de = _date.fromisoformat(str(e))
        except Exception:
            return ""
        if ds.year == de.year:
            return f"{ds.strftime('%d/%m')} a {de.strftime('%d/%m')}"
        return f"{ds.strftime('%d/%m/%Y')} a {de.strftime('%d/%m/%Y')}"

    def _vendas_por_periodo(rows, c_start_, c_end_, abertura_oficial):
        from datetime import date, timedelta
        antecipadas = {"vendas": 0, "faturamento": 0.0}
        antecipadas_periodo = ""
        aberto_start = c_start_
        if c_start_ and abertura_oficial and abertura_oficial > c_start_:
            try:
                fim_ant = (date.fromisoformat(str(abertura_oficial)) - timedelta(days=1)).isoformat()
                antecipadas = _sum_janela(rows, c_start_, fim_ant)
                antecipadas_periodo = _fmt_intervalo(c_start_, fim_ant)
                aberto_start = abertura_oficial
            except Exception:
                pass
        aberto = _sum_janela(rows, aberto_start, c_end_)
        aberto_periodo = _fmt_intervalo(aberto_start, c_end_) if aberto_start and c_end_ else ""
        semana = {"vendas": 0, "faturamento": 0.0}
        semana_periodo = ""
        if c_end_:
            try:
                sem_start = (date.fromisoformat(str(c_end_)) + timedelta(days=1)).isoformat()
                sem_end   = (date.fromisoformat(str(c_end_)) + timedelta(days=7)).isoformat()
                semana = _sum_janela(rows, sem_start, sem_end)
                semana_periodo = _fmt_intervalo(sem_start, sem_end)
            except Exception:
                pass
        total = {
            "vendas": antecipadas["vendas"] + aberto["vendas"] + semana["vendas"],
            "faturamento": antecipadas["faturamento"] + aberto["faturamento"] + semana["faturamento"],
        }
        return {
            "antecipadas": antecipadas, "aberto": aberto, "semana_seguinte": semana, "total": total,
            "antecipadas_periodo": antecipadas_periodo, "aberto_periodo": aberto_periodo, "semana_periodo": semana_periodo,
        }

    def _semana_seguinte_de(hotmart_obj) -> dict:
        rows = getattr(hotmart_obj, "timeline", []) or []
        v = sum(_i(t.get("vendas")) for t in rows)
        f = sum(float(t.get("faturamento") or 0) for t in rows)
        return {"vendas": v, "faturamento": f}

    def _com_semana_seguinte(vpp: dict, semana: dict) -> dict:
        if not vpp:
            return vpp
        vpp["semana_seguinte"] = semana
        vpp["total"] = {
            "vendas": vpp["antecipadas"]["vendas"] + vpp["aberto"]["vendas"] + semana["vendas"],
            "faturamento": vpp["antecipadas"]["faturamento"] + vpp["aberto"]["faturamento"] + semana["faturamento"],
        }
        return vpp

    vendas_por_periodo = {}
    prev_vendas_por_periodo = {}
    if launch:
        vendas_por_periodo = _vendas_por_periodo(timeline_raw, c_start, c_end, cfg.get("abertura_oficial_carrinho") or "")
        # A janela padrão do lançamento termina em carrinho_end_date, então
        # "Semana Seguinte" (7 dias depois) nunca aparece na timeline normal
        # — usa a consulta extra feita só pra esse bloco.
        if hotmart_semana_seguinte is not None:
            vendas_por_periodo = _com_semana_seguinte(vendas_por_periodo, _semana_seguinte_de(hotmart_semana_seguinte))
        if previous:
            prev_hm_tl = getattr(prev_hotmart, "timeline", []) or []
            prev_vendas_por_periodo = _vendas_por_periodo(
                prev_hm_tl, prev_cfg.get("carrinho_start_date") or "", prev_cfg.get("carrinho_end_date") or "",
                prev_cfg.get("abertura_oficial_carrinho") or "",
            )
            if prev_hotmart_semana_seguinte is not None:
                prev_vendas_por_periodo = _com_semana_seguinte(prev_vendas_por_periodo, _semana_seguinte_de(prev_hotmart_semana_seguinte))

    # Detalhamento por Dia de Captação (pauta debriefing legado) — Investimento/
    # Vendas/CPL/ROAS por dia, em semanas de 7 dias, comparado dia-a-dia (por
    # posição — "dia 1 da Captação" vs "dia 1 da Captação anterior", não por
    # data de calendário) com o lançamento anterior.
    def _com_iso(rows, start_iso):
        if not rows or not start_iso:
            return [dict(r, iso=None) for r in (rows or [])]
        try:
            from datetime import date as _date
            ano = _date.fromisoformat(str(start_iso)).year
        except Exception:
            return [dict(r, iso=None) for r in rows]
        out = []
        mes_ant = None
        for r in rows:
            iso = None
            try:
                dd, mm = str(r.get("date", "")).split("/")
                mm_i = int(mm)
                if mes_ant is not None and mm_i < mes_ant - 1:
                    ano += 1
                mes_ant = mm_i
                iso = f"{ano:04d}-{mm_i:02d}-{int(dd):02d}"
            except Exception:
                pass
            out.append({**r, "iso": iso})
        return out

    def _detalhamento_dia_captacao(rows, vendas_por_dia: dict):
        vendas_by_date = (vendas_por_dia or {}).get("por_dia") or {}
        out = []
        for r in rows:
            v = vendas_by_date.get(r.get("iso"), {"vendas": 0, "faturamento": 0.0})
            invest = _f(r.get("total_gasto"))
            out.append({
                "date": r.get("date"), "weekday": r.get("weekday"),
                "invest": invest, "vendas": v["vendas"],
                "cpl": _f(r.get("total_cpl")),
                "roas": (v["faturamento"] / invest) if invest > 0 else 0.0,
            })
        return out

    detalhamento_captacao: list = []
    prev_detalhamento_captacao: list = []
    if launch:
        from frontend.db_readers.leads import read_vendas_por_dia_cadastro  # noqa: PLC0415
        # Vendas por dia de CADASTRO do lead (não data da compra) — quem vira
        # lead num dia de Captação só compra semanas depois, no carrinho
        # aberto, então cruzar por data de venda dava quase sempre zero.
        vendas_por_dia_cadastro = read_vendas_por_dia_cadastro(launch.code, vendas)
        rows_com_iso = _com_iso(daily or [], cfg.get("captacao_start_date") or "")
        detalhamento_captacao = _detalhamento_dia_captacao(rows_com_iso, vendas_por_dia_cadastro)
        if previous and prev_daily_captacao:
            prev_vendas_por_dia_cadastro = read_vendas_por_dia_cadastro(previous.code, prev_vendas)
            prev_rows_com_iso = _com_iso(prev_daily_captacao, prev_cfg.get("captacao_start_date") or "")
            prev_detalhamento_captacao = _detalhamento_dia_captacao(prev_rows_com_iso, prev_vendas_por_dia_cadastro)
    # Semanas de 7 dias, cada linha com o dia correspondente (mesma posição)
    # do lançamento anterior anexado em "prev".
    detalhamento_semanas: list = []
    for i in range(0, len(detalhamento_captacao), 7):
        semana = detalhamento_captacao[i:i + 7]
        for j, row in enumerate(semana):
            idx = i + j
            row["prev"] = prev_detalhamento_captacao[idx] if idx < len(prev_detalhamento_captacao) else None
        detalhamento_semanas.append(semana)

    # Curva diária de % de vendas do lançamento que são Boleto Parcelado
    # (TMB) — usa timeline_raw (todo o lançamento, não só carrinho aberto).
    boleto_parcelado_curva: list = []
    if launch:
        tmb_por_dia: dict = {}
        for t in (getattr(tmb, "timeline", []) or []):
            tmb_por_dia[t.get("data", "")] = tmb_por_dia.get(t.get("data", ""), 0) + _i(t.get("vendas"))
        for t in timeline_raw:
            d = t.get("data", "")
            total_dia = _i(t.get("vendas"))
            tmb_dia = tmb_por_dia.get(d, 0)
            boleto_parcelado_curva.append({
                "data": d, "data_str": t.get("data_str", d),
                "pct": (tmb_dia / total_dia * 100) if total_dia > 0 else 0.0,
            })

    # Cada método com o número do lançamento anterior do mesmo método, pra
    # badge de comparação no card. Casa pelo rótulo já normalizado pelo
    # _metodo_pagamento_pt, então "CREDIT_CARD" de um lançamento antigo casa
    # com "Cartão de Crédito" do atual.
    prev_por_metodo = {
        (p.get("metodo") or ""): _i(p.get("qtd"))
        for p in (getattr(prev_hotmart, "pagamentos", []) or [])
    }
    pagamentos_hm = [
        {**p, "prev_qtd": prev_por_metodo.get(p.get("metodo") or "", 0)}
        for p in (getattr(hotmart, "pagamentos", []) or [])
    ]
    total_tmb  = _i(getattr(vendas, "tmb_vendas",    0))
    total_hm_v = _i(getattr(vendas, "hotmart_vendas", 0))
    prev_total_tmb = _i(getattr(prev_vendas, "tmb_vendas", 0))

    # Vendas por faixa de parcelamento, somando as faixas de cada método.
    # Estas 4 categorias são mutuamente exclusivas e somam o total de vendas,
    # então a pizza é legítima. A versão antiga tinha uma 5ª barra,
    # "Recorrência", vinda de `recorrencia_qtd` — que não conta recorrência
    # (ver hotmart.py) e somava linhas já descartadas: as 5 categorias davam
    # 1.586 num lançamento de 1.013 vendas, e a pizza saía sobre esse
    # denominador. Removida em 17/09/26; não repor sem refazer o critério.
    def _faixas(pgtos, tmb: int) -> list[tuple[str, int]]:
        return [
            ("À vista", sum(_i(p.get("a_vista")) for p in pgtos)),
            ("Parcelado em 12x", sum(_i(p.get("parcelado_12x")) for p in pgtos)),
            ("Outras parcelas", sum(_i(p.get("parcelado_outros")) for p in pgtos)),
            ("Entrada (boleto parcelado)", tmb),
        ]

    prev_faixas = dict(_faixas(getattr(prev_hotmart, "pagamentos", []) or [], prev_total_tmb))
    vendas_forma = [
        {"label": lbl, "qtd": qtd, "prev_qtd": prev_faixas.get(lbl, 0)}
        for lbl, qtd in _faixas(pagamentos_hm, total_tmb)
    ]

    def _find_pay(metodo_keywords):
        for p in pagamentos_hm:
            m = (p.get("metodo") or "").lower()
            if any(k in m for k in metodo_keywords):
                return p
        return None

    boleto_hm = _find_pay(["boleto"])
    cartao_hm = _find_pay(["crédito", "credito", "cartão", "cartao", "credit"])
    pix_hm    = _find_pay(["pix"])

    max_peak_yt = max((getattr(a, "peak_concurrent", 0) or 0 for a in (youtube_aulas or [])), default=0)

    meta_segmentos = sorted(
        [{"segmento": k, **v} for k, v in (getattr(meta, "por_segmento", {}) or {}).items()],
        key=lambda x: _f(x.get("gasto")), reverse=True,
    )[:12] if meta else []

    google_segmentos = sorted(
        [{"segmento": k, **v} for k, v in (getattr(google, "por_segmento", {}) or {}).items()],
        key=lambda x: _f(x.get("gasto")), reverse=True,
    )[:12] if google else []

    meta_clima = _build_clima_breakdown(meta, "por_temperatura_captacao")
    prev_meta_clima = _build_clima_breakdown(prev_meta, "por_temperatura_captacao")
    _attach_clima_variation(meta_clima, prev_meta_clima)
    _attach_clima_sales(meta_clima, (sales_attr or {}).get("meta_por_temperatura"))

    google_clima = _build_clima_breakdown(google, "por_temperatura", leads_key="conversoes")
    prev_google_clima = _build_clima_breakdown(prev_google, "por_temperatura", leads_key="conversoes")
    _attach_clima_variation(google_clima, prev_google_clima)
    _attach_clima_sales(google_clima, (sales_attr or {}).get("google_por_temperatura"))

    meta_preq_clima = _build_clima_breakdown(meta, "por_temperatura_prequali")
    prev_meta_preq_clima = _build_clima_breakdown(prev_meta, "por_temperatura_prequali")
    _attach_clima_variation(meta_preq_clima, prev_meta_preq_clima)

    google_preq_clima = _build_clima_breakdown(google, "por_temperatura_prequali", leads_key="conversoes")
    prev_google_preq_clima = _build_clima_breakdown(prev_google, "por_temperatura_prequali", leads_key="conversoes")
    _attach_clima_variation(google_preq_clima, prev_google_preq_clima)

    meta_preq_etapa = (getattr(meta, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    prev_meta_preq_etapa = (getattr(prev_meta, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    google_preq_etapa = (getattr(google, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    prev_google_preq_etapa = (getattr(prev_google, "por_etapa", {}) or {}).get("Pré-Qualificação") or {}
    prequali_invest = {
        "meta": {
            "total": _f(meta_preq_etapa.get("custo")),
            "prev_total": _f(prev_meta_preq_etapa.get("custo")),
            "data_inicio": meta_preq_etapa.get("data_inicio") or "",
            "climas": meta_preq_clima,
        },
        "google": {
            "total": _f(google_preq_etapa.get("custo")),
            "prev_total": _f(prev_google_preq_etapa.get("custo")),
            "data_inicio": google_preq_etapa.get("data_inicio") or "",
            "climas": google_preq_clima,
        },
    }
    prequali_invest["total"] = prequali_invest["meta"]["total"] + prequali_invest["google"]["total"]
    prequali_invest["prev_total"] = prequali_invest["meta"]["prev_total"] + prequali_invest["google"]["prev_total"]

    # Top 5 anúncios (por leads) da Pré-Qualificação, por plataforma — TikTok
    # fica vazio até existir integração.
    # Nome: o do Facebook vem completo (descreve o criativo); o do Google/
    # YouTube costuma só repetir o ADxxx sem descrição — usa o nome do Meta
    # como preferência quando o mesmo ad_code roda nas duas plataformas.
    _meta_nome_por_code: dict[str, str] = {}
    for _a in (getattr(meta, "preq_por_ad", None) or []) + (getattr(meta, "captacao_por_ad", None) or []):
        _code = str(_a.get("ad_code") or "").upper()
        if _code and _code not in _meta_nome_por_code and _a.get("nome"):
            _meta_nome_por_code[_code] = _a["nome"]

    def _preq_top_ads_view(ads: list, prefer_meta_nome: bool = False, n: int = 5) -> list:
        out = []
        for a in ads[:n]:
            row = dict(a)
            if prefer_meta_nome:
                nome_meta = _meta_nome_por_code.get(str(row.get("ad_code") or "").upper())
                if nome_meta:
                    row["nome"] = nome_meta
            # ThruView: contador real no Meta (thruplays) ou video_views no
            # Google (TrueView). "Viu 50%" divide sobre impressões (mesma
            # base usada em "Investimento em Pré-Qualificação") — no Google,
            # video_views_50 é estimativa por quartil de impressões, não
            # contagem real, então dividir por thruview/views passava de 100%.
            thruview = int(row.get("thruplays") or row.get("video_views") or 0)
            views_50 = int(row.get("views_50") or 0)
            impressoes = int(row.get("impressoes") or 0)
            base_50 = impressoes if impressoes > 0 else thruview
            row["thruview"] = thruview
            row["pct_50"] = (views_50 / base_50 * 100) if base_50 > 0 else 0.0
            out.append(row)
        return out

    preq_top_ads = {
        "meta":   _preq_top_ads_view(getattr(meta, "preq_por_ad", None) or []),
        "google": _preq_top_ads_view(getattr(google, "preq_por_ad", None) or [], prefer_meta_nome=True),
        "tiktok": [],
    }

    leads_detail_table = _build_leads_detail_table(
        meta, google, prev_meta, prev_google, sales_attr, prev_sales_attr,
    )
    # "Performance da Qualificação" — mesma tabela público×leads/CPL/ROAS,
    # escopada pra Pré-Qualificação (pauta 10/09/26, ref. Slide 8 do
    # DEBRIEFING 2.0). Sales key *_temperatura_sales_por_etapa já vem
    # filtrado por etapa em _sales_attribution.
    leads_detail_table_prequali = _build_leads_detail_table(
        meta, google, prev_meta, prev_google, sales_attr, prev_sales_attr,
        meta_attr="por_temperatura_prequali", google_attr="por_temperatura_prequali",
        meta_sales_key="meta_temperatura_sales_por_etapa",
        google_sales_key="google_temperatura_sales_por_etapa",
    )

    meta_temp_sales        = (sales_attr or {}).get("meta_por_temperatura",   {}) or {}
    prev_meta_temp_sales   = (prev_sales_attr or {}).get("meta_por_temperatura", {}) or {}
    google_temp_sales      = (sales_attr or {}).get("google_por_temperatura", {}) or {}
    prev_google_temp_sales = (prev_sales_attr or {}).get("google_por_temperatura", {}) or {}
    google_tipo_sales      = _merge_google_tipo_sales((sales_attr or {}).get("google_por_tipo_campanha"))
    prev_google_tipo_sales = _merge_google_tipo_sales((prev_sales_attr or {}).get("google_por_tipo_campanha"))
    max_mt = max((_i(v.get("vendas")) for v in meta_temp_sales.values()),   default=1) or 1
    max_gt = max((_i(v.get("vendas")) for v in google_tipo_sales.values()), default=1) or 1

    # Saúde do Lançamento 2.0 — pesos propostos pelo usuário (16/09/26), veio
    # da versão anterior (4 fatores de 25 pts) pra 7 fatores com pesos
    # diferentes. "Atingimento da meta de faturamento" (precisa de
    # meta_faturamento cadastrada no wizard) e "Volume de vendas" (precisa do
    # lançamento anterior do mesmo produto) ficam de fora da nota quando o
    # dado de referência não existe — o peso deles é redistribuído
    # proporcionalmente entre os fatores que TÊM dado, em vez de contar como
    # 0 (não cadastrar a meta não é "lançamento ruim", é "sem referência").
    _saude_resumo = (creative_data or {}).get("resumo") or {}
    _saude_rows = (creative_data or {}).get("rows") or []
    _saude_rastreados = _i(_saude_resumo.get("compradores_com_utm"))
    _saude_total_buyers = _i(_saude_resumo.get("total_compradores")) or total_vendas
    saude_pct_rastreado = round(_saude_rastreados / _saude_total_buyers * 100, 1) if _saude_total_buyers > 0 else 0.0
    saude_ads_total = len(_saude_rows)
    saude_ads_com_venda = len([r for r in _saude_rows if _f(r.get("vendas")) > 0])
    saude_custo_venda = invest / total_vendas if total_vendas > 0 else 0.0
    saude_conversao_funil = (total_vendas / total_leads * 100) if total_leads > 0 else 0.0
    saude_meta_faturamento = _f(cfg.get("meta_faturamento")) or None
    saude_atingimento_meta = (receita / saude_meta_faturamento * 100) if saude_meta_faturamento else None

    _SAUDE_PESOS = {"roas": 50, "meta_fat": 15, "cac": 10, "conv": 10, "ads": 5, "vol": 5, "rastr": 5}
    saude_score_roas = min(_SAUDE_PESOS["roas"], round(roas / 3 * _SAUDE_PESOS["roas"], 1))
    saude_score_meta_fat = (
        min(_SAUDE_PESOS["meta_fat"], round(saude_atingimento_meta / 100 * _SAUDE_PESOS["meta_fat"], 1))
        if saude_atingimento_meta is not None else None
    )
    # CAC saudável é o que sobra margem em relação ao ticket — 10 pts se
    # custo por venda = R$0, 0 pts se custo por venda >= ticket (ponto de
    # empate, sem contar custo do produto/operação).
    saude_score_cac = (
        round(_SAUDE_PESOS["cac"] * max(0.0, 1 - saude_custo_venda / ticket), 1)
        if ticket > 0 and total_vendas > 0 else 0.0
    )
    # Conversão do funil: nota cheia a partir de 3% (leads → vendas) —
    # referência de mercado pra lançamento de curso, ajustável se o usuário
    # achar o corte errado.
    saude_score_conv = round(min(1.0, saude_conversao_funil / 3) * _SAUDE_PESOS["conv"], 1)
    saude_score_ads = round(saude_ads_com_venda / saude_ads_total * _SAUDE_PESOS["ads"], 1) if saude_ads_total > 0 else 0.0
    saude_score_vol = (
        round(min(1.0, total_vendas / prev_total_vendas) * _SAUDE_PESOS["vol"], 1)
        if prev_total_vendas > 0 else None
    )
    saude_score_rastr = round(saude_pct_rastreado / 100 * _SAUDE_PESOS["rastr"], 1)

    _saude_scores = {
        "roas": saude_score_roas, "meta_fat": saude_score_meta_fat, "cac": saude_score_cac,
        "conv": saude_score_conv, "ads": saude_score_ads, "vol": saude_score_vol, "rastr": saude_score_rastr,
    }
    _saude_peso_disponivel = sum(p for k, p in _SAUDE_PESOS.items() if _saude_scores[k] is not None)
    saude_score = int(round(
        sum(s for s in _saude_scores.values() if s is not None) / _saude_peso_disponivel * 100
    )) if _saude_peso_disponivel > 0 else 0

    # Rótulo (trava por ROAS + guardas) — regra em `_saude_classificacao`.
    # "Em andamento" é o carrinho que ainda não fechou; sem data de carrinho
    # cadastrada cai na data final do lançamento em dim_lancamentos.
    from datetime import date as _date  # noqa: PLC0415
    _fim_carrinho = str(c_end or (getattr(launch, "data_fim", "") if launch else "") or "")
    saude_em_andamento = bool(not _fim_carrinho or _fim_carrinho[:10] >= _date.today().isoformat())
    saude_sem_dados = receita <= 0 and total_vendas <= 0
    saude_faixa = _saude_classificacao(
        saude_score, roas, em_andamento=saude_em_andamento, sem_dados=saude_sem_dados,
    )

    return {
        "has_data": bool(meta or google or vendas),
        "has_prev": bool(previous and (prev_meta or prev_google or prev_vendas)),
        "prev_code": previous.code if previous else "",
        "periodo_atual": periodo_atual, "periodo_prev": periodo_prev,
        # KPIs
        "invest": invest, "wa_gasto": wa_gasto, "receita": receita, "roas": roas,
        "receita_bruta": receita_bruta, "roas_bruto": roas_bruto,
        "total_vendas": total_vendas, "ticket": ticket,
        "total_leads": total_leads, "cpl": cpl,
        "fontes_leads": fontes_leads,
        # Saúde do lançamento
        "saude_score": saude_score, "saude_pesos": _SAUDE_PESOS,
        "saude_faixa": saude_faixa, "saude_em_andamento": saude_em_andamento,
        "saude_score_roas": saude_score_roas, "saude_score_meta_fat": saude_score_meta_fat,
        "saude_score_cac": saude_score_cac, "saude_score_conv": saude_score_conv,
        "saude_score_ads": saude_score_ads, "saude_score_vol": saude_score_vol,
        "saude_score_rastr": saude_score_rastr,
        "saude_custo_venda": saude_custo_venda, "saude_conversao_funil": saude_conversao_funil,
        "saude_meta_faturamento": saude_meta_faturamento, "saude_atingimento_meta": saude_atingimento_meta,
        "saude_pct_rastreado": saude_pct_rastreado,
        "saude_ads_com_venda": saude_ads_com_venda, "saude_ads_total": saude_ads_total,
        # Prev KPIs
        "prev_invest": prev_invest, "prev_receita": prev_receita, "prev_roas": prev_roas,
        "prev_receita_bruta": prev_receita_bruta, "prev_roas_bruto": prev_roas_bruto,
        "prev_total_vendas": prev_total_vendas, "prev_ticket": prev_ticket,
        "prev_total_leads": prev_total_leads, "prev_cpl": prev_cpl,
        # Etapas
        "etapas": etapas, "prev_etapas": prev_etapas,
        # Top ads
        "top_geral": top_geral, "top_meta": top_meta, "top_google": top_google,
        # Daily breakdown
        "daily": daily or [],
        # Timeline vendas (Hotmart)
        "timeline": timeline, "max_vendas_dia": max_vendas_dia,
        # Vendas por Período (antecipadas / carrinho aberto / semana seguinte)
        "vendas_por_periodo": vendas_por_periodo, "prev_vendas_por_periodo": prev_vendas_por_periodo,
        # Compradores por dia que entraram no grupo (Pré-Quali x Captação)
        "compradores_por_dia_grupo": compradores_por_dia_grupo,
        "prev_compradores_por_dia_grupo": prev_compradores_por_dia_grupo,
        # Detalhamento por Dia de Captação (Investimento/Vendas/CPL/ROAS)
        "detalhamento_semanas": detalhamento_semanas,
        # Forma de Pagamento da Entrada (Boleto Parcelado / TMB)
        "forma_pagamento_entrada": forma_pagamento_entrada,
        "boleto_parcelado_curva": boleto_parcelado_curva,
        # Comparativo de Vendas (Comercial x Orgânico) multi-lançamento
        "comparativo_historico": comparativo_historico or [],
        # Tabela histórica grande multi-lançamento
        "historico_grande": historico_grande or [],
        # Pessoas nos Grupos WhatsApp e Vendas na 1ª Hora — Resumo Executivo
        "pessoas_grupos_normais": pessoas_grupos_normais,
        "pessoas_grupos_vip": pessoas_grupos_vip,
        "vendas_primeira_hora": vendas_primeira_hora,
        "prev_pessoas_grupos_normais": prev_pessoas_grupos_normais,
        "prev_pessoas_grupos_vip": prev_pessoas_grupos_vip,
        "prev_vendas_primeira_hora": prev_vendas_primeira_hora,
        # Pagamentos
        "pagamentos_hm": pagamentos_hm, "total_tmb": total_tmb,
        "vendas_forma": vendas_forma,
        "total_hm": total_hm_v, "total_vendas_pay": total_tmb + total_hm_v,
        "boleto_hm": boleto_hm, "cartao_hm": cartao_hm, "pix_hm": pix_hm,
        # Audiences (captação only)
        "meta_segmentos": meta_segmentos, "google_segmentos": google_segmentos,
        "meta_clima": meta_clima, "google_clima": google_clima,
        "prequali_invest": prequali_invest,
        "preq_top_ads": preq_top_ads,
        "top_ads_captacao": _build_top_ads_captacao(meta, google, sales_attr),
        "top_ads_prequali": _build_top_ads_captacao(
            meta, google, sales_attr, meta_ads_attr="preq_por_ad", google_ads_attr="preq_por_ad",
            etapa="Pré-Qualificação",
        ),
        "leads_detail_table": leads_detail_table,
        "leads_detail_table_prequali": leads_detail_table_prequali,
        # Detalhamento dos públicos (categoria de adset) por clima — Captação Meta
        "publicos_captacao": {
            c: v for c, v in (
                (c, (getattr(meta, "por_publico_captacao", {}) or {}).get(c))
                for c in _CLIMA_ORDER
            ) if v
        },
        # Idem, Google Ads (audiências reais da API, sem categorização por nome)
        "publicos_captacao_google": {
            c: v for c, v in (
                (c, (getattr(google, "por_publico_captacao", {}) or {}).get(c))
                for c in _CLIMA_ORDER
            ) if v
        },
        "rmkt_adsets": _build_rmkt_adsets(meta, google, whatsapp=wa_gasto, cfg=cfg),
        "prev_rmkt_adsets": _build_rmkt_adsets(prev_meta, prev_google, whatsapp=prev_wa_gasto, cfg=_launch_cfg(previous.code) if previous else None),
        # Sales por temperatura/tipo
        "meta_temp_sales": meta_temp_sales, "google_tipo_sales": google_tipo_sales,
        "prev_meta_temp_sales": prev_meta_temp_sales, "prev_google_tipo_sales": prev_google_tipo_sales,
        "google_temp_sales": google_temp_sales, "prev_google_temp_sales": prev_google_temp_sales,
        "clima_order": _CLIMA_ORDER,
        "max_mt": max_mt, "max_gt": max_gt,
        "youtube_aulas": youtube_aulas or [],
        "max_peak_yt": max_peak_yt,
        # Compradores × histórico de lead (novo/antigo/sem cadastro)
        "leads_antigos": leads_antigos,
        # Perfil do lead por anúncio (top 5 × pesquisa)
        "perfil_por_anuncio": _enrich_perfil_por_anuncio(
            perfil_por_anuncio, meta, google, sales_attr,
            prev_meta=prev_meta, prev_google=prev_google, prev_sales_attr=prev_sales_attr,
        ),
        # Engajamento da pesquisa (respostas × base de leads)
        "pesquisa_engajamento": pesquisa_engajamento,
        # Sorteio — participação por aula (Google Forms) × base de leads
        "sorteio": sorteio,
        # Comercial × IA × Orgânico (sck Hotmart / utm_source TMB)
        "vendas_por_canal": getattr(vendas, "por_canal", {}) or {},
        # Antigo × novo (ADxxx já usado em lançamento anterior do produto)
        "antigo_novo": _build_antigo_novo(meta, google, sales_attr),
        # Qualidade por estado (Meta invest/leads + compradores/receita)
        "qualidade_regiao": qualidade_regiao,
        # Caminho do comprador — funil unificado por pessoa (lead→grupo→pesquisa→compra)
        "caminho_comprador": (caminho_comprador or {}).get("resumo"),
        # Compradores que já estavam cadastrados em lançamentos anteriores
        "cadastrados_lancamentos_anteriores": cadastrados_lancamentos_anteriores,
        # Landing pages que mais converteram (GA4), por etapa
        "landing_pages_preq": (landing_pages_por_etapa or {}).get("Pré-Qualificação") or [],
        "landing_pages_capt": (landing_pages_por_etapa or {}).get("Captação") or [],
        # Leads (Active Campaign) × pessoas nos grupos de WhatsApp
        "leads_x_whatsapp": leads_x_whatsapp,
        "vendas_grupos_whatsapp": vendas_grupos_whatsapp,
        "disparo_resumo": disparo_resumo,
        "ebook_compradores": ebook_compradores,
        "hotmart_recompra": hotmart_recompra,
        # Oferta & bônus — preenchido manualmente no wizard de configuração
        "oferta_descricao": cfg.get("produto_nome"),
        "oferta_preco_vista": cfg.get("produto_preco_vista"),
        "oferta_preco_parcelado": cfg.get("produto_preco_parcelado"),
        "oferta_parcela_cartao": cfg.get("oferta_parcela_cartao"),
        "oferta_parcela_boleto": cfg.get("oferta_parcela_boleto"),
        "oferta_carrinho_start": cfg.get("carrinho_start_date"),
        "oferta_carrinho_end": cfg.get("carrinho_end_date"),
    }
