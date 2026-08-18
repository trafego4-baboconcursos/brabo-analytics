"""
src/typeform_resolve.py — Resolução de form_id do Typeform a partir do código de lançamento.

Usado tanto pelo ETL (etl/etl_typeform.py, para saber quais formulários puxar)
quanto pelo frontend (frontend/db_readers/typeform.py, para saber quais
form_id ler da tabela typeform_respostas). Mantido num único lugar para não
divergir: cada lado resolvendo o form_id de um jeito diferente foi o que
causou o form_id fixo desatualizado no ETL (ver histórico do PI-AGO-26).
"""
import requests


def fetch_typeform_forms(token: str) -> dict[str, str]:
    """Retorna {form_id: title} de todos os formulários da conta."""
    headers = {"Authorization": f"Bearer {token}"}
    all_forms: dict[str, str] = {}
    page = 1
    while True:
        r = requests.get(
            "https://api.typeform.com/forms",
            headers=headers,
            params={"page_size": 200, "page": page},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
        for f in items:
            all_forms[f["id"]] = f["title"]
        if len(all_forms) >= data.get("total_items", 0) or not items:
            break
        page += 1
    return all_forms


def resolve_launch_form_ids(code: str, forms: dict[str, str]) -> list[str]:
    """Todos os form_id cujo título contém o código do lançamento (ex: 'PI-AGO-26')."""
    code_norm = code.lower().strip()
    return [fid for fid, title in forms.items() if code_norm in title.lower()]


def resolve_projeto_alunos_form_ids(code: str, forms: dict[str, str]) -> tuple[str | None, str | None]:
    """Caso específico das pesquisas 'Projeto' e 'Alunos' de um lançamento."""
    code_norm = code.lower().strip()
    proj_id = None
    alunos_id = None
    for fid, title in forms.items():
        title_norm = title.lower()
        if code_norm in title_norm:
            if "alun" in title_norm:
                alunos_id = fid
            elif "projeto" in title_norm or "pesquisa" in title_norm:
                proj_id = fid
    return proj_id, alunos_id