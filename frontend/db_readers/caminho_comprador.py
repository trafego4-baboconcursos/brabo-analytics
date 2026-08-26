"""
frontend/db_readers/caminho_comprador.py — Base unificada "Caminho do Comprador".

Pauta do debriefing (reunião 25/08/26), item 7: pra cada comprador, tentar
identificar origem/anúncio → data de cadastro → normal/VIP → respondeu
pesquisa? → comprou → orgânico/comercial, juntando por e-mail/telefone.

"Participou do sorteio/live" fica de fora — não existe fonte pra isso ainda
(ver levantamento em documentacao/historico/LEVANTAMENTO_DEBRIEFING_MELHORIAS_2026-08-25.md).
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _extract_launch_code
from frontend.db import _get_engine
from frontend.db_readers.whatsapp_groups import _escolhe_tabela, _norm_phone

logger = get_logger("db")


def _plataforma_lead(utm_source: Any) -> str | None:
    s = str(utm_source or "").strip().lower()
    if not s:
        return None
    if "facebook" in s or s in ("fb", "ig", "instagram", "meta"):
        return "Meta"
    if "google" in s or "youtube" in s or s == "yt":
        return "Google"
    return "Outro"


def read_caminho_comprador(launch_folder_or_code: Any, vendas: Any = None) -> dict | None:
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415 — evita import circular
    from frontend.db_readers.typeform import _resolve_typeform_ids  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    if vendas is None:
        vendas = read_vendas(code)
    if not vendas:
        return None
    buyers = {e for e in (vendas.emails_hotmart | vendas.emails_tmb) if e}
    if not buyers:
        return None

    engine = _get_engine()

    # 1. Lead: código do anúncio (utm_term, fallback utm_content), plataforma, data de cadastro
    leads_df = pd.read_sql(
        text("""
            SELECT LOWER(email) AS email, utm_term, utm_content, utm_source, created_at
            FROM leads WHERE lancamento_codigo = :code AND LOWER(email) = ANY(:emails)
        """),
        engine, params={"code": code, "emails": [e.lower() for e in buyers]},
    )
    lead_info: dict[str, dict] = {}
    if not leads_df.empty:
        ad_term = leads_df["utm_term"].astype(str).str.extract(r"^(AD\d+)", flags=re.IGNORECASE)[0]
        ad_content = leads_df["utm_content"].astype(str).str.extract(r"^(AD\d+)", flags=re.IGNORECASE)[0]
        leads_df["ad_code"] = ad_term.fillna(ad_content).str.upper()
        for _, r in leads_df.iterrows():
            lead_info[r["email"]] = {
                "ad_code": r["ad_code"] if pd.notna(r["ad_code"]) else None,
                "plataforma": _plataforma_lead(r["utm_source"]),
                "data_cadastro": str(r["created_at"])[:10] if pd.notna(r["created_at"]) else None,
            }

    # 2. Grupos WhatsApp — normal × VIP, por telefone
    base = code.replace("-", "_")
    candidatos_normal = [f"{base}_API", base]
    candidatos_vip = [f"{base}_VIP_API", f"{base}_VIPS", f"{base}_VIP",
                       base.rsplit("_", 1)[0] + "_VIP"]
    fones_normal: set[str] = set()
    fones_vip: set[str] = set()
    with engine.connect() as conn:
        t_normal = _escolhe_tabela(conn, candidatos_normal)
        t_vip = _escolhe_tabela(conn, candidatos_vip)
        if t_normal:
            rows = conn.execute(text(f'SELECT DISTINCT "NÚMERO" FROM "{t_normal}"')).fetchall()
            fones_normal = {p for p in (_norm_phone(r[0]) for r in rows) if p}
        if t_vip:
            rows = conn.execute(text(f'SELECT DISTINCT "NÚMERO" FROM "{t_vip}"')).fetchall()
            fones_vip = {p for p in (_norm_phone(r[0]) for r in rows) if p}

        # 3. Pesquisa — quem respondeu, por e-mail
        proj_id, _ = _resolve_typeform_ids(code)
        proj_id = proj_id or code
        tf_rows = conn.execute(
            text("SELECT DISTINCT LOWER(email) FROM typeform_respostas WHERE upper(coalesce(form_id, '')) = :fid AND email IS NOT NULL"),
            {"fid": proj_id.upper()},
        ).fetchall()
        respondentes = {r[0] for r in tf_rows}

    canal_por_email = vendas.canal_por_email or {}
    receita = vendas.receita_por_email or {}
    vendas_por_email = vendas.vendas_por_email or {}
    phone_por_email = vendas.phone_por_email or {}
    estado_por_email = vendas.estado_por_email or {}
    nome_por_email = vendas.nome_por_email or {}

    rows = []
    for email in buyers:
        li = lead_info.get(email, {})
        phone = _norm_phone(phone_por_email.get(email))
        if phone and phone in fones_vip:
            grupo = "VIP"
        elif phone and phone in fones_normal:
            grupo = "Normal"
        else:
            grupo = "Nenhum"
        rows.append({
            "email": email,
            "nome": nome_por_email.get(email, ""),
            "estado": estado_por_email.get(email),
            "ad_code": li.get("ad_code"),
            "plataforma": li.get("plataforma"),
            "data_cadastro": li.get("data_cadastro"),
            "grupo": grupo,
            "respondeu_pesquisa": email in respondentes,
            "canal": canal_por_email.get(email, "Orgânico"),
            "vendas": int(vendas_por_email.get(email, 0)),
            "receita": float(receita.get(email, 0)),
        })
    rows.sort(key=lambda r: r["receita"], reverse=True)

    total = len(rows)

    def _pct(n: int) -> float:
        return n / total * 100 if total else 0.0

    com_lead = sum(1 for r in rows if r["ad_code"])
    com_grupo = sum(1 for r in rows if r["grupo"] != "Nenhum")
    com_pesquisa = sum(1 for r in rows if r["respondeu_pesquisa"])
    comercial_ia = sum(1 for r in rows if r["canal"] != "Orgânico")

    resumo = {
        "total": total,
        "com_lead": com_lead, "pct_lead": _pct(com_lead),
        "com_grupo": com_grupo, "pct_grupo": _pct(com_grupo),
        "vip": sum(1 for r in rows if r["grupo"] == "VIP"),
        "com_pesquisa": com_pesquisa, "pct_pesquisa": _pct(com_pesquisa),
        "comercial_ia": comercial_ia, "pct_comercial_ia": _pct(comercial_ia),
    }
    return {"rows": rows, "resumo": resumo}
