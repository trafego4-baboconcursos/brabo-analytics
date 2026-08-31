"""
frontend/db_readers/typeform.py — Leitura das respostas/formulários do Typeform no banco
(a conta do Typeform foi cancelada; tudo vem do backup em Supabase).
"""
from __future__ import annotations

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
from src.typeform_resolve import resolve_projeto_alunos_form_ids

logger = get_logger("db")

_typeform_forms_cache: dict[str, str] | None = None
_typeform_forms_cache_expiry: float = 0.0
_typeform_fields_cache: dict[str, dict[str, str]] = {}

_TYPEFORM_CACHE_TTL_OK  = 1800.0   # 30 min quando a leitura do banco funciona
_TYPEFORM_CACHE_TTL_ERR = 3600.0   # 1 h quando falha (backoff)

# typeform_respostas (sync ao vivo, só lançamentos recentes) + os dois backups
# completos das duas contas Typeform (feitos antes do cancelamento da API) —
# tratadas como uma fonte só, deduplicada por response_id (a mais recente por
# updated_at, quando o mesmo response_id aparece em mais de uma tabela).
# O filtro (where_sql) é aplicado dentro de cada tabela antes do UNION — se
# aplicado só por fora, o DISTINCT ON teria que varrer ~1M linhas a cada
# chamada (era o caso de read_typeform_count, pensada pra ser barata).
_TF_RESPOSTAS_TABLES = ("typeform_respostas", "typeform_respostas_backup", "typeform_respostas_backup_2")


def _tf_source(where_sql: str, cols: str = "*") -> str:
    branches = " UNION ALL ".join(
        f"SELECT {cols} FROM {t} WHERE {where_sql}" for t in _TF_RESPOSTAS_TABLES
    )
    return f"""
        (
            SELECT DISTINCT ON (response_id) *
            FROM ({branches}) tf_all
            ORDER BY response_id, updated_at DESC NULLS LAST
        )
    """


def _get_typeform_forms() -> dict[str, str]:
    """form_id -> título, lido do backup local (typeform_forms/typeform_forms_2).

    Substituiu a chamada à API do Typeform (conta cancelada) — o backup foi
    feito antes do cancelamento e cobre todos os formulários já criados.
    Formulários novos não existirão mais, então não há dado a perder.
    """
    global _typeform_forms_cache, _typeform_forms_cache_expiry
    now = _time_module.time()
    if _typeform_forms_cache is not None and now < _typeform_forms_cache_expiry:
        return _typeform_forms_cache

    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT form_id, title FROM typeform_forms "
                "UNION SELECT form_id, title FROM typeform_forms_2"
            )).fetchall()
        _typeform_forms_cache = {r[0]: r[1] for r in rows}
        _typeform_forms_cache_expiry = now + _TYPEFORM_CACHE_TTL_OK
    except Exception:
        logger.exception("Erro ao ler backup de formulários do Typeform (typeform_forms)")
        _typeform_forms_cache = {}
        _typeform_forms_cache_expiry = now + _TYPEFORM_CACHE_TTL_ERR

    return _typeform_forms_cache or {}


def _get_typeform_fields(form_id: str) -> dict[str, str]:
    """Mapeamento field_id -> título da pergunta.

    Não há mais chamada à API do Typeform (conta cancelada) e o backup das
    respostas não guarda field.title dentro do JSON. Sem esse mapeamento,
    _reconstruct_tabular_df cai no fallback (field_id cru como nome de
    coluna) — os relatórios de perfil/demografia do /typeform ficam com
    nomes de coluna ilegíveis até esse mapeamento ser recuperado de outra
    fonte (ex: export manual do Typeform antes do cancelamento).
    """
    return _typeform_fields_cache.get(form_id, {})


def _resolve_typeform_ids(code: str) -> tuple[Optional[str], Optional[str]]:
    forms = _get_typeform_forms()
    return resolve_projeto_alunos_form_ids(code, forms)


# ── Sistema de pesquisa novo (substituiu o Typeform a partir do PBB-AGO-26) ──
# Schema normalizado: formularios (1 por lançamento) → perguntas (uma linha por
# pergunta, titulo já é o texto legível) → submissoes (1 por resposta) →
# respostas (1 linha por pergunta respondida, valor jsonb: 'texto'/'opcao'/
# 'opcoes'+'texto_outro'). Sem o gap de field-title que existe no Typeform.

def _resolve_novo_sistema_formulario_ids(code: str) -> list[int]:
    """Formulários cujo título contém o código do lançamento (ex: '[PBB-AGO-26]')."""
    engine = _get_engine()
    with engine.connect() as conn:
        ids = conn.execute(
            text("SELECT id FROM formularios WHERE publicado = true AND lower(titulo) LIKE :pat"),
            {"pat": f"%{code.lower()}%"},
        ).scalars().all()
    return list(ids)


def _read_novo_sistema_emails(formulario_ids: list[int]) -> set[str]:
    """Só os e-mails — equivalente leve pro contador (read_typeform_count)."""
    if not formulario_ids:
        return set()
    engine = _get_engine()
    with engine.connect() as conn:
        emails = conn.execute(text("""
            SELECT DISTINCT r.valor->>'texto' AS email
            FROM submissoes s
            JOIN respostas r ON r.submissao_id = s.id
            JOIN perguntas p ON p.id = r.pergunta_id
            WHERE s.formulario_id = ANY(:fids) AND p.tipo = 'email'
        """), {"fids": formulario_ids}).scalars().all()
    return {str(e).strip().lower() for e in emails if e and "@" in str(e)}


def _read_novo_sistema_respostas(formulario_ids: list[int]) -> pd.DataFrame:
    """Tabular email_norm + uma coluna por pergunta (titulo), no mesmo formato
    que _reconstruct_tabular_df produz pro Typeform — dá pra concatenar direto."""
    if not formulario_ids:
        return pd.DataFrame()

    engine = _get_engine()
    raw = pd.read_sql(text("""
        SELECT s.id AS submissao_id, p.titulo AS pergunta, r.valor
        FROM submissoes s
        JOIN respostas r ON r.submissao_id = s.id
        JOIN perguntas p ON p.id = r.pergunta_id
        WHERE s.formulario_id = ANY(:fids)
    """), engine, params={"fids": formulario_ids})
    if raw.empty:
        return pd.DataFrame()

    def _extract_valor(v: Any) -> str:
        if not isinstance(v, dict):
            return ""
        if "opcoes" in v:
            parts = [str(p) for p in (v.get("opcoes") or [])]
            outro = v.get("texto_outro")
            if outro:
                parts.append(str(outro))
            return ", ".join(parts)
        if "opcao" in v:
            val = str(v.get("opcao") or "")
            outro = v.get("texto_outro")
            return f"{val} ({outro})" if outro else val
        return str(v.get("texto") or "")

    raw["valor_str"] = raw["valor"].apply(_extract_valor)
    # Se duas perguntas de formulários diferentes casados pelo mesmo código
    # tiverem o título idêntico, aggfunc="first" evita erro de pivot — não é
    # o caso hoje (1 formulário por código), mas não quebra se acontecer.
    wide = raw.pivot_table(index="submissao_id", columns="pergunta", values="valor_str", aggfunc="first")
    wide = wide.reset_index(drop=True)

    email_col = next((c for c in wide.columns if "mail" in _norm_text(c)), None)
    if not email_col:
        return pd.DataFrame()

    wide["email_norm"] = wide[email_col].astype(str).str.strip().str.lower()
    wide = wide[wide["email_norm"].str.contains("@", na=False)]
    return wide


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


def read_typeform_count(launch_folder_or_code: Any) -> int:
    """Versão enxuta de read_typeform() só para o contador da navegação.

    A função completa traz a coluna `answers` (JSONB com todas as respostas)
    de cada linha, faz parsing e cruza com vendas/CRM — caro (~30s) para só
    exibir "quantas pessoas responderam". Aqui buscamos só `email`, evitando
    o transporte do JSONB pela rede (o gargalo real, não o Postgres em si).
    """
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    with engine.connect() as conn:
        l_row = conn.execute(text("SELECT data_inicio, data_fim FROM dim_lancamentos WHERE codigo = :code"), {"code": code}).fetchone()
        if not l_row:
            return 0
        dim_start, dim_end = l_row

    proj_id, _ = _resolve_typeform_ids(code)
    if not proj_id:
        proj_id = code

    count_cols = "response_id, updated_at, email"
    with engine.connect() as conn:
        fid_where = "upper(coalesce(form_id, '')) = :fid"
        emails = conn.execute(
            text("SELECT email FROM " + _tf_source(fid_where, count_cols) + " t"),
            {"fid": proj_id.upper()},
        ).scalars().all()
        if not emails:
            emails = conn.execute(
                text(
                    "SELECT email FROM "
                    + _tf_source(
                        "submitted_at::date BETWEEN :start AND :end AND upper(coalesce(form_id, '')) = :code",
                        count_cols,
                    )
                    + " t"
                ),
                {"start": dim_start, "end": dim_end, "code": code.upper()},
            ).scalars().all()

    norm_emails = {str(e).strip().lower() for e in emails if e and "@" in str(e)}

    novo_fids = _resolve_novo_sistema_formulario_ids(code)
    norm_emails |= _read_novo_sistema_emails(novo_fids)

    return len(norm_emails)


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
        project, dim_start, dim_end = l_row
        vendas_start = start_date or dim_start
        vendas_end = end_date or dim_end

    proj_id, alunos_id = _resolve_typeform_ids(code)
    if not proj_id:
        proj_id = code

    # 1. Carrega dados do Typeform do Supabase
    fid_where = "upper(coalesce(form_id, '')) = :fid"
    tf_df_raw = pd.read_sql(
        text("SELECT * FROM " + _tf_source(fid_where) + " t"),
        engine,
        params={"fid": proj_id.upper()}
    )
    if tf_df_raw.empty:
        # Fallback histórico por data e código do lançamento
        date_where = "submitted_at::date BETWEEN :start AND :end AND upper(coalesce(form_id, '')) = :code"
        tf_df_raw = pd.read_sql(
            text("SELECT * FROM " + _tf_source(date_where) + " t"),
            engine,
            params={"start": dim_start, "end": dim_end, "code": code.upper()}
        )

    # Reconstruir o DataFrame tabular baseado nas respostas JSONB (Typeform)
    records = _reconstruct_tabular_df(tf_df_raw) if not tf_df_raw.empty else []
    tf_df_typeform = pd.DataFrame(records)

    # Respostas do sistema de pesquisa novo (PBB-AGO-26 em diante) — mesmo
    # código do lançamento, formulário próprio, sem passar pelo Typeform.
    novo_fids = _resolve_novo_sistema_formulario_ids(code)
    novo_df = _read_novo_sistema_respostas(novo_fids)

    if tf_df_typeform.empty and novo_df.empty:
        return summary

    tf_df = pd.concat([tf_df_typeform, novo_df], ignore_index=True, sort=False)
    tf_df = tf_df.drop_duplicates("email_norm", keep="last")

    summary.has_data = True
    summary.total_tf_raw = len(tf_df_raw) + len(novo_df)
    summary.total_tf = len(tf_df)

    # Confrontar pesquisas
    tf_alunos_raw = pd.DataFrame()
    if alunos_id:
        tf_alunos_raw = pd.read_sql(
            text("SELECT * FROM " + _tf_source(fid_where) + " t"),
            engine,
            params={"fid": alunos_id.upper()}
        )
    if not tf_alunos_raw.empty:
        _build_typeform_comparison(summary, tf_df, tf_alunos_raw, proj_id, alunos_id)

    # 2. Carrega vendas e CRM para cruzamento
    # Mesma janela usada pelos demais readers — evita duplicar a consulta inteira
    # de Hotmart+TMB com uma cache-key diferente (start=None).
    v_sum = read_vendas(code, start_date=vendas_start, end_date=vendas_end)
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


_PERFIL_PERGUNTAS = [
    ("Gênero", "genero"),
    ("Idade", "idade"),
    ("Situação profissional", "situacao profissional"),
    ("Nível", "voce se considera"),
]


def read_perfil_por_anuncio(launch_folder_or_code: Any, top_n: int = 5) -> dict | None:
    """Perfil do lead por anúncio (pauta debriefing): cruza os leads dos top
    anúncios (utm_content → ADxxx) com as respostas da pesquisa por e-mail e
    devolve a distribuição das perguntas-padrão por anúncio."""
    code = _extract_launch_code(launch_folder_or_code)
    engine = _get_engine()

    proj_id, _ = _resolve_typeform_ids(code)
    if not proj_id:
        proj_id = code
    tf_df_raw = pd.read_sql(
        text("SELECT * FROM " + _tf_source("upper(coalesce(form_id, '')) = :fid") + " t"),
        engine, params={"fid": proj_id.upper()},
    )
    records = _reconstruct_tabular_df(tf_df_raw) if not tf_df_raw.empty else []
    tf_df_typeform = pd.DataFrame(records)

    novo_fids = _resolve_novo_sistema_formulario_ids(code)
    novo_df = _read_novo_sistema_respostas(novo_fids)

    if tf_df_typeform.empty and novo_df.empty:
        return None
    tf_df = pd.concat([tf_df_typeform, novo_df], ignore_index=True, sort=False)
    tf_df = tf_df.drop_duplicates("email_norm", keep="last")

    # O código ADxxx do anúncio vem no utm_term (utm_content traz o adset);
    # utm_content fica de fallback pra lançamentos antigos.
    leads_df = pd.read_sql(
        text("SELECT LOWER(TRIM(email)) AS email_norm, utm_term, utm_content FROM leads WHERE lancamento_codigo = :code"),
        engine, params={"code": code},
    )
    if leads_df.empty:
        return None
    ad_term = leads_df["utm_term"].astype(str).str.extract(r"^(AD\d+)", flags=re.IGNORECASE)[0]
    ad_content = leads_df["utm_content"].astype(str).str.extract(r"^(AD\d+)", flags=re.IGNORECASE)[0]
    leads_df["ad_code"] = ad_term.fillna(ad_content).str.upper()
    leads_df = leads_df.dropna(subset=["ad_code"]).drop_duplicates("email_norm")

    merged = tf_df.merge(leads_df[["email_norm", "ad_code"]], on="email_norm", how="inner")
    if merged.empty:
        return None

    leads_por_ad = leads_df["ad_code"].value_counts()
    top_ads = merged["ad_code"].value_counts().head(top_n)

    # Resolve as colunas das perguntas-padrão uma vez só
    colunas: list[tuple[str, str]] = []
    for label, needle in _PERFIL_PERGUNTAS:
        pattern = re.compile(r"\b" + re.escape(needle) + r"\b")
        for c in merged.columns:
            if pattern.search(_norm_text(c)):
                colunas.append((label, c))
                break

    ads = []
    for ad_code, n_resp in top_ads.items():
        sub = merged[merged["ad_code"] == ad_code]
        dist: dict[str, list[dict]] = {}
        for label, col in colunas:
            vc = sub[col].dropna()
            vc = vc[vc.astype(str).str.strip() != ""]
            if vc.empty:
                continue
            pcts = (vc.value_counts(normalize=True) * 100).head(3)
            dist[label] = [{"opcao": str(k), "pct": float(v)} for k, v in pcts.items()]
        ads.append({
            "ad_code": ad_code,
            "leads": int(leads_por_ad.get(ad_code, 0)),
            "respostas": int(n_resp),
            "dist": dist,
        })

    return {
        "perguntas": [label for label, _ in colunas],
        "ads": ads,
        "total_cruzado": int(len(merged)),
    }


def read_pesquisa_engajamento(launch_folder_or_code: Any) -> dict | None:
    """Resumo de engajamento da pesquisa (pauta debriefing): quantos leads da
    base responderam. "Quem recebeu" depende da fonte de disparo (WhatsApp/
    automação) — não existe no AC Campaigns, então a taxa é sobre a base."""
    code = _extract_launch_code(launch_folder_or_code)
    proj_id, _ = _resolve_typeform_ids(code)
    if not proj_id:
        proj_id = code
    engine = _get_engine()
    fid_where = "upper(coalesce(form_id, '')) = :fid"
    with engine.connect() as conn:
        tf_emails = conn.execute(text(
            "SELECT email FROM " + _tf_source(fid_where) + " t WHERE email IS NOT NULL"
        ), {"fid": proj_id.upper()}).scalars().all()

    novo_fids = _resolve_novo_sistema_formulario_ids(code)
    all_emails = {str(e).strip().lower() for e in tf_emails if e} | _read_novo_sistema_emails(novo_fids)
    respostas = len(all_emails)
    if not respostas:
        return None

    with engine.connect() as conn:
        lead_emails = conn.execute(text(
            "SELECT email FROM leads WHERE lancamento_codigo = :code"
        ), {"code": code}).scalars().all()
    lead_emails_norm = {str(e).strip().lower() for e in lead_emails if e}
    base = len(lead_emails_norm)
    cruzadas = len(all_emails & lead_emails_norm)

    return {
        "respostas": int(respostas),
        "base_leads": int(base),
        "respostas_da_base": int(cruzadas),
        "taxa_resposta": (cruzadas / base * 100) if base else 0.0,
    }


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
