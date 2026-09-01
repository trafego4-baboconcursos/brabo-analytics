"""
ETL: Active Campaign → Supabase (tabela: leads)

Dois modos de operação:

  1. CSV (recomendado para cargas históricas — rápido, sem limite de API):
       python etl/etl_active_campaign.py --from-csv "analises/[PBB-ABR-26]/Active Campaign/active-campaign-pbb-abr-26.csv"

  2. API (para sincronização incremental, funciona melhor em listas pequenas):
       python etl/etl_active_campaign.py --api --since 2026-04-01 --until 2026-04-30
       python etl/etl_active_campaign.py --api --discover-fields   # lista IDs dos campos UTM
"""
import os
import sys
import argparse
import re
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get
from validation import validate_dataframe

load_dotenv()

logger = get_logger("etl.ac")

# ── Função auxiliar de extração do código de lançamento ─────────────────────
def extract_launch_code(campaign_name: str) -> str | None:
    if pd.isna(campaign_name) or not campaign_name:
        return None
    match = re.search(r'(PBB|PES|PI)-\w{3}-\d{2}', str(campaign_name), re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None

def extract_launch_code_from_path(filepath: str) -> str | None:
    match = re.search(r'\[(PBB|PES|PI)-\w{3}-\d{2}\]', str(filepath), re.IGNORECASE)
    if match:
        return match.group(0).strip("[]").upper()
    match = re.search(r'(PBB|PES|PI)-\w{3}-\d{2}', str(filepath), re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None

# ── Mapeamento das colunas do export CSV do Active Campaign ──────────────────
# Colunas identificadas no export real da Brabo Concursos
CSV_COLUMN_MAP = {
    "ID":             "id",
    "Email":          "email",
    "Nome":           "nome",
    "Sobrenome":      "sobrenome",
    "Número de telefone": "phone",
    "Numero de telefone": "phone",   # fallback para encoding alternativo
    "Data da criação": "created_at",
    "Data da criacão": "created_at",   # fallback para encoding alternativo
    "*Utm_campaign":  "utm_campaign",
    "*Utm_source":    "utm_source",
    "*Utm_medium":    "utm_medium",
    "*Utm_content":   "utm_content",
    "*Utm_term":      "utm_term",
}

# ── IDs dos campos customizados de UTM (modo API) ───────────────────────────
# Execute com --discover-fields para ver os IDs e preencha o .env
UTM_FIELD_IDS = {
    "utm_campaign": int(os.getenv("AC_FIELD_UTM_CAMPAIGN") or "0"),
    "utm_source":   int(os.getenv("AC_FIELD_UTM_SOURCE") or "0"),
    "utm_medium":   int(os.getenv("AC_FIELD_UTM_MEDIUM") or "0"),
    "utm_content":  int(os.getenv("AC_FIELD_UTM_CONTENT") or "0"),
    "utm_term":     int(os.getenv("AC_FIELD_UTM_TERM") or "0"),
    # Click IDs (campos criados na conta em ago/26; IDs via --discover-fields)
    "gclid":        int(os.getenv("AC_FIELD_GCLID") or "24"),
    "fbclid":       int(os.getenv("AC_FIELD_FBCLID") or "25"),
    "ttclid":       int(os.getenv("AC_FIELD_TTCLID") or "26"),
    # IDs reais de anúncio/plataforma vindos da UTM padrão (vk_source/vk_ad_id)
    "vk_source":    int(os.getenv("AC_FIELD_VK_SOURCE") or "9"),
    "vk_ad_id":     int(os.getenv("AC_FIELD_VK_AD_ID") or "10"),
}

TABLE = "leads"


# ─────────────────────────────────────────────────────────────────────────────
# Modo CSV
# ─────────────────────────────────────────────────────────────────────────────

def load_from_csv(filepath: str, launch_code: str | None = None) -> pd.DataFrame:
    """Lê o export CSV do Active Campaign e retorna DataFrame normalizado."""
    df = pd.read_csv(filepath, dtype=str, low_memory=False)

    # Seleciona e renomeia apenas as colunas que existem no CSV
    present = {k: v for k, v in CSV_COLUMN_MAP.items() if k in df.columns}
    df = df[list(present.keys())].rename(columns=present)

    df["email"] = df["email"].str.lower().str.strip()
    df["id"]    = df["id"].astype(str)

    # Converte data de criação para ISO
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", dayfirst=True)

    # Adiciona colunas ausentes como nulo para compatibilidade com o schema
    for col in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid", "ttclid", "vk_source", "vk_ad_id", "nome", "sobrenome", "phone"]:
        if col not in df.columns:
            df[col] = None

    df["nome"] = df["nome"].str.strip() if df["nome"].notna().any() else df["nome"]
    df["sobrenome"] = df["sobrenome"].str.strip() if df["sobrenome"].notna().any() else df["sobrenome"]
    # Normaliza telefone: mantém só dígitos (remove DDI/formatação) para facilitar match
    df["phone"] = df["phone"].fillna("").astype(str).str.replace(r"\D", "", regex=True)
    df["phone"] = df["phone"].apply(lambda v: v[-11:] if len(v) >= 10 else None)

    # Extrai o código do lançamento
    df["lancamento_codigo"] = df["utm_campaign"].apply(extract_launch_code)
    fallback_code = extract_launch_code_from_path(filepath)
    if fallback_code:
        df["lancamento_codigo"] = df["lancamento_codigo"].fillna(fallback_code)
    if launch_code:
        df = df[df["lancamento_codigo"] == launch_code.upper()].copy()

    df["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Mantém registros com utm_content OU utm_term preenchido
    # (UTMs antigas: ad name em utm_content; UTMs novas pbb-abr-26+: ad name em utm_term)
    has_content = df["utm_content"].notna() & (df["utm_content"] != "")
    has_term    = df["utm_term"].notna()    & (df["utm_term"]    != "")
    df = df[has_content | has_term].copy()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Modo API
# ─────────────────────────────────────────────────────────────────────────────

def _ac_headers() -> dict:
    return {"Api-Token": os.environ["AC_API_KEY"]}


def _ac_get(path: str, **params) -> dict:
    base_url = os.environ["AC_API_URL"].rstrip("/")
    if "/api/3" not in base_url:
        base_url += "/api/3"
    url = base_url + "/" + path
    r = http_get(url, headers=_ac_headers(), params=params)
    return r.json()


def discover_fields():
    """Imprime todos os custom fields para identificar os IDs de UTM."""
    data = _ac_get("fields", limit=100)
    print(f"\n{'ID':>6}  {'Título'}")
    print("─" * 40)
    for f in data.get("fields", []):
        print(f"  {f['id']:>4}  {f['title']}")


def load_from_api(since: str, until: str) -> pd.DataFrame:
    """Busca contatos atualizados no período via API com seus campos UTM.

    Usa updated_after/updated_before para capturar contatos que se
    cadastraram em lançamentos anteriores mas atualizaram seus UTMs no
    período — o que created_after perdia.

    Os field values vêm embutidos na resposta de contatos via include=fieldValues,
    evitando o custo de paginar toda a tabela fieldValues da conta.
    """
    missing = [k for k, v in UTM_FIELD_IDS.items() if v == 0]
    if missing:
        logger.warning("Campos UTM não configurados no .env: %s", missing)
        logger.warning("Execute: python etl/etl_active_campaign.py --api --discover-fields")

    # ID numérico → nome UTM para lookup rápido
    field_id_to_utm = {str(v): k for k, v in UTM_FIELD_IDS.items() if v != 0}

    fv_by_contact: dict[str, dict[str, str]] = {}
    contacts, offset = [], 0
    while True:
        data = _ac_get(
            "contacts",
            limit=100,
            offset=offset,
            include="fieldValues",
            **{
                "filters[updated_after]":  f"{since}T00:00:00",
                "filters[updated_before]": f"{until}T23:59:59",
            },
        )
        batch = data.get("contacts", [])
        if not batch:
            break
        contacts.extend(batch)
        for fv in data.get("fieldValues", []):
            cid  = fv.get("contact")
            fid  = str(fv.get("field"))
            val  = fv.get("value", "")
            name = field_id_to_utm.get(fid)
            if name and cid:
                fv_by_contact.setdefault(cid, {})[name] = val
        total = int(data.get("meta", {}).get("total", 0))
        offset += len(batch)
        if offset >= total:
            break

    if not contacts:
        return pd.DataFrame()

    logger.info("%d contatos atualizados no período.", len(contacts))

    records = []
    for c in contacts:
        cid          = c["id"]
        utms         = fv_by_contact.get(cid, {})
        utm_campaign = utms.get("utm_campaign")
        utm_content  = utms.get("utm_content")
        utm_term     = utms.get("utm_term")
        phone = re.sub(r"\D", "", c.get("phone") or "")
        records.append({
            "id":                cid,
            "email":             c.get("email", "").lower().strip(),
            "nome":              (c.get("firstName") or "").strip() or None,
            "sobrenome":         (c.get("lastName") or "").strip() or None,
            "phone":             phone[-11:] if len(phone) >= 10 else None,
            "created_at":        c.get("cdate"),
            "utm_campaign":      utm_campaign,
            "lancamento_codigo": extract_launch_code(utm_campaign) if utm_campaign else None,
            "utm_source":        utms.get("utm_source"),
            "utm_medium":        utms.get("utm_medium"),
            "utm_content":       utm_content,
            "utm_term":          utm_term,
            "gclid":             utms.get("gclid") or None,
            "fbclid":            utms.get("fbclid") or None,
            "ttclid":            utms.get("ttclid") or None,
            "vk_source":         utms.get("vk_source") or None,
            "vk_ad_id":          utms.get("vk_ad_id") or None,
            "updated_at":        datetime.now(timezone.utc).isoformat(),
        })

    df = pd.DataFrame(records)
    # Mantém registros com utm_content OU utm_term preenchido
    # (PBB-JUN-26 em diante usa utm_term para o código AD)
    has_content = df["utm_content"].notna() & (df["utm_content"] != "")
    has_term    = df["utm_term"].notna()    & (df["utm_term"]    != "")
    df = df[has_content | has_term].copy()
    # Um contato pode mudar de página na paginação por offset se for atualizado
    # entre uma chamada e outra (updated_after/before), aparecendo duas vezes.
    df = df.drop_duplicates(subset="id", keep="last")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Upsert no Supabase
# ─────────────────────────────────────────────────────────────────────────────

_AC_REQUIRED_COLS = ["id", "email", "created_at", "lancamento_codigo"]

def upsert(df: pd.DataFrame, label: str = ""):
    """DELETE + INSERT atômicos por lote: se o INSERT falhar no meio, o DELETE
    daquele lote também é desfeito — nunca perde leads já gravados por causa
    de uma queda de conexão no meio do processo."""
    if not validate_dataframe(df, _AC_REQUIRED_COLS, "leads", logger):
        return
    df = df.drop_duplicates(subset="id", keep="last")
    df = df.astype(object).where(df.notna(), None)
    engine = get_engine()
    cols = list(df.columns)
    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    records = df.to_dict("records")
    batch_size = 500
    for i in range(0, len(records), batch_size):
        chunk = records[i:i + batch_size]
        ids = [r["id"] for r in chunk]
        with engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {TABLE} WHERE id = ANY(:ids)"),
                {"ids": ids},
            )
            conn.execute(
                text(f"INSERT INTO {TABLE} ({col_list}) VALUES ({placeholders})"),
                chunk,
            )
    logger.info("Upsert concluído: %d leads gravados em '%s'%s", len(df), TABLE, label)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ETL Active Campaign - Supabase")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--from-csv", metavar="FILE", help="Caminho para o CSV exportado do Active Campaign")
    group.add_argument("--api", action="store_true", help="Busca via API (requer credenciais no .env)")
    parser.add_argument("--since", default="2026-01-01", help="Data inicial (modo --api)")
    parser.add_argument("--until", default=datetime.now().strftime("%Y-%m-%d"), help="Data final (modo --api)")
    parser.add_argument("--launch-code", metavar="CODE", help="Filtra a carga para um lancamento especifico")
    parser.add_argument("--discover-fields", action="store_true", help="Lista IDs dos custom fields (modo --api)")
    args = parser.parse_args()

    if args.api and args.discover_fields:
        logger.info("Listando custom fields da conta Active Campaign...")
        discover_fields()
        return

    if args.from_csv:
        logger.info("[AC] %s <- CSV: %s", TABLE, args.from_csv)
        df = load_from_csv(args.from_csv, args.launch_code)
        logger.info("%d leads com utm_content ou utm_term preenchido", len(df))
        upsert(df)
    else:
        logger.info("[AC] %s  [%s -> %s]  (API)", TABLE, args.since, args.until)
        df = load_from_api(args.since, args.until)
        upsert(df, f"  [{args.since} -> {args.until}]")


if __name__ == "__main__":
    main()
