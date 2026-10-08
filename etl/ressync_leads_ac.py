"""
Ressincroniza `leads` e `lead_lancamentos` contra TODOS os contatos do Active
Campaign — não só o período recente que `etl_active_campaign.py --api` cobre.

Objetivo: docs/projetos/PLANO_RESSINCRONIZACAO_LEADS_AC.md
  1. corrige created_at corrompido (parser dayfirst + fuso errado na carga de 13/08);
  2. completa o historico de tags de lancamento em lead_lancamentos.

NAO escreve em leads.tags/tags_atualizado_em (decisao da secao 6 do plano: descartar
essas colunas, lead_lancamentos ja cobre o caso de uso).

Uso:
    python etl/ressync_leads_ac.py                 # continua do checkpoint salvo
    python etl/ressync_leads_ac.py --max-pages 3    # teste pequeno, nao avanca checkpoint
    python etl/ressync_leads_ac.py --reset          # zera o checkpoint e comeca do zero

Protecao de rate limit: a API do AC devolve ratelimit-limit/ratelimit-remaining em
todo response (medido em 18/09/26: limit=500). O script le esses headers a cada
pagina e pausa sozinho se sobrar menos de 20% da cota, pra nao brigar com o
scheduler de producao (mesma conta/API key, roda a cada 30 min).
"""
import os
import sys
import json
import time
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get
from etl_active_campaign import (
    _ac_headers,
    _launch_code_from_tag,
    _upsert_lead_lancamentos,
    extract_launch_code,
    upsert,
    UTM_FIELD_IDS,
)
from sqlalchemy import text

logger = get_logger("etl.ressync_ac")

CHECKPOINT_FILE = Path(__file__).parent.parent / "outputs" / "ressync_leads_ac_checkpoint.json"
CORROMPIDOS_STATE_FILE = Path(__file__).parent.parent / "outputs" / "ressync_corrompidos_state.json"
PAGE_SIZE = 100
IDS_BATCH_SIZE = 300  # medido em 18/09/26: 400 ids[] estoura limite de tamanho de URL (HTTP 400)


def _load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
    return {"offset": 0, "paginas_ok": 0, "contatos_processados": 0}


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _ac_contacts_url() -> str:
    base_url = os.environ["AC_API_URL"].rstrip("/")
    if "/api/3" not in base_url:
        base_url += "/api/3"
    return base_url + "/contacts"


def _respect_rate_limit(headers: dict) -> None:
    """Reduz o ritmo antes de bater no teto informado pela própria API (evita
    a mesma conta/API key do scheduler de produção ficar rate-limited)."""
    try:
        remaining = int(headers.get("ratelimit-remaining", ""))
        limit = int(headers.get("ratelimit-limit", ""))
    except (TypeError, ValueError):
        return
    if limit <= 0:
        return
    if remaining < limit * 0.2:
        pausa = float(headers.get("retry-after") or 2) * 5
        logger.warning("Rate limit em %d/%d — pausando %.0fs pra dar folga ao scheduler.", remaining, limit, pausa)
        time.sleep(pausa)


def _fetch_page(offset: int) -> dict:
    r = http_get(
        _ac_contacts_url(),
        headers=_ac_headers(),
        params={
            "limit": PAGE_SIZE,
            "offset": offset,
            "include": "fieldValues,contactTags.tag",
            "orders[id]": "ASC",
        },
    )
    _respect_rate_limit(r.headers)
    return r.json()


def _page_to_records(data: dict) -> tuple[list[dict], dict[tuple, str]]:
    field_id_to_utm = {str(v): k for k, v in UTM_FIELD_IDS.items() if v != 0}
    fv_by_contact: dict[str, dict[str, str]] = {}
    for fv in data.get("fieldValues", []):
        cid = fv.get("contact")
        name = field_id_to_utm.get(str(fv.get("field")))
        if name and cid:
            fv_by_contact.setdefault(cid, {})[name] = fv.get("value", "")

    tags_por_id: dict[str, str] = {}
    for t in data.get("tags", []):
        code = _launch_code_from_tag(t.get("tag", ""))
        if code:
            tags_por_id[str(t.get("id"))] = code

    lanc_por_contato: dict[tuple, str] = {}
    for ct in data.get("contactTags", []):
        code = tags_por_id.get(str(ct.get("tag")))
        cid = ct.get("contact")
        if code and cid:
            lanc_por_contato[(str(cid), code)] = ct.get("cdate")

    records = []
    for c in data.get("contacts", []):
        cid = c["id"]
        utms = fv_by_contact.get(cid, {})
        utm_campaign = utms.get("utm_campaign")
        phone = re.sub(r"\D", "", c.get("phone") or "")
        records.append({
            "id":                cid,
            "email":             (c.get("email") or "").lower().strip(),
            "nome":              (c.get("firstName") or "").strip() or None,
            "sobrenome":         (c.get("lastName") or "").strip() or None,
            "phone":             phone[-11:] if len(phone) >= 10 else None,
            "created_at":        c.get("cdate"),
            "utm_campaign":      utm_campaign,
            "lancamento_codigo": extract_launch_code(utm_campaign) if utm_campaign else None,
            "utm_source":        utms.get("utm_source"),
            "utm_medium":        utms.get("utm_medium"),
            "utm_content":       utms.get("utm_content"),
            "utm_term":          utms.get("utm_term"),
            "gclid":             utms.get("gclid") or None,
            "fbclid":            utms.get("fbclid") or None,
            "ttclid":            utms.get("ttclid") or None,
            "vk_source":         utms.get("vk_source") or None,
            "vk_ad_id":          utms.get("vk_ad_id") or None,
            "updated_at":        datetime.now(timezone.utc).isoformat(),
        })
    return records, lanc_por_contato


def _fetch_by_ids(ids: list[str]) -> dict:
    params = [("ids[]", cid) for cid in ids] + [("include", "fieldValues,contactTags.tag")]
    r = http_get(_ac_contacts_url(), headers=_ac_headers(), params=params)
    _respect_rate_limit(r.headers)
    return r.json()


def _get_corrupted_ids() -> list[str]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id FROM leads WHERE created_at IS NULL OR created_at > now() ORDER BY id"
        )).fetchall()
    return [r[0] for r in rows]


def _load_corrompidos_state(reset: bool) -> dict:
    if reset and CORROMPIDOS_STATE_FILE.exists():
        CORROMPIDOS_STATE_FILE.unlink()
        logger.info("Estado do modo --so-corrompidos zerado.")
    if CORROMPIDOS_STATE_FILE.exists():
        return json.loads(CORROMPIDOS_STATE_FILE.read_text(encoding="utf-8"))
    ids = _get_corrupted_ids()
    logger.info("%d leads corrompidos (created_at nulo ou futuro) capturados agora — lista fixada pro resto da execução.", len(ids))
    state = {"ids": ids, "lote_atual": 0}
    CORROMPIDOS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CORROMPIDOS_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    return state


def _save_corrompidos_state(state: dict) -> None:
    CORROMPIDOS_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def run_corrompidos(batch_size: int, max_batches: int | None, reset: bool, dry_run: bool) -> None:
    state = _load_corrompidos_state(reset)
    ids = state["ids"]
    lote_atual = state["lote_atual"]
    total_lotes = -(-len(ids) // batch_size)  # ceil division

    logger.info("Retomando do lote %d/%d (%d ids no total, lote de %d).",
                lote_atual, total_lotes, len(ids), batch_size)

    inicio = time.monotonic()
    lotes_nesta_execucao = 0
    encontrados_total = 0

    while lote_atual < total_lotes:
        if max_batches is not None and lotes_nesta_execucao >= max_batches:
            logger.info("Limite de %d lotes desta execução atingido (--max-batches). Parando sem avançar o estado definitivo.", max_batches)
            break

        subset = ids[lote_atual * batch_size: (lote_atual + 1) * batch_size]
        try:
            data = _fetch_by_ids(subset)
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            logger.error(
                "Falha persistente buscando lote %d após os retries internos: %s. "
                "Estado salvo em lote %d — rode de novo pra continuar daqui.",
                lote_atual, e, lote_atual,
            )
            sys.exit(1)

        records, lanc_por_contato = _page_to_records(data)
        encontrados_total += len(records)
        df = pd.DataFrame(records)
        # Aqui NÃO filtramos por utm_content/utm_term: esses ids já estão em
        # `leads` hoje (foi de lá que vieram), então já passaram nesse filtro
        # quando entraram pela primeira vez — o objetivo agora é só corrigir
        # created_at (e capturar tags), não decidir de novo se o lead entra.
        if not dry_run:
            if not df.empty:
                upsert(df, f"  [ressync corrompidos lote={lote_atual}]")
            _upsert_lead_lancamentos(lanc_por_contato)
        else:
            logger.info("[dry-run] lote=%d: %d ids pedidos, %d contatos retornados, %d pares de tag",
                        lote_atual, len(subset), len(records), len(lanc_por_contato))

        lote_atual += 1
        lotes_nesta_execucao += 1

        if not dry_run:
            state["lote_atual"] = lote_atual
            _save_corrompidos_state(state)

        elapsed_min = (time.monotonic() - inicio) / 60
        ritmo = lotes_nesta_execucao * batch_size / elapsed_min if elapsed_min > 0 else 0
        restante_min = (len(ids) - lote_atual * batch_size) / ritmo if ritmo > 0 else float("nan")
        logger.info(
            "lote=%d/%d — %d/%d ids processados (%.1f%%) — ritmo: %.0f ids/min — ETA restante: %.1f min",
            lote_atual, total_lotes, min(lote_atual * batch_size, len(ids)), len(ids),
            100 * min(lote_atual * batch_size, len(ids)) / len(ids), ritmo, restante_min,
        )

    if lote_atual >= total_lotes:
        logger.info("Ressync dos corrompidos completo: %d ids pedidos, %d contatos encontrados na AC.", len(ids), encontrados_total)


def run(max_pages: int | None, reset: bool, dry_run: bool) -> None:
    if reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("Checkpoint zerado.")

    state = _load_checkpoint()
    offset = state["offset"]
    paginas_ok = state["paginas_ok"]
    contatos_processados = state["contatos_processados"]

    logger.info("Iniciando do offset %d (checkpoint: %d páginas, %d contatos já processados)",
                offset, paginas_ok, contatos_processados)

    inicio = time.monotonic()
    paginas_nesta_execucao = 0
    total = None

    while True:
        if max_pages is not None and paginas_nesta_execucao >= max_pages:
            logger.info("Limite de %d páginas desta execução atingido (--max-pages). Parando sem avançar o checkpoint definitivo.", max_pages)
            break

        try:
            data = _fetch_page(offset)
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            logger.error(
                "Falha persistente buscando offset %d após os retries internos: %s. "
                "Checkpoint salvo em %d — rode de novo pra continuar daqui.",
                offset, e, offset,
            )
            sys.exit(1)

        batch = data.get("contacts", [])
        if not batch:
            logger.info("Sem mais contatos — ressync completo em offset %d.", offset)
            break

        total = int(data.get("meta", {}).get("total", 0))
        records, lanc_por_contato = _page_to_records(data)

        df = pd.DataFrame(records)
        has_content = df["utm_content"].notna() & (df["utm_content"] != "")
        has_term    = df["utm_term"].notna()    & (df["utm_term"]    != "")
        df_leads = df[has_content | has_term].copy()

        if not dry_run:
            if not df_leads.empty:
                upsert(df_leads, f"  [ressync offset={offset}]")
            _upsert_lead_lancamentos(lanc_por_contato)
        else:
            logger.info("[dry-run] offset=%d: %d contatos, %d elegíveis para leads, %d pares de tag",
                        offset, len(batch), len(df_leads), len(lanc_por_contato))

        offset += len(batch)
        paginas_ok += 1
        paginas_nesta_execucao += 1
        contatos_processados += len(batch)

        if not dry_run:
            _save_checkpoint({
                "offset": offset,
                "paginas_ok": paginas_ok,
                "contatos_processados": contatos_processados,
                "total_contatos_ac": total,
            })

        elapsed_min = (time.monotonic() - inicio) / 60
        ritmo = paginas_nesta_execucao * PAGE_SIZE / elapsed_min if elapsed_min > 0 else 0
        restante_min = (total - offset) / ritmo if ritmo > 0 else float("nan")
        logger.info(
            "offset=%d/%d (%.1f%%) — ritmo desta execução: %.0f contatos/min — ETA restante: %.0f min",
            offset, total, 100 * offset / total if total else 0, ritmo, restante_min,
        )

        if offset >= total:
            logger.info("Ressync completo: %d contatos.", offset)
            break


def main():
    parser = argparse.ArgumentParser(description="Ressync leads + lead_lancamentos contra o Active Campaign")
    parser.add_argument("--so-corrompidos", action="store_true",
                         help="Só corrige os leads com created_at nulo/futuro hoje em `leads` (via ids[] em lote, ~500x menos requisições que o crawl completo)")
    parser.add_argument("--batch-size", type=int, default=IDS_BATCH_SIZE, help="Tamanho do lote de ids[] (modo --so-corrompidos)")
    parser.add_argument("--max-batches", type=int, default=None, help="Limita a execução a N lotes (teste, modo --so-corrompidos)")
    parser.add_argument("--max-pages", type=int, default=None, help="Limita a execução a N páginas (teste, crawl completo)")
    parser.add_argument("--reset", action="store_true", help="Zera o checkpoint/estado salvo e recomeça do zero")
    parser.add_argument("--dry-run", action="store_true", help="Não escreve no banco, só reporta o que faria")
    args = parser.parse_args()
    if args.so_corrompidos:
        run_corrompidos(batch_size=args.batch_size, max_batches=args.max_batches, reset=args.reset, dry_run=args.dry_run)
    else:
        run(max_pages=args.max_pages, reset=args.reset, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
