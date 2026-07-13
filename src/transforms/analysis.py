import datetime as dt
from pathlib import Path

from ingest.csv_utils import find_header, normalize_header, read_csv_rows


CATEGORY_ORDER = [
    "Facebook Quente",
    "Facebook Frio",
    "Facebook Especifico",
    "YouTube Quente",
    "YouTube Frio",
    "YouTube Especifico",
    "Pre-Qualificacao YT",
    "Pre-Qualificacao FB",
    "Outros",
]


def _parse_number(raw: str) -> float:
    text = (raw or "").strip().replace('"', "")
    if not text:
        return 0.0
    has_comma = "," in text
    has_dot = "." in text
    if has_comma and has_dot:
        text = text.replace(".", "").replace(",", ".")
    elif has_comma and not has_dot:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_datetime(raw: str) -> dt.datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return dt.datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _is_prequal(text: str) -> bool:
    t = normalize_header(text)
    return "pre quali" in t or "pre qual" in t or "qualifica" in t


def _classify_utm(utm_source: str, utm_medium: str, utm_campaign: str) -> str:
    source = normalize_header(utm_source)
    medium = normalize_header(utm_medium)
    campaign = normalize_header(utm_campaign)
    is_fb = source.startswith("fb") or "facebook" in source
    is_yt = source.startswith("yt") or "youtube" in source or "google" in source or "gads" in source or "adwords" in source
    is_pre = _is_prequal(utm_source) or _is_prequal(utm_medium) or _is_prequal(utm_campaign)

    if is_pre and is_fb:
        return "Pre-Qualificacao FB"
    if is_pre and is_yt:
        return "Pre-Qualificacao YT"

    if is_fb:
        if "frio" in source or "frio" in medium or "frio" in campaign:
            return "Facebook Frio"
        if "especific" in source or "especific" in medium or "especific" in campaign:
            return "Facebook Especifico"
        if "quente" in source or "quente" in medium or "quente" in campaign:
            return "Facebook Quente"
        return "Outros"

    if is_yt:
        if "frio" in source or "frio" in medium or "frio" in campaign:
            return "YouTube Frio"
        if "especific" in source or "especific" in medium or "especific" in campaign:
            return "YouTube Especifico"
        if "quente" in source or "quente" in medium or "quente" in campaign:
            return "YouTube Quente"
        return "Outros"

    return "Outros"


def _classify_campaign(name: str, platform: str) -> str:
    t = normalize_header(name)
    is_pre = _is_prequal(name)
    if platform == "Facebook":
        if is_pre:
            return "Pre-Qualificacao FB"
        if "frio" in t:
            return "Facebook Frio"
        if "especific" in t:
            return "Facebook Especifico"
        if "quente" in t:
            return "Facebook Quente"
        return "Outros"
    if platform == "YouTube":
        if is_pre:
            return "Pre-Qualificacao YT"
        if "frio" in t:
            return "YouTube Frio"
        if "especific" in t:
            return "YouTube Especifico"
        if "quente" in t:
            return "YouTube Quente"
        return "Outros"
    return "Outros"


def _normalize_payment(text: str) -> str:
    t = normalize_header(text)
    if "boleto" in t:
        return "boleto"
    if "pix" in t:
        return "pix"
    if "cart" in t:
        return "cartao"
    return "outros"


def _pick_boleto_status_header(headers: list[str]) -> str | None:
    preferred = find_header(headers, r"situa")
    if preferred:
        return preferred
    return find_header(headers, r"status")


def _first_header(headers: list[str], patterns: list[str]) -> str | None:
    for pattern in patterns:
        h = find_header(headers, pattern)
        if h:
            return h
    return None


def _is_ri_sale(row: dict, tipo_cobranca_h: str | None, recorrencia_h: str | None) -> bool:
    if not tipo_cobranca_h:
        return False
    tipo = normalize_header(row.get(tipo_cobranca_h, ""))
    if "recuperador inteligente" not in tipo:
        return False
    if not recorrencia_h:
        return True
    rec = _parse_number(row.get(recorrencia_h, ""))
    # Keep only first recurring charge to avoid overcounting RI chains.
    return rec in (0.0, 1.0)


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def _format_money(value: float) -> str:
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def run_analysis(config: dict) -> dict:
    launch_code = config["launch"]["code"]
    inputs = config["inputs"]
    campaign_filter = config.get("filters", {}).get("campaign_name_contains", launch_code)

    # Leads
    lead_headers, lead_rows = read_csv_rows(Path(inputs["active_campaign"]["leads_csv"]))
    email_h = _first_header(lead_headers, [r"^email$", r"e mail", r"mail"])
    date_h = find_header(lead_headers, r"data da cria|data cri")
    utm_source_h = find_header(lead_headers, r"utm source")
    utm_medium_h = find_header(lead_headers, r"utm medium")
    utm_campaign_h = find_header(lead_headers, r"utm campaign")
    utm_content_h = find_header(lead_headers, r"utm content")
    utm_term_h = find_header(lead_headers, r"utm term")

    lead_map: dict[str, dict] = {}
    lead_date: dict[str, dt.datetime | None] = {}
    for row in lead_rows:
        email = (row.get(email_h or "", "") or "").strip().lower()
        if not email:
            continue
        created = _parse_datetime(row.get(date_h or "", ""))
        replace = False
        if email not in lead_date:
            replace = True
        elif created and lead_date[email] and created > lead_date[email]:
            replace = True
        elif created and not lead_date[email]:
            replace = True
        if replace:
            lead_date[email] = created
            lead_map[email] = {
                "utm_source": row.get(utm_source_h or "", ""),
                "utm_medium": row.get(utm_medium_h or "", ""),
                "utm_campaign": row.get(utm_campaign_h or "", ""),
                "utm_content": row.get(utm_content_h or "", ""),
                "utm_term": row.get(utm_term_h or "", ""),
            }

    # Sales hotmart
    hot_headers, hot_rows = read_csv_rows(Path(inputs["sales"]["hotmart_csv"]))
    hot_email_h = _first_header(hot_headers, [r"email do", r"^email$", r"e mail"])
    hot_total_h = _first_header(hot_headers, [r"faturamento bruto", r"preco total", r"pre o total", r"valor", r"receita"])
    hot_pay_h = _first_header(hot_headers, [r"tipo de pagamento", r"metodo de pagamento", r"pagamento"])
    hot_tipo_cobranca_h = _first_header(hot_headers, [r"tipo de cobr", r"tipo cobranca"])
    hot_recorrencia_h = _first_header(hot_headers, [r"cobrancas", r"parcela", r"recorr", r"numero de cobr"])

    sales_rows: list[dict] = []
    ri_sales_rows: list[dict] = []
    hotmart_buyers: set[str] = set()
    for row in hot_rows:
        email = (row.get(hot_email_h or "", "") or "").strip().lower()
        if not email:
            continue
        value = _parse_number(row.get(hot_total_h or "", ""))
        payment = _normalize_payment(row.get(hot_pay_h or "", ""))
        entry = {"email": email, "value": value, "payment": payment}
        if _is_ri_sale(row, hot_tipo_cobranca_h, hot_recorrencia_h):
            ri_sales_rows.append(entry)
        else:
            sales_rows.append(entry)
            hotmart_buyers.add(email)

    # Sales boleto (TMB)
    bol_headers, bol_rows = read_csv_rows(Path(inputs["sales"]["boleto_csv"]))
    bol_email_h = _first_header(bol_headers, [r"cliente email", r"e mail", r"^email$"])
    bol_ticket_h = _first_header(bol_headers, [r"ticket", r"valor", r"receita"])
    bol_status_h = _pick_boleto_status_header(bol_headers)
    tmb_buyers: set[str] = set()
    for row in bol_rows:
        if bol_status_h:
            status = normalize_header(row.get(bol_status_h, ""))
            if status not in {"vigente", "efetivado"}:
                continue
        email = (row.get(bol_email_h or "", "") or "").strip().lower()
        if not email:
            continue
        value = _parse_number(row.get(bol_ticket_h or "", ""))
        sales_rows.append({"email": email, "value": value, "payment": "boleto"})
        tmb_buyers.add(email)

    buyers = {row["email"] for row in sales_rows}
    buyers_with_utm = {email for email in buyers if email in lead_map}
    buyers_without_utm = buyers - buyers_with_utm

    ri_buyers = {row["email"] for row in ri_sales_rows}
    ri_buyers_with_utm = {email for email in ri_buyers if email in lead_map}

    total_sales = len(buyers)
    total_revenue = sum(row["value"] for row in sales_rows)
    ri_total_sales = len(ri_buyers)
    ri_total_revenue = sum(row["value"] for row in ri_sales_rows)

    # Spend - Meta
    meta_headers, meta_rows = read_csv_rows(Path(inputs["meta_ads"]["campaigns_csv"]))
    meta_name_h = _first_header(meta_headers, [r"nome da campanha", r"campanha"])
    meta_spend_h = _first_header(meta_headers, [r"valor usado", r"gasto", r"investimento", r"amount spent"])
    meta_spend = 0.0
    spend_by_source: dict[str, float] = {}
    for row in meta_rows:
        name = row.get(meta_name_h or "", "")
        spend = _parse_number(row.get(meta_spend_h or "", ""))
        meta_spend += spend
        cat = _classify_campaign(name, "Facebook")
        spend_by_source[cat] = spend_by_source.get(cat, 0.0) + spend

    # Spend - Google (YouTube)
    g_headers, g_rows = read_csv_rows(
        Path(inputs["google_ads"]["campaigns_csv"]),
        required_headers=["campanha", "custo"],
    )
    g_name_h = _first_header(g_headers, [r"^campanha$", r"campaign"])
    g_spend_h = _first_header(g_headers, [r"^custo$", r"cost", r"valor"])
    yt_spend = 0.0
    for row in g_rows:
        name = row.get(g_name_h or "", "")
        if campaign_filter and campaign_filter not in name:
            continue
        spend = _parse_number(row.get(g_spend_h or "", ""))
        yt_spend += spend
        cat = _classify_campaign(name, "YouTube")
        spend_by_source[cat] = spend_by_source.get(cat, 0.0) + spend

    total_spend = meta_spend + yt_spend
    roas = total_revenue / total_spend if total_spend else 0.0

    # Revenue and buyers by source
    revenue_by_source: dict[str, float] = {}
    buyers_by_source: dict[str, set[str]] = {}
    for row in sales_rows:
        email = row["email"]
        if email not in lead_map:
            continue
        lead = lead_map[email]
        cat = _classify_utm(lead["utm_source"], lead["utm_medium"], lead["utm_campaign"])
        revenue_by_source[cat] = revenue_by_source.get(cat, 0.0) + row["value"]
        buyers_by_source.setdefault(cat, set()).add(email)

    total_buyers_with_utm = len(buyers_with_utm)

    distribution = []
    for source in CATEGORY_ORDER:
        buyers_count = len(buyers_by_source.get(source, set()))
        pct = buyers_count / total_buyers_with_utm if total_buyers_with_utm else 0.0
        revenue = revenue_by_source.get(source, 0.0)
        spend = spend_by_source.get(source, 0.0)
        roas_source = revenue / spend if spend else 0.0
        distribution.append(
            {
                "source": source,
                "buyers": buyers_count,
                "pct": _format_percent(pct),
                "revenue": _format_money(revenue),
                "spend": _format_money(spend),
                "roas": f"{roas_source:.2f}".replace(".", ","),
                "revenue_raw": revenue,
                "spend_raw": spend,
                "roas_raw": roas_source,
            }
        )

    # Top UTMs by category
    utm_agg: dict[str, dict] = {}
    for row in sales_rows:
        email = row["email"]
        if email not in lead_map:
            continue
        lead = lead_map[email]
        cat = _classify_utm(lead["utm_source"], lead["utm_medium"], lead["utm_campaign"])
        key = f'{lead["utm_source"]} | {lead["utm_medium"]} | {lead["utm_campaign"]}'
        agg_key = f"{cat}||{key}"
        if agg_key not in utm_agg:
            utm_agg[agg_key] = {
                "category": cat,
                "utm_source": lead["utm_source"],
                "utm_medium": lead["utm_medium"],
                "utm_campaign": lead["utm_campaign"],
                "buyers": set(),
                "revenue": 0.0,
                "cartao": 0,
                "boleto": 0,
                "pix": 0,
                "outros": 0,
            }
        item = utm_agg[agg_key]
        item["buyers"].add(email)
        item["revenue"] += row["value"]
        if row["payment"] == "cartao":
            item["cartao"] += 1
        elif row["payment"] == "boleto":
            item["boleto"] += 1
        elif row["payment"] == "pix":
            item["pix"] += 1
        else:
            item["outros"] += 1

    top_utms: dict[str, list[dict]] = {cat: [] for cat in CATEGORY_ORDER}
    for item in utm_agg.values():
        cat = item["category"]
        top_utms.setdefault(cat, []).append(item)

    for cat, items in top_utms.items():
        items.sort(key=lambda x: x["revenue"], reverse=True)
        top_utms[cat] = [
            {
                "buyers": len(i["buyers"]),
                "revenue": _format_money(i["revenue"]),
                "revenue_raw": i["revenue"],
                "cartao": i["cartao"],
                "boleto": i["boleto"],
                "pix": i["pix"],
                "outros": i["outros"],
                "utm_source": i["utm_source"],
                "utm_medium": i["utm_medium"],
                "utm_campaign": i["utm_campaign"],
            }
            for i in items[:3]
        ]

    return {
        "launch_code": launch_code,
        "total_sales": total_sales,
        "total_revenue": _format_money(total_revenue),
        "total_revenue_raw": total_revenue,
        "buyers_with_utm": len(buyers_with_utm),
        "buyers_without_utm": len(buyers_without_utm),
        "buyers_with_utm_pct": _format_percent(len(buyers_with_utm) / total_sales if total_sales else 0),
        "buyers_without_utm_pct": _format_percent(len(buyers_without_utm) / total_sales if total_sales else 0),
        "fb_spend": _format_money(meta_spend),
        "yt_spend": _format_money(yt_spend),
        "roas": f"{roas:.2f}".replace(".", ","),
        "total_sales_raw": total_sales,
        "hotmart_sales_raw": len(hotmart_buyers),
        "tmb_sales_raw": len(tmb_buyers),
        "fb_spend_raw": meta_spend,
        "yt_spend_raw": yt_spend,
        "roas_raw": roas,
        "distribution": distribution,
        "top_utms": top_utms,
        "ri_summary": {
            "sales": ri_total_sales,
            "revenue": _format_money(ri_total_revenue),
            "revenue_raw": ri_total_revenue,
            "buyers_with_utm": len(ri_buyers_with_utm),
            "buyers_with_utm_pct": _format_percent(len(ri_buyers_with_utm) / ri_total_sales if ri_total_sales else 0),
            "buyers_without_utm": ri_total_sales - len(ri_buyers_with_utm),
            "buyers_without_utm_pct": _format_percent((ri_total_sales - len(ri_buyers_with_utm)) / ri_total_sales if ri_total_sales else 0),
        },
    }
