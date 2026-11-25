"""
frontend/db_readers/perpetuo.py — Perpétuo (tráfego pago contínuo).

4 verticais: Mestre em Questões (TJ-SP / INSS / Banco do Brasil) + Planner.
Campanhas always-on, sem janela de datas fixa — identificadas pela tag
[perpétuo] no nome (ver etl/launch_resolver.py) e classificadas num
pseudo-lançamento (ex: PERPETUO-PMQ-TJSP). De propósito NÃO tem linha em
dim_lancamentos: não é um lançamento de verdade, não deve aparecer no
seletor de lançamentos — só é usado como chave de agrupamento aqui.

Suporta seletor de período (7/30/90 dias) e comparação com o período
anterior de mesma duração, no mesmo padrão de instagram_detail.py.
"""
from __future__ import annotations

from datetime import date, timedelta

from src.periodo import resolver_periodo

from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine, _get_users_engine
from frontend.services.attribution import _extract_ad_code
from frontend.db_readers._vendas_comum import (
    _HOTMART_STATUS_APROVADO,
    HOTMART_IDS_PERPETUO_POR_VERTICAL as _IDS,
    HOTMART_EDITORA_IDS_PERPETUO_POR_VERTICAL as _IDS_ED,
    PRODUTOR_EDITORA,
    _hm_data_sql,
    _parcela_unica_info,
)

logger = get_logger("db")

VERTICALS: dict[str, dict] = {
    "pmq-tjsp": {"codigo": "PERPETUO-PMQ-TJSP", "nome": "Mestre em Questões — TJ-SP",
                 "hotmart": _IDS["pmq-tjsp"], "hotmart_editora": _IDS_ED["pmq-tjsp"]},
    "pmq-inss": {"codigo": "PERPETUO-PMQ-INSS", "nome": "Mestre em Questões — INSS",
                 "hotmart": _IDS["pmq-inss"], "hotmart_editora": _IDS_ED["pmq-inss"]},
    "pmq-pbb":  {"codigo": "PERPETUO-PMQ-PBB",  "nome": "Mestre em Questões — Banco do Brasil",
                 "hotmart": _IDS["pmq-pbb"], "hotmart_editora": _IDS_ED["pmq-pbb"]},
    "planner":  {"codigo": "PERPETUO-PLANNER",  "nome": "Planner",
                 "hotmart": _IDS["planner"], "hotmart_editora": _IDS_ED["planner"]},
}


def _pct_delta(curr: float, prev: float) -> float | None:
    if not prev:
        return None
    return round((curr - prev) / prev * 100, 1)


def _meta_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT date, ad_name, adset_name, spend, impressions, clicks, leads, "
            "video_views_3s, video_views_25, video_views_50, video_views_75, video_views_100, video_thruplays "
            "FROM meta_ads_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _google_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT date, ad_name, cost, impressions, clicks, conversions, "
            "video_views, video_views_25, video_views_50, video_views_75, video_views_100 "
            "FROM google_ads_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


def _google_audience_rows(conn, codigo: str, start: date, end: date):
    return conn.execute(
        text(
            "SELECT audience_name, ad_group_name, impressions, clicks, cost, conversions "
            "FROM google_ads_audiences_daily WHERE lancamento_codigo = :codigo AND date BETWEEN :start AND :end"
        ),
        {"codigo": codigo, "start": start, "end": end},
    ).fetchall()


# Receita do perpétuo = LÍQUIDO de venda APROVADA, como no resto do sistema. Até 21/10/26 somava
# `valor_de_compra_com_impostos` (o que o cliente pagou, parcelamento incluído) de QUALQUER status —
# reembolso e cancelamento entravam. Nas vendas de 2026 `valor_de_compra_sem_impostos` já é o líquido
# do produtor; nas antigas o líquido está em `faturamento_liquido`.
_VALOR_LIQUIDO_SQL = (
    "COALESCE(NULLIF(replace(faturamento_liquido,',','.'),'')::numeric, "
    "NULLIF(replace(valor_de_compra_sem_impostos,',','.'),'')::numeric, 0)"
)


def _ultimo_dia_com_gasto(codigo: str) -> date | None:
    """Último dia com gasto da vertical em qualquer plataforma (None se nunca teve)."""
    try:
        with _get_engine().connect() as conn:
            return conn.execute(
                text(
                    "SELECT MAX(d) FROM ("
                    "SELECT MAX(date) AS d FROM meta_ads_daily WHERE lancamento_codigo = :codigo AND spend > 0 "
                    "UNION ALL "
                    "SELECT MAX(date) FROM google_ads_daily WHERE lancamento_codigo = :codigo AND cost > 0) x"
                ),
                {"codigo": codigo},
            ).scalar()
    except Exception:
        logger.exception("read_perpetuo: falha ao buscar o último dia com gasto de %s", codigo)
        return None


def _vendas(produtos: list[str], start: date, end: date, produtos_editora: list[str] | None = None) -> dict:
    """Vendas Hotmart dos produtos da vertical no período.

    **Não é venda atribuída ao anúncio** — é toda venda do produto na janela.
    O perpétuo vende direto, sem captura de lead: o comprador não tem UTM desta
    campanha (o que existe em `leads` é o cadastro antigo dele, de um
    lançamento, e creditar aquilo seria pior que não creditar), e o `src` da
    Hotmart chega vazio porque os anúncios não o passam no link de checkout.
    Enquanto o `src` não for configurado, o número aqui é **teto**: inclui
    orgânico, e-mail e régua. A página diz isso na tela.

    Vive no banco OPERACIONAL e soma DUAS contas da Hotmart: a Aprovasim (`hotmart_clean_oficial`, pelos IDs
    de `produtos`) e a Brabo Editora (`hotmart_editora_clean_oficial`, pelos IDs de `produtos_editora`, só linhas
    do produtor Brabo Editora — as da Aprovasim que a tabela traz já estão na principal). Devolve também a
    parte da Editora (`vendas_editora`/`receita_editora`) para o total da empresa não contá-la duas vezes.
    """
    vazio = {"vendas": 0, "receita": 0.0, "vendas_editora": 0, "receita_editora": 0.0}
    if not produtos and not produtos_editora:
        return vazio
    data_sql = _hm_data_sql("data_da_transacao")
    valor = _VALOR_LIQUIDO_SQL
    base = ("SELECT COUNT(*) AS vendas, COALESCE(SUM({valor}),0) AS receita FROM {tabela} "
            "WHERE codigo_do_produto = ANY(:ids) AND status_da_transacao = ANY(:ok){extra} "
            "AND {data} BETWEEN :start AND :end")
    ok = list(_HOTMART_STATUS_APROVADO)
    saida = dict(vazio)
    try:
        with _get_users_engine().connect() as conn:
            if produtos:
                r = conn.execute(text(base.format(valor=valor, tabela="hotmart_clean_oficial", extra="", data=data_sql)),
                                 {"ids": produtos, "ok": ok, "start": start, "end": end}).fetchone()
                saida["vendas"], saida["receita"] = int(r[0] or 0), float(r[1] or 0.0)
            if produtos_editora:
                r = conn.execute(text(base.format(valor=valor, tabela="hotmart_editora_clean_oficial",
                                                  extra=" AND produtor_a = :produtor", data=data_sql)),
                                 {"ids": produtos_editora, "ok": ok, "produtor": PRODUTOR_EDITORA,
                                  "start": start, "end": end}).fetchone()
                saida["vendas_editora"], saida["receita_editora"] = int(r[0] or 0), float(r[1] or 0.0)
    except Exception:
        logger.exception("read_perpetuo: falha ao ler vendas dos produtos %s / editora %s", produtos, produtos_editora)
        return vazio
    saida["vendas"] += saida["vendas_editora"]
    saida["receita"] += saida["receita_editora"]
    return saida


# ── Quebra das vendas: sem vendedor × comercial, e preço cheio × com desconto ─────────────────────────────
# Vendas do perpétuo misturam duas origens: a compra direta (anúncio, orgânico, e-mail, régua) e o cross sell dos
# vendedores do Comercial. A venda é do comercial quando a oferta (`codigo_do_preco`) está em `comercial_ofertas`
# com código AT, ou quando a transação tem atribuição aprovada em `comercial_atribuicoes` (mesma regra da
# área /comercial). O resto é "sem vendedor" — e continua sendo teto de venda do anúncio.
_LIMITE_DESCONTO = 0.97   # preço pago abaixo de 97% do preço de referência = com desconto
_MIN_VENDAS_REFERENCIA = 5


def _num(v) -> float:
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else 0.0
    except ValueError:
        return 0.0


def classificar_vendas(linhas: list[dict], ofertas: dict[str, str], atribuicoes: dict[str, str]) -> dict:
    """Separa as vendas em sem vendedor × comercial (por vendedor) e em preço cheio × com desconto.

    Não existe preço de lista no banco, e a Hotmart não tem cupom nessas vendas (o desconto vem como OFERTA de preço
    menor do mesmo produto). Então o preço de referência de cada produto é o MAIOR preço praticado de forma
    relevante no período (aparece em pelo menos 10% das vendas do produto, mínimo 3). Venda abaixo de 97% dele é
    "com desconto". Cobrança repetida (parcela 2+) não tem preço próprio: conta no canal, fora do preço. Produto com
    menos de 5 vendas com preço não tem referência e conta como preço cheio.
    """
    itens = []
    for l in linhas:
        por_parcela, rep, _c, parc = _parcela_unica_info(l)
        pago = _num(l.get("pago"))
        preco = None if rep or pago <= 0 else (pago * max(1, parc) if por_parcela else pago)
        at = atribuicoes.get(str(l.get("transacao"))) or ofertas.get(str(l.get("preco_id") or ""))
        itens.append({"produto_id": str(l.get("produto_id")), "produto": l.get("produto") or "", "at": at,
                      "preco_nome": l.get("preco_nome") or "", "preco": preco, "receita": _num(l.get("liquido"))})

    referencia: dict[str, float] = {}
    por_produto: dict[str, list[float]] = {}
    for i in itens:
        if i["preco"] is not None:
            por_produto.setdefault(i["produto_id"], []).append(round(i["preco"]))
    for pid, precos in por_produto.items():
        if len(precos) < _MIN_VENDAS_REFERENCIA:
            continue
        contagem: dict[float, int] = {}
        for pr in precos:
            contagem[pr] = contagem.get(pr, 0) + 1
        piso = max(3, 0.10 * len(precos))
        relevantes = [pr for pr, n in contagem.items() if n >= piso]
        if relevantes:
            referencia[pid] = float(max(relevantes))

    def vazio() -> dict:
        return {"vendas": 0, "receita": 0.0, "cheio": 0, "desconto": 0, "receita_desconto": 0.0}

    canais = {"sem_vendedor": vazio(), "comercial": vazio()}
    vendedores: dict[str, dict] = {}
    produtos: dict[str, dict] = {}
    ofertas_desc: dict[tuple, dict] = {}
    perda = 0.0
    for i in itens:
        ref = referencia.get(i["produto_id"])
        desconto = bool(ref and i["preco"] is not None and i["preco"] < _LIMITE_DESCONTO * ref)
        alvos = [canais["comercial" if i["at"] else "sem_vendedor"]]
        if i["at"]:
            alvos.append(vendedores.setdefault(i["at"], vazio()))
        alvos.append(produtos.setdefault(i["produto_id"], dict(vazio(), produto=i["produto"], referencia=ref)))
        for a in alvos:
            a["vendas"] += 1
            a["receita"] += i["receita"]
            if desconto:
                a["desconto"] += 1
                a["receita_desconto"] += i["receita"]
            else:
                a["cheio"] += 1
        if desconto:
            perda += ref - i["preco"]
            o = ofertas_desc.setdefault((i["produto_id"], i["preco_nome"], round(i["preco"])),
                                        {"produto": i["produto"], "oferta": i["preco_nome"] or "(sem nome)",
                                         "preco": round(i["preco"]), "referencia": ref, "vendas": 0})
            o["vendas"] += 1

    def arredonda(d: dict) -> dict:
        d["receita"] = round(d["receita"], 2)
        d["receita_desconto"] = round(d["receita_desconto"], 2)
        return d

    total = vazio()
    for c in canais.values():
        for k in total:
            total[k] += c[k]
    return {
        "total": arredonda(total),
        "canais": {k: arredonda(v) for k, v in canais.items()},
        "vendedores": sorted(({"at": k, **arredonda(v)} for k, v in vendedores.items()), key=lambda x: -x["vendas"]),
        "produtos": sorted((arredonda(v) for v in produtos.values()), key=lambda x: -x["vendas"]),
        "descontos": sorted(ofertas_desc.values(), key=lambda x: -x["vendas"]),
        "perda_desconto": round(perda, 2),
        "limite_desconto_pct": int(_LIMITE_DESCONTO * 100),
    }


_COLS_QUEBRA = ("codigo_da_transacao AS transacao, codigo_do_produto AS produto_id, produto, codigo_do_preco AS preco_id, "
                "nome_deste_preco AS preco_nome, valor_de_compra_sem_impostos AS pago, tipo_de_cobranca, "
                "quantidade_de_cobrancas, quantidade_total_de_parcelas, codigo_do_produto, codigo_do_preco, ")


def _quebra_vendas(produtos: list[str], start: date, end: date, produtos_editora: list[str] | None = None) -> dict | None:
    """Linhas de venda da vertical no período (mesmo recorte de `_vendas`: soma das duas contas) classificadas por
    `classificar_vendas`. None em falha — a página só não mostra a quebra."""
    if not produtos and not produtos_editora:
        return None
    data_sql = _hm_data_sql("data_da_transacao")
    ok = list(_HOTMART_STATUS_APROVADO)
    base = ("SELECT " + _COLS_QUEBRA + _VALOR_LIQUIDO_SQL + " AS liquido FROM @TABELA@ "
            "WHERE codigo_do_produto = ANY(:ids) AND status_da_transacao = ANY(:ok)@EXTRA@ "
            "AND " + data_sql + " BETWEEN :start AND :end")
    linhas: list[dict] = []
    try:
        with _get_users_engine().connect() as conn:
            if produtos:
                r = conn.execute(text(base.replace("@TABELA@", "hotmart_clean_oficial").replace("@EXTRA@", "")),
                                 {"ids": produtos, "ok": ok, "start": start, "end": end})
                linhas += [dict(x._mapping) for x in r]
            if produtos_editora:
                r = conn.execute(text(base.replace("@TABELA@", "hotmart_editora_clean_oficial").replace("@EXTRA@", " AND produtor_a = :produtor")),
                                 {"ids": produtos_editora, "ok": ok, "produtor": PRODUTOR_EDITORA, "start": start, "end": end})
                linhas += [dict(x._mapping) for x in r]
            ofertas = {r[0]: r[1] for r in conn.execute(text("SELECT codigo_do_preco, codigo_at FROM comercial_ofertas")) if r[1]}
            atribuicoes = {r[0]: r[1] for r in conn.execute(text(
                "SELECT transacao, vendedor_codigo FROM comercial_atribuicoes WHERE status = 'aprovada' AND vendedor_codigo IS NOT NULL"))}
    except Exception:
        logger.exception("read_perpetuo: falha ao montar a quebra das vendas")
        return None
    return classificar_vendas(linhas, ofertas, atribuicoes)


def _vendas_por_dia(produtos: list[str], start: date, end: date, produtos_editora: list[str] | None = None) -> dict:
    """Mesmo recorte de `_vendas` (mesmas contas, status e valor líquido), aberto por dia.

    Devolve {date: (vendas, receita)}. A soma dos dias bate com o cartão "Vendas do produto" de propósito:
    o gráfico diário é o mesmo número, só que distribuído no período. Falha devolve {} (o gráfico some).
    """
    if not produtos and not produtos_editora:
        return {}
    data_sql = _hm_data_sql("data_da_transacao")
    base = ("SELECT {data} AS dia, COUNT(*), COALESCE(SUM({valor}),0) FROM {tabela} "
            "WHERE codigo_do_produto = ANY(:ids) AND status_da_transacao = ANY(:ok){extra} "
            "AND {data} BETWEEN :start AND :end GROUP BY 1")
    ok = list(_HOTMART_STATUS_APROVADO)
    saida: dict[date, tuple[int, float]] = {}

    def _somar(linhas):
        for dia, n, receita in linhas:
            if dia is None:
                continue
            v, r = saida.get(dia, (0, 0.0))
            saida[dia] = (v + int(n or 0), r + float(receita or 0))

    try:
        with _get_users_engine().connect() as conn:
            if produtos:
                _somar(conn.execute(text(base.format(data=data_sql, valor=_VALOR_LIQUIDO_SQL,
                                                     tabela="hotmart_clean_oficial", extra="")),
                                    {"ids": produtos, "ok": ok, "start": start, "end": end}).fetchall())
            if produtos_editora:
                _somar(conn.execute(text(base.format(data=data_sql, valor=_VALOR_LIQUIDO_SQL,
                                                     tabela="hotmart_editora_clean_oficial",
                                                     extra=" AND produtor_a = :produtor")),
                                    {"ids": produtos_editora, "ok": ok, "produtor": PRODUTOR_EDITORA,
                                     "start": start, "end": end}).fetchall())
    except Exception:
        logger.exception("read_perpetuo: falha ao ler vendas por dia de %s / editora %s", produtos, produtos_editora)
        return {}
    return saida


def _serie_diaria(start: date, end: date, vendas_dia: dict, meta_rows, google_rows) -> list[dict]:
    """Um ponto por dia do período (dia sem venda entra com zero): vendas, faturamento e investimento."""
    invest: dict[date, float] = {}
    for r in meta_rows:
        invest[r.date] = invest.get(r.date, 0.0) + float(r.spend or 0)
    for r in google_rows:
        invest[r.date] = invest.get(r.date, 0.0) + float(r.cost or 0)
    serie, dia = [], start
    while dia <= end:
        n, receita = vendas_dia.get(dia, (0, 0.0))
        serie.append({"dia": dia.isoformat(), "vendas": n, "receita": round(receita, 2),
                      "invest": round(invest.get(dia, 0.0), 2)})
        dia += timedelta(days=1)
    return serie


def _meta_totals(rows) -> dict:
    return {
        "spend": sum(float(r.spend or 0) for r in rows),
        "impressions": sum(r.impressions or 0 for r in rows),
        "clicks": sum(r.clicks or 0 for r in rows),
        "leads": sum(r.leads or 0 for r in rows),
    }


def _google_totals(rows) -> dict:
    return {
        "cost": sum(float(r.cost or 0) for r in rows),
        "impressions": sum(r.impressions or 0 for r in rows),
        "clicks": sum(r.clicks or 0 for r in rows),
        "conversions": sum(float(r.conversions or 0) for r in rows),
    }


def _meta_criativos(rows) -> list[dict]:
    by_ad: dict[str, dict] = {}
    for r in rows:
        code = _extract_ad_code(r.ad_name) or (r.ad_name or "")
        d = by_ad.setdefault(code, {
            "ad_code": code, "ad_name": r.ad_name, "spend": 0.0, "impressions": 0,
            "views_3s": 0, "thruplays": 0, "views_50": 0, "views_100": 0,
        })
        d["spend"] += float(r.spend or 0)
        d["impressions"] += r.impressions or 0
        d["views_3s"] += r.video_views_3s or 0
        d["thruplays"] += r.video_thruplays or 0
        d["views_50"] += r.video_views_50 or 0
        d["views_100"] += r.video_views_100 or 0
    out = []
    for d in by_ad.values():
        d["hook_rate"] = round(d["views_3s"] / d["impressions"] * 100, 2) if d["impressions"] else 0
        d["hold_rate"] = round(d["thruplays"] / d["views_3s"] * 100, 2) if d["views_3s"] else 0
        d["custo_por_thruplay"] = round(d["spend"] / d["thruplays"], 4) if d["thruplays"] else None
        out.append(d)
    return sorted(out, key=lambda d: -d["spend"])


def _google_criativos(rows) -> list[dict]:
    by_ad: dict[str, dict] = {}
    for r in rows:
        code = _extract_ad_code(r.ad_name) or (r.ad_name or "")
        d = by_ad.setdefault(code, {
            "ad_code": code, "ad_name": r.ad_name, "cost": 0.0, "impressions": 0,
            "views": 0, "views_50": 0, "views_100": 0,
        })
        d["cost"] += float(r.cost or 0)
        d["impressions"] += r.impressions or 0
        d["views"] += r.video_views or 0
        d["views_50"] += r.video_views_50 or 0
        d["views_100"] += r.video_views_100 or 0
    out = []
    for d in by_ad.values():
        d["cpv"] = round(d["cost"] / d["views"], 4) if d["views"] else None
        d["completion_rate"] = round(d["views_100"] / d["views"] * 100, 2) if d["views"] else 0
        out.append(d)
    return sorted(out, key=lambda d: -d["cost"])


def _meta_publico(rows) -> list[dict]:
    """Meta não tem tabela de interesse/público por ad set — agrupa pelo
    nome do ad set, que já carrega a segmentação (mesma leitura manual já
    feita no levantamento da Distribuição Felipe Graton, só automatizada)."""
    by_adset: dict[str, dict] = {}
    for r in rows:
        name = r.adset_name or "(sem ad set)"
        d = by_adset.setdefault(name, {"adset_name": name, "spend": 0.0, "impressions": 0, "leads": 0})
        d["spend"] += float(r.spend or 0)
        d["impressions"] += r.impressions or 0
        d["leads"] += r.leads or 0
    return sorted(by_adset.values(), key=lambda d: -d["spend"])


def _google_publico(rows) -> list[dict]:
    by_audience: dict[str, dict] = {}
    for r in rows:
        name = r.audience_name or "(sem público)"
        d = by_audience.setdefault(name, {"audience_name": name, "spend": 0.0, "impressions": 0, "conversions": 0.0})
        d["spend"] += float(r.cost or 0)
        d["impressions"] += r.impressions or 0
        d["conversions"] += float(r.conversions or 0)
    return sorted(by_audience.values(), key=lambda d: -d["spend"])


def read_perpetuo(vertical: str, days: int = 30, compare: bool = False, inicio=None, fim=None) -> dict | None:
    info = VERTICALS.get(vertical)
    if not info:
        return None
    codigo = info["codigo"]

    start, end, days, personalizado = resolver_periodo(days, inicio, fim)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)

    try:
        with _get_engine().connect() as conn:
            meta_rows = _meta_rows(conn, codigo, start, end)
            google_rows = _google_rows(conn, codigo, start, end)
            google_aud_rows = _google_audience_rows(conn, codigo, start, end)
            prev_meta_rows = _meta_rows(conn, codigo, prev_start, prev_end) if compare else []
            prev_google_rows = _google_rows(conn, codigo, prev_start, prev_end) if compare else []
    except Exception:
        logger.exception("read_perpetuo: falha para %s", vertical)
        return None

    # Sem dado no período: separa "vertical pausada" (já teve gasto) de "campanha ainda não entra no ETL".
    ultimo_gasto = None
    if not meta_rows and not google_rows:
        ultimo_gasto = _ultimo_dia_com_gasto(codigo)

    meta_totals = _meta_totals(meta_rows)
    google_totals = _google_totals(google_rows)
    vendas = _vendas(info.get("hotmart") or [], start, end, info.get("hotmart_editora"))
    investimento_total = meta_totals["spend"] + google_totals["cost"]
    leads_total = meta_totals["leads"] + google_totals["conversions"]

    result = {
        "vertical": vertical,
        "nome": info["nome"],
        "no_data": not meta_rows and not google_rows,
        "ultimo_gasto": ultimo_gasto.isoformat() if ultimo_gasto else None,
        "days": days,
        "personalizado": personalizado,
        "compare": compare,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "investimento_meta": meta_totals["spend"],
        "investimento_google": google_totals["cost"],
        "investimento_total": investimento_total,
        "leads_meta": meta_totals["leads"],
        "conversoes_google": google_totals["conversions"],
        "leads_total": leads_total,
        "cpl": round(investimento_total / leads_total, 2) if leads_total else None,
        # Venda do PRODUTO no período, não venda atribuída ao anúncio — ver _vendas().
        "vendas": vendas["vendas"],
        "receita": round(vendas["receita"], 2),
        "cpa": round(investimento_total / vendas["vendas"], 2) if vendas["vendas"] else None,
        "roas": round(vendas["receita"] / investimento_total, 2) if investimento_total else None,
        "vendas_atribuidas": False,
        "quebra_vendas": _quebra_vendas(info.get("hotmart") or [], start, end, info.get("hotmart_editora")),
        "serie_diaria": _serie_diaria(
            start, end,
            _vendas_por_dia(info.get("hotmart") or [], start, end, info.get("hotmart_editora")),
            meta_rows, google_rows),
        "criativos_meta": _meta_criativos(meta_rows),
        "criativos_google": _google_criativos(google_rows),
        "publico_meta": _meta_publico(meta_rows),
        "publico_google": _google_publico(google_aud_rows),
    }

    if compare:
        prev_meta_totals = _meta_totals(prev_meta_rows)
        prev_google_totals = _google_totals(prev_google_rows)
        prev_investimento_total = prev_meta_totals["spend"] + prev_google_totals["cost"]
        prev_vendas = _vendas(info.get("hotmart") or [], prev_start, prev_end, info.get("hotmart_editora"))
        prev_leads_total = prev_meta_totals["leads"] + prev_google_totals["conversions"]
        result["prev_range_start"] = prev_start.isoformat()
        result["prev_range_end"] = prev_end.isoformat()
        # Valores absolutos do período anterior: o Resumo soma as 4 verticais, e delta em % não se soma.
        result["prev"] = {"investimento_total": prev_investimento_total, "leads_total": prev_leads_total,
                          "vendas": prev_vendas["vendas"], "receita": prev_vendas["receita"]}
        prev_cpa = (prev_investimento_total / prev_vendas["vendas"]) if prev_vendas["vendas"] else 0.0
        prev_roas = (prev_vendas["receita"] / prev_investimento_total) if prev_investimento_total else 0.0
        result["deltas"] = {
            "roas": _pct_delta(result["roas"] or 0.0, prev_roas),
            "investimento_total": _pct_delta(investimento_total, prev_investimento_total),
            "leads_total": _pct_delta(leads_total, prev_leads_total),
            "vendas": _pct_delta(vendas["vendas"], prev_vendas["vendas"]),
            "receita": _pct_delta(vendas["receita"], prev_vendas["receita"]),
            "cpa": _pct_delta(result["cpa"] or 0.0, prev_cpa),
        }

    return result


def read_perpetuo_resumo(days: int = 30, compare: bool = False, inicio=None, fim=None) -> dict:
    """Painel executivo do perpétuo: as 4 verticais somadas no período do seletor.

    Monta em cima de `read_perpetuo` de cada vertical, então os números batem com as páginas dos produtos
    (mesma ressalva: venda do produto, não atribuída ao anúncio — custo por venda e ROAS são teto).
    Devolve o mesmo formato de período de `read_perpetuo` (o macro `seletor_periodo` usa), mais
    `verticais` (uma linha por vertical, na ordem de VERTICALS), `serie_diaria` (soma por dia, com a
    venda de cada vertical em `por_vertical`) e, com `compare`, `deltas`.
    """
    linhas, falhas = [], []
    for slug, info in VERTICALS.items():
        d = read_perpetuo(slug, days, compare, inicio, fim)
        if not d:
            falhas.append(info["nome"])
            continue
        linhas.append({"slug": slug, "d": d})
    if not linhas:
        return {"erro": True, "verticais": [], "serie_diaria": []}
    base = linhas[0]["d"]

    def soma(chave, fonte=None):
        return sum(((l["d"].get(fonte) or {}) if fonte else l["d"]).get(chave) or 0 for l in linhas)

    inv, vendas, receita, leads = soma("investimento_total"), soma("vendas"), soma("receita"), soma("leads_total")
    serie: dict[str, dict] = {}
    for l in linhas:
        for p in l["d"].get("serie_diaria") or []:
            s = serie.setdefault(p["dia"], {"dia": p["dia"], "vendas": 0, "receita": 0.0, "invest": 0.0, "por_vertical": {}})
            s["vendas"] += p["vendas"]
            s["receita"] = round(s["receita"] + p["receita"], 2)
            s["invest"] = round(s["invest"] + p["invest"], 2)
            if p["vendas"]:
                s["por_vertical"][l["d"]["nome"]] = p["vendas"]

    out = {
        "erro": False,
        "falhas": falhas,
        "days": base["days"], "personalizado": base["personalizado"], "compare": compare,
        "range_start": base["range_start"], "range_end": base["range_end"],
        "investimento_meta": soma("investimento_meta"), "investimento_google": soma("investimento_google"),
        "investimento_total": inv, "leads_total": leads, "vendas": vendas, "receita": round(receita, 2),
        "cpl": round(inv / leads, 2) if leads else None,
        "cpa": round(inv / vendas, 2) if vendas else None,
        "roas": round(receita / inv, 2) if inv else None,
        "verticais": [{
            "slug": l["slug"], "nome": l["d"]["nome"],
            "investimento": l["d"]["investimento_total"], "vendas": l["d"]["vendas"], "receita": l["d"]["receita"],
            "cpa": l["d"]["cpa"], "roas": l["d"]["roas"],
            "parte_receita": round(l["d"]["receita"] / receita * 100, 1) if receita else None,
            "sem_veiculacao": l["d"]["no_data"], "ultimo_gasto": l["d"].get("ultimo_gasto"),
        } for l in linhas],
        "serie_diaria": [serie[k] for k in sorted(serie)],
    }
    if compare:
        out["prev_range_start"], out["prev_range_end"] = base.get("prev_range_start"), base.get("prev_range_end")
        p_inv, p_v, p_r = soma("investimento_total", "prev"), soma("vendas", "prev"), soma("receita", "prev")
        p_cpa = (p_inv / p_v) if p_v else 0.0
        out["deltas"] = {
            "roas": _pct_delta(out["roas"] or 0.0, (p_r / p_inv) if p_inv else 0.0),
            "investimento_total": _pct_delta(inv, p_inv),
            "leads_total": _pct_delta(leads, soma("leads_total", "prev")),
            "vendas": _pct_delta(vendas, p_v),
            "receita": _pct_delta(receita, p_r),
            "cpa": _pct_delta(out["cpa"] or 0.0, p_cpa),
        }
    return out


# ── Visão mês a mês ───────────────────────────────────────────────────────────

_MESES_PT = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


def _rotulo_mes(ano: int, mes: int) -> str:
    return f"{_MESES_PT[mes - 1]}/{ano % 100:02d}"


def _primeiro_dia(ano: int, mes: int) -> date:
    return date(ano, mes, 1)


def _ultimo_dia(ano: int, mes: int) -> date:
    return (_primeiro_dia(ano + (mes == 12), 1 if mes == 12 else mes + 1)
            - timedelta(days=1))


def read_perpetuo_mensal(meses: int = 6) -> dict:
    """Investimento, vendas, receita, CPA e ROAS por MÊS CIVIL e por vertical.

    O seletor da página é em dias corridos (7/30/90) e nunca fecha um mês: a
    pergunta "quanto o perpétuo deu em agosto?" não tinha resposta na tela e
    saía de consulta manual (06/10/26). Aqui o corte é o mês fechado.

    Mesmas fontes da página: verba em `meta_ads_daily`/`google_ads_daily`
    (analytics, pelo pseudo-lançamento PERPETUO-*), venda em
    `hotmart_clean_oficial` (operacional, pelo código do produto). A venda
    continua NÃO atribuída ao anúncio — ver o docstring de `_vendas`: o ROAS
    aqui é teto, porque inclui orgânico, e-mail e régua.
    """
    hoje = date.today()
    pares: list[tuple[int, int]] = []
    ano, mes = hoje.year, hoje.month
    for _ in range(max(1, meses)):
        pares.append((ano, mes))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    pares.reverse()
    inicio, fim = _primeiro_dia(*pares[0]), _ultimo_dia(*pares[-1])

    codigos = [v["codigo"] for v in VERTICALS.values()]
    # chave: (YYYY-MM, codigo do pseudo-lançamento) -> investido
    investido: dict[tuple[str, str], float] = {}
    try:
        with _get_engine().connect() as conn:
            for tabela, col in (("meta_ads_daily", "spend"), ("google_ads_daily", "cost")):
                for ym, codigo, custo in conn.execute(
                    text(f"SELECT to_char(date, 'YYYY-MM'), lancamento_codigo, "
                         f"COALESCE(SUM({col}), 0) FROM {tabela} "
                         f"WHERE lancamento_codigo = ANY(:codigos) "
                         f"AND date BETWEEN :inicio AND :fim GROUP BY 1, 2"),
                    {"codigos": codigos, "inicio": inicio, "fim": fim},
                ).fetchall():
                    investido[(ym, codigo)] = investido.get((ym, codigo), 0.0) + float(custo or 0)
    except Exception:
        logger.exception("read_perpetuo_mensal: falha ao ler investimento")
        return {"meses": [], "erro": "investimento"}

    produto_da_vertical = {p: slug for slug, v in VERTICALS.items() for p in v["hotmart"]}
    # chave: (YYYY-MM, slug da vertical) -> (vendas, receita)
    vendas: dict[tuple[str, str], tuple[int, float]] = {}
    data_sql = _hm_data_sql("data_da_transacao")
    valor = _VALOR_LIQUIDO_SQL
    try:
        with _get_users_engine().connect() as conn:
            for ym, produto, n, receita in conn.execute(
                text(f"SELECT to_char({data_sql}, 'YYYY-MM'), codigo_do_produto, "
                     f"COUNT(*), COALESCE(SUM({valor}), 0) FROM hotmart_clean_oficial "
                     f"WHERE codigo_do_produto = ANY(:ids) AND status_da_transacao = ANY(:ok) "
                     f"AND {data_sql} BETWEEN :inicio AND :fim GROUP BY 1, 2"),
                {"ids": list(produto_da_vertical), "ok": list(_HOTMART_STATUS_APROVADO),
                 "inicio": inicio, "fim": fim},
            ).fetchall():
                slug = produto_da_vertical.get(str(produto))
                if not slug:
                    continue
                v, r = vendas.get((ym, slug), (0, 0.0))
                vendas[(ym, slug)] = (v + int(n or 0), r + float(receita or 0))
            # Conta Brabo Editora: mesmos produtos do perpétuo com IDs próprios (ver _vendas_comum).
            produto_da_vertical_ed = {p: slug for slug, v in VERTICALS.items() for p in v.get("hotmart_editora") or []}
            for ym, produto, n, receita in conn.execute(
                text(f"SELECT to_char({data_sql}, 'YYYY-MM'), codigo_do_produto, "
                     f"COUNT(*), COALESCE(SUM({valor}), 0) FROM hotmart_editora_clean_oficial "
                     f"WHERE codigo_do_produto = ANY(:ids) AND produtor_a = :produtor "
                     f"AND status_da_transacao = ANY(:ok) "
                     f"AND {data_sql} BETWEEN :inicio AND :fim GROUP BY 1, 2"),
                {"ids": list(produto_da_vertical_ed), "produtor": PRODUTOR_EDITORA, "ok": list(_HOTMART_STATUS_APROVADO),
                 "inicio": inicio, "fim": fim},
            ).fetchall():
                slug = produto_da_vertical_ed.get(str(produto))
                if not slug:
                    continue
                v, r = vendas.get((ym, slug), (0, 0.0))
                vendas[(ym, slug)] = (v + int(n or 0), r + float(receita or 0))
    except Exception:
        logger.exception("read_perpetuo_mensal: falha ao ler vendas")
        return {"meses": [], "erro": "vendas"}

    saida = []
    for ano, mes in pares:
        ym = f"{ano:04d}-{mes:02d}"
        linhas, t_inv, t_vnd, t_rec = [], 0.0, 0, 0.0
        for slug, v in VERTICALS.items():
            inv = investido.get((ym, v["codigo"]), 0.0)
            qtd, rec = vendas.get((ym, slug), (0, 0.0))
            if not inv and not qtd:
                continue
            linhas.append({
                "slug": slug, "nome": v["nome"],
                "investido": inv, "vendas": qtd, "receita": rec,
                "cpa": inv / qtd if qtd else 0.0,
                "roas": rec / inv if inv else 0.0,
            })
            t_inv += inv
            t_vnd += qtd
            t_rec += rec
        if not linhas:
            continue
        saida.append({
            "ym": ym,
            "label": _rotulo_mes(ano, mes),
            "parcial": (ano, mes) == (hoje.year, hoje.month),
            "linhas": linhas,
            "total": {
                "investido": t_inv, "vendas": t_vnd, "receita": t_rec,
                "cpa": t_inv / t_vnd if t_vnd else 0.0,
                "roas": t_rec / t_inv if t_inv else 0.0,
            },
        })
    saida.reverse()  # mês mais recente primeiro
    return {"meses": saida}


def read_perpetuo_ano(ano: int) -> dict:
    """Vendas (aprovadas, líquidas) dos produtos do perpétuo no ano civil, por vertical.

    Alimenta o faturamento total da empresa em /lancamentos. Devolve
    {"total": {"vendas", "receita"}, "verticais": {slug: {"nome", "vendas", "receita"}}}.
    """
    verticais: dict[str, dict] = {}
    for slug, info in VERTICALS.items():
        v = _vendas(info.get("hotmart") or [], date(ano, 1, 1), date(ano, 12, 31), info.get("hotmart_editora"))
        verticais[slug] = {"nome": info["nome"], "vendas": v["vendas"], "receita": v["receita"],
                           "vendas_editora": v["vendas_editora"], "receita_editora": v["receita_editora"]}
    return {
        "total": {"vendas": sum(x["vendas"] for x in verticais.values()),
                  "receita": sum(x["receita"] for x in verticais.values()),
                  "vendas_editora": sum(x["vendas_editora"] for x in verticais.values()),
                  "receita_editora": sum(x["receita_editora"] for x in verticais.values())},
        "verticais": verticais,
    }


def read_perpetuo_cards(ano: int) -> list[dict]:
    """Resumo do ano de cada vertical do perpétuo, para os cartões de /lancamentos.

    Venda e faturamento são do PRODUTO (líquido, venda aprovada), não venda atribuída ao anúncio;
    por isso o ROAS é teto (ver `_vendas`). Investimento = Meta + Google do código PERPETUO-*.
    """
    hoje = date.today()
    ini30 = hoje - timedelta(days=29)
    por_codigo: dict[str, dict] = {}
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT lancamento_codigo, SUM(v), SUM(v) FILTER (WHERE d >= :ini30)
                FROM (SELECT lancamento_codigo, date AS d, spend AS v FROM meta_ads_daily
                      WHERE lancamento_codigo ILIKE 'PERPETUO%' AND date BETWEEN :ini AND :fim
                      UNION ALL
                      SELECT lancamento_codigo, date, cost FROM google_ads_daily
                      WHERE lancamento_codigo ILIKE 'PERPETUO%' AND date BETWEEN :ini AND :fim) t
                GROUP BY 1
            """), {"ini": date(ano, 1, 1), "fim": date(ano, 12, 31), "ini30": ini30}).fetchall()
        por_codigo = {str(c): {"ano": float(a or 0), "d30": float(b or 0)} for c, a, b in rows}
    except Exception:
        logger.exception("read_perpetuo_cards: falha ao somar o investimento")

    cartoes = []
    for slug, info in VERTICALS.items():
        ids = info.get("hotmart") or []
        ids_ed = info.get("hotmart_editora")
        v_ano = _vendas(ids, date(ano, 1, 1), date(ano, 12, 31), ids_ed)
        v_30 = _vendas(ids, ini30, hoje, ids_ed)
        inv = por_codigo.get(info["codigo"], {"ano": 0.0, "d30": 0.0})
        cartoes.append({
            "slug": slug, "nome": info["nome"], "codigo": info["codigo"],
            "vendas": v_ano["vendas"], "receita": v_ano["receita"],
            "vendas_30d": v_30["vendas"], "receita_30d": v_30["receita"],
            "invest": inv["ano"], "invest_30d": inv["d30"],
            "roas": v_ano["receita"] / inv["ano"] if inv["ano"] > 0 else 0.0,
        })
    return cartoes
