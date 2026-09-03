"""
ETL: Contagem de grupos de WhatsApp — via Google Sheets (leitura) → Supabase
    - whatsapp_sheets_resumo: Total Grupos Cheios / Total Leads / Total Limpo
      (estado atual), 1 linha por lançamento+bloco.
    - whatsapp_sheets_diario: histórico dia a dia (Entradas/Saídas/Leads no
      dia), 1 linha por dia+lançamento+bloco.

O sendflow-analytics-poller é quem calcula tudo (dedup por telefone, exclusão
de admin, entradas/saídas diárias) e escreve na planilha do Google Sheets.
Este script só LÊ essas células/colunas (nunca escreve na planilha) e grava
no banco do brabo-analytics — o Brabo Analytics não fala com a SendFlow nem
com o Sheets na hora de renderizar a página, só consulta essas duas tabelas.

Credencial: GOOGLE_SHEETS_CONTAGEM_JSON (conteúdo do JSON da service account
— a mesma que o poller já usa pra escrever nessas planilhas, então já tem
acesso garantido). Mapeamento lançamento -> planilha em
config/sheets_contagem.yaml.

Uso:
    python etl/etl_sheets_contagem.py
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()

logger = get_logger("etl.sheets_contagem")

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sheets_contagem.yaml"
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_EPOCH_SHEETS = date(1899, 12, 30)  # epoch de datas seriais do Sheets/Excel


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _service():
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    sa_json = os.environ.get("GOOGLE_SHEETS_CONTAGEM_JSON")
    if not sa_json:
        logger.error("GOOGLE_SHEETS_CONTAGEM_JSON não configurada.")
        return None
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json), scopes=_SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _parse_data(valor) -> str | None:
    """Aceita tanto data serial do Sheets (número) quanto string 'dd/mm/yyyy'."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return (_EPOCH_SHEETS + timedelta(days=int(valor))).isoformat()
    try:
        return datetime.strptime(str(valor).strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _int(valor) -> int | None:
    if valor is None or valor == "":
        return None
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return None


def _ler_bloco(svc, sheet_id: str, bloco: dict) -> dict | None:
    aba = bloco["aba"]
    lr = bloco["linha_resumo"]
    ltl = bloco["linha_total_limpo"]
    try:
        r = svc.spreadsheets().values().batchGet(
            spreadsheetId=sheet_id,
            ranges=[
                f"'{aba}'!F{lr}:G{lr}",   # grupos_cheios, total_leads (bruto)
                f"'{aba}'!G{ltl}",         # total_limpo
                f"'{aba}'!A2:C2000",       # DATA2, ENTRADAS, SAÍDAS
                f"'{aba}'!I2:J2000",       # DATA, LEADS NO DIA
            ],
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
    except Exception:
        logger.exception("falha ao ler aba '%s' da planilha %s", aba, sheet_id)
        return None

    valores = r.get("valueRanges", [])
    resumo_linha = (valores[0].get("values") or [[]])[0] if valores[0].get("values") else []
    grupos_cheios = _int(resumo_linha[0]) if len(resumo_linha) > 0 else None
    total_leads = _int(resumo_linha[1]) if len(resumo_linha) > 1 else None
    total_limpo_linha = (valores[1].get("values") or [[]])[0] if valores[1].get("values") else []
    total_limpo = _int(total_limpo_linha[0]) if total_limpo_linha else None

    entradas_saidas: dict[str, tuple[int | None, int | None]] = {}
    for row in valores[2].get("values") or []:
        if not row:
            continue
        dia = _parse_data(row[0])
        if not dia:
            continue
        entradas_saidas[dia] = (
            _int(row[1]) if len(row) > 1 else None,
            _int(row[2]) if len(row) > 2 else None,
        )

    leads_no_dia: dict[str, int | None] = {}
    for row in valores[3].get("values") or []:
        if not row:
            continue
        dia = _parse_data(row[0])
        if not dia:
            continue
        leads_no_dia[dia] = _int(row[1]) if len(row) > 1 else None

    dias = set(entradas_saidas) | set(leads_no_dia)
    diario = []
    for dia in sorted(dias):
        entradas, saidas = entradas_saidas.get(dia, (None, None))
        diario.append({
            "date": dia,
            "entradas": entradas,
            "saidas": saidas,
            "leads_no_dia": leads_no_dia.get(dia),
        })

    return {
        "grupos_cheios": grupos_cheios,
        "total_leads": total_leads,
        "total_limpo": total_limpo,
        "diario": diario,
    }


def _upsert_resumo(engine, launch_code: str, bloco: str, dados: dict) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO whatsapp_sheets_resumo
                    (launch_code, bloco, total_grupos_cheios, total_leads, total_limpo, updated_at)
                VALUES
                    (:launch_code, :bloco, :grupos_cheios, :total_leads, :total_limpo, NOW())
                ON CONFLICT (launch_code, bloco) DO UPDATE SET
                    total_grupos_cheios = EXCLUDED.total_grupos_cheios,
                    total_leads = EXCLUDED.total_leads,
                    total_limpo = EXCLUDED.total_limpo,
                    updated_at = NOW()
            """),
            {
                "launch_code": launch_code, "bloco": bloco,
                "grupos_cheios": dados["grupos_cheios"],
                "total_leads": dados["total_leads"],
                "total_limpo": dados["total_limpo"],
            },
        )


def _upsert_diario(engine, launch_code: str, bloco: str, linhas: list[dict]) -> None:
    if not linhas:
        return
    with engine.begin() as conn:
        for linha in linhas:
            conn.execute(
                text("""
                    INSERT INTO whatsapp_sheets_diario
                        (date, launch_code, bloco, entradas, saidas, leads_no_dia, updated_at)
                    VALUES
                        (:date, :launch_code, :bloco, :entradas, :saidas, :leads_no_dia, NOW())
                    ON CONFLICT (date, launch_code, bloco) DO UPDATE SET
                        entradas = EXCLUDED.entradas,
                        saidas = EXCLUDED.saidas,
                        leads_no_dia = EXCLUDED.leads_no_dia,
                        updated_at = NOW()
                """),
                {"launch_code": launch_code, "bloco": bloco, **linha},
            )


def main() -> None:
    cfg = load_config()
    if not cfg:
        logger.warning("config/sheets_contagem.yaml vazio ou não encontrado — nada a fazer.")
        return

    svc = _service()
    if svc is None:
        return

    engine = get_engine()
    for launch_code, info in cfg.items():
        sheet_id = info["sheet_id"]
        for bloco in ("normal", "vip"):
            if bloco not in info:
                continue
            dados = _ler_bloco(svc, sheet_id, info[bloco])
            if dados is None:
                continue
            _upsert_resumo(engine, launch_code, bloco, dados)
            _upsert_diario(engine, launch_code, bloco, dados["diario"])
            logger.info(
                "%s/%s: grupos_cheios=%s total_leads=%s total_limpo=%s (%d dias)",
                launch_code, bloco, dados["grupos_cheios"], dados["total_leads"],
                dados["total_limpo"], len(dados["diario"]),
            )


if __name__ == "__main__":
    main()
