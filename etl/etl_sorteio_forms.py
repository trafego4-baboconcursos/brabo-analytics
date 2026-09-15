"""
etl/etl_sorteio_forms.py — Respostas do sorteio (Google Forms) → Supabase.

Um lote novo de formulários (Aula 1-4 + Resumão) é criado do ZERO a cada
lançamento — não é um formulário reaproveitado (achado em 15/09/26: 74
formulários só de "Projeto INSS", voltando até 08/2023). A nomeação é
inconsistente entre lotes ("Aula 2" / "Aula 2 ok" / "Aula 2 - ok" / "Aula
02", "Resumão" com/sem acento, alguns "lixos" tipo "Aula X"/"Backup"/sem
número de aula) — por isso a descoberta é via Drive API (busca por
`name contains '<termo do projeto>'`) e a aula é normalizada por regex,
não por nome exato de arquivo.

Grava TODAS as respostas históricas de todos os formulários encontrados em
sorteio_respostas; a separação por lançamento acontece na leitura
(frontend/db_readers/sorteio.py), batendo created_at contra a janela de
cada launch_config (o "ciclo" de um lançamento = do início de Aulas no Ar
dele até o início de Aulas no Ar do próximo — resolve a "cauda" de gente
que responde dias depois da aula, que já vimos passar de 2 semanas).

Credencial: GOOGLE_FORMS_OAUTH_CLIENT_JSON (OAuth Desktop app) + arquivo
token_google_forms.json na raiz do repo (guarda refresh_token — gerado uma
vez via consentimento manual, escopos forms.body/responses.readonly +
drive.metadata.readonly, nunca precisa refazer login). Projetos/termos de
busca em config/sorteio_projetos.yaml.

Uso:
    python etl/etl_sorteio_forms.py
"""
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Table, Column, Text, TIMESTAMP, MetaData

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()

logger = get_logger("etl.sorteio_forms")

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sorteio_projetos.yaml"
TOKEN_PATH = Path(__file__).parent.parent / "token_google_forms.json"
_SCOPES = [
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

DDL = """
CREATE TABLE IF NOT EXISTS sorteio_respostas (
    response_id   TEXT PRIMARY KEY,
    form_id       TEXT NOT NULL,
    projeto       TEXT NOT NULL,
    aula          TEXT NOT NULL,
    nome          TEXT,
    email         TEXT,
    cidade_estado TEXT,
    telefone      TEXT,
    created_at    TIMESTAMPTZ NOT NULL,
    synced_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sorteio_respostas_created_at_idx ON sorteio_respostas (created_at);
CREATE INDEX IF NOT EXISTS sorteio_respostas_projeto_aula_idx ON sorteio_respostas (projeto, aula);
"""

# fragmento (regex, ordem importa) -> aula normalizada. Cobre as variações
# reais encontradas: "Aula 1", "Aula 01", "Aula 2 ok", "Aula 2 - ok",
# "Aula 3.", "Aula 3 ok", "Resumão"/"Resumo"/"Aula Resumão" (acento pode vir
# corrompido na API, por isso casa só em "esum"). Formulários sem nenhum
# desses padrões ("Aula X", "Backup", "Sorteio - Projeto INSS" sem sufixo)
# são ignorados — não são aula real.
_AULA_PATTERNS = [
    (re.compile(r"esum", re.I), "Resumão"),
    (re.compile(r"aula\s*0?1\b", re.I), "Aula 1"),
    (re.compile(r"aula\s*0?2\b", re.I), "Aula 2"),
    (re.compile(r"aula\s*0?3\b", re.I), "Aula 3"),
    (re.compile(r"aula\s*0?4\b", re.I), "Aula 4"),
]

_CAMPO_POR_TITULO = {
    "nome": "nome",
    "email": "email",
    "cidade": "cidade_estado",
    "telefone": "telefone",
}


def _normaliza_aula(nome_arquivo: str) -> str | None:
    for pattern, aula in _AULA_PATTERNS:
        if pattern.search(nome_arquivo):
            return aula
    return None


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_PATH.exists():
        logger.error("%s não encontrado — rodar o consentimento OAuth uma vez antes.", TOKEN_PATH)
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), _SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _descobre_formularios(drive, termo: str) -> list[dict]:
    """Lista {id, name} de todo formulário cujo nome contém `termo`, com
    paginação (Drive limita a 100 por página)."""
    arquivos = []
    page_token = None
    while True:
        resp = drive.files().list(
            q=f"mimeType='application/vnd.google-apps.form' and name contains '{termo}'",
            fields="nextPageToken, files(id,name)",
            pageSize=100, pageToken=page_token,
        ).execute()
        arquivos.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return arquivos


def _mapa_perguntas(form: dict) -> dict[str, str]:
    mapa = {}
    for item in form.get("items", []):
        q = (item.get("questionItem") or {}).get("question")
        if not q:
            continue
        titulo = (item.get("title") or "").strip().lower()
        for frag, coluna in _CAMPO_POR_TITULO.items():
            if frag in titulo:
                mapa[q["questionId"]] = coluna
                break
    return mapa


def _extrai_resposta(resp: dict, perguntas: dict[str, str]) -> dict:
    linha = {"nome": None, "email": None, "cidade_estado": None, "telefone": None}
    for qid, ans in (resp.get("answers") or {}).items():
        coluna = perguntas.get(qid)
        if not coluna:
            continue
        valores = [a.get("value", "") for a in (ans.get("textAnswers") or {}).get("answers", [])]
        linha[coluna] = ", ".join(v for v in valores if v).strip() or None
    return linha


_METADATA = MetaData()
_SORTEIO_TABLE = Table(
    "sorteio_respostas", _METADATA,
    Column("response_id", Text, primary_key=True),
    Column("form_id", Text),
    Column("projeto", Text),
    Column("aula", Text),
    Column("nome", Text),
    Column("email", Text),
    Column("cidade_estado", Text),
    Column("telefone", Text),
    Column("created_at", TIMESTAMP(timezone=True)),
    Column("synced_at", TIMESTAMP(timezone=True)),
)


def _upsert(engine, form_id: str, projeto: str, aula: str, respostas: list[dict], perguntas: dict[str, str]) -> int:
    """Um INSERT só com todas as linhas da página (até 200) — uma viagem de
    rede em vez de uma por resposta, que levava a sincronização a travar por
    horas nos formulários com milhares de respostas (ex: uma aula só já
    tinha 12 mil)."""
    if not respostas:
        return 0
    linhas = [
        {
            "response_id": r["responseId"], "form_id": form_id, "projeto": projeto, "aula": aula,
            "created_at": r["createTime"], **_extrai_resposta(r, perguntas),
        }
        for r in respostas
    ]
    stmt = pg_insert(_SORTEIO_TABLE).values(linhas)
    stmt = stmt.on_conflict_do_update(
        index_elements=["response_id"],
        set_={
            "nome": stmt.excluded.nome,
            "email": stmt.excluded.email,
            "cidade_estado": stmt.excluded.cidade_estado,
            "telefone": stmt.excluded.telefone,
            "created_at": stmt.excluded.created_at,
            "synced_at": text("now()"),
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
    return len(respostas)


def main() -> None:
    cfg = load_config()
    if not cfg:
        logger.warning("config/sorteio_projetos.yaml vazio ou não encontrado — nada a fazer.")
        return

    creds = _credentials()
    if creds is None:
        return
    from googleapiclient.discovery import build  # noqa: PLC0415
    forms_svc = build("forms", "v1", credentials=creds)
    drive_svc = build("drive", "v3", credentials=creds)

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(DDL))

    for projeto, termo in cfg.items():
        arquivos = _descobre_formularios(drive_svc, termo)
        logger.info("%s: %d formulário(s) encontrado(s) buscando '%s'.", projeto, len(arquivos), termo)

        por_aula: dict[str, int] = {}
        ignorados = 0
        for arq in arquivos:
            aula = _normaliza_aula(arq["name"])
            if not aula:
                ignorados += 1
                continue
            form_id = arq["id"]
            try:
                form = forms_svc.forms().get(formId=form_id).execute()
            except Exception:
                logger.exception("%s (%s): falha ao ler estrutura do formulário %r", projeto, aula, arq["name"])
                continue
            perguntas = _mapa_perguntas(form)

            total = 0
            page_token = None
            while True:
                try:
                    resp = forms_svc.forms().responses().list(
                        formId=form_id, pageSize=200, pageToken=page_token,
                    ).execute()
                except Exception:
                    logger.exception("%s (%s): falha ao paginar respostas do formulário %r", projeto, aula, arq["name"])
                    break
                respostas = resp.get("responses", [])
                total += _upsert(engine, form_id, projeto, aula, respostas, perguntas)
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            por_aula[aula] = por_aula.get(aula, 0) + total

        logger.info("%s: sincronizado — %s (%d formulário(s) ignorado(s) sem aula reconhecida).",
                     projeto, ", ".join(f"{a}={n}" for a, n in sorted(por_aula.items())), ignorados)


if __name__ == "__main__":
    main()
