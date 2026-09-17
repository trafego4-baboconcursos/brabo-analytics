"""
frontend/db_readers/hotmart.py — Detalhe e recompra da Hotmart.

``read_hotmart_details`` abre a venda por forma de pagamento, parcelamento e
data; ``read_hotmart_recompra`` cruza com lançamentos anteriores para separar
comprador novo de recorrente.

A fonte é ``hotmart_clean_oficial``, no banco **operacional** — nunca a cópia no
banco analytics, que está desatualizada.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine, _get_users_engine
from frontend.db_readers._vendas_comum import (
    _hm_data_sql,
    _hm_metodo_label,
    _metodo_pagamento_pt,
    _hm_parse_date,
    _parcela_unica_info,
)
from frontend.models import HotmartDetails
from frontend.utils import (
    _extract_launch_code,
    _norm_text,
    _normalize_product_ids,
    _safe_date,
)
from logger import get_logger

logger = get_logger("db")


def read_hotmart_details(launch_folder_or_code: Any, start_date=None, end_date=None) -> HotmartDetails:
    code = _extract_launch_code(launch_folder_or_code)

    with _get_engine().connect() as conn:
        l_row = conn.execute(text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
        if not l_row:
            return HotmartDetails()
        project, dim_start, dim_end = l_row

    effective_start = _safe_date(start_date) or _safe_date(dim_start)
    effective_end   = _safe_date(end_date)   or _safe_date(dim_end)

    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415
    cfg = read_launch_config(code)
    hotmart_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))

    ops_engine = _get_users_engine()
    details = HotmartDetails()
    details.has_data = True

    sql = (
        r"""
        SELECT * FROM hotmart_clean_oficial
        WHERE CASE
              WHEN produto ILIKE '%inss%' THEN 'INSS'
              WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
              WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
              ELSE 'OUTRO'
          END = :project
          AND COALESCE(
            """ + _hm_data_sql("data_da_transacao") + """,
            """ + _hm_data_sql("confirmacao_do_pagamento") + r"""
          ) BETWEEN :start AND :end
          AND (email_do_a_comprador_a IS NULL OR (
              email_do_a_comprador_a NOT ILIKE '%+teste%'
              AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'
          ))
    """
    )
    params: dict = {"project": project, "start": effective_start, "end": effective_end}
    if hotmart_ids:
        sql += " AND codigo_do_produto = ANY(:product_ids)"
        params["product_ids"] = hotmart_ids

    df_all = pd.read_sql(text(sql), ops_engine, params=params)
    if df_all.empty:
        return details

    details.total_emitidos = len(df_all)

    df_all["status_norm"] = df_all["status_da_transacao"].astype(str).apply(_norm_text)
    details.total_cancelados = int(df_all["status_norm"].isin({"cancelado", "reclamado", "reembolsado", "chargeback", "cancelada"}).sum())
    details.taxa_cancelamento = details.total_cancelados / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    details.total_reclamacoes = int(df_all["status_norm"].isin({"reclamado", "dispute"}).sum())
    details.taxa_reclamacao = details.total_reclamacoes / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    boletos_df = df_all[df_all["metodo_de_pagamento"].str.lower().str.contains("boleto", na=False)]
    details.boleto_emitido_qtd = len(boletos_df)
    details.boleto_pago_qtd = len(boletos_df[boletos_df["status_norm"].isin({"completo", "complete", "aprovado", "approved", "pago"})])
    details.taxa_conversao_boleto = details.boleto_pago_qtd / details.boleto_emitido_qtd * 100 if details.boleto_emitido_qtd > 0 else 0.0
    details.taxa_boleto_gerado = details.boleto_emitido_qtd / details.total_emitidos * 100 if details.total_emitidos > 0 else 0.0

    df_paid = df_all[df_all["status_norm"].isin({"completo", "completa", "complete", "completed", "aprovado", "aprovada", "approved", "pago", "paga"})].copy()

    def _hmd_num(v):
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            x = float(str(v).replace(",", "."))
            return x if math.isfinite(x) else None
        except (ValueError, TypeError):
            return None

    df_paid["valor_liq"] = 0.0
    df_paid["valor_bruto"] = 0.0
    recorrencia_qtd = 0
    recorrencia_receita = 0.0
    recorrencia_idx = []
    repeticao_idx = []
    for idx, row in df_paid.iterrows():
        valor = _hmd_num(row.get("faturamento_liquido"))
        if valor is None:
            valor = _hmd_num(row.get("valor_de_compra_sem_impostos"))
        if valor is None:
            valor = 0.0
        valor_bruto = _hmd_num(row.get("valor_de_compra_com_impostos"))
        if valor_bruto is None:
            valor_bruto = valor
        eh_por_parcela, eh_repeticao, cobrancas, parcelas = _parcela_unica_info(row)
        if eh_por_parcela:
            # Venda "de parcela única" (tipo_de_cobranca = Recuperador
            # Inteligente, ou tipo vazio com quantidade_de_cobrancas
            # presente): valor gravado é o da PARCELA (ex: R$149,90) — vira
            # faturamento real multiplicando pelo número de parcelas. É isso
            # que esse bloco resolve, e só isso.
            #
            # CUIDADO: recorrencia_qtd/receita NÃO são "vendas recorrentes".
            # A condição `tipo vazio + tem quantidade_de_cobrancas` casa com
            # praticamente toda venda vinda da API, então o contador dispara
            # no lançamento inteiro (740 de 752 no PES-SET-26), e ainda soma
            # linhas que o filtro de repetição descarta depois — das 740, só
            # 197 eram venda do painel. Foram exibidas por engano como
            # "Recorrência" num gráfico do debriefing até 17/09/26; hoje
            # ninguém lê esses dois campos. Não use como contagem de nada
            # sem refazer o critério.
            valor *= max(1, parcelas)
            valor_bruto *= max(1, parcelas)
            recorrencia_qtd += 1
            recorrencia_receita += valor
            recorrencia_idx.append(idx)
        if eh_repeticao:
            # Retentativa/cobrança subsequente de um contrato já contado —
            # nunca é venda nova, independente do tipo_de_cobranca. Removida
            # de df_paid abaixo pra não inflar total_vendas/receita_liquida.
            repeticao_idx.append(idx)
            continue
        df_paid.at[idx, "valor_liq"] = valor
        df_paid.at[idx, "valor_bruto"] = valor_bruto

    df_paid = df_paid.drop(index=repeticao_idx, errors="ignore")
    details.recorrencia_qtd = recorrencia_qtd
    details.recorrencia_receita = recorrencia_receita
    details.total_vendas = len(df_paid)
    details.receita_liquida = float(df_paid["valor_liq"].sum())
    details.receita_bruta = float(df_paid["valor_bruto"].sum())
    details.faturamento = details.receita_liquida
    details.taxas = max(0.0, details.receita_bruta - details.receita_liquida)
    details.taxas_pct = details.taxas / details.receita_bruta * 100 if details.receita_bruta > 0 else 0.0
    details.ticket_medio = details.faturamento / details.total_vendas if details.total_vendas > 0 else 0.0

    pix_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("pix", na=False)]
    card_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("cartao|card|credit", na=False)]
    details.pix_ticket = float(pix_df["valor_liq"].mean()) if not pix_df.empty else 0.0
    details.card_ticket = float(card_df["valor_liq"].mean()) if not card_df.empty else 0.0
    if details.card_ticket > 0:
        details.pix_premium = (details.pix_ticket - details.card_ticket) / details.card_ticket * 100

    if not card_df.empty:
        df_paid["parcelas_int"] = pd.to_numeric(df_paid["quantidade_total_de_parcelas"], errors="coerce").fillna(1).astype(int)
        card_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("cartao|card|credit", na=False)]
        details.vendas_12x_pct = len(card_df[card_df["parcelas_int"] == 12]) / len(card_df) * 100 if not card_df.empty else 0.0

        p_dist = card_df["parcelas_int"].value_counts().sort_index()
        for p_val, cnt in p_dist.items():
            details.parcelas.append({
                "label": "À vista" if p_val == 1 else f"{p_val}x",
                "qtd": int(cnt),
                "pct_vendas": float(cnt / len(card_df) * 100)
            })

    # Detalhamento de vendas por forma (pauta debriefing) — à vista (qualquer
    # método com 1 parcela) x parcelado em 12x x outros parcelamentos, SEM as
    # linhas de recorrência (já contadas à parte acima, não são venda nova).
    df_regular = df_paid.drop(index=recorrencia_idx, errors="ignore")
    if not df_regular.empty:
        parcelas_regular = pd.to_numeric(df_regular["quantidade_total_de_parcelas"], errors="coerce").fillna(1).astype(int)
        details.a_vista_qtd = int((parcelas_regular == 1).sum())
        details.parcelado_12x_qtd = int((parcelas_regular == 12).sum())
        details.outros_parcelamentos_qtd = int(((parcelas_regular > 1) & (parcelas_regular != 12)).sum())

    if not df_paid.empty and "metodo_de_pagamento" in df_paid.columns:
        # Agrupa pelo rótulo normalizado, não pelo valor cru: o mesmo método
        # vem em português e em inglês conforme a época da venda (CSV x API).
        pay_grouped = df_paid.groupby(df_paid["metodo_de_pagamento"].map(_metodo_pagamento_pt))
        for metodo, group in pay_grouped:
            faturamento = float(group["valor_liq"].sum())
            # À vista x parcelado dentro do próprio método: calculado sobre as
            # linhas do grupo pra que a_vista + parcelado feche exatamente com
            # o "qtd" mostrado no card. Sem parcelas informadas = 1 (à vista).
            # a_vista + parcelado_12x + parcelado_outros também fecha com qtd.
            parcelas_grupo = pd.to_numeric(group["quantidade_total_de_parcelas"], errors="coerce").fillna(1).astype(int)
            details.pagamentos.append({
                "metodo": str(metodo),
                "qtd": int(len(group)),
                "a_vista": int((parcelas_grupo == 1).sum()),
                "parcelado": int((parcelas_grupo >= 2).sum()),
                "parcelado_12x": int((parcelas_grupo == 12).sum()),
                "parcelado_outros": int(((parcelas_grupo >= 2) & (parcelas_grupo != 12)).sum()),
                "pct_vendas": float(len(group) / details.total_vendas * 100) if details.total_vendas > 0 else 0.0,
                "faturamento": faturamento,
                "pct_faturamento": float(faturamento / details.faturamento * 100) if details.faturamento > 0 else 0.0,
                "ticket_medio": float(group["valor_liq"].mean()) if not group.empty else 0.0,
            })
        details.pagamentos = sorted(details.pagamentos, key=lambda item: item["qtd"], reverse=True)

    if not df_paid.empty:
        df_paid["parcelas_int"] = pd.to_numeric(df_paid["quantidade_total_de_parcelas"], errors="coerce").fillna(1).astype(int)
        av_df = df_paid[df_paid["metodo_de_pagamento"].str.lower().str.contains("pix|boleto", na=False) | (df_paid["parcelas_int"] == 1)]
        parc_df = df_paid[(df_paid["parcelas_int"] > 1) & df_paid["metodo_de_pagamento"].str.lower().str.contains("cart", na=False)]
        details.fluxo_caixa = {
            "a_vista": float(av_df["valor_liq"].sum()),
            "parcelado": float(parc_df["valor_liq"].sum())
        }

    if not df_paid.empty:
        import re as _re  # noqa: PLC0415
        def _parse_hm_date(s):
            s = str(s or "").strip()
            if _re.match(r'^\d{2}/\d{2}/\d{4}', s):
                try: return pd.to_datetime(s[:10], format="%d/%m/%Y")
                except Exception: pass
            if _re.match(r'^\d{10,13}$', s):
                # epoch (ms se 13 digitos, s caso contrario) — mesmo formato
                # ja tratado no SQL de filtragem (WHERE) e em read_dia1_sales;
                # sem esse branch, toda linha nesse formato virava NaT e
                # sumia da timeline (Hotmart ficava ausente do grafico).
                try:
                    epoch_s = int(s) / 1000 if len(s) == 13 else int(s)
                    return pd.Timestamp(epoch_s, unit="s", tz="UTC").tz_convert("America/Sao_Paulo").tz_localize(None)
                except Exception: pass
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if dt is not pd.NaT and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                    # formato ISO com Z/offset (webhook) vem em UTC — converte
                    # pra Brasília antes de descartar o tz, senão vendas perto
                    # da meia-noite caem no dia errado (mesmo ajuste do epoch acima)
                    dt = dt.tz_convert("America/Sao_Paulo").tz_localize(None)
                return dt
            except Exception: return pd.NaT
        df_paid["data_parsed"] = df_paid["data_da_transacao"].apply(_parse_hm_date)
        d1_date = df_paid["data_parsed"].min()
        timeline_grouped = df_paid.groupby(df_paid["data_parsed"].dt.date).agg(
            vendas=("valor_liq", "count"),
            faturamento=("valor_liq", "sum")
        ).reset_index().sort_values("data_parsed")

        for _, row in timeline_grouped.iterrows():
            dt = row["data_parsed"]
            details.timeline.append({
                "data": dt.strftime("%Y-%m-%d"),
                "data_str": dt.strftime("%d/%b"),
                "vendas": int(row["vendas"]),
                "faturamento": float(row["faturamento"]),
                "is_d1": pd.notna(d1_date) and dt == d1_date.date()
            })

    ofertas_grouped = df_paid.groupby("nome_deste_preco")
    for name, group in ofertas_grouped:
        name_str = str(name).strip()
        tipo = "Base" if name_str.lower() in ("none", "(none)", "") else ("Cross" if "cross" in name_str.lower() else ("Upsell" if "upsell" in name_str.lower() else "Lead"))
        details.ofertas.append({
            "nome": name_str or "Oferta Base",
            "tipo": tipo,
            "qtd": len(group),
            "faturamento": float(group["valor_bruto"].sum()),
            "ticket_medio": float(group["valor_bruto"].mean())
        })
    details.ofertas = sorted(details.ofertas, key=lambda x: x["qtd"], reverse=True)

    for col, target in [("estado_provincia", details.estados), ("cidade", details.cidades)]:
        if col in df_paid.columns:
            g = df_paid.groupby(col).agg(qtd=("valor_bruto", "count"), fat=("valor_bruto", "sum")).sort_values("qtd", ascending=False).head(10)
            for idx, r in g.iterrows():
                target.append({
                    "estado" if col == "estado_provincia" else "cidade": str(idx),
                    "qtd": int(r["qtd"]),
                    "faturamento": float(r["fat"])
                })

    return details


_HM_PAGO = {"completo", "completa", "complete", "completed", "aprovado", "aprovada", "approved", "pago", "paga"}
_HM_CANCELADO = {"cancelado", "cancelada", "canceled", "cancelled"}


def read_hotmart_recompra(launch_folder_or_code: Any, vendas: Any = None) -> dict | None:
    """Boleto gerado e não pago / cartão cancelado → quantos recompraram por
    outro meio (Hotmart ou TMB). Precisa de TODOS os status, então lê
    `hotmart_oficial` (banco operacional) — a `hotmart_clean_oficial` usada
    no resto do dashboard só tem venda paga. Pauta do fechamento do
    debriefing (PI-AGO-26, 04/09/26).

    Janela: dim_lancamentos [data_inicio, data_fim + 7 dias] (boleto vence
    depois do carrinho). "Recomprou" = tem venda paga em qualquer método na
    Hotmart (dentro da janela) ou está entre os compradores TMB do lançamento;
    o meio da recompra é o da PRIMEIRA venda paga da pessoa (1 por pessoa)."""
    code = _extract_launch_code(launch_folder_or_code)
    with _get_engine().connect() as conn:
        l_row = conn.execute(text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
    if not l_row:
        return None
    project, dim_start, dim_end = l_row
    start = _safe_date(dim_start)
    end = _safe_date(dim_end)
    if not start or not end:
        return None
    end_grace = end + pd.Timedelta(days=7).to_pytimedelta()

    from frontend.db_readers.launches import read_launch_config  # noqa: PLC0415
    cfg = read_launch_config(code)
    hotmart_ids = _normalize_product_ids(cfg.get("hotmart_produto_ids"))

    sql = r"""
        SELECT codigo_da_transacao, status_da_transacao, data_da_transacao,
               metodo_de_pagamento, tipo_de_cobranca, email_do_a_comprador_a AS email
        FROM hotmart_oficial
        WHERE CASE
              WHEN produto ILIKE '%inss%' THEN 'INSS'
              WHEN (produto ILIKE '%tj%' OR produto ILIKE '%tjsp%') THEN 'TJ'
              WHEN (produto ILIKE '%bb%' OR produto ILIKE '%banco do brasil%' OR produto ILIKE '%bbsa%') THEN 'BB'
              ELSE 'OUTRO'
          END = :project
          AND (email_do_a_comprador_a IS NULL OR (
              email_do_a_comprador_a NOT ILIKE '%+teste%'
              AND email_do_a_comprador_a NOT ILIKE '%@aprovasim.com'
          ))
    """
    params: dict = {"project": project}
    if hotmart_ids:
        sql += " AND codigo_do_produto::text = ANY(:product_ids)"
        params["product_ids"] = [str(i) for i in hotmart_ids]
    try:
        df = pd.read_sql(text(sql), _get_users_engine(), params=params)
    except Exception:
        logger.exception("read_hotmart_recompra: falha ao ler hotmart_oficial (%s)", code)
        return None
    if df.empty:
        return None

    df["dt"] = pd.to_datetime(df["data_da_transacao"].apply(_hm_parse_date), errors="coerce")
    df = df[(df["dt"] >= pd.Timestamp(start)) & (df["dt"] <= pd.Timestamp(end_grace) + pd.Timedelta(hours=23, minutes=59))].copy()
    if df.empty:
        return None
    df["email"] = df["email"].astype(str).str.lower().str.strip()
    df["status_norm"] = df["status_da_transacao"].astype(str).apply(_norm_text)
    df["metodo_norm"] = df["metodo_de_pagamento"].astype(str).apply(_norm_text)
    df["metodo_label"] = [_hm_metodo_label(m, t) for m, t in zip(df["metodo_de_pagamento"], df["tipo_de_cobranca"])]

    pagos = df[df["status_norm"].isin(_HM_PAGO)].sort_values("dt")
    primeiro_pago = pagos.drop_duplicates(subset="email", keep="first").set_index("email")["metodo_label"].to_dict()

    if vendas is None:
        # Import dentro da função: sales.py importa este módulo no topo.
        from frontend.db_readers.sales import read_vendas  # noqa: PLC0415

        vendas = read_vendas(code)
    tmb_emails = {e.lower() for e in (getattr(vendas, "emails_tmb", set()) or set()) if e}
    pagos_emails = set(primeiro_pago) | tmb_emails

    def _bloco(sub: pd.DataFrame) -> dict:
        pessoas = {e for e in sub["email"] if e and e != "nan"}
        recomp = pessoas & pagos_emails
        por_meio: dict[str, int] = {}
        for e in recomp:
            meio = primeiro_pago.get(e) or "TMB"
            por_meio[meio] = por_meio.get(meio, 0) + 1
        return {
            "transacoes": int(len(sub)),
            "pessoas": len(pessoas),
            "recompraram": len(recomp),
            "nao_recompraram": len(pessoas - recomp),
            "pct_recompra": (len(recomp) / len(pessoas) * 100) if pessoas else 0.0,
            # Desempate por nome do meio: por_meio é montado iterando um set de
            # e-mails, então a ordem de inserção muda a cada processo. Sem o
            # critério total, "Boleto" e "Pix" empatados em 1 trocavam de lugar
            # entre dois carregamentos da mesma página. Mesmo defeito que havia
            # em read_caminho_comprador.
            "por_meio": sorted(
                ({"meio": k, "qtd": v} for k, v in por_meio.items()),
                key=lambda x: (-x["qtd"], x["meio"]),
            ),
        }

    boleto = df[df["metodo_norm"].str.contains("boleto|billet", na=False) & ~df["status_norm"].isin(_HM_PAGO)]
    cartao_canc = df[df["metodo_norm"].str.contains("cart|credit|card|installment", na=False) & df["status_norm"].isin(_HM_CANCELADO)]
    cartao_atrasado = df[df["metodo_norm"].str.contains("cart|credit|card|installment", na=False) & df["status_norm"].isin({"atrasado", "delayed"})]

    return {
        "janela": f"{start.strftime('%d/%m')} a {end_grace.strftime('%d/%m/%Y')}",
        "boleto": _bloco(boleto),
        "cartao": _bloco(cartao_canc),
        "cartao_atrasado": {"transacoes": int(len(cartao_atrasado)), "pessoas": int(cartao_atrasado["email"].nunique())},
    }
