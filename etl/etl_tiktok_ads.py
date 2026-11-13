"""
ETL: TikTok Ads (Marketing API v1.3) → Supabase (tabela: tiktok_ads_daily)

Uso:
    python etl/etl_tiktok_ads.py --since 2026-11-01 --until 2026-11-12
    python etl/etl_tiktok_ads.py --since 2025-05-01 --launch-code PES-JAN-26

Pré-requisitos .env (app "Brabo-Analytics" em business-api.tiktok.com):
    TIKTOK_ACCESS_TOKEN    — token de longa duração (sai da troca do auth_code;
                             não expira enquanto a autorização não for revogada)
    TIKTOK_ADVERTISER_IDS  — contas de anúncio, separadas por vírgula

Uma linha por anúncio por dia, no fuso da conta (as 4 contas são UTC-3).
Mesma mecânica do etl_meta_ads: apaga a janela e regrava, na mesma transação,
com nome de campanha congelado e etapa/temperatura classificadas pelo nome
(etl/campanha_historico.py, plataforma "tiktok": colchetes como no Meta e, sem
colchete, substring — as campanhas antigas do TikTok são texto livre).
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from http_retry import http_get
from validation import validate_dataframe
from launch_resolver import resolve_launch_code
from campanha_historico import preparar as preparar_campanhas

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logger = get_logger("etl.tiktok")

API_BASE = "https://business-api.tiktok.com/open_api/v1.3"
TABLE = "tiktok_ads_daily"
PAGE_SIZE = 1000
# Com a dimensão stat_time_day o relatório aceita no máximo 30 dias por chamada.
JANELA_DIAS = 30

# métrica da API -> coluna da tabela
METRICAS = {
    "spend": "spend",
    "impressions": "impressions",
    "clicks": "clicks",
    "reach": "reach",
    # Evento de otimização do grupo (lead no LEAD_GENERATION). Em VIDEO_VIEWS é 0:
    # o "resultado" desse objetivo é a view de 6s, que vem em `results`.
    "conversion": "conversions",
    "result": "results",
    "video_play_actions": "video_plays",
    "video_watched_2s": "video_views_2s",
    "video_watched_6s": "video_views_6s",
    "video_views_p25": "video_views_25",
    "video_views_p50": "video_views_50",
    "video_views_p75": "video_views_75",
    "video_views_p100": "video_views_100",
    "average_video_play": "video_avg_time_watched",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "follows": "follows",
    "profile_visits": "profile_visits",
}
ATRIBUTOS = ["campaign_id", "campaign_name", "adgroup_id", "adgroup_name", "ad_name"]
_DECIMAIS = {"spend", "video_avg_time_watched"}


class TikTokApiError(RuntimeError):
    pass


def _token() -> str:
    return os.environ.get("TIKTOK_ACCESS_TOKEN", "").strip()


def _advertiser_ids() -> list[str]:
    return [a.strip() for a in os.environ.get("TIKTOK_ADVERTISER_IDS", "").split(",") if a.strip()]


def api_get(path: str, **params) -> dict:
    """GET na Marketing API. A API responde HTTP 200 mesmo com erro — o erro
    vem em `code` (0 = ok), então é aqui que ele vira exceção. O token vai no
    header, nunca na URL: não aparece em traceback nem em etl_runs."""
    query = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in params.items()}
    r = http_get(f"{API_BASE}{path}", params=query, headers={"Access-Token": _token()})
    body = r.json()
    if body.get("code") != 0:
        raise TikTokApiError(f"{path}: code={body.get('code')} {body.get('message')}")
    return body.get("data") or {}


def janelas(since: str, until: str) -> list[tuple[str, str]]:
    """Fatia [since, until] em blocos de até JANELA_DIAS dias."""
    ini, fim = date.fromisoformat(since), date.fromisoformat(until)
    blocos = []
    while ini <= fim:
        bloco_fim = min(ini + timedelta(days=JANELA_DIAS - 1), fim)
        blocos.append((ini.isoformat(), bloco_fim.isoformat()))
        ini = bloco_fim + timedelta(days=1)
    return blocos


def fetch_objetivos(advertiser_id: str) -> dict[str, str]:
    """{campaign_id: objective_type} — o relatório não traz o objetivo."""
    objetivos, page = {}, 1
    while True:
        data = api_get("/campaign/get/", advertiser_id=advertiser_id, page=page, page_size=1000,
                       fields=["campaign_id", "objective_type"])
        for c in data.get("list", []):
            objetivos[str(c["campaign_id"])] = c.get("objective_type")
        if page >= (data.get("page_info") or {}).get("total_page", 1):
            return objetivos
        page += 1


def fetch_report(advertiser_id: str, since: str, until: str) -> list[dict]:
    """Relatório integrado por anúncio e dia, paginado e fatiado em janelas de 30 dias."""
    linhas = []
    for ini, fim in janelas(since, until):
        page = 1
        while True:
            data = api_get(
                "/report/integrated/get/",
                advertiser_id=advertiser_id, report_type="BASIC", data_level="AUCTION_AD",
                dimensions=["ad_id", "stat_time_day"], metrics=ATRIBUTOS + list(METRICAS),
                start_date=ini, end_date=fim, page=page, page_size=PAGE_SIZE,
            )
            linhas.extend(data.get("list", []))
            if page >= (data.get("page_info") or {}).get("total_page", 1):
                break
            page += 1
    return linhas


def _num(valor, decimal: bool):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return 0.0 if decimal else 0
    return v if decimal else int(v)


def build_df(linhas: list[dict], advertiser_id: str = "", objetivos: dict[str, str] | None = None) -> pd.DataFrame:
    # Defaults: tests/test_etl_schema.py monta o DataFrame com build_df([{}]).
    objetivos = objetivos or {}
    registros = []
    for item in linhas:
        dim, met = item.get("dimensions") or {}, item.get("metrics") or {}
        dia = str(dim.get("stat_time_day", ""))[:10]
        campanha = met.get("campaign_name")
        reg = {
            "date": dia,
            "ad_id": str(dim.get("ad_id")),
            "ad_name": met.get("ad_name"),
            "adgroup_id": met.get("adgroup_id"),
            "adgroup_name": met.get("adgroup_name"),
            "campaign_id": met.get("campaign_id"),
            "campaign_name": campanha,
            "objective_type": objetivos.get(str(met.get("campaign_id"))),
            "account_id": advertiser_id,
            "lancamento_codigo": resolve_launch_code(campanha, dia),
        }
        for api, coluna in METRICAS.items():
            reg[coluna] = _num(met.get(api), coluna in _DECIMAIS)
        registros.append(reg)
    return pd.DataFrame(registros)


def sem_entrega(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta anúncio-dia sem impressão nem gasto: o relatório devolve linha
    zerada para anúncio ativo que não entregou, e ela só incharia a tabela."""
    if df.empty:
        return df
    return df[(df["impressions"] > 0) | (df["spend"] > 0)]


_REQUIRED_COLS = ["date", "ad_id", "ad_name", "spend", "impressions", "clicks"]


def upsert(df: pd.DataFrame, since: str, until: str, launch_code: str | None = None,
           renomear: bool = False, contas: list[str] | None = None):
    if df.empty:
        logger.info("Nenhuma linha com entrega no TikTok em [%s -> %s]; limpando a janela mesmo assim", since, until)
    elif not validate_dataframe(df, _REQUIRED_COLS, TABLE, logger):
        return
    df = df.copy()
    df["updated_at"] = datetime.now(timezone.utc).isoformat()
    filtro = ["date BETWEEN :s AND :u"]
    params: dict = {"s": since, "u": until}
    if launch_code:
        filtro.append("lancamento_codigo = :code")
        params["code"] = launch_code.upper()
    if contas:
        # Só apaga as contas que foram lidas: conta que saiu do .env não perde o histórico.
        filtro.append("account_id = ANY(:contas)")
        params["contas"] = contas
    engine = get_engine()
    with engine.begin() as conn:
        if not df.empty:
            df = preparar_campanhas(
                conn, df, tabela=TABLE, plataforma="tiktok", since=since, until=until,
                launch_code=launch_code, renomear=renomear,
            )
        conn.execute(text(f"DELETE FROM {TABLE} WHERE {' AND '.join(filtro)}"), params)
        # Na mesma transação do DELETE (ver etl_meta_ads.upsert): fora dela a janela fica vazia entre os dois passos.
        if not df.empty:
            df.to_sql(TABLE, conn, if_exists="append", index=False, method="multi", chunksize=500)
    logger.info("Upsert concluído: %d linhas gravadas em '%s'", len(df), TABLE)


def main():
    parser = argparse.ArgumentParser(description="ETL TikTok Ads -> Supabase")
    parser.add_argument("--since", metavar="YYYY-MM-DD", required=True)
    parser.add_argument("--until", metavar="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--launch-code", metavar="CODE", help="Filtra e substitui dados apenas de um lançamento")
    parser.add_argument("--renomear-campanhas", action="store_true",
                        help="Deixa o nome atual da campanha sobrescrever o nome histórico")
    parser.add_argument("--dry-run", action="store_true", help="Busca e resume, não grava")
    args = parser.parse_args()

    contas = _advertiser_ids()
    if not _token() or not contas:
        # Sai com 0 de propósito: no servidor, antes de as variáveis existirem, a fonte
        # não deve disparar alerta de erro a cada ciclo. O aviso fica no log.
        logger.warning("TIKTOK_ACCESS_TOKEN/TIKTOK_ADVERTISER_IDS ausentes no .env — TikTok Ads pulado")
        return

    logger.info("[TikTok Ads] %s  [%s -> %s]  (%d contas)", TABLE, args.since, args.until, len(contas))
    frames = []
    for conta in contas:
        objetivos = fetch_objetivos(conta)
        linhas = fetch_report(conta, args.since, args.until)
        df_conta = sem_entrega(build_df(linhas, conta, objetivos))
        logger.info("Conta %s: %d linhas da API, %d com entrega", conta, len(linhas), len(df_conta))
        frames.append(df_conta)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if args.launch_code and not df.empty:
        df = df[df["lancamento_codigo"] == args.launch_code.upper()]

    if args.dry_run:
        if df.empty:
            logger.info("[dry-run] nada com entrega no período")
            return
        resumo = (df.groupby(["account_id", "lancamento_codigo", "campaign_name"], dropna=False)
                    .agg(dias=("date", "nunique"), anuncios=("ad_id", "nunique"),
                         gasto=("spend", "sum"), impressoes=("impressions", "sum"),
                         conversoes=("conversions", "sum"))
                    .reset_index())
        print(resumo.to_string(index=False))
        print(f"\nTotal: {len(df)} linhas | R$ {df['spend'].sum():,.2f}")
        return

    upsert(df, args.since, args.until, args.launch_code, args.renomear_campanhas, contas)


if __name__ == "__main__":
    main()
