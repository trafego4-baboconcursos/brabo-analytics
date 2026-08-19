"""
frontend/db_readers/typeform.py — Integração com a API do Typeform e leitura do banco.
"""
from __future__ import annotations

import os
import json
import re
import time as _time_module
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.utils import _norm_text, _extract_launch_code
from frontend.db import _get_engine
from frontend.models import TypeformSummary
from src.typeform_resolve import fetch_typeform_forms, resolve_projeto_alunos_form_ids

logger = get_logger("db")

_typeform_forms_cache: dict[str, str] | None = None
_typeform_forms_cache_expiry: float = 0.0
_typeform_fields_cache: dict[str, dict[str, str]] = {}

_TYPEFORM_CACHE_TTL_OK  = 1800.0   # 30 min quando API responde
_TYPEFORM_CACHE_TTL_ERR = 3600.0   # 1 h quando API falha (backoff)


def _get_typeform_forms() -> dict[str, str]:
    global _typeform_forms_cache, _typeform_forms_cache_expiry
    now = _time_module.time()
    if _typeform_forms_cache is not None and now < _typeform_forms_cache_expiry:
        return _typeform_forms_cache

    token = os.environ.get("TYPEFORM_TOKEN")
    if not token:
        return {}
    try:
        _typeform_forms_cache = fetch_typeform_forms(token)
        _typeform_forms_cache_expiry = now + _TYPEFORM_CACHE_TTL_OK
    except Exception:
        logger.exception("Erro ao obter formulários da API do Typeform")
        _typeform_forms_cache = {}
        _typeform_forms_cache_expiry = now + _TYPEFORM_CACHE_TTL_ERR

    return _typeform_forms_cache or {}


def _get_typeform_fields(form_id: str) -> dict[str, str]:
    global _typeform_fields_cache
    if form_id in _typeform_fields_cache:
        return _typeform_fields_cache[form_id]

    token = os.environ.get("TYPEFORM_TOKEN")
    if not token:
        return {}

    import requests
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.typeform.com/forms/{form_id}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        form_data = r.json()
        fields = form_data.get("fields", [])
        mapping = {f["id"]: f["title"] for f in fields if "id" in f and "title" in f}
        _typeform_fields_cache[form_id] = mapping
    except Exception:
        logger.exception("Erro ao obter campos do form %s no Typeform", form_id)
        _typeform_fields_cache[form_id] = {}

    return _typeform_fields_cache[form_id]


def _resolve_typeform_ids(code: str) -> tuple[Optional[str], Optional[str]]:
    forms = _get_typeform_forms()
    return resolve_projeto_alunos_form_ids(code, forms)


def _reconstruct_tabular_df(tf_df_raw: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    if tf_df_raw.empty:
        return records

    # Pre-fetch mappings for all unique form_ids in the DataFrame
    unique_forms = tf_df_raw["form_id"].dropna().unique()
    form_mappings = {}
    for fid in unique_forms:
        form_mappings[fid] = _get_typeform_fields(fid)

    for _, row in tf_df_raw.iterrows():
        email = str(row["email"]).strip().lower()
        if not email or "@" not in email:
            continue

        row_form_id = row.get("form_id")
        mapping = form_mappings.get(row_form_id, {})

        answers_list = row["answers"]
        if isinstance(answers_list, str):
            try:
                answers_list = json.loads(answers_list)
            except Exception:
                answers_list = []
        elif not isinstance(answers_list, list):
            answers_list = []

        row_data = {"email_norm": email}
        for ans in answers_list:
            field_obj = ans.get("field", {})
            fid = field_obj.get("id")

            # Fallback chain: raw title field -> API title mapping -> raw ID field
            title = field_obj.get("title") or mapping.get(fid) or fid
            if not title:
                continue

            a_type = ans.get("type")
            val = ""
            if a_type == "choice":
                val = ans.get("choice", {}).get("label", "")
            elif a_type == "choices":
                val = ", ".join(ans.get("choices", {}).get("labels", []))
            elif a_type == "text":
                val = ans.get("text", "")
            elif a_type == "email":
                val = ans.get("email", "")
            elif a_type == "number":
                val = str(ans.get("number", ""))
            elif a_type == "boolean":
                val = str(ans.get("boolean", ""))

            row_data[title] = val
        records.append(row_data)
    return records


def _build_typeform_comparison(
    summary: TypeformSummary,
    df_proj: pd.DataFrame,
    df_alunos_raw: pd.DataFrame,
    proj_id: str,
    alunos_id: str,
) -> None:
    if df_proj.empty or df_alunos_raw.empty:
        summary.compare_available = False
        return

    records_alunos = _reconstruct_tabular_df(df_alunos_raw)
    if not records_alunos:
        summary.compare_available = False
        return

    df_alunos = pd.DataFrame(records_alunos)
    df_alunos = df_alunos.drop_duplicates("email_norm", keep="last")

    emails_proj = set(df_proj["email_norm"])
    emails_alunos = set(df_alunos["email_norm"])
    overlap = emails_proj & emails_alunos

    forms = _get_typeform_forms()
    label_proj = forms.get(proj_id, "Pesquisa Projeto")
    label_alunos = forms.get(alunos_id, "Pesquisa Alunos")

    summary.compare_available = True
    summary.compare_label_a = label_proj
    summary.compare_label_b = label_alunos
    summary.compare_total_a = int(len(emails_proj))
    summary.compare_total_b = int(len(emails_alunos))
    summary.compare_overlap = int(len(overlap))
    summary.compare_only_a = int(len(emails_proj - emails_alunos))
    summary.compare_only_b = int(len(emails_alunos - emails_proj))

    identical = (
        summary.compare_total_a == summary.compare_total_b
        and summary.compare_overlap == summary.compare_total_a
        and df_proj.shape == df_alunos.shape
    )
    summary.compare_identical = identical

    insights: list[str] = []
    if identical:
        insights.append(
            "As duas pesquisas parecem conter a mesma base de respondentes."
        )
    else:
        if summary.compare_total_a:
            overlap_pct_a = summary.compare_overlap / summary.compare_total_a * 100
            insights.append(
                f"Pesquisa de Alunos cobre {overlap_pct_a:.1f}% da base da Pesquisa de Projeto por e-mail."
            )
        if summary.compare_only_a:
            insights.append(
                f"Pesquisa de Projeto traz {summary.compare_only_a:,} respondentes exclusivos que não se inscreveram ou não responderam na pesquisa de Alunos.".replace(",", ".")
            )
        if summary.compare_only_b:
            insights.append(
                f"Pesquisa de Alunos traz {summary.compare_only_b:,} respondentes exclusivos que não aparecem na pesquisa de Projeto.".replace(",", ".")
            )

        common_cols = [
            ("estado", "Estado"),
            ("genero", "Gênero"),
            ("idade", "Idade"),
            ("situacao profissional", "Situação profissional"),
            ("voce se considera", "Perfil de estudo"),
        ]
        diffs = []
        for pattern, label in common_cols:
            col_a = next((c for c in df_proj.columns if pattern in _norm_text(c)), None)
            col_b = next((c for c in df_alunos.columns if pattern in _norm_text(c)), None)
            if not col_a or not col_b:
                continue

            dist_a = df_proj[col_a].astype(str).str.strip()
            dist_b = df_alunos[col_b].astype(str).str.strip()
            dist_a = dist_a[dist_a.ne("")]
            dist_b = dist_b[dist_b.ne("")]
            if dist_a.empty or dist_b.empty:
                continue

            pct_a = dist_a.value_counts(normalize=True) * 100
            pct_b = dist_b.value_counts(normalize=True) * 100
            all_keys = set(pct_a.index) | set(pct_b.index)

            best_key = None
            best_diff = 0.0
            for key in all_keys:
                diff = abs(float(pct_a.get(key, 0.0)) - float(pct_b.get(key, 0.0)))
                if diff > best_diff:
                    best_diff = diff
                    best_key = str(key)
            if best_key and best_diff >= 3:
                diffs.append((best_diff, f"{label}: '{best_key}' varia {best_diff:.1f} p.p. entre as duas pesquisas (Projeto vs Alunos)."))

        for _, text_ins in sorted(diffs, reverse=True)[:3]:
            insights.append(text_ins)
    summary.compare_insights = insights

    # Insights específicos de compradores (Alunos)
    influence_col = next((c for c in df_alunos.columns if "influenciou" in c.lower() or "decisao de entrar" in c.lower()), None)
    if influence_col:
        all_choices = []
        for val in df_alunos[influence_col].dropna():
            parts = [p.strip() for p in str(val).split(",") if p.strip()]
            all_choices.extend(parts)
        if all_choices:
            series_choices = pd.Series(all_choices)
            vc = series_choices.value_counts()
            summary.top_influence_factors = [
                {"opcao": str(opt), "qtd": int(cnt), "pct": float(cnt / len(df_alunos) * 100)}
                for opt, cnt in vc.items() if str(opt).strip() != ""
            ]

    def extract_depoimentos(col_pattern: str, min_len: int = 25, limit: int = 8) -> list[str]:
        col = next((c for c in df_alunos.columns if col_pattern in _norm_text(c)), None)
        if not col:
            return []
        series = df_alunos[col].dropna().astype(str).str.strip()
        filtered = []
        for t in series:
            t_clean = t.replace("\n", " ").replace("\r", " ").strip()
            if (len(t_clean) >= min_len
                    and not t_clean.lower().startswith("asdas")
                    and not t_clean.lower().startswith("teste")
                    and len(set(t_clean.lower())) > 6):
                filtered.append(t_clean)
        filtered_sorted = sorted(filtered, key=len, reverse=True)
        return filtered_sorted[:limit]

    summary.alunos_depoimentos_decidir = extract_depoimentos("o que fez voce decidir entrar")
    summary.alunos_depoimentos_convenceu = extract_depoimentos("o que o felipe falou que convenceu")
    summary.alunos_depoimentos_atencao = extract_depoimentos("o que mais chamou sua atencao")


def read_typeform(launch_folder_or_code: Any, start_date=None, end_date=None) -> TypeformSummary:
    # deferred import to avoid circular dependency (read_vendas still in database_reader)
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415

    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()
    summary = TypeformSummary()

    with engine.connect() as conn:
        l_row = conn.execute(text("SELECT projeto, data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
        if not l_row:
            return summary
        project, start_date, end_date = l_row

    proj_id, alunos_id = _resolve_typeform_ids(code)
    if not proj_id:
        proj_id = code

    # 1. Carrega dados do Typeform do Supabase
    tf_df_raw = pd.read_sql(
        text("SELECT * FROM typeform_respostas WHERE upper(coalesce(form_id, '')) = :fid"),
        engine,
        params={"fid": proj_id.upper()}
    )
    if tf_df_raw.empty:
        # Fallback histórico por data e código do lançamento
        tf_df_raw = pd.read_sql(
            text("""
                SELECT *
                FROM typeform_respostas
                WHERE submitted_at::date BETWEEN :start AND :end
                  AND upper(coalesce(form_id, '')) = :code
            """),
            engine,
            params={"start": start_date, "end": end_date, "code": code.upper()}
        )

    if tf_df_raw.empty:
        return summary

    summary.has_data = True
    summary.total_tf_raw = len(tf_df_raw)

    # Reconstruir o DataFrame tabular baseado nas respostas JSONB
    records = _reconstruct_tabular_df(tf_df_raw)
    if not records:
        return summary

    tf_df = pd.DataFrame(records)
    tf_df = tf_df.drop_duplicates("email_norm", keep="last")
    summary.total_tf = len(tf_df)

    # Confrontar pesquisas
    tf_alunos_raw = pd.DataFrame()
    if alunos_id:
        tf_alunos_raw = pd.read_sql(
            text("SELECT * FROM typeform_respostas WHERE upper(coalesce(form_id, '')) = :fid"),
            engine,
            params={"fid": alunos_id.upper()}
        )
    if not tf_alunos_raw.empty:
        _build_typeform_comparison(summary, tf_df, tf_alunos_raw, proj_id, alunos_id)

    # 2. Carrega vendas e CRM para cruzamento
    # Mesma janela usada pelos demais readers — evita duplicar a consulta inteira
    # de Hotmart+TMB com uma cache-key diferente (start=None).
    v_sum = read_vendas(code, start_date=start_date, end_date=end_date)
    buyers = (v_sum.emails_hotmart | v_sum.emails_tmb) if v_sum else set()
    summary.vendas_hotmart_total = v_sum.hotmart_vendas if v_sum else 0
    summary.vendas_tmb_total = v_sum.tmb_vendas if v_sum else 0
    summary.receita_total = v_sum.total_receita if v_sum else 0.0

    # CRM leads
    leads_df = pd.read_sql(
        text("SELECT email, utm_source, utm_content FROM leads WHERE lancamento_codigo = :code"),
        engine,
        params={"code": code}
    )
    crm_emails = set(leads_df["email"].str.strip().str.lower()) if not leads_df.empty else set()
    summary.leads_crm_total = len(leads_df)

    # Cruzamento
    tf_emails = set(tf_df["email_norm"])
    tf_e_crm = tf_emails & crm_emails
    tf_e_vendas = tf_emails & buyers

    summary.tf_leads_crm = len(tf_e_crm)
    summary.tf_compras = len(tf_e_vendas)
    summary.tf_compras_crm = len(tf_e_crm & buyers)

    summary.tx_lead_pct = summary.tf_leads_crm / summary.total_tf * 100 if summary.total_tf > 0 else 0.0
    summary.tx_venda_tf_pct = summary.tf_compras / summary.total_tf * 100 if summary.total_tf > 0 else 0.0
    if summary.leads_crm_total > 0:
        total_compradores_crm = len(crm_emails & buyers)
        summary.tx_venda_lead_pct = total_compradores_crm / summary.leads_crm_total * 100

    summary.receita_tf = sum(v_sum.receita_por_email.get(em, 0.0) for em in tf_e_vendas) if v_sum else 0.0
    summary.receita_tf_pct = summary.receita_tf / summary.receita_total * 100 if summary.receita_total > 0 else 0.0

    # Demografia
    tf_comp = tf_df[tf_df["email_norm"].isin(tf_e_vendas)].copy()
    tf_ncomp = tf_df[~tf_df["email_norm"].isin(tf_e_vendas)].copy()

    def comp_ncomp_distribution(col_name_part: str) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        col = None
        pattern = re.compile(r"\b" + re.escape(col_name_part.lower()) + r"\b")
        for c in tf_df.columns:
            if pattern.search(_norm_text(c)):
                col = c
                break
        if not col or tf_comp.empty:
            return {}, {}, {}

        vc_comp = tf_comp[col].value_counts(normalize=True) * 100
        vc_ncomp = tf_ncomp[col].value_counts(normalize=True) * 100 if not tf_ncomp.empty else pd.Series()

        all_keys = set(vc_comp.index) | set(vc_ncomp.index)

        comp_dist = {}
        ncomp_dist = {}
        diff_dist = {}

        for k in all_keys:
            if pd.isna(k) or str(k).strip() == "":
                continue
            c_val = float(vc_comp.get(k, 0.0))
            nc_val = float(vc_ncomp.get(k, 0.0)) if not vc_ncomp.empty else 0.0
            comp_dist[str(k)] = c_val
            ncomp_dist[str(k)] = nc_val
            diff_dist[str(k)] = c_val - nc_val

        sorted_keys = sorted(comp_dist.keys(), key=lambda x: comp_dist[x], reverse=True)
        return (
            {k: comp_dist[k] for k in sorted_keys},
            {k: ncomp_dist[k] for k in sorted_keys},
            {k: diff_dist[k] for k in sorted_keys}
        )

    summary.genero_comp_pct, summary.genero_ncomp_pct, summary.genero_diff = comp_ncomp_distribution("genero")
    summary.situacao_comp_pct, summary.situacao_ncomp_pct, summary.situacao_diff = comp_ncomp_distribution("situacao profissional")
    summary.nivel_comp_pct, summary.nivel_ncomp_pct, summary.nivel_diff = comp_ncomp_distribution("voce se considera")
    summary.idade_comp_pct, summary.idade_ncomp_pct, summary.idade_diff = comp_ncomp_distribution("idade")
    summary.graton_comp_pct, summary.graton_ncomp_pct, summary.graton_diff = comp_ncomp_distribution("felipe graton")

    # Obstáculos
    obstaculos = [
        ("Não sei estudar do jeito certo", ["nao sei estudar do jeito certo", "falta de tecnicas de estudos"]),
        ("Não sei montar um cronograma", ["nao sei montar um cronograma"]),
        ("Procrastinação", ["procrastinacao"]),
        ("Estou há muito tempo sem estudar", ["tempo sem estudar"]),
        ("Pouco tempo disponível", ["pouco tempo disponivel"]),
        ("Medo de esquecer no dia da prova", ["esquecer tudo no dia da prova", "esquecer no dia da prova"]),
        ("Medo de estudar e não passar", ["estudar muito e nao conseguir passar", "estudar e nao passar"]),
        ("Sem dinheiro para curso", ["dinheiro para investir", "dinheiro para curso", "sem dinheiro"]),
        ("Medo de não sair o concurso", ["nao sair o concurso"]),
    ]

    obst_comp = {}
    obst_ncomp = {}
    obst_diff = {}

    for label, patterns in obstaculos:
        col = None
        for c in tf_df.columns:
            c_norm = _norm_text(c)
            if _norm_text(label) in c_norm or any(_norm_text(pat) in c_norm for pat in patterns):
                col = c
                break
        if col:
            val_comp = (tf_comp[col].notna().sum() / len(tf_comp) * 100) if len(tf_comp) > 0 else 0.0
            val_ncomp = (tf_ncomp[col].notna().sum() / len(tf_ncomp) * 100) if len(tf_ncomp) > 0 else 0.0
        else:
            preocupacoes_col = None
            for c in tf_df.columns:
                c_norm = _norm_text(c)
                if "preocupam" in c_norm or "preocupa" in c_norm or "opcao" in c_norm or "dificuldade" in c_norm:
                    preocupacoes_col = c
                    break
            if preocupacoes_col:
                comp_series = tf_comp[preocupacoes_col].dropna().astype(str).apply(_norm_text)
                ncomp_series = tf_ncomp[preocupacoes_col].dropna().astype(str).apply(_norm_text)
                combined_pattern = "|".join([_norm_text(pat) for pat in patterns])
                count_comp = comp_series.str.contains(combined_pattern, regex=True).sum()
                count_ncomp = ncomp_series.str.contains(combined_pattern, regex=True).sum()
                val_comp = (count_comp / len(tf_comp) * 100) if len(tf_comp) > 0 else 0.0
                val_ncomp = (count_ncomp / len(tf_ncomp) * 100) if len(tf_ncomp) > 0 else 0.0
            else:
                val_comp = 0.0
                val_ncomp = 0.0
        obst_comp[label] = val_comp
        obst_ncomp[label] = val_ncomp
        obst_diff[label] = val_comp - val_ncomp

    sorted_obst = sorted(obst_comp.keys(), key=lambda x: obst_comp[x], reverse=True)
    summary.obstaculos_comp_pct = {k: obst_comp[k] for k in sorted_obst}
    summary.obstaculos_ncomp_pct = {k: obst_ncomp[k] for k in sorted_obst}
    summary.obstaculos_diff = {k: obst_diff[k] for k in sorted_obst}

    # Geografia & UTMs
    estado_col = None
    for c in tf_df.columns:
        if "estado" in _norm_text(c):
            estado_col = c
            break
    if not estado_col:
        # Fallback: usa a exportação local do Typeform quando o título do campo
        # não veio de forma consistente no JSON salvo no banco.
        typeform_dir = Path("analises") / f"[{code}]" / "Typeform"
        csv_candidates = []
        if typeform_dir.exists():
            csv_candidates = sorted(typeform_dir.glob("*.csv"), key=lambda p: ("pesquisa" not in p.name.lower(), p.name.lower()))
        for csv_path in csv_candidates:
            try:
                local_df = pd.read_csv(csv_path, encoding="utf-8")
            except Exception:
                logger.warning("Falha ao ler CSV %s; pulando", csv_path)
                continue
            email_col = next((c for c in local_df.columns if "mail" in _norm_text(c)), None)
            estado_local_col = next((c for c in local_df.columns if "estado" in _norm_text(c)), None)
            if not email_col or not estado_local_col:
                continue
            local_geo = local_df[[email_col, estado_local_col]].copy()
            local_geo["email_norm"] = local_geo[email_col].astype(str).str.strip().str.lower()
            local_geo[estado_local_col] = local_geo[estado_local_col].astype(str).str.strip()
            local_geo = local_geo[local_geo["email_norm"].str.contains("@", na=False)]
            local_geo = local_geo[local_geo[estado_local_col] != ""]
            local_geo = local_geo.drop_duplicates("email_norm", keep="last")
            if local_geo.empty:
                continue
            tf_df = tf_df.merge(
                local_geo[["email_norm", estado_local_col]].rename(columns={estado_local_col: "__estado_fallback__"}),
                on="email_norm",
                how="left",
            )
            tf_comp = tf_df[tf_df["email_norm"].isin(tf_e_vendas)].copy()
            estado_col = "__estado_fallback__"
            break
    if estado_col:
        vc_geral = tf_df[estado_col].value_counts()
        summary.top_estados_geral = [
            {"estado": str(est), "qtd": int(qtd), "pct": float(qtd / len(tf_df) * 100)}
            for est, qtd in vc_geral.head(10).items() if str(est).strip() != ""
        ]

        vc_comp = tf_comp[estado_col].value_counts()
        summary.top_estados_comp = [
            {"estado": str(est), "qtd": int(qtd), "pct": float(qtd / len(tf_comp) * 100) if len(tf_comp) > 0 else 0.0}
            for est, qtd in vc_comp.head(10).items() if str(est).strip() != ""
        ]

    # UTMs de leads AC dos respondentes compradores (Anúncios / utm_content)
    if not leads_df.empty:
        leads_df["email_norm"] = leads_df["email"].str.strip().str.lower()
        crm_comp_tf = leads_df[leads_df["email_norm"].isin(tf_e_vendas)]
        if not crm_comp_tf.empty:
            ad_group = crm_comp_tf.groupby("utm_content", dropna=False).agg(
                qtd=("email_norm", "count"),
                source=("utm_source", lambda x: x.mode()[0] if not x.mode().empty else None)
            ).reset_index()
            ad_group = ad_group.sort_values(by="qtd", ascending=False).head(10)
            for _, row in ad_group.iterrows():
                ad_name = str(row["utm_content"]) if pd.notna(row["utm_content"]) and str(row["utm_content"]).strip() != "" else "Sem identificação de anúncio"
                src_val = str(row["source"]) if pd.notna(row["source"]) else ""
                plat = "Outros"
                src_lower = src_val.lower()
                ad_lower = ad_name.lower()
                if src_lower.startswith("yt") or "youtube" in src_lower or "yt-" in ad_lower:
                    plat = "YouTube"
                elif src_lower.startswith("fb") or "facebook" in src_lower or "meta" in src_lower or "instagram" in src_lower or "fb-" in ad_lower or "instagram" in ad_lower:
                    plat = "Meta / FB"
                summary.top_utm_sources.append({
                    "source": ad_name,
                    "qtd": int(row["qtd"]),
                    "canal": plat
                })

    summary.ia_insights = _generate_ia_insights(summary)
    return summary


def _generate_ia_insights(summary: TypeformSummary) -> list[dict]:
    insights = []

    # 1. Análise de Gênero
    gen_diff = summary.genero_diff.get("Masculino", 0.0)
    if gen_diff > 5:
        insights.append({
            "tipo": "oportunidade",
            "icone": "ti ti-trending-up",
            "titulo": "Alta Conversão Masculina",
            "descricao": f"O público Masculino apresentou uma conversão muito maior (+{gen_diff:.0f} pp) entre compradores do que na captação geral. Recomendamos direcionar criativos específicos e maior verba para esse segmento nas campanhas de tráfego do próximo lançamento."
        })
    elif gen_diff < -5:
        insights.append({
            "tipo": "oportunidade",
            "icone": "ti ti-trending-up",
            "titulo": "Alta Conversão Feminina",
            "descricao": f"O público Feminino apresentou uma conversão muito maior (+{abs(gen_diff):.0f} pp) entre compradores do que na captação geral. Recomendamos adaptar a comunicação visual e reforçar a segmentação feminina nos canais pagos."
        })

    # 2. Análise de Dificuldades (Estudo do jeito certo)
    estudo_certo = summary.obstaculos_comp_pct.get("Não sei estudar do jeito certo", 0.0)
    if estudo_certo > 50:
        insights.append({
            "tipo": "recomendacao",
            "icone": "ti ti-bulb",
            "titulo": "Metodologia como Gancho Principal",
            "descricao": f"{estudo_certo:.1f}% dos compradores declaram ter dificuldade em 'Não sei estudar do jeito certo'. Isso prova que o Método de Estudos é o fator chave que destrava a venda. Foque a comunicação do lançamento no processo do método de estudos."
        })

    # 3. Análise de Obstáculo Financeiro
    dinheiro = summary.obstaculos_ncomp_pct.get("Sem dinheiro para curso", 0.0)
    if dinheiro > 35:
        insights.append({
            "tipo": "atencao",
            "icone": "ti ti-alert-triangle",
            "titulo": "Sensibilidade a Preço na Captação",
            "descricao": f"{dinheiro:.1f}% dos leads não-compradores apontaram 'Sem dinheiro para curso' como obstáculo. Oferecer opções de parcelamento facilitado, boleto parcelado ou focar na economia a longo prazo da estabilidade do concurso pode recuperar parte dessa base."
        })

    # 4. Análise de Fatores de Influência (Apostila Física vs Mentoria)
    if summary.top_influence_factors:
        top_factor = summary.top_influence_factors[0]
        factor_name = top_factor["opcao"]
        factor_pct = top_factor["pct"]
        insights.append({
            "tipo": "recomendacao",
            "icone": "ti ti-package",
            "titulo": f"Super Driver de Venda: {factor_name}",
            "descricao": f"Este recurso influenciou {factor_pct:.1f}% dos compradores na decisão de compra. Recomendação: Destacar imagens e unboxing deste recurso no topo da página de vendas e no vídeo de vendas oficial (VSL)."
        })

    # 5. Análise de Nível de Estudos
    iniciante_diff = summary.nivel_diff.get("Sou Iniciante", 0.0)
    if iniciante_diff > 3:
        insights.append({
            "tipo": "atencao",
            "icone": "ti ti-school",
            "titulo": "Alinhamento Iniciante",
            "descricao": f"Há uma concentração maior de iniciantes (+{iniciante_diff:.1f} pp) entre compradores do que na captação geral. Garanta que o conteúdo de aquecimento e as primeiras aulas da mentoria sejam extremamente didáticos e acolhedores, sem jargões técnicos excessivos."
        })

    return insights
