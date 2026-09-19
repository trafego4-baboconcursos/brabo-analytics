"""
frontend/db_readers/leads.py — leitores de leads, Active Campaign e confronto de atribuição.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code, _norm_text
from frontend.db import _get_engine
from frontend.models import (
    LeadsSummary, VendasSummary,
    AcCampaign, AcCampaignSummary, Launch,
)

logger = get_logger("db")


def read_ac_leads_for_attribution(
    launch_code: str, start_date=None, end_date=None,
    emails: set | None = None, phones: set | None = None,
) -> pd.DataFrame:  # noqa: ARG001
    """Retorna DataFrame com email_norm e UTMs da tabela leads para o lançamento.

    Com `emails`/`phones`, traz só as linhas que casam por e-mail OU telefone —
    é o que a atribuição precisa (ela só olha comprador). Sem eles, devolve a
    base inteira, o que custa caro: eram 269 mil linhas por chamada no
    PI-AGO-26 (ver ARQUITETURA.md, 14/09/26 — egress).
    """
    engine = _get_engine()
    filtro = ""
    params: dict = {"code": launch_code}
    if emails is not None or phones is not None:
        condicoes = []
        if emails:
            condicoes.append("LOWER(TRIM(email)) = ANY(:emails)")
            params["emails"] = list(emails)
        if phones:
            condicoes.append("TRIM(COALESCE(phone, '')) = ANY(:phones)")
            params["phones"] = list(phones)
        if not condicoes:
            return pd.DataFrame(columns=[
                "email", "utm_source", "utm_medium", "utm_campaign", "utm_content",
                "utm_term", "phone", "nome", "sobrenome", "email_norm", "nome_norm",
            ])
        filtro = " AND (" + " OR ".join(condicoes) + ")"
    df = pd.read_sql(
        text(f"""
            SELECT email, utm_source, utm_medium, utm_campaign, utm_content, utm_term, phone, nome, sobrenome
            FROM leads
            WHERE lancamento_codigo = :code{filtro}
        """),
        engine,
        params=params,
    )
    if df.empty:
        return df
    df["email_norm"] = df["email"].astype(str).str.strip().str.lower()
    df = df[df["email_norm"].str.contains("@", na=False)].copy()
    for col in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["phone"] = df["phone"].fillna("").astype(str).str.strip()
    nome_full = (df["nome"].fillna("") + " " + df["sobrenome"].fillna("")).str.strip()
    df["nome_norm"] = nome_full.apply(_norm_text).str.replace(r"\s+", " ", regex=True)
    return df


def read_term_campaign_map(launch_code: str) -> dict[str, str]:
    """{utm_term: campanha mais frequente} entre os leads de tráfego Google.

    Usado pela atribuição pra recuperar vendas de períodos com UTM quebrada
    (campanha vazia, só o utm_term identifica o grupo). É uma agregação, então
    roda no servidor: antes saía junto com a base inteira de leads carregada
    em memória (ver ARQUITETURA.md, 14/09/26 — egress).

    Empate resolvido pela campanha alfabeticamente menor, que é o que o
    `idxmax()` do pandas devolvia (índice ordenado pelo groupby).
    """
    engine = _get_engine()
    with engine.connect() as conn:
        linhas = conn.execute(
            text("""
                SELECT BTRIM(utm_term) AS termo, BTRIM(utm_campaign) AS campanha, COUNT(*) AS n
                FROM leads
                WHERE lancamento_codigo = :code
                  AND BTRIM(COALESCE(utm_term, '')) <> ''
                  AND BTRIM(COALESCE(utm_campaign, '')) <> ''
                  AND utm_source ILIKE '%google%'
                GROUP BY 1, 2
                ORDER BY termo, n DESC, campanha
            """),
            {"code": launch_code},
        ).fetchall()
    mapa: dict[str, str] = {}
    for termo, campanha, _n in linhas:
        mapa.setdefault(termo, campanha)  # ORDER BY já deixou o vencedor na frente
    return mapa


def read_lancamentos_anteriores(launch_code: str, emails: set[str] | None = None) -> dict[str, list[str]]:
    """{email: [códigos dos lançamentos ANTERIORES em que o contato se cadastrou]}.

    A tabela `leads` só guarda o cadastro mais recente (o upsert do ETL
    sobrescreve lancamento_codigo), então o histórico vem de
    `lead_lancamentos`, materializada das tags cumulativas do Active Campaign
    (ver etl_active_campaign.py::_launch_code_from_tag).

    "Anterior" é pela data da tag: só entram lançamentos cuja tag foi aplicada
    ANTES da tag do lançamento consultado. Sem isso um lançamento que rodou
    depois apareceria como se fosse passado.

    `emails` restringe a consulta a um conjunto (ex: só os compradores); sem
    ele devolve todos os leads do lançamento.
    """
    engine = _get_engine()
    filtro = " AND LOWER(TRIM(l.email)) = ANY(:emails)" if emails else ""
    params: dict[str, Any] = {"code": launch_code}
    if emails:
        params["emails"] = [e.strip().lower() for e in emails]

    with engine.connect() as conn:
        linhas = conn.execute(
            text(f"""
                SELECT LOWER(TRIM(l.email)) AS email, ant.lancamento_codigo, ant.tagged_at
                FROM leads l
                JOIN lead_lancamentos atual
                  ON atual.contact_id = l.id AND atual.lancamento_codigo = :code
                JOIN lead_lancamentos ant
                  ON ant.contact_id = l.id
                 AND ant.lancamento_codigo <> :code
                 AND ant.tagged_at < atual.tagged_at
                WHERE l.email IS NOT NULL{filtro}
                ORDER BY email, ant.tagged_at
            """),
            params,
        ).fetchall()

    historico: dict[str, list[str]] = {}
    for email, codigo, _quando in linhas:
        historico.setdefault(email, []).append(codigo)
    return historico


def read_recorrencia_lancamento(launch_code: str) -> dict | None:
    """Quantos leads do lançamento já tinham se cadastrado em lançamentos
    anteriores — agregado no servidor (o detalhe por lead está em
    read_lancamentos_anteriores). Devolve None quando não há tag do
    lançamento no AC (ex: lançamento antigo demais ou tag ainda não criada)."""
    engine = _get_engine()
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM lead_lancamentos WHERE lancamento_codigo = :code"),
            {"code": launch_code},
        ).scalar() or 0
        if not total:
            return None
        recorrentes = conn.execute(
            text("""
                SELECT COUNT(*) FROM (
                    SELECT atual.contact_id
                    FROM lead_lancamentos atual
                    JOIN lead_lancamentos ant
                      ON ant.contact_id = atual.contact_id
                     AND ant.lancamento_codigo <> atual.lancamento_codigo
                     AND ant.tagged_at < atual.tagged_at
                    WHERE atual.lancamento_codigo = :code
                    GROUP BY atual.contact_id
                ) x
            """),
            {"code": launch_code},
        ).scalar() or 0
        por_origem = conn.execute(
            text("""
                SELECT ant.lancamento_codigo, COUNT(DISTINCT ant.contact_id) AS n
                FROM lead_lancamentos atual
                JOIN lead_lancamentos ant
                  ON ant.contact_id = atual.contact_id
                 AND ant.lancamento_codigo <> atual.lancamento_codigo
                 AND ant.tagged_at < atual.tagged_at
                WHERE atual.lancamento_codigo = :code
                GROUP BY 1
                ORDER BY n DESC
            """),
            {"code": launch_code},
        ).fetchall()

    return {
        "total": int(total),
        "recorrentes": int(recorrentes),
        "novos": int(total - recorrentes),
        "pct_recorrentes": round(recorrentes / total * 100, 2) if total else 0.0,
        "por_lancamento_anterior": [{"codigo": c, "leads": int(n)} for c, n in por_origem],
    }


def read_cadastrados_lancamentos_anteriores(launch_folder_or_code: Any, vendas: VendasSummary | None = None) -> dict | None:
    """Dos COMPRADORES do lançamento, quantos já estavam cadastrados (tag de
    lançamento no AC) em lançamentos ANTERIORES — e em quais.

    Diferente de `read_lancamentos_anteriores`: aquela função só devolve
    histórico de quem também tem a tag do lançamento ATUAL em
    `lead_lancamentos`, então perde quem comprou sem se recadastrar (respondeu
    só à comunicação com a base antiga). Aqui o corte é a data de início do
    lançamento (mesmo critério de `read_leads_antigos_compradores`), não a tag
    atual — cobre os dois casos.

    None quando não há vendas, não dá pra descobrir o início do lançamento, ou
    nenhum comprador tem histórico em `lead_lancamentos` (cobertura do
    backfill ainda é parcial — ver ARQUITETURA.md).
    """
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415 — evita import circular
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415
    from src.constants import LAUNCH_NAMES  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    if vendas is None:
        vendas = read_vendas(code)
    if not vendas:
        return None
    buyers = {e.strip().lower() for e in (vendas.emails_hotmart | vendas.emails_tmb) if e}
    if not buyers:
        return None

    engine = _get_engine()
    cfg = read_launch_config(code)
    inicio = cfg.get("pre_quali_start_date") or cfg.get("captacao_start_date")
    if not inicio:
        row = pd.read_sql(
            text("SELECT data_inicio FROM dim_lancamentos WHERE codigo = :code"),
            engine, params={"code": code},
        )
        inicio = str(row.iloc[0, 0]) if not row.empty else None
    if not inicio:
        return None
    inicio = str(inicio)[:10]

    with engine.connect() as conn:
        linhas = conn.execute(
            text("""
                SELECT LOWER(TRIM(l.email)) AS email, l.lancamento_codigo AS cadastro_recente,
                       ll.lancamento_codigo AS lancamento_anterior
                FROM leads l
                LEFT JOIN lead_lancamentos ll
                  ON ll.contact_id = l.id
                 AND ll.lancamento_codigo <> :code
                 AND ll.tagged_at < :inicio
                WHERE l.email = ANY(:emails)
            """),
            {"code": code, "inicio": inicio, "emails": list(buyers)},
        ).fetchall()

    por_email: dict[str, dict] = {}
    for email, cadastro_recente, lanc_anterior in linhas:
        d = por_email.setdefault(email, {"cadastrado_atual": False, "anteriores": set()})
        d["cadastrado_atual"] = d["cadastrado_atual"] or (cadastro_recente == code)
        if lanc_anterior:
            d["anteriores"].add(lanc_anterior)

    contagem: dict[str, int] = {}
    total_com_historico = 0
    sem_cadastro_atual = 0
    for d in por_email.values():
        if not d["anteriores"]:
            continue
        total_com_historico += 1
        if not d["cadastrado_atual"]:
            sem_cadastro_atual += 1
        for codigo in d["anteriores"]:
            contagem[codigo] = contagem.get(codigo, 0) + 1

    if not total_com_historico:
        return None

    datas: dict[str, Any] = {}
    codigos = list(contagem.keys())
    if codigos:
        df_datas = pd.read_sql(
            text("SELECT codigo, data_inicio FROM dim_lancamentos WHERE codigo = ANY(:codigos)"),
            engine, params={"codigos": codigos},
        )
        datas = dict(zip(df_datas["codigo"], df_datas["data_inicio"]))

    # Fallback de ordenação pra código sem `dim_lancamentos` (lançamento
    # anterior ao sistema atual, ex.: PI-JUL-24): extrai ano/mês do próprio
    # código (PREFIXO-MES-AA) em vez de jogar no fim sem ordem nenhuma.
    _MES_NUM = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
                "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}

    def _ordem(codigo: str, data_inicio: Any) -> tuple:
        if data_inicio is not None:
            return (0, str(data_inicio)[:10])
        partes = codigo.split("-")
        if len(partes) == 3 and partes[1].upper() in _MES_NUM and partes[2].isdigit():
            ano = 2000 + int(partes[2])
            return (0, f"{ano:04d}-{_MES_NUM[partes[1].upper()]:02d}")
        return (1, codigo)

    por_lancamento = sorted(
        (
            {"codigo": c, "nome": LAUNCH_NAMES.get(c, c), "n": n, "data_inicio": datas.get(c)}
            for c, n in contagem.items()
        ),
        key=lambda x: _ordem(x["codigo"], x["data_inicio"]),
    )

    total_compradores = len(buyers)
    return {
        "total_compradores": total_compradores,
        "total_com_historico": total_com_historico,
        "pct_com_historico": round(total_com_historico / total_compradores * 100, 2) if total_compradores else 0.0,
        "sem_cadastro_atual": sem_cadastro_atual,
        "pct_sem_cadastro_atual": round(sem_cadastro_atual / total_com_historico * 100, 2) if total_com_historico else 0.0,
        "por_lancamento": por_lancamento,
    }


def read_vendas_por_dia_cadastro(launch_folder_or_code: Any, vendas: VendasSummary | None = None) -> dict | None:
    """Vendas (Hotmart+TMB) agrupadas pela data em que o comprador virou LEAD
    na tabela `leads` (Active Campaign) — não pela data da compra em si.

    Serve pra medir o potencial de vendas gerado em cada dia de Captação: quem
    vira lead num dia da Captação normalmente só compra dias/semanas depois,
    durante o carrinho aberto — cruzar vendas por DATA DE VENDA com dias de
    Captação dá quase sempre zero (pauta debriefing 14/09/26, PI-AGO-26)."""
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415 — evita import circular

    code = _extract_launch_code(launch_folder_or_code)
    if vendas is None:
        vendas = read_vendas(code)
    if not vendas:
        return None
    buyers = (vendas.emails_hotmart or set()) | (vendas.emails_tmb or set())
    if not buyers:
        return None

    engine = _get_engine()
    df = pd.read_sql(
        text("""
            SELECT LOWER(TRIM(email)) AS email, created_at
            FROM leads
            WHERE lancamento_codigo = :code AND LOWER(TRIM(email)) = ANY(:emails)
        """),
        engine, params={"code": code, "emails": [e.lower() for e in buyers]},
    )
    # Alguém pode ter mais de uma linha em `leads` (recadastro/re-captura) —
    # fica a data do PRIMEIRO cadastro, é quando o potencial de venda nasceu.
    cadastro_por_email: dict[str, str] = {}
    for _, r in df.iterrows():
        if pd.isna(r["created_at"]):
            continue
        d = str(r["created_at"])[:10]
        email = r["email"]
        if email not in cadastro_por_email or d < cadastro_por_email[email]:
            cadastro_por_email[email] = d

    receita_por_email = vendas.receita_por_email or {}
    vendas_por_email = vendas.vendas_por_email or {}
    por_dia: dict[str, dict] = {}
    sem_data = 0
    for email in buyers:
        d = cadastro_por_email.get(email)
        if not d:
            sem_data += 1
            continue
        entry = por_dia.setdefault(d, {"vendas": 0, "faturamento": 0.0})
        entry["vendas"] += int(vendas_por_email.get(email, 1) or 1)
        entry["faturamento"] += float(receita_por_email.get(email, 0.0))
    return {"por_dia": por_dia, "sem_data": sem_data, "total": len(buyers)}


def read_utm_cobertura(launch_folder_or_code: Any) -> dict | None:
    """% de leads (tabela `leads`, Active Campaign) com utm_content preenchido
    — é a UTM que carrega o código do anúncio (ADxxx), chave de atribuição do
    sistema inteiro. Sem ela o lead não casa com nenhum criativo/campanha."""
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE COALESCE(NULLIF(TRIM(utm_content), ''), '') != '') AS com_utm
                FROM leads WHERE lancamento_codigo = :code
            """),
            {"code": code},
        ).fetchone()
    total = int(row[0] or 0)
    if not total:
        return None
    com_utm = int(row[1] or 0)
    return {"total": total, "com_utm": com_utm, "pct": com_utm / total * 100}


def read_leads(launch_folder_or_code: Any, vendas: VendasSummary | None = None, start_date=None, end_date=None) -> LeadsSummary | None:  # noqa: ARG001
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    # Agregado por combinação (UTM + dia) em vez de linha a linha: as seis
    # quebras montadas abaixo (canal, dia, etapa, temperatura, source, medium)
    # derivam só dessas colunas, então somar a contagem de cada combinação dá
    # exatamente o mesmo resultado sem baixar a lista de leads inteira do
    # lançamento — eram 269 mil linhas no PI-AGO-26 a cada chamada, a maior
    # fonte de egress do banco (ver ARQUITETURA.md, 14/09/26).
    df = pd.read_sql(
        text("""
            SELECT utm_source, utm_medium, utm_campaign,
                   (created_at AT TIME ZONE 'UTC')::date AS dia,
                   COUNT(*) AS leads
            FROM leads WHERE lancamento_codigo = :code
            GROUP BY 1, 2, 3, 4
        """),
        engine,
        params={"code": code}
    )
    if df.empty:
        return None

    summary = LeadsSummary()
    summary.total_leads = int(df["leads"].sum())

    buyers = (vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()
    receita_por_email = vendas.receita_por_email if vendas else {}
    summary.total_compradores = len(buyers)

    # Único ponto que precisa de detalhe por pessoa: conversão e faturamento
    # de cada quebra. São só os compradores (poucos milhares), não a base toda.
    _COMP_COLS = ["email_norm", "utm_source", "utm_medium", "utm_campaign", "dia"]
    comp_df = pd.read_sql(
        text("""
            SELECT LOWER(TRIM(email)) AS email_norm, utm_source, utm_medium, utm_campaign,
                   (created_at AT TIME ZONE 'UTC')::date AS dia
            FROM leads
            WHERE lancamento_codigo = :code AND LOWER(TRIM(email)) = ANY(:buyers)
        """),
        engine,
        params={"code": code, "buyers": list(buyers)},
    ) if buyers else pd.DataFrame(columns=_COMP_COLS)

    rastreados_emails = set(comp_df["email_norm"]) if not comp_df.empty else set()
    summary.compradores_rastreados = len(rastreados_emails)
    summary.compradores_sem_utm = max(0, summary.total_compradores - summary.compradores_rastreados)
    summary.emails_rastreados = rastreados_emails
    summary.tx_conversao = summary.compradores_rastreados / summary.total_leads * 100 if summary.total_leads > 0 else 0.0

    comp_df["receita"] = (
        comp_df["email_norm"].map(lambda e: receita_por_email.get(e, 0.0))
        if not comp_df.empty else pd.Series(dtype=float)
    )

    def _vendas_do_grupo(coluna: str, valor) -> tuple[int, float]:
        """(compradores, faturamento) do grupo — equivalente ao antigo
        cruzamento em memória, mas só sobre as linhas dos compradores."""
        # devolve 0 (int) quando não há comprador no grupo, igual ao
        # sum(()) do código anterior — mantém o tipo idêntico ao original
        if comp_df.empty:
            return 0, 0
        sub = comp_df[comp_df[coluna] == valor]
        if sub.empty:
            return 0, 0
        return len(sub), float(sub["receita"].sum())

    SOURCE_LABEL = {
        "facebook": "Facebook Ads",
        "fb": "Facebook Ads",
        "instagram": "Instagram Ads",
        "ig": "Instagram Ads",
        "google": "Google Ads",
        "youtube": "YouTube",
        "tiktok": "TikTok Ads",
        "email": "E-mail",
        "organico": "Orgânico",
        "organic": "Orgânico",
        "direto": "Direto / Orgânico",
    }
    def _canal(serie):
        return serie.fillna("").str.strip().str.lower().map(
            lambda s: SOURCE_LABEL.get(s, s.title() if s else "Direto / Orgânico")
        )

    df["canal"] = _canal(df["utm_source"])
    if not comp_df.empty:
        comp_df["canal"] = _canal(comp_df["utm_source"])
    canal_rows = []
    for canal, grp in df.groupby("canal"):
        n = int(grp["leads"].sum())
        v, fat = _vendas_do_grupo("canal", canal)
        canal_rows.append({
            "canal": canal,
            "leads": n,
            "compradores": v,
            "faturamento": fat,
            "conversao": v / n * 100 if n > 0 else 0.0,
            "ticket": fat / v if v > 0 else 0.0,
        })
    summary.por_canal = sorted([r for r in canal_rows if r["leads"] >= 10], key=lambda x: x["leads"], reverse=True)

    WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    dia_rows = []
    for dia, grp in df.groupby("dia"):
        n = int(grp["leads"].sum())
        v, fat = _vendas_do_grupo("dia", dia)
        dt = pd.Timestamp(dia)
        dia_rows.append({
            "_dt": dt,
            "date": dt.strftime("%d/%m"),
            "weekday": WEEKDAYS_PT[dt.weekday()],
            "leads": n,
            "compradores": v,
            "conversao": v / n * 100 if n > 0 else 0.0,
            "faturamento": fat,
        })
    today = pd.Timestamp.now().normalize()
    dia_rows_sorted = sorted(
        [r for r in dia_rows if r["_dt"] <= today],
        key=lambda x: x["_dt"]
    )
    if dia_rows_sorted:
        last_dt = dia_rows_sorted[-1]["_dt"]
        cutoff = last_dt - pd.Timedelta(days=90)
        dia_rows_sorted = [r for r in dia_rows_sorted if r["_dt"] >= cutoff]
    for r in dia_rows_sorted:
        del r["_dt"]
    summary.por_dia = dia_rows_sorted

    ETAPA_MAP_LEADS = [
        ("pré-qualificação", "Pré-Qualificação"), ("pre-qualificacao", "Pré-Qualificação"),
        ("pré-quali", "Pré-Qualificação"), ("pre-quali", "Pré-Qualificação"),
        ("replay", "Replay"),
        ("lembrete", "Lembrete"),
        ("matrícula", "Matrículas Abertas"), ("matricula", "Matrículas Abertas"), ("abertas", "Matrículas Abertas"),
        ("aula", "Aulas no Ar"), ("tráfego", "Aulas no Ar"), ("trafego", "Aulas no Ar"),
        ("captação", "Captação"), ("captacao", "Captação"), ("capta", "Captação"),
    ]

    def _etapa(camp: str) -> str:
        c = (camp or "").lower()
        for kw, label in ETAPA_MAP_LEADS:
            if kw in c:
                return label
        return "Outros"

    df["etapa"] = df["utm_campaign"].fillna("").apply(_etapa)
    if not comp_df.empty:
        comp_df["etapa"] = comp_df["utm_campaign"].fillna("").apply(_etapa)
    etapa_rows = []
    for etapa, grp in df.groupby("etapa"):
        n = int(grp["leads"].sum())
        v, fat = _vendas_do_grupo("etapa", etapa)
        etapa_rows.append({
            "etapa": etapa,
            "leads": n,
            "compradores": v,
            "faturamento": fat,
            "conversao": v / n * 100 if n > 0 else 0.0,
            "ticket": fat / v if v > 0 else 0.0,
        })
    ETAPAS_ORDER = ["Pré-Qualificação", "Captação", "Lembrete", "Aulas no Ar", "Replay", "Matrículas Abertas", "Outros"]
    summary.por_etapa = sorted(etapa_rows, key=lambda x: ETAPAS_ORDER.index(x["etapa"]) if x["etapa"] in ETAPAS_ORDER else 99)

    def _temp(camp: str) -> str:
        c = (camp or "").lower()
        if "específico" in c or "especifico" in c: return "Específico"
        if "quente" in c:  return "Quente"
        if "morno" in c:   return "Morno"
        if "frio" in c:    return "Frio"
        return "Não classificado"

    df["temp"] = df["utm_campaign"].fillna("").apply(_temp)
    if not comp_df.empty:
        comp_df["temp"] = comp_df["utm_campaign"].fillna("").apply(_temp)
    temp_rows = []
    for temp, grp in df.groupby("temp"):
        n = int(grp["leads"].sum())
        v, fat = _vendas_do_grupo("temp", temp)
        temp_rows.append({
            "temp": temp,
            "leads": n,
            "compradores": v,
            "faturamento": fat,
            "conversao": v / n * 100 if n > 0 else 0.0,
            "ticket": fat / v if v > 0 else 0.0,
        })
    TEMP_ORDER = ["Específico", "Quente", "Morno", "Frio", "Não classificado"]
    summary.por_temperatura = sorted(temp_rows, key=lambda x: TEMP_ORDER.index(x["temp"]) if x["temp"] in TEMP_ORDER else 99)

    df["utm_source_norm"] = df["utm_source"].fillna("Sem source").str.strip()
    df["utm_medium_norm"] = df["utm_medium"].fillna("Sem medium").str.strip()
    if not comp_df.empty:
        comp_df["utm_source_norm"] = comp_df["utm_source"].fillna("Sem source").str.strip()
        comp_df["utm_medium_norm"] = comp_df["utm_medium"].fillna("Sem medium").str.strip()
    for src, grp in df.groupby("utm_source_norm"):
        n = int(grp["leads"].sum())
        v, fat = _vendas_do_grupo("utm_source_norm", src)
        summary.por_utm_source[src] = {"source": src, "leads": n, "vendas": v, "faturamento": fat, "conversao": v / n * 100 if n > 0 else 0.0}
    for med, grp in df.groupby("utm_medium_norm"):
        n = int(grp["leads"].sum())
        v, fat = _vendas_do_grupo("utm_medium_norm", med)
        summary.por_utm_medium[med] = {"medium": med, "leads": n, "vendas": v, "faturamento": fat, "conversao": v / n * 100 if n > 0 else 0.0}

    return summary


def read_leads_antigos_compradores(launch_folder_or_code: Any, vendas: VendasSummary | None = None) -> dict | None:
    """Classifica os compradores pelo histórico do contato no Active Campaign.

    A tabela `leads` tem UMA linha por contato do AC (o lancamento_codigo é
    sobrescrito no cadastro mais recente), então a distinção usa a data de
    criação do contato contra o início do lançamento:

    - novo:     contato criado a partir do início do lançamento
    - antigo:   contato já existia na base antes do lançamento começar
    - sem_lead: e-mail sem registro na tabela de leads
    """
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415 — evita import circular
    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    if vendas is None:
        vendas = read_vendas(code)
    if not vendas:
        return None
    buyers = {e for e in (vendas.emails_hotmart | vendas.emails_tmb) if e}
    if not buyers:
        return None

    cfg = read_launch_config(code)
    inicio = cfg.get("pre_quali_start_date") or cfg.get("captacao_start_date")
    engine = _get_engine()
    if not inicio:
        row = pd.read_sql(
            text("SELECT data_inicio FROM dim_lancamentos WHERE codigo = :code"),
            engine, params={"code": code},
        )
        inicio = str(row.iloc[0, 0]) if not row.empty else None
    if not inicio:
        return None
    inicio = str(inicio)

    df = pd.read_sql(
        text("SELECT LOWER(email) AS email, MIN(created_at) AS created_at FROM leads WHERE LOWER(email) = ANY(:emails) GROUP BY 1"),
        engine,
        params={"emails": [e.lower() for e in buyers]},
    )
    created = {r["email"]: r["created_at"] for _, r in df.iterrows()}

    receita = vendas.receita_por_email or {}
    cats = {k: {"n": 0, "receita": 0.0} for k in ("novo", "antigo", "sem_lead")}
    for email in buyers:
        c = created.get(email.lower())
        if c is None or pd.isna(c):
            cat = "sem_lead"
        elif str(c)[:10] < inicio[:10]:
            cat = "antigo"
        else:
            cat = "novo"
        cats[cat]["n"] += 1
        cats[cat]["receita"] += float(receita.get(email) or 0)

    total = len(buyers)
    for v in cats.values():
        v["pct"] = v["n"] / total * 100 if total else 0.0
    return {"total": total, "inicio": inicio[:10], **cats}


def read_ebook_compradores(launch_folder_or_code: Any, vendas: VendasSummary | None = None) -> dict | None:
    """Ebook → compra. "Baixou" = clicou no link do PDF do e-mail da automação
    do lançamento (tabela `ac_ebook_clicks`, alimentada por etl/etl_ac_ebook.py).
    O contato do AC vira e-mail pela tabela `leads` (leads.id = id do contato)
    e o e-mail cruza com os compradores Hotmart+TMB.

    None quando não há cliques gravados pro lançamento (tabela ausente ou
    ETL ainda não rodou) — a seção some do debriefing."""
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415 — evita import circular

    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            cliques = conn.execute(
                text("""
                    SELECT c.contact_id, LOWER(l.email) AS email, c.link_url, c.campaign_name
                    FROM ac_ebook_clicks c
                    LEFT JOIN leads l ON l.id = c.contact_id
                    WHERE c.lancamento_codigo = :code
                """),
                {"code": code},
            ).fetchall()
    except Exception:
        logger.debug("ac_ebook_clicks indisponível pra %s", code, exc_info=True)
        return None
    if not cliques:
        return None

    contatos = {r[0] for r in cliques}
    emails = {r[1] for r in cliques if r[1]}

    def _label_link(url: str, camp: str) -> str:
        # Distingue PDFs da mesma campanha/automação pela data no path do
        # content.app-us1.com (ex.: .../2026/08/05/<hash>.pdf → "05/08/2026");
        # sem esse padrão (ex.: link do Drive), cai no nome da campanha.
        m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if m:
            ano, mes, dia = m.groups()
            return f"{camp} — {dia}/{mes}/{ano}"
        return camp

    por_link: dict[str, dict] = {}
    for cid, _email, url, camp in cliques:
        d = por_link.setdefault(url, {"url": url, "campanha": _label_link(url, camp), "contatos": set()})
        d["contatos"].add(cid)

    if vendas is None:
        vendas = read_vendas(code)
    buyers = {e.lower() for e in ((vendas.emails_hotmart | vendas.emails_tmb) if vendas else set()) if e}
    receita = (vendas.receita_por_email if vendas else {}) or {}
    compradores = emails & buyers
    n_emails = len(emails)
    return {
        "downloads": len(contatos),
        "com_email": n_emails,
        "sem_email": len(contatos) - n_emails,
        "compradores": len(compradores),
        "pct_compra": (len(compradores) / n_emails * 100) if n_emails else 0.0,
        "receita": float(sum(receita.get(e, 0.0) or 0.0 for e in compradores)),
        "total_compradores": len(buyers),
        "pct_dos_compradores": (len(compradores) / len(buyers) * 100) if buyers else 0.0,
        "links": sorted(
            ({"url": d["url"], "campanha": d["campanha"], "downloads": len(d["contatos"])} for d in por_link.values()),
            key=lambda x: x["downloads"], reverse=True,
        ),
    }


def read_ac_campaigns(launch: Launch) -> AcCampaignSummary:
    """Busca estatísticas de campanhas de e-mail do Active Campaign filtradas por datas e keywords."""
    engine = _get_engine()
    summary = AcCampaignSummary()

    if not launch or not launch.data_inicio or not launch.data_fim:
        return summary

    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT 1 FROM ac_campaigns LIMIT 1"))
        except Exception:
            logger.debug("Tabela ac_campaigns não encontrada; retornando summary vazio")
            return summary

        rows = conn.execute(
            text("""
                SELECT
                    id, nome_campanha, data_envio, envios, aberturas,
                    aberturas_unicas, cliques, descadastros, bounces
                FROM ac_campaigns
                WHERE DATE(data_envio) >= :start_dt AND DATE(data_envio) <= :end_dt
                ORDER BY data_envio DESC
            """),
            {"start_dt": launch.data_inicio, "end_dt": launch.data_fim}
        ).fetchall()

    if not rows:
        return summary

    code_prefix = launch.code.split("-")[0].upper()
    if code_prefix == "PBB":
        keywords = ["bb", "banco do brasil"]
    elif code_prefix == "PI":
        keywords = ["inss"]
    elif code_prefix == "PES":
        keywords = ["tjsp", "escrevente"]
    else:
        keywords = ["inss", "tjsp", "bb", "banco do brasil"]

    for row in rows:
        nome_campanha = (row[1] or "").lower()
        if not any(k in nome_campanha for k in keywords):
            continue

        envios = row[3] or 0
        aberturas = row[4] or 0
        cliques = row[6] or 0
        descadastros = row[7] or 0

        c = AcCampaign(
            id=row[0],
            nome=row[1],
            data_envio=str(row[2])[:10] if row[2] else "",
            envios=envios,
            aberturas=aberturas,
            aberturas_unicas=row[5] or 0,
            cliques=cliques,
            descadastros=descadastros,
            bounces=row[8] or 0,
            tx_abertura=aberturas / envios * 100 if envios > 0 else 0.0,
            tx_clique=cliques / aberturas * 100 if aberturas > 0 else 0.0,
            tx_descadastro=descadastros / envios * 100 if envios > 0 else 0.0
        )
        summary.campanhas.append(c)
        summary.total_envios += envios
        summary.total_aberturas += aberturas
        summary.total_cliques += cliques

    if not summary.campanhas:
        return summary

    summary.has_data = True

    if summary.total_envios > 0:
        summary.tx_abertura_media = summary.total_aberturas / summary.total_envios * 100
    if summary.total_aberturas > 0:
        summary.tx_clique_media = summary.total_cliques / summary.total_aberturas * 100

    df = pd.DataFrame([{
        "data": c.data_envio,
        "envios": c.envios,
        "aberturas": c.aberturas,
        "cliques": c.cliques
    } for c in summary.campanhas if c.data_envio])

    if not df.empty:
        df_grouped = df.groupby("data").sum().reset_index()
        summary.por_dia = df_grouped.to_dict("records")

    return summary
